"""Test cases: .plans/portable-git-daily-report-dev-workflow.git.test-cases.md.

Design doc: .plans/portable-git-daily-report-dev-workflow.md (Task 2, AC-1/AC-3/AC-12).

TC-017 through TC-020 characterize the observable legacy PowerShell contract and
are deliberately GREEN.  TC-021 onward specify the portable GitPr contract.  They
are intentionally assertion-level RED until git_pr.py is implemented; the recording
runner never starts Git, Azure CLI, or a browser.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[6]
LEGACY_PR = REPO_ROOT / "scripts" / "git" / "Git-CreatePR.ps1"
GIT_PR = Path(__file__).resolve().parents[1] / "git_pr.py"


@dataclass(frozen=True)
class ProcessResult:
    """The Task 1 recording-runner response shape."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Records argv calls and returns fixtures without starting a process."""

    def __init__(self, responses: dict[tuple[str, ...], ProcessResult] | None = None) -> None:
        self.calls: list[tuple[list[str], Path]] = []
        self.responses = responses or {}

    def run(self, args: list[str], cwd: Path) -> ProcessResult:
        assert isinstance(args, list), "Commands must cross the boundary as argv lists"
        assert all(isinstance(value, str) for value in args), "Every argv value must be a string"
        self.calls.append((args, cwd))
        return self.responses.get(tuple(args), ProcessResult())


class SequencedRecordingRunner(RecordingRunner):
    """Returns deterministic successive responses for re-query assertions."""

    def __init__(self, responses: dict[tuple[str, ...], list[ProcessResult]]) -> None:
        super().__init__()
        self.responses = {args: list(results) for args, results in responses.items()}

    def run(self, args: list[str], cwd: Path) -> ProcessResult:
        assert isinstance(args, list), "Commands must cross the boundary as argv lists"
        assert all(isinstance(value, str) for value in args), "Every argv value must be a string"
        self.calls.append((args, cwd))
        results = self.responses.get(tuple(args), [])
        return results.pop(0) if results else ProcessResult()


def _legacy() -> str:
    """Read the legacy PR baseline, skipping where it does not ship.

    An installed skill carries no `scripts/git/`, so this characterization source is
    source-repository-only and the suite must stay green without it.
    """
    if not LEGACY_PR.is_file():
        pytest.skip("legacy Git-CreatePR.ps1 is absent outside the source repository")
    return LEGACY_PR.read_text(encoding="utf-8")


def _legacy_function(script: str, name: str) -> str:
    """Return a single PowerShell function body so documentation text cannot affect order checks."""

    start = script.index(f"function {name}")
    next_function = script.find("\nfunction ", start + 1)
    return script[start : next_function if next_function != -1 else len(script)]


def _portable_pr() -> ModuleType:
    """Fail as an assertion, rather than an import/setup error, until Task 2 lands."""

    assert GIT_PR.is_file(), (
        "Portable PR planner is not implemented: expected "
        "prompts/source/skills/git-skill/scripts/git_pr.py"
    )
    spec = importlib.util.spec_from_file_location("portable_git_pr", GIT_PR)
    assert spec and spec.loader, "git_pr.py must be importable as a standalone Python module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _planning_runner() -> RecordingRunner:
    """Provide a deterministic repository-planning boundary without running Git."""

    return RecordingRunner(
        {
            ("remote", "get-url", "origin"): ProcessResult(
                stdout="https://dev.azure.com/Contoso/Fleet/_git/Vehicle.Api\n"
            ),
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-pr-metadata\n"),
            ("branch", "-r"): ProcessResult(stdout=" origin/dev\n origin/master\n"),
            ("fetch", "origin", "dev", "--quiet"): ProcessResult(),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/dev"): ProcessResult(),
            ("log", "origin/dev..US/1878-pr-metadata", "--pretty=format:%s"): ProcessResult(
                stdout="#1907 add metadata"
            ),
        }
    )


# TC-017: Characterize Azure DevOps remote URL parsing.
# Steps:
# 1. Read the existing PR helper.
# 2. Provide HTTPS and SSH Azure DevOps remote URL forms.
# 3. Verify organization, project, and repository parsing supports both forms.
# Design: Task 2, AC-3.
@pytest.mark.parametrize(
    "remote_url",
    [
        "https://dev.azure.com/Contoso/Fleet/_git/Vehicle.Api",
        "https://user@dev.azure.com/Contoso/Fleet/_git/Vehicle.Api",
        "git@ssh.dev.azure.com:v3/Contoso/Fleet/Vehicle.Api",
    ],
)
def test_TC_017_Should_KeepAzureDevOpsRemoteVariants_When_CharacterizingPowerShell(remote_url: str) -> None:
    script = _legacy()

    assert "function Get-AzureDevOpsInfo" in script
    assert "dev\\.azure\\.com[:/](?:v3/)?([^/]+)/([^/]+)/_git/([^/\\s]+)" in script
    assert "dev\\.azure\\.com[:/](?:v3/)?([^/]+)/([^/]+)/([^/\\s]+)" in script
    assert "[Uri]::UnescapeDataString($Matches[2])" in script
    assert "dev.azure.com" in remote_url


# TC-018: Characterize target selection, fetched comparison ref, and task extraction.
# Steps:
# 1. Read the existing PR helper.
# 2. Request a PR from a feature branch and inspect target/ref selection.
# 3. Verify target priority, remote ref preference, and commit-subject task extraction.
# Design: Task 2, AC-1 and AC-3.
def test_TC_018_Should_KeepTargetComparisonAndCommitTaskRules_When_CharacterizingPowerShell() -> None:
    script = _legacy()
    target = _legacy_function(script, "Get-AutoTargetBranch")
    comparison = _legacy_function(script, "Get-ComparisonRef")
    tasks = _legacy_function(script, "Get-CommitTaskIds")

    feature_priority = target[target.index("# For feature branches") :]
    assert feature_priority.index("origin/dev") < feature_priority.index("origin/master") < feature_priority.index("origin/main")
    assert 'return "origin/$TargetBranch"' in comparison
    assert '$commitRange = "$comparisonRef..$SourceBranch"' in tasks
    assert "#(\\d+)\\s+(.+)$" in tasks and "^(\\d+)[-\\s]+(.+)$" in tasks


# TC-019: Characterize title formatting and description precedence.
# Steps:
# 1. Read the existing PR helper.
# 2. Provide a story branch, explicit description, review report, and template.
# 3. Verify title uses the branch and descriptions resolve explicit file, review, template, then fallback.
# Design: Task 2, AC-3.
def test_TC_019_Should_KeepTitleAndDescriptionPrecedence_When_CharacterizingPowerShell() -> None:
    script = _legacy()
    title = _legacy_function(script, "Format-PRTitle")
    description = _legacy_function(script, "Get-PRDescription")

    assert 'return "#$branchId $summary"' in title
    assert 'return "Merge $BranchName"' in title
    explicit = description.index("$resolvedDescriptionFile = Resolve-DescriptionFilePath")
    review = description.index("$codeReviewFile = Find-CodeReviewDescriptionFile")
    template = description.index("$templateFile = Find-PullRequestTemplate")
    fallback = description.index("return Format-DefaultPRDescription")
    assert explicit < review < template < fallback


# TC-020: Characterize preview/no-task safety and metadata repair behavior.
# Steps:
# 1. Read the existing PR helper.
# 2. Attempt a plan without commit task IDs and inspect preview behavior.
# 3. Verify creation stops without an explicit override, preview exits before creation, and metadata repair is available.
# Design: Task 2, AC-3 and AC-12.
def test_TC_020_Should_KeepPrSafetyStopsAndMetadataRepair_When_CharacterizingPowerShell() -> None:
    script = _legacy()
    main = script[script.index("# Main script execution") :]

    assert "-not $AllowNoWorkItems" in main
    assert "No task work item IDs found in source-branch commit subjects" in main
    assert main.index("if ($Preview)") < main.index("Get-GitRemoteUrl") < main.index('"az", "repos", "pr", "create"')
    assert "az repos pr update" in script and "az repos pr work-item add" in script


# TC-021: Parse supported Azure DevOps remote URL variants through a pure result.
# Steps:
# 1. Provide HTTPS, credentialed HTTPS, and SSH remote URLs.
# 2. Parse each URL without starting a process.
# 3. Verify the same organization, decoded project, and repository are returned.
# Design: Task 2, AC-3.
@pytest.mark.parametrize(
    "remote_url",
    [
        "https://dev.azure.com/Contoso/Fleet%20Ops/_git/Vehicle.Api",
        "https://user@dev.azure.com/Contoso/Fleet%20Ops/_git/Vehicle.Api",
        "git@ssh.dev.azure.com:v3/Contoso/Fleet%20Ops/Vehicle.Api",
    ],
)
def test_TC_021_Should_ParseAzureDevOpsRemote_When_UrlUsesSupportedVariant(remote_url: str) -> None:
    pr = _portable_pr()

    info = pr.parse_azure_devops_remote(remote_url)

    assert info.organization == "Contoso"
    assert info.project == "Fleet Ops"
    assert info.repository == "Vehicle.Api"


# TC-022: Resolve target, comparison ref, and commit task IDs without mutating a repository.
# Steps:
# 1. Provide a feature branch, remote branches, and commit subjects.
# 2. Build a PR plan through the recording boundary.
# 3. Verify dev is selected, origin/dev is compared, and unique task IDs are extracted.
# Design: Task 2, AC-1 and AC-3.
def test_TC_022_Should_UseRemoteComparisonRefAndCommitTaskIds_When_PlanningFeaturePr() -> None:
    pr = _portable_pr()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-pr-metadata\n"),
            ("branch", "-r"): ProcessResult(stdout=" origin/dev\n origin/master\n"),
            ("fetch", "origin", "dev", "--quiet"): ProcessResult(),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/dev"): ProcessResult(),
            ("log", "origin/dev..US/1878-pr-metadata", "--pretty=format:%s"): ProcessResult(
                stdout="#1908 test: add coverage\n#1907 fix: link tasks\n#1908 duplicate"
            ),
        }
    )

    plan = pr.GitPr(runner).plan(Path("repo"))

    assert plan.target_branch == "dev"
    assert plan.comparison_ref == "origin/dev"
    assert plan.work_item_ids == ("1907", "1908")
    assert ["log", "origin/dev..US/1878-pr-metadata", "--pretty=format:%s"] in [args for args, _ in runner.calls]


# TC-023: Stop before any Azure call when source commits have no task ID.
# Steps:
# 1. Provide a valid source/target context with a non-task commit subject.
# 2. Request PR creation without an override.
# 3. Verify the result stops with the no-work-item reason and Azure CLI is never requested.
# Design: Task 2, AC-3 and AC-12.
def test_TC_023_Should_StopBeforeAzureCreate_When_NoCommitTaskIdsAndNoOverride() -> None:
    pr = _portable_pr()
    runner = RecordingRunner({("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="feature/no-id\n")})

    result = pr.GitPr(runner).create(Path("repo"), target_branch="master")

    assert result.ok is False
    assert result.error == "No task work item IDs found in source-branch commit subjects"
    assert not any(args[:4] == ["az", "repos", "pr", "create"] for args, _ in runner.calls)


# TC-024: Produce a non-mutating complete preview, including explicit no-work-item override.
# Steps:
# 1. Provide no task IDs and explicitly allow that condition.
# 2. Request preview mode.
# 3. Verify the plan is returned and neither Azure create nor Git cleanup runs.
# Design: Task 2, AC-3 and AC-12.
def test_TC_024_Should_ReturnPreviewWithoutMutation_When_NoWorkItemsAreExplicitlyAllowed() -> None:
    pr = _portable_pr()
    runner = RecordingRunner({("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="feature/no-id\n")})

    result = pr.GitPr(runner).create(Path("repo"), target_branch="master", allow_no_work_items=True, preview=True)

    assert result.ok is True
    assert result.preview is True
    assert result.plan.work_item_ids == ()
    assert not any(args[0] in {"az", "checkout", "pull", "branch", "push"} for args, _ in runner.calls)


# TC-025: Use branch title and deterministic description precedence.
# Steps:
# 1. Supply a title-worthy branch plus explicit, review, template, and fallback descriptions.
# 2. Build the PR plan.
# 3. Verify branch title is used and the first available description wins.
# Design: Task 2, AC-3.
def test_TC_025_Should_ChooseExplicitThenReviewThenTemplateThenFallback_When_BuildingDescription() -> None:
    pr = _portable_pr()

    assert pr.format_pr_title("US/1878-pr-metadata") == "#1878 pr metadata"
    assert pr.resolve_description(explicit="explicit", review="review", template="template", fallback="fallback") == "explicit"
    assert pr.resolve_description(explicit=None, review="review", template="template", fallback="fallback") == "review"
    assert pr.resolve_description(explicit=None, review=None, template="template", fallback="fallback") == "template"
    assert pr.resolve_description(explicit=None, review=None, template=None, fallback="fallback") == "fallback"


# TC-026: Create Azure DevOps PR with complete argv and detected work-item links.
# Steps:
# 1. Provide a complete PR plan and a create response.
# 2. Create the PR through the recording boundary.
# 3. Verify Azure CLI receives explicit org, project, repo, refs, title, description, and task IDs.
# Design: Task 2, AC-3.
def test_TC_026_Should_SendCompleteAzureCliArgv_When_CreatingPr() -> None:
    pr = _portable_pr()
    runner = RecordingRunner({("az", "repos", "pr", "create", "--org", "https://dev.azure.com/Contoso", "--project", "Fleet", "--repository", "Vehicle.Api", "--source-branch", "US/1878-pr-metadata", "--target-branch", "master", "--title", "#1878 pr metadata", "--description", "body", "--work-items", "1907", "1908", "--output", "json"): ProcessResult(stdout='{"pullRequestId": 42}')})
    plan = pr.PrPlan("Contoso", "Fleet", "Vehicle.Api", "US/1878-pr-metadata", "master", "origin/master", "#1878 pr metadata", "body", ("1907", "1908"))

    result = pr.GitPr(runner).create_from_plan(Path("repo"), plan)

    assert result.ok is True
    assert result.pull_request_id == 42
    assert runner.calls[0][0] == ["az", "repos", "pr", "create", "--org", "https://dev.azure.com/Contoso", "--project", "Fleet", "--repository", "Vehicle.Api", "--source-branch", "US/1878-pr-metadata", "--target-branch", "master", "--title", "#1878 pr metadata", "--description", "body", "--work-items", "1907", "1908", "--output", "json"]


# TC-027: Repair title, description, and only missing linked work items after creation.
# Steps:
# 1. Provide a created PR with legacy title, empty description, and one missing task link.
# 2. Verify and repair its metadata through the recording boundary.
# 3. Provide corrected title, body, and work-item responses on the mandatory re-query.
# 4. Verify title/body update and a single missing-work-item repair are requested.
# Design: Task 2, AC-3.
def test_TC_027_Should_RepairIncompleteMetadata_When_VerificationFindsDrift() -> None:
    pr = _portable_pr()
    show = ("az", "repos", "pr", "show", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    work_items = ("az", "repos", "pr", "work-item", "list", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    runner = SequencedRecordingRunner(
        {
            show: [
                ProcessResult(stdout='{"title":"Merge feature into master","description":""}'),
                ProcessResult(stdout='{"title":"#1878 pr metadata","description":"body"}'),
            ],
            work_items: [
                ProcessResult(stdout="[{\"id\":1907}]"),
                ProcessResult(stdout="[{\"id\":1907},{\"id\":1908}]"),
            ],
        }
    )

    result = pr.GitPr(runner).verify_metadata(Path("repo"), 42, "https://dev.azure.com/Contoso", "#1878 pr metadata", "body", ("1907", "1908"))

    commands = [args for args, _ in runner.calls]
    assert result.ok is True
    assert ["az", "repos", "pr", "update", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--title", "#1878 pr metadata", "--output", "none"] in commands
    assert ["az", "repos", "pr", "update", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--description", "body", "--output", "none"] in commands
    assert ["az", "repos", "pr", "work-item", "add", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--work-items", "1908", "--output", "none"] in commands
    assert commands.count(list(show)) == 2
    assert commands.count(list(work_items)) == 2


# TC-028: Stop optional auto-merge on conflicts or merge failure.
# Steps:
# 1. Provide a PR that reports a conflict or merge failure.
# 2. Request auto-merge.
# 3. Verify completion fails and neither target sync nor source cleanup follows.
# Design: Task 2, AC-3 and AC-12.
@pytest.mark.parametrize("merge_status", ["conflicts", "failure"])
def test_TC_028_Should_NotSyncOrCleanup_When_AutoMergeCannotComplete(merge_status: str) -> None:
    pr = _portable_pr()
    runner = RecordingRunner({("az", "repos", "pr", "show", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json"): ProcessResult(stdout=f'{{"mergeStatus":"{merge_status}","status":"active"}}')})

    result = pr.GitPr(runner).auto_merge(Path("repo"), 42, "https://dev.azure.com/Contoso", "master", "US/1878-pr-metadata")

    assert result.ok is False
    assert result.error == f"PR auto-merge unavailable: {merge_status}"
    assert not any(args[0] in {"checkout", "pull", "branch", "push"} for args, _ in runner.calls)


# TC-029: Sync target only after a completed auto-merge and refuse unsafe cleanup.
# Steps:
# 1. Provide a completed PR and successful target synchronization.
# 2. Request source cleanup without explicit confirmation.
# 3. Verify checkout/pull run, but source deletion is refused.
# Design: Task 2, AC-3 and AC-12.
def test_TC_029_Should_SyncTargetButRefuseCleanup_When_AutoMergeCompletesWithoutConfirmation() -> None:
    pr = _portable_pr()
    runner = RecordingRunner()

    result = pr.GitPr(runner).sync_and_cleanup(Path("repo"), target_branch="master", source_branch="US/1878-pr-metadata", confirmed_cleanup=False)

    commands = [args for args, _ in runner.calls]
    assert result.ok is True
    assert result.cleanup_refused is True
    assert commands[:2] == [["checkout", "master"], ["pull", "origin", "master"]]
    assert not any(args[:2] == ["branch", "-D"] or args[:3] == ["push", "origin", "--delete"] for args in commands)


# TC-030: Obtain and parse origin remote details while planning a PR.
# Steps:
# 1. Provide an origin Azure DevOps remote plus a feature-branch planning context.
# 2. Build a plan through the recording boundary.
# 3. Verify origin is queried and organization, decoded project, and repository populate the plan.
# Design: Task 2, AC-3.
def test_TC_030_Should_QueryAndParseOriginRemote_When_PlanningPr() -> None:
    pr = _portable_pr()
    runner = RecordingRunner(
        {
            ("remote", "get-url", "origin"): ProcessResult(
                stdout="https://dev.azure.com/Contoso/Fleet%20Ops/_git/Vehicle.Api\n"
            ),
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-pr-metadata\n"),
            ("branch", "-r"): ProcessResult(stdout=" origin/dev\n origin/master\n"),
            ("fetch", "origin", "dev", "--quiet"): ProcessResult(),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/dev"): ProcessResult(),
            ("log", "origin/dev..US/1878-pr-metadata", "--pretty=format:%s"): ProcessResult(stdout="#1907 add metadata"),
        }
    )

    plan = pr.GitPr(runner).plan(Path("repo"))

    assert plan.organization == "Contoso"
    assert plan.project == "Fleet Ops"
    assert plan.repository == "Vehicle.Api"
    assert ["remote", "get-url", "origin"] in [args for args, _ in runner.calls]


# TC-031: Re-query repaired PR metadata and fail if it remains wrong.
# Steps:
# 1. Provide a PR whose title, body, and work-item links remain incomplete after repair requests.
# 2. Verify and repair its metadata through the recording boundary.
# 3. Verify title/body/work-item state is queried again and the outcome reports failure.
# Design: Task 2, AC-3 and AC-12.
def test_TC_031_Should_FailMetadataVerification_When_RequeryStillFindsDrift() -> None:
    pr = _portable_pr()
    show = ("az", "repos", "pr", "show", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    work_items = ("az", "repos", "pr", "work-item", "list", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    runner = SequencedRecordingRunner(
        {
            show: [
                ProcessResult(stdout='{"title":"old title","description":"old body"}'),
                ProcessResult(stdout='{"title":"old title","description":"old body"}'),
            ],
            work_items: [
                ProcessResult(stdout="[]"),
                ProcessResult(stdout="[]"),
            ],
        }
    )

    result = pr.GitPr(runner).verify_metadata(
        Path("repo"), 42, "https://dev.azure.com/Contoso", "#1878 pr metadata", "body", ("1907",)
    )

    commands = [args for args, _ in runner.calls]
    assert result.ok is False
    assert result.error == "PR metadata repair verification failed"
    assert commands.count(list(show)) == 2
    assert commands.count(list(work_items)) == 2


# TC-035: Re-query repaired PR metadata and fail if final metadata cannot be parsed.
# Steps:
# 1. Provide a PR with metadata drift that causes title, body, and work-item repairs.
# 2. Return empty or malformed metadata responses on the required post-repair re-query.
# 3. Verify repair commands were requested but verification reports failure.
# Design: Task 2, AC-3 and AC-12.
@pytest.mark.parametrize("final_metadata", ["", "not json"])
def test_TC_035_Should_FailMetadataVerification_When_RequeryIsUnavailableOrUnparseable(final_metadata: str) -> None:
    pr = _portable_pr()
    show = ("az", "repos", "pr", "show", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    work_items = ("az", "repos", "pr", "work-item", "list", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    runner = SequencedRecordingRunner(
        {
            show: [
                ProcessResult(stdout='{"title":"old title","description":"old body"}'),
                ProcessResult(stdout=final_metadata),
            ],
            work_items: [
                ProcessResult(stdout="[]"),
                ProcessResult(stdout=final_metadata),
            ],
        }
    )

    result = pr.GitPr(runner).verify_metadata(
        Path("repo"), 42, "https://dev.azure.com/Contoso", "#1878 pr metadata", "body", ("1907",)
    )

    commands = [args for args, _ in runner.calls]
    assert result.ok is False
    assert result.error == "PR metadata repair verification failed"
    assert ["az", "repos", "pr", "update", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--title", "#1878 pr metadata", "--output", "none"] in commands
    assert ["az", "repos", "pr", "update", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--description", "body", "--output", "none"] in commands
    assert ["az", "repos", "pr", "work-item", "add", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--work-items", "1907", "--output", "none"] in commands
    assert commands.count(list(show)) == 2
    assert commands.count(list(work_items)) == 2


# TC-045: Use an explicit description before repository-backed sources.
# Steps:
# 1. Create a code-review file and both project template files under a temporary repository.
# 2. Build the PR plan with an explicit description through the recording Git boundary.
# 3. Verify the explicit raw content wins without reading a repository-backed description.
# Design: Task 2, AC-3.
def test_TC_045_Should_UseExplicitDescription_When_RepositorySourcesAlsoExist(tmp_path: Path) -> None:
    pr = _portable_pr()
    (tmp_path / ".CodeReview").mkdir()
    (tmp_path / ".CodeReview" / "US-1878-pr-metadata.md").write_text("review content", encoding="utf-8")
    (tmp_path / ".azuredevops").mkdir()
    (tmp_path / ".azuredevops" / "pull_request_template.md").write_text("azure template", encoding="utf-8")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "pull_request_template.md").write_text("github template", encoding="utf-8")

    plan = pr.GitPr(_planning_runner()).plan(tmp_path, description="explicit content")

    assert plan.description == "explicit content"


# TC-046: Prefer the source-branch code-review report over a project template.
# Steps:
# 1. Create the sanitized source-branch review file and a project template under a temporary repository.
# 2. Build the PR plan without an explicit description through the recording Git boundary.
# 3. Verify the plan uses the raw review-file content.
# Design: Task 2, AC-3.
def test_TC_046_Should_UseCodeReviewDescription_When_TemplateAlsoExists(tmp_path: Path) -> None:
    pr = _portable_pr()
    (tmp_path / ".CodeReview").mkdir()
    (tmp_path / ".CodeReview" / "US-1878-pr-metadata.md").write_text("review content", encoding="utf-8")
    (tmp_path / ".azuredevops").mkdir()
    (tmp_path / ".azuredevops" / "pull_request_template.md").write_text("azure template", encoding="utf-8")

    plan = pr.GitPr(_planning_runner()).plan(tmp_path)

    assert plan.description == "review content"


# TC-047: Use the first available project template when no code-review report exists.
# Steps:
# 1. Create one project template candidate under a temporary repository, without a review file.
# 2. Build the PR plan through the recording Git boundary.
# 3. Verify .azuredevops is preferred and .github is used when it is the only template.
# Design: Task 2, AC-3.
@pytest.mark.parametrize(
    ("template_path", "expected_content"),
    [
        (".azuredevops/pull_request_template.md", "azure template"),
        (".github/pull_request_template.md", "github template"),
    ],
)
def test_TC_047_Should_UseProjectTemplateInSearchOrder_When_NoCodeReviewExists(
    tmp_path: Path, template_path: str, expected_content: str
) -> None:
    pr = _portable_pr()
    template = tmp_path / template_path
    template.parent.mkdir()
    template.write_text(expected_content, encoding="utf-8")

    plan = pr.GitPr(_planning_runner()).plan(tmp_path)

    assert plan.description == expected_content


# TC-048: Use the default description only after no repository-backed source exists.
# Steps:
# 1. Provide a temporary repository without explicit, review, or template description sources.
# 2. Build the PR plan through the recording Git boundary.
# 3. Verify the fallback description is returned.
# Design: Task 2, AC-3.
def test_TC_048_Should_UseFallbackDescription_When_NoRepositoryDescriptionSourceExists(tmp_path: Path) -> None:
    pr = _portable_pr()

    plan = pr.GitPr(_planning_runner()).plan(tmp_path)

    assert plan.description == "Merge US/1878-pr-metadata into dev"


# TC-032: Request Azure auto-complete and sync only once the PR is completed.
# Steps:
# 1. Provide an active PR followed by a completed PR response.
# 2. Request optional auto-merge and target synchronization through the recording boundary.
# 3. Verify the explicit auto-complete argv precedes completed-state confirmation and target checkout/pull.
# Design: Task 2, AC-3 and AC-12.
def test_TC_032_Should_RequestAutoCompleteThenSync_When_PrCompletes() -> None:
    pr = _portable_pr()
    show = ("az", "repos", "pr", "show", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--output", "json")
    auto_complete = ["az", "repos", "pr", "update", "--id", "42", "--org", "https://dev.azure.com/Contoso", "--auto-complete", "true", "--output", "none"]
    runner = SequencedRecordingRunner(
        {
            show: [
                ProcessResult(stdout='{"status":"active","mergeStatus":"succeeded"}'),
                ProcessResult(stdout='{"status":"completed","mergeStatus":"succeeded"}'),
            ]
        }
    )

    result = pr.GitPr(runner).auto_merge_and_sync(Path("repo"), 42, "https://dev.azure.com/Contoso", "master")

    commands = [args for args, _ in runner.calls]
    assert result.ok is True
    assert commands.index(auto_complete) < commands.index(list(show), commands.index(auto_complete) + 1)
    assert commands.index(list(show), commands.index(auto_complete) + 1) < commands.index(["checkout", "master"])
    assert commands[-2:] == [["checkout", "master"], ["pull", "origin", "master"]]


# TC-033: Delete confirmed source branches only after target checkout and pull succeed.
# Steps:
# 1. Provide successful target checkout and pull responses.
# 2. Confirm source cleanup through the recording boundary.
# 3. Verify local and remote source deletion occur after the target is synchronized.
# Design: Task 2, AC-3 and AC-12.
def test_TC_033_Should_DeleteLocalAndRemoteSource_When_CleanupIsConfirmedAfterTargetSync() -> None:
    pr = _portable_pr()
    runner = RecordingRunner()

    result = pr.GitPr(runner).sync_and_cleanup(
        Path("repo"), target_branch="master", source_branch="US/1878-pr-metadata", confirmed_cleanup=True
    )

    commands = [args for args, _ in runner.calls]
    assert result.ok is True
    assert result.cleanup_complete is True
    assert commands == [
        ["checkout", "master"],
        ["pull", "origin", "master"],
        ["branch", "-D", "US/1878-pr-metadata"],
        ["push", "origin", "--delete", "US/1878-pr-metadata"],
    ]


# TC-034: Stop cleanup when target checkout or pull fails.
# Steps:
# 1. Provide a failed target checkout or pull response.
# 2. Request confirmed cleanup through the recording boundary.
# 3. Verify the operation fails and neither local nor remote source deletion is requested.
# Design: Task 2, AC-3 and AC-12.
@pytest.mark.parametrize(
    ("responses", "expected_calls"),
    [
        ({("checkout", "master"): ProcessResult(returncode=1, stderr="checkout failed")}, [["checkout", "master"]]),
        ({("pull", "origin", "master"): ProcessResult(returncode=1, stderr="pull failed")}, [["checkout", "master"], ["pull", "origin", "master"]]),
    ],
)
def test_TC_034_Should_StopCleanup_When_TargetSynchronizationFails(
    responses: dict[tuple[str, ...], ProcessResult], expected_calls: list[list[str]]
) -> None:
    pr = _portable_pr()
    runner = RecordingRunner(responses)

    result = pr.GitPr(runner).sync_and_cleanup(
        Path("repo"), target_branch="master", source_branch="US/1878-pr-metadata", confirmed_cleanup=True
    )

    commands = [args for args, _ in runner.calls]
    assert result.ok is False
    assert result.error == "Target synchronization failed"
    assert commands == expected_calls
