import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "deploy-target.ps1"


def _write_mocks(bindir):
    (bindir / "git.cmd").write_text(
        '@echo off\r\npwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0mock-git.ps1" %*\r\n', encoding="utf-8"
    )
    (bindir / "pac.cmd").write_text(
        '@echo off\r\necho %*>>"%PAC_LOG%"\r\necho Environment Url: %PAC_MOCK%\r\n', encoding="utf-8"
    )
    (bindir / "npm.cmd").write_text('@echo off\r\nexit /b 0\r\n', encoding="utf-8")
    (bindir / "mock-git.ps1").write_text(
        r'''$joined = $args -join ' '
if ($env:GIT_LOG) { Add-Content -LiteralPath $env:GIT_LOG -Value $joined }
if ($joined -match 'ls-remote') {
  $count = 0
  if (Test-Path $env:GIT_COUNT) { $count = [int](Get-Content -Raw $env:GIT_COUNT) }
  Set-Content -LiteralPath $env:GIT_COUNT -Value ($count + 1)
  $sets = $env:GIT_LS_REMOTE_SEQUENCE -split '\|\|\|'
  $index = [Math]::Min($count, $sets.Count - 1)
  Write-Output $sets[$index]
  exit 0
}
if ($joined -match 'fetch') { exit 0 }
if ($joined -match 'rev-parse --verify') { Write-Output $env:GIT_FETCH_SHA; exit 0 }
if ($joined -match 'worktree add') {
  $path = $args[-2]
  New-Item -ItemType Directory -Force -Path $path | Out-Null
  $scriptPath = Join-Path $path 'Solution/scripts/deploy-variant.ps1'
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $scriptPath) | Out-Null
  @'
param([string]$Variant, [string]$BuildMode, [string]$ExpectedOrgUrl)
Write-Output '[deploy-variant] Deploy source contract: expected-org-pin-v1'
Write-Output "[deploy-variant] Auto version (timestamp): 20260824.101010"
Write-Output '[deploy-variant] Verified solution readback: CORECustomControl variant, unmanaged=False'
Write-Output '[deploy-variant] Deploy source contract: verified-publish-readback-v1'
'@ | Set-Content -LiteralPath $scriptPath -Encoding utf8
  Set-Content -LiteralPath (Join-Path $path 'package-lock.json') -Value '{}' -Encoding utf8
  $zipPath = Join-Path $path 'Solution/bin/Debug/CORECustomControl.zip'
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $zipPath) | Out-Null
  Set-Content -LiteralPath $zipPath -Value 'test package' -Encoding utf8
  exit 0
}
if ($joined -match 'worktree remove') {
  $path = $args[-1]
  if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
  exit 0
}
exit 0
''', encoding="utf-8"
    )


def run(tmp_path, *args, git_lines="", pac_org="https://yanaintegrationdevqa.crm5.dynamics.com", fetch_sha="abc"):
    bindir = tmp_path / "bin"; bindir.mkdir(exist_ok=True)
    _write_mocks(bindir)
    env = os.environ | {
        "PATH": str(bindir) + os.pathsep + os.environ["PATH"],
        "GIT_LS_REMOTE_SEQUENCE": git_lines,
        "GIT_COUNT": str(tmp_path / "git-count.txt"),
        "GIT_FETCH_SHA": fetch_sha,
        "YANA_PCF_PYTHON": sys.executable,
        "GIT_LOG": str(tmp_path / "git-log.txt"),
        "PAC_LOG": str(tmp_path / "pac-log.txt"),
        "PAC_MOCK": pac_org,
    }
    return subprocess.run(["pwsh", "-NoProfile", "-File", str(SCRIPT), *args], text=True, capture_output=True, env=env)


def test_pinned_rc_latest_requires_exact_source(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    p = run(tmp_path, "-Target", "RC", "-SourceVersion", "latest", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="aaa refs/heads/1.5.0\nbbb refs/heads/1.6.1\nccc refs/heads/RC/9.0")
    assert p.returncode == 2 and "exact" in p.stdout.lower()
    assert not (tmp_path / "git-log.txt").exists(), "ambiguous latest RC must not query candidate refs"


def test_personal_without_branch_needs_input(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    p = run(tmp_path, "-Target", "Personal", "-Repo", str(repo), "-Plan")
    assert p.returncode == 2 and "NEEDS_INPUT" in p.stdout


def test_hotfix_without_branch_or_version_needs_input(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir()
    p = run(tmp_path, "-Target", "Hotfix", "-Repo", str(repo), "-Plan")
    assert p.returncode == 2 and "NEEDS_INPUT" in p.stdout


def test_explicit_semver_uses_exact_origin_branch(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    p = run(tmp_path, "-Target", "RC", "-SourceVersion", "1.5.1", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="deadbeef refs/heads/1.5.1")
    assert p.returncode == 0
    assert json.loads(plan.read_text())["sourceBranch"] == "origin/1.5.1"


def test_tampered_plan_aborts_before_remote_or_pac(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    assert run(tmp_path, "-Target", "Preview", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/dev").returncode == 0
    data = json.loads(plan.read_text()); data["variant"] = "evil"; plan.write_text(json.dumps(data))
    p = run(tmp_path, "-PlanFile", str(plan), "-Apply", "-ConfirmSourceSha", "abc")
    assert "Plan hash mismatch" in (p.stdout + p.stderr)


def test_prod_plan_is_blocked_before_source_resolution(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    p = run(tmp_path, "-Target", "Prod", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/master")
    assert p.returncode == 2 and "CI/CD only" in p.stdout
    assert not (tmp_path / "git-log.txt").exists()


def test_wrong_org_fails_before_deploy(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    assert run(tmp_path, "-Target", "Preview", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/dev").returncode == 0
    p = run(tmp_path, "-PlanFile", str(plan), "-Apply", "-ConfirmSourceSha", "abc", git_lines="abc refs/heads/dev", pac_org="https://wrong.crm.dynamics.com")
    assert p.returncode != 0 and "PAC org mismatch" in (p.stdout + p.stderr)
    assert "worktree add" not in (tmp_path / "git-log.txt").read_text(encoding="utf-8")


def test_remote_sha_drift_aborts_before_pac_or_worktree(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    assert run(tmp_path, "-Target", "Preview", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/dev").returncode == 0
    p = run(tmp_path, "-PlanFile", str(plan), "-Apply", "-ConfirmSourceSha", "abc", git_lines="def refs/heads/dev")
    log = (tmp_path / "git-log.txt").read_text(encoding="utf-8")
    assert p.returncode != 0 and "Remote SHA changed" in (p.stdout + p.stderr)
    assert "worktree add" not in log
    assert not (tmp_path / "pac-log.txt").exists(), "SHA drift must abort before PAC lookup"


def test_apply_fetches_exact_source_and_blocks_if_fetched_sha_differs(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); plan = tmp_path / "plan.json"
    assert run(tmp_path, "-Target", "Preview", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/dev").returncode == 0
    p = run(tmp_path, "-PlanFile", str(plan), "-Apply", "-ConfirmSourceSha", "abc", git_lines="abc refs/heads/dev", fetch_sha="def")
    log = (tmp_path / "git-log.txt").read_text(encoding="utf-8")
    assert p.returncode != 0 and "Fetched pinned ref differs" in (p.stdout + p.stderr)
    assert "fetch --no-tags --quiet origin +refs/heads/dev:refs/codex/pcf-deploy/" in log
    assert "worktree add" not in log
    assert not (tmp_path / "pac-log.txt").exists(), "fetched pin mismatch must abort before PAC lookup"


def test_dirty_checkout_never_becomes_source_or_mutation_target(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); (repo / "dirty.txt").write_text("keep", encoding="utf-8")
    plan = tmp_path / "plan.json"
    p = run(tmp_path, "-Target", "Personal", "-Repo", str(repo), "-Plan")
    assert p.returncode == 2 and "NEEDS_INPUT" in p.stdout
    assert (repo / "dirty.txt").read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "git-log.txt").exists(), "missing branch must not query current checkout"


def test_apply_uses_planned_worktree_and_writes_distinct_source_receipt(tmp_path):
    repo = tmp_path / "repo"; repo.mkdir(); (repo / "dirty.txt").write_text("keep", encoding="utf-8")
    plan = tmp_path / "plan.json"
    assert run(tmp_path, "-Target", "Preview", "-Repo", str(repo), "-Plan", "-PlanFile", str(plan), git_lines="abc refs/heads/dev").returncode == 0
    data = json.loads(plan.read_text(encoding="utf-8"))
    p = run(tmp_path, "-PlanFile", str(plan), "-Apply", "-ConfirmSourceSha", "abc", git_lines="abc refs/heads/dev")
    assert p.returncode == 0, p.stdout + p.stderr
    receipt_path = Path(str(plan) + ".receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    log = (tmp_path / "git-log.txt").read_text(encoding="utf-8")
    assert receipt["sourceVersion"] == "dev"
    assert receipt["technicalVariantVersion"] == "20260824.101010"
    assert receipt["technicalVariantVersion"] != receipt["sourceVersion"]
    assert "worktree add" in log and "worktree remove" in log
    assert "fetch --no-tags --quiet origin +refs/heads/dev:refs/codex/pcf-deploy/" in log
    assert "update-ref -d refs/codex/pcf-deploy/" in log
    assert receipt["bundleSha256"]
    assert not Path(data["worktreePath"]).exists()
    assert (repo / "dirty.txt").read_text(encoding="utf-8") == "keep"


class DeployTargetTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(prefix="pcf-deploy-wrapper-test-")
        self.tmp_path = Path(self._temp.name)

    def tearDown(self):
        self._temp.cleanup()

    def test_pinned_rc_latest_requires_exact_source(self):
        test_pinned_rc_latest_requires_exact_source(self.tmp_path)

    def test_personal_without_branch_needs_input(self):
        test_personal_without_branch_needs_input(self.tmp_path)

    def test_hotfix_without_branch_or_version_needs_input(self):
        test_hotfix_without_branch_or_version_needs_input(self.tmp_path)

    def test_explicit_semver_uses_exact_origin_branch(self):
        test_explicit_semver_uses_exact_origin_branch(self.tmp_path)

    def test_tampered_plan_aborts_before_remote_or_pac(self):
        test_tampered_plan_aborts_before_remote_or_pac(self.tmp_path)

    def test_prod_plan_is_blocked_before_source_resolution(self):
        test_prod_plan_is_blocked_before_source_resolution(self.tmp_path)

    def test_wrong_org_fails_before_deploy(self):
        test_wrong_org_fails_before_deploy(self.tmp_path)

    def test_remote_sha_drift_aborts_before_pac_or_worktree(self):
        test_remote_sha_drift_aborts_before_pac_or_worktree(self.tmp_path)

    def test_apply_fetches_exact_source_and_blocks_if_fetched_sha_differs(self):
        test_apply_fetches_exact_source_and_blocks_if_fetched_sha_differs(self.tmp_path)

    def test_dirty_checkout_never_becomes_source_or_mutation_target(self):
        test_dirty_checkout_never_becomes_source_or_mutation_target(self.tmp_path)

    def test_apply_uses_planned_worktree_and_writes_distinct_source_receipt(self):
        test_apply_uses_planned_worktree_and_writes_distinct_source_receipt(self.tmp_path)
