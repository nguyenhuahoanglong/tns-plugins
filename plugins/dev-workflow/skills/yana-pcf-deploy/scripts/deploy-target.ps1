[CmdletBinding(DefaultParameterSetName='Plan')]
param(
 [Parameter(ParameterSetName='Plan',Mandatory)][ValidateSet('Preview','RC','Personal','Hotfix','Prod')][string]$Target,
 [Parameter(ParameterSetName='Plan')][ValidateSet('Pinned','CurrentWork')][string]$SourcePolicy='Pinned',
 [Parameter(ParameterSetName='Plan')][string]$SourceVersion='latest',
 [Parameter(ParameterSetName='Plan')][string]$Branch,
 [Parameter(ParameterSetName='Plan')][string]$Variant,
 [Parameter(ParameterSetName='Plan')][ValidateSet('Debug','Release')][string]$BuildMode,
 [Parameter(ParameterSetName='Plan')][string]$EnvironmentUrl,
 [Parameter(ParameterSetName='Plan')][string]$PythonExecutable,
 [Parameter(ParameterSetName='Plan')][string]$ExpectedSourceSha,
 [Parameter(ParameterSetName='Plan',Mandatory)][string]$Repo,
 [Parameter(ParameterSetName='Plan',Mandatory)][switch]$Plan,
 [Parameter(ParameterSetName='Plan')][Parameter(ParameterSetName='Apply',Mandatory)][string]$PlanFile,
 [Parameter(ParameterSetName='Apply',Mandatory)][switch]$Apply,
 [Parameter(ParameterSetName='Apply',Mandatory)][string]$ConfirmSourceSha
)
$ErrorActionPreference='Stop'
$DevQa='https://yanaintegrationdevqa.crm5.dynamics.com'
$SourceHelper=Join-Path $PSScriptRoot 'prepare_deploy_source.py'

function NeedsInput([string]$message){ Write-Output "NEEDS_INPUT: $message"; exit 2 }
function Git([string]$repo,[string[]]$gitArgs){
 $git=(Get-Command git -CommandType Application|Select-Object -First 1).Source
 $out=& $git -C $repo @gitArgs 2>&1
 if($LASTEXITCODE){ throw "git failed: $($out -join "`n")" }
 @($out)
}
function Refs([string]$repo){
 @(Git $repo @('ls-remote','--heads','origin')|ForEach-Object{ if($_ -match '^([0-9a-f]+)\s+refs/heads/(.+)$'){ [pscustomobject]@{Sha=$matches[1];Branch=$matches[2]} } })
}
function Hash($value){
 $bytes=[Text.Encoding]::UTF8.GetBytes(($value|ConvertTo-Json -Compress -Depth 30))
 ([BitConverter]::ToString(([Security.Cryptography.SHA256]::Create().ComputeHash($bytes)))).Replace('-','').ToLowerInvariant()
}
function ExpectedHash($value){
 $ordered=[ordered]@{}
 foreach($property in $value.PSObject.Properties){ if($property.Name -ne 'planHash'){ $ordered[$property.Name]=$property.Value } }
 Hash $ordered
}
function Get-Python([string]$requested){
 $candidate=if($requested){$requested}elseif($env:YANA_PCF_PYTHON){$env:YANA_PCF_PYTHON}else{
  $python=Get-Command python -CommandType Application -ErrorAction SilentlyContinue|Select-Object -First 1
  if($python){$python.Source}else{$null}
 }
 if(!$candidate -or !(Test-Path -LiteralPath $candidate -PathType Leaf)){ throw 'Native Python 3.10+ path is required; read deploy setup receipt and set YANA_PCF_PYTHON or pass -PythonExecutable.' }
 if($candidate -match '(?i)[\\/]WindowsApps[\\/]'){throw 'Microsoft Store Python alias is not supported; use native Python path from setup receipt.'}
 $version=& $candidate --version 2>&1
 if($LASTEXITCODE -or $version -notmatch '^Python\s+(?:3\.(?:1[0-9]|[2-9][0-9])|[4-9]\.)'){
  throw 'Native Python 3.10+ is required; select executable recorded by PCF deploy setup.'
 }
 (Resolve-Path -LiteralPath $candidate).Path
}
function Invoke-SourceJson([string[]]$arguments){
 $python=$script:ResolvedPython
 if(!$python){$python=Get-Python $null}
 $output=& $python -B $SourceHelper @arguments 2>&1
 $exitCode=$LASTEXITCODE
 $joined=($output -join "`n")
 if($exitCode){
  try{$errorData=$joined|ConvertFrom-Json}catch{$errorData=$null}
  if($errorData -and $errorData.status -eq 'NEEDS_INPUT'){NeedsInput $errorData.message}
  if($errorData -and $errorData.message){throw $errorData.message}
  throw "Source preparation failed: $joined"
 }
 try{return ($joined|ConvertFrom-Json)}catch{throw "Source helper returned invalid JSON: $joined"}
}
function Read-PcfConfig([string]$repo){
 Invoke-SourceJson @('config','--repo',$repo)
}
function ExpectedOrg([string]$configured){
 $url=if($EnvironmentUrl){$EnvironmentUrl}elseif($configured){$configured}else{$DevQa}
 $parsed=$null
 if(-not [Uri]::TryCreate($url,[UriKind]::Absolute,[ref]$parsed) -or $parsed.Scheme -ne 'https' -or $parsed.UserInfo -or $parsed.Query -or $parsed.Fragment -or $parsed.AbsolutePath.Trim('/') -or (-not $parsed.IsDefaultPort -and $parsed.Port -ne 443)){
  NeedsInput 'Target environment must be an HTTPS Dataverse org origin.'
 }
 $parsed.GetLeftPart([UriPartial]::Authority).TrimEnd('/')
}
function PacExact([string]$url){
 $o=@(& pac org who 2>&1)
 if($LASTEXITCODE){throw 'pac org who failed; complete PAC sign-in and retry.'}
 $urls=@($o|ForEach-Object{[regex]::Matches($_,'https://[^\s/]+')|ForEach-Object{$_.Value}})
 if($urls.Count-ne 1-or$urls[0].TrimEnd('/')-ine$url.TrimEnd('/')){throw "PAC org mismatch; expected exact $url. No build/import started."}
}
function Test-DeployScriptContract([string]$path){
 if(!(Test-Path -LiteralPath $path)){throw "Tracked deploy script missing: $path"}
 $content=Get-Content -LiteralPath $path -Raw
 $required=@(
  'ExpectedOrgUrl',
  'Deploy source contract: expected-org-pin-v1',
  'Deploy source contract: verified-publish-readback-v1'
 )
 $missing=@($required|Where-Object{$content -notmatch [regex]::Escape($_)})
 if($missing.Count){throw "Deploy script contract not installed; refusing build/import. Apply assets/deploy-variant-contract.patch first. Missing: $($missing -join ', ')"}
}
function Invoke-DeployScript([string]$worktree,$deployment){
 $script=Join-Path $worktree 'Solution/scripts/deploy-variant.ps1'
 Test-DeployScriptContract $script
 $npm=Get-Command npm -CommandType Application -ErrorAction SilentlyContinue|Select-Object -First 1
 if(!$npm){throw 'npm is missing; run PCF deploy setup once and retry.'}
 $packageLock=Join-Path $worktree 'package-lock.json'
 if(!(Test-Path -LiteralPath $packageLock)){throw 'Deployment snapshot has no package-lock.json; refusing an unreproducible build.'}
 Push-Location $worktree
 try{
  Write-Output '[deploy-target] Restoring locked dependencies in isolated source snapshot...'
  $install=& $npm.Source ci --ignore-scripts --no-audit --no-fund 2>&1
  if($LASTEXITCODE){throw "npm ci failed in isolated snapshot: $(($install|Select-Object -Last 25)-join "`n")"}
  Write-Output "[deploy-target] Building variant '$($deployment.variant)' from $($deployment.sourceBranch) at $($deployment.sourceSha)..."
  $log="$($deployment.planFile).deploy.log"
  & $script -Variant $deployment.variant -BuildMode $deployment.buildMode -ExpectedOrgUrl $deployment.expectedOrgUrl *>&1|Tee-Object -FilePath $log|ForEach-Object{Write-Host $_}
  if($LASTEXITCODE){throw 'deploy-variant.ps1 failed; import/publish/readback not confirmed.'}
  $auto=(Select-String -LiteralPath $log -Pattern '^\[deploy-variant\] Auto version \(timestamp\):\s*(.+)$'|Select-Object -Last 1).Matches.Groups[1].Value
  if(!$auto){throw 'Tracked deploy script did not report timestamp technical version.'}
  if(!(Select-String -LiteralPath $log -Pattern 'Verified solution readback:' -Quiet)){throw 'Deploy script did not confirm target solution readback; result is not verified.'}
  $zipPath=Join-Path $worktree "Solution/bin/$($deployment.buildMode)/CORECustomControl.zip"
  if(!(Test-Path -LiteralPath $zipPath)){throw "Built package missing: $zipPath"}
  $zipHash=(Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  [pscustomobject]@{technicalVariantVersion=$auto;bundlePath=$zipPath;bundleSha256=$zipHash;deployLog=$log}
 }finally{Pop-Location}
}

if($Plan){
 if($Target -eq 'Prod'){NeedsInput 'Prod is CI/CD only; local import is blocked.'}
 $rp=(Resolve-Path -LiteralPath $Repo).Path
 if(!(Test-Path -LiteralPath $SourceHelper)){throw "Bundled source helper missing: $SourceHelper"}
 $script:ResolvedPython=Get-Python $PythonExecutable
 if($SourcePolicy -eq 'Pinned' -and $Target -eq 'Personal' -and !$Branch){NeedsInput 'Pinned Personal requires explicit -Branch; use CurrentWork for current checkout.'}
 if($SourcePolicy -eq 'Pinned' -and $Target -eq 'Hotfix' -and !$Branch -and $SourceVersion -notmatch '^\d+\.\d+\.\d+$'){
  NeedsInput 'Pinned Hotfix requires explicit -Branch or exact SemVer -SourceVersion.'
 }
 if($SourcePolicy -eq 'Pinned' -and $Target -eq 'RC' -and !$Branch -and $SourceVersion -notmatch '^\d+\.\d+\.\d+$'){
  NeedsInput 'Pinned RC requires exact -Branch or -SourceVersion; do not guess highest SemVer.'
 }
 $config=@{}
 if($SourcePolicy -eq 'CurrentWork' -or (Test-Path -LiteralPath (Join-Path $rp 'AGENTS.local.md')) -or ($Target -eq 'Personal' -and !$Variant)){
  $config=Read-PcfConfig $rp
 }
 $expectedOrg=ExpectedOrg $config.deploy_environment_url
 if(!$BuildMode){$BuildMode='Debug'}
 if(!$Variant){
  switch($Target){
   'Preview'{$Variant='Preview'}
   'RC'{$Variant='RC'}
   'Hotfix'{$Variant='Hotfix'}
   'Personal'{$Variant=$config.personal_variant;if(!$Variant){NeedsInput 'Personal variant missing; run deploy setup and save personal_variant.'}}
  }
 }
 if($Variant -notmatch '^[A-Za-z0-9]+$'){NeedsInput 'Variant must contain only letters and digits.'}
 $sourcePlan=$null
 if($SourcePolicy -eq 'CurrentWork'){
  if($Target -notin @('Personal','RC')){NeedsInput 'CurrentWork supports Personal and RC targets only; use Pinned for Preview or Hotfix.'}
  if($Branch){NeedsInput 'CurrentWork always uses checked-out branch; switch branch or use Pinned for an explicit branch.'}
  $intent=if($Target -eq 'RC'){'rc'}else{'personal'}
  $planArgs=@('plan','--repo',$rp,'--intent',$intent,'--fetch')
  if($Target -eq 'RC' -and $SourceVersion -ne 'latest'){
   if($SourceVersion -notmatch '^\d+\.\d+\.\d+$'){NeedsInput 'RC source must be exact X.Y.Z.'}
   $planArgs+=@('--release-source',$SourceVersion)
  }
  $sourcePlan=Invoke-SourceJson $planArgs
  if($ExpectedSourceSha -and $ExpectedSourceSha -ne $sourcePlan.sourceSha){throw 'ExpectedSourceSha differs from latest resolved source; refresh release evidence and re-plan.'}
  $branchName=$sourcePlan.sourceBranch
  $sha=$sourcePlan.sourceSha
  $version=if($sourcePlan.releaseSource){$sourcePlan.releaseSource}else{$sourcePlan.currentBranch}
 }else{
  if($Target -eq 'Personal' -and !$Branch){NeedsInput 'Pinned Personal requires explicit -Branch; use CurrentWork for current checkout.'}
  if($Target -eq 'Hotfix' -and !$Branch -and $SourceVersion -notmatch '^\d+\.\d+\.\d+$'){
   NeedsInput 'Pinned Hotfix requires explicit -Branch or exact SemVer -SourceVersion.'
  }
  $refs=Refs $rp
  switch($Target){
   'Preview'{$selected=@($refs|Where-Object Branch -eq 'dev')}
   'RC'{
    if($Branch){$chosen=$Branch -replace '^origin/',''}
    elseif($SourceVersion -match '^\d+\.\d+\.\d+$'){$chosen=$SourceVersion}
    else{NeedsInput 'Pinned RC requires exact -Branch or -SourceVersion; do not guess highest SemVer.'}
    $selected=@($refs|Where-Object Branch -eq $chosen)
   }
   'Personal'{$chosen=$Branch -replace '^origin/','';$selected=@($refs|Where-Object Branch -eq $chosen)}
   'Hotfix'{if($Branch){$chosen=$Branch -replace '^origin/',''}else{$chosen=$SourceVersion};$selected=@($refs|Where-Object Branch -eq $chosen)}
  }
  if(@($selected).Count-ne 1){NeedsInput 'Pinned source branch is absent or not unique on origin.'}
  $branchName="origin/$($selected[0].Branch)";$sha=$selected[0].Sha;$version=$selected[0].Branch
  if($ExpectedSourceSha -and $ExpectedSourceSha -ne $sha){throw 'ExpectedSourceSha differs from live branch tip; refresh release evidence and re-plan.'}
 }
 $temp=[IO.Path]::GetTempPath()
 $plannedCurrentBranch=if($sourcePlan){$sourcePlan.currentBranch}else{$null}
 $plannedCurrentHead=if($sourcePlan){$sourcePlan.currentHeadSha}else{$null}
 $plannedChangesHash=if($sourcePlan){$sourcePlan.workingChangesHash}else{$null}
 $d=[ordered]@{
  target=$Target;sourcePolicy=$SourcePolicy;sourceBranch=$branchName;sourceSha=$sha;sourceVersion=$version
  currentBranch=$plannedCurrentBranch
  currentHeadSha=$plannedCurrentHead
  workingChangesHash=$plannedChangesHash
  sourcePlan=$sourcePlan;variant=$Variant;buildMode=$BuildMode;expectedOrgUrl=$expectedOrg
  deploymentMode='unmanaged';worktreePath=Join-Path $temp "yana-pcf-deploy-$([guid]::NewGuid())"
  repoPath=$rp;pythonExecutable=$script:ResolvedPython;planHash=$null
 }
 $hashInput=[ordered]@{}
 foreach($key in $d.Keys){if($key -ne 'planHash'){$hashInput[$key]=$d[$key]}}
 $d.planHash=Hash $hashInput
 if(!$PlanFile){$PlanFile=Join-Path $temp "yana-pcf-deploy-plan-$([guid]::NewGuid()).json"}
 $d|ConvertTo-Json -Depth 30|Set-Content -LiteralPath $PlanFile -Encoding utf8
 Write-Output "PLAN_READY: $PlanFile"
 Write-Output ("SOURCE: {0} @ {1}" -f $d.sourceBranch,$d.sourceSha)
 Write-Output ("VARIANT: {0}; ENV: {1}; POLICY: {2}" -f $d.variant,$d.expectedOrgUrl,$d.sourcePolicy)
 if($sourcePlan){Write-Output ("SOURCE_SYNC: {0}" -f $sourcePlan.mergeStrategy)}
 if($sourcePlan -and $sourcePlan.mergeStrategy -eq 'merge-commit'){Write-Output 'SYNC_NOTE: Apply will create a local Git merge commit to sync latest source into the checked-out branch; it will not push.'}
 if($sourcePlan -and $sourcePlan.sourceKind -eq 'local-only'){Write-Output 'SOURCE_NOTE: no remote upstream configured; deploying local branch only.'}
 if($sourcePlan -and $sourcePlan.releaseEvidence){Write-Output ("RELEASE_SOURCE_EVIDENCE: {0}" -f $sourcePlan.releaseEvidence)}
 if($sourcePlan -and $sourcePlan.workingChangesPresent){Write-Output ("LOCAL_CHANGES_HASH: {0}" -f $sourcePlan.workingChangesHash)}
 exit
}

$d=Get-Content -Raw -LiteralPath $PlanFile|ConvertFrom-Json
if($d.planHash -ne (ExpectedHash $d)){throw 'Plan hash mismatch; abort and re-plan.'}
if($d.target -eq 'Prod'){throw 'Prod is CI/CD only; local import is blocked.'}
$script:ResolvedPython=Get-Python $d.pythonExecutable
if($ConfirmSourceSha -ne $d.sourceSha){throw 'ConfirmSourceSha does not match planned source SHA.'}
$rp=(Resolve-Path -LiteralPath $d.repoPath).Path
$worktree=$null;$snapshotRoot=$null;$sourcePlanFile=$null;$pinRef=$null
try{
 if($d.sourcePolicy -eq 'CurrentWork'){
  PacExact $d.expectedOrgUrl
  $sourcePlanFile=Join-Path ([IO.Path]::GetTempPath()) "yana-pcf-source-plan-$([guid]::NewGuid()).json"
  $d.sourcePlan|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $sourcePlanFile -Encoding utf8
  $snap=Invoke-SourceJson @('sync','--repo',$rp,'--plan-file',$sourcePlanFile,'--fetch')
  $worktree=$snap.worktreePath;$snapshotRoot=$snap.snapshotRoot
  $sourceEvidence=$snap
 }else{
  $now=@(Refs $rp|Where-Object Branch -eq ($d.sourceBranch -replace '^origin/',''))
  if($now.Count-ne 1-or$now[0].Sha-ne$d.sourceSha){throw 'Remote SHA changed after plan; abort and re-plan.'}
  $pinnedBranch=$d.sourceBranch -replace '^origin/',''
  $pinRef="refs/codex/pcf-deploy/$([guid]::NewGuid().ToString('N'))"
  Git $rp @('fetch','--no-tags','--quiet','origin',"+refs/heads/$pinnedBranch`:$pinRef")|Out-Null
  $fetchedSha=@(Git $rp @('rev-parse','--verify',"$($pinRef)^{commit}"))[0]
  if($fetchedSha -ne $d.sourceSha){throw 'Fetched pinned ref differs from planned source SHA; abort before PAC or build.'}
  PacExact $d.expectedOrgUrl
  $worktree=[IO.Path]::GetFullPath($d.worktreePath)
  $temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
  if(!$worktree.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)-or(Test-Path -LiteralPath $worktree)){throw 'Planned worktree path is unsafe or already exists.'}
  Git $rp @('worktree','add','--detach',$worktree,$d.sourceSha)|Out-Null
  $sourceEvidence=$null
 }
 $result=Invoke-DeployScript $worktree ([pscustomobject]@{variant=$d.variant;buildMode=$d.buildMode;expectedOrgUrl=$d.expectedOrgUrl;sourceBranch=$d.sourceBranch;sourceSha=$d.sourceSha;planFile=$PlanFile})
 $receipt=[ordered]@{
  target=$d.target;sourcePolicy=$d.sourcePolicy;sourceBranch=$d.sourceBranch;sourceSha=$d.sourceSha
  sourceVersion=$d.sourceVersion;currentBranch=$d.currentBranch;currentHeadSha=$d.currentHeadSha
  syncedCheckoutHeadSha=if($sourceEvidence){$sourceEvidence.syncedCheckoutHeadSha}else{$null}
  checkoutUpdated=if($sourceEvidence){$sourceEvidence.checkoutUpdated}else{$false}
  mergeStrategy=if($sourceEvidence){$sourceEvidence.mergeStrategy}else{$null}
  remoteUpdate=if($sourceEvidence){$sourceEvidence.remoteUpdate}else{'pinned source; checkout not updated'}
  releaseEvidence=if($sourceEvidence){$sourceEvidence.releaseEvidence}else{$null}
  workingChangesHash=$d.workingChangesHash
  postSyncWorkingChangesHash=if($sourceEvidence){$sourceEvidence.workingChangesHash}else{$null}
  snapshotHash=if($sourceEvidence){$sourceEvidence.snapshotHash}else{$null}
  sourceTreeHash=if($sourceEvidence){$sourceEvidence.sourceTreeHash}else{$null}
  technicalVariantVersion=$result.technicalVariantVersion;variant=$d.variant;buildMode=$d.buildMode
  expectedOrgUrl=$d.expectedOrgUrl;bundleSha256=$result.bundleSha256;verification='solution-readback-passed'
 }
 $out="$PlanFile.receipt.json";$receipt|ConvertTo-Json -Depth 15|Set-Content -LiteralPath $out -Encoding utf8
 Write-Output "DEPLOY_RECEIPT: $out"
}finally{
 if($snapshotRoot){
  try{Invoke-SourceJson @('cleanup','--repo',$rp,'--snapshot-root',$snapshotRoot)|Out-Null}catch{Write-Warning "Could not clean source snapshot: $($_.Exception.Message)"}
 }
 elseif($worktree -and (Test-Path -LiteralPath $worktree)){Git $rp @('worktree','remove','--force',$worktree)|Out-Null}
 if($sourcePlanFile -and (Test-Path -LiteralPath $sourcePlanFile)){Remove-Item -LiteralPath $sourcePlanFile -Force}
 if($pinRef){try{Git $rp @('update-ref','-d',$pinRef)|Out-Null}catch{Write-Warning "Could not remove temporary pinned ref: $pinRef"}}
}
