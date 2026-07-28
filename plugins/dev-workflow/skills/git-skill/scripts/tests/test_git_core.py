"""Test cases: .plans/portable-git-daily-report-dev-workflow.git.test-cases.md.

Design doc: .plans/portable-git-daily-report-dev-workflow.md (Task 1, AC-1/AC-2/AC-12).

Characterization tests deliberately pin the observable PowerShell behavior first.  Portable
contract tests use a recording process boundary and must remain assertion-level RED until
git_core.py exists; they never invoke Git or mutate a repository.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[6]
LEGACY_GIT = REPO_ROOT / "scripts" / "git"
GIT_CORE = Path(__file__).resolve().parents[1] / "git_core.py"


@dataclass(frozen=True)
class ProcessResult:
    """Minimal process result supplied by the test boundary."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Records argv calls; it intentionally never starts a process."""

    def __init__(self, responses: dict[tuple[str, ...], ProcessResult] | None = None) -> None:
        self.calls: list[tuple[list[str], Path]] = []
        self.responses = responses or {}

    def run(self, args: list[str], cwd: Path) -> ProcessResult:
        assert isinstance(args, list), "Git commands must be passed as an argv list"
        assert all(isinstance(arg, str) for arg in args), "Git argv values must be strings"
        self.calls.append((args, cwd))
        return self.responses.get(tuple(args), ProcessResult())


def _legacy_script(name: str) -> str:
    """Read a legacy PowerShell baseline, skipping where it does not ship.

    These characterization tests pin the behavior the portable rewrite replaced, so
    they only apply inside the source repository. An installed skill carries no
    `scripts/git/`, and the suite must stay green there rather than error.
    """
    script = LEGACY_GIT / name
    if not script.is_file():
        pytest.skip(f"legacy baseline {name} is absent outside the source repository")
    return script.read_text(encoding="utf-8")


def _portable_core() -> ModuleType:
    """Load only after a clear assertion explains the intended RED state."""

    assert GIT_CORE.is_file(), (
        "Portable Git core is not implemented: expected "
        "prompts/source/skills/git-skill/scripts/git_core.py"
    )
    spec = importlib.util.spec_from_file_location("portable_git_core", GIT_CORE)
    assert spec and spec.loader, "git_core.py must be importable as a standalone Python module"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# TC-001: Characterize context and commit/push command order.
# Steps:
# 1. Read the current commit helper.
# 2. Request either supported read-only context mode.
# 3. Verify that context is read-only and commit mode stages, commits, then pushes.
# Design reference: Task 1, AC-1.
def test_TC_001_Should_KeepCurrentCommitContextAndPushBehavior_When_CharacterizingPowerShell() -> None:
    script = _legacy_script("Git-CommitPush.ps1")

    assert "[switch]$GetContext" in script and "[switch]$Brief" in script
    assert "if ($GetContext)" in script and "if ($Brief)" in script
    assert script.index("git add .") < script.index('git commit -m "$Message"') < script.index("git push origin HEAD")
    assert "[switch]$StagedOnly" in script and "-not $StagedOnly" in script


# TC-002: Characterize default branch discovery and branch creation safety.
# Steps:
# 1. Read the current branch helper.
# 2. Simulate an unavailable remote default branch through its documented fallback path.
# 3. Verify master is the fallback and creation first updates the default branch.
# Design reference: Task 1, AC-2.
def test_TC_002_Should_KeepCurrentDefaultBranchFallbackAndCreationOrder_When_CharacterizingPowerShell() -> None:
    script = _legacy_script("Git-NewBranch.ps1")

    assert "git symbolic-ref refs/remotes/origin/HEAD" in script
    assert "origin/master" in script and "origin/main" in script
    assert "return 'master'" in script
    assert script.index("git checkout $DefaultBranch") < script.index("git pull origin $DefaultBranch") < script.index("git checkout -b $BranchName")


# TC-003: Characterize stash message and untracked-file option.
# Steps:
# 1. Read the current stash helper.
# 2. Supply a branch and description.
# 3. Verify the stash command includes the branch-labelled message and supports untracked files.
# Design reference: Task 1, AC-2.
def test_TC_003_Should_KeepCurrentStashMessageAndUntrackedOption_When_CharacterizingPowerShell() -> None:
    script = _legacy_script("Git-StashSave.ps1")

    assert '$stashMessage = "WIP on $currentBranch`: $Description"' in script
    assert "$stashArgs = @('stash', 'save')" in script
    assert "if ($IncludeUntracked)" in script and "$stashArgs += '--include-untracked'" in script
    assert "& git $stashArgs" in script


# TC-004: Characterize confirmation boundaries for destructive branch and stash actions.
# Steps:
# 1. Read the current management helper.
# 2. Select branch or stash deletion.
# 3. Verify confirmation is requested before any destructive Git command.
# Design reference: Task 1, AC-12.
def test_TC_004_Should_KeepCurrentConfirmationBoundaries_When_CharacterizingPowerShell() -> None:
    script = _legacy_script("Git-ManageBranches.ps1")

    assert script.index("Confirm deletion of") < script.index("git branch -D $branch.Name")
    assert script.index("Confirm deletion of ALL") < script.index("git stash clear")
    assert "Cannot delete current branch" in script
    assert "Do you also want to delete the remote branches?" in script


# TC-005: Run Git only through argv arrays at the process boundary.
# Steps:
# 1. Provide a recording command runner.
# 2. Request repository context for a path containing spaces.
# 3. Verify every Git request is an argv list and no shell command string is used.
# Design reference: Task 1, AC-1 and AC-12.
def test_TC_005_Should_UseArgvArrays_When_RequestingPortableContext() -> None:
    core = _portable_core()
    runner = RecordingRunner({("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-work\n")})

    core.GitCore(runner).context(Path("repo with spaces"), brief=True)

    assert runner.calls
    assert all(isinstance(args, list) and " " not in args[0] for args, _ in runner.calls)
    assert "shell=True" not in GIT_CORE.read_text(encoding="utf-8")


# TC-006: Return brief context from current branch and staged diff without mutation.
# Steps:
# 1. Provide a story branch, staged change, and matching diff statistic.
# 2. Request brief context.
# 3. Verify the story ID and staged statistic are returned without a mutating command.
# Design reference: Task 1, AC-1.
def test_TC_006_Should_ReturnStagedBriefContextWithoutMutation_When_ChangesAreStaged() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-work\n"),
            ("status", "--porcelain"): ProcessResult(stdout="M  feature.py\n"),
            ("diff", "--staged", "--name-only"): ProcessResult(stdout="feature.py\n"),
            ("diff", "--staged", "--stat"): ProcessResult(stdout=" feature.py | 1 +\n"),
        }
    )

    context = core.GitCore(runner).context(Path("repo"), brief=True)

    assert context.branch == "US/1878-work"
    assert context.work_item_id == "1878"
    assert context.diff_stat == " feature.py | 1 +"
    assert all(args[0] not in {"add", "commit", "push", "checkout", "merge", "stash"} for args, _ in runner.calls)


# TC-007: Preserve unstaged files for a staged-only task commit and push.
# Steps:
# 1. Provide staged task work and separate unstaged work on a story branch.
# 2. Commit using the task ID and staged-only mode.
# 3. Verify no add command runs, the task ID is retained, and push follows commit.
# Design reference: Task 1, AC-1 and AC-12.
def test_TC_007_Should_PreserveUnstagedWork_When_CommittingStagedOnlyTaskChanges() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-work\n"),
            ("diff", "--staged", "--name-only"): ProcessResult(stdout="task.py\n"),
        }
    )

    result = core.GitCore(runner).commit_push(
        Path("repo"), message="#1907 feat: portable commit", staged_only=True, no_prefix=True
    )

    commands = [args for args, _ in runner.calls]
    assert ["add", "."] not in commands
    assert ["commit", "-m", "#1907 feat: portable commit"] in commands
    assert commands.index(["commit", "-m", "#1907 feat: portable commit"]) < commands.index(["push", "origin", "HEAD"])
    assert result.message.startswith("#1907 ")


# TC-008: Stash dirty default-branch work, create the story branch, then reapply it.
# Steps:
# 1. Start with uncommitted work on the default branch.
# 2. Request a new story branch while preserving untracked files.
# 3. Verify stash, branch creation, and stash reapplication occur in that order.
# Design reference: Task 1, AC-2 and AC-12.
def test_TC_008_Should_ReapplyDirtyDefaultWork_When_CreatingStoryBranch() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="master\n"),
            ("status", "--porcelain"): ProcessResult(stdout=" M tracked.txt\n?? new.txt\n"),
            ("symbolic-ref", "refs/remotes/origin/HEAD"): ProcessResult(stdout="refs/remotes/origin/master\n"),
        }
    )

    core.GitCore(runner).new_branch(Path("repo"), "US/1878-work", preserve_dirty_default=True)

    commands = [args for args, _ in runner.calls]
    stash = ["stash", "push", "--include-untracked", "-m", "WIP on master: create US/1878-work"]
    assert commands.index(stash) < commands.index(["checkout", "master"]) < commands.index(["checkout", "-b", "US/1878-work"]) < commands.index(["stash", "pop", "stash@{0}"])


# TC-009: Detect remote default branch with master fallback and stop after command failure.
# Steps:
# 1. Make remote HEAD unavailable and expose a master remote branch.
# 2. Request a branch creation and make checkout fail.
# 3. Verify master is selected and no pull or branch creation follows the failure.
# Design reference: Task 1, AC-2 and AC-12.
def test_TC_009_Should_FallbackToMasterAndStop_When_DefaultCheckoutFails() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("symbolic-ref", "refs/remotes/origin/HEAD"): ProcessResult(returncode=1),
            ("branch", "-r"): ProcessResult(stdout="  origin/master\n  origin/feature\n"),
            ("checkout", "master"): ProcessResult(returncode=1, stderr="blocked"),
        }
    )

    result = core.GitCore(runner).new_branch(Path("repo"), "US/1878-work")

    commands = [args for args, _ in runner.calls]
    assert result.ok is False
    assert result.default_branch == "master"
    assert ["pull", "origin", "master"] not in commands
    assert ["checkout", "-b", "US/1878-work"] not in commands


# TC-010: Preview destructive management actions until explicit confirmation.
# Steps:
# 1. Provide a local-only branch and a stash.
# 2. Request deletion without confirmation.
# 3. Verify the preview is returned and no delete, clear, or push command runs.
# Design reference: Task 1, AC-12.
def test_TC_010_Should_PreviewWithoutDeleting_When_ManagementIsNotConfirmed() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("branch", "-vv"): ProcessResult(stdout="  old 1234567 old work\n* current abcdef0 current work\n"),
            ("stash", "list"): ProcessResult(stdout="stash@{0}: WIP on current: work\n"),
        }
    )

    preview = core.GitCore(runner).management_preview(Path("repo"), delete_local_only=True, clear_stashes=True, confirmed=False)

    assert preview.requires_confirmation is True
    assert preview.branches == ["old"]
    assert preview.stashes == ["stash@{0}"]
    assert all(args not in (["branch", "-D", "old"], ["stash", "clear"]) and args[:2] != ["push", "origin"] for args, _ in runner.calls)


# TC-011: Prefix a provided commit message from the current story branch.
# Steps:
# 1. Provide a current story branch and staged task change.
# 2. Commit with a message that has no work-item prefix.
# 3. Verify the commit message uses the story ID before it is pushed.
# Design reference: Task 1, AC-2.
def test_TC_011_Should_PrefixProvidedMessage_When_CurrentBranchContainsStoryId() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-portable-git\n"),
            ("diff", "--staged", "--name-only"): ProcessResult(stdout="git_core.py\n"),
        }
    )

    result = core.GitCore(runner).commit_push(Path("repo"), message="feat: portable commit", staged_only=True)

    assert result.message == "#1878 feat: portable commit"
    assert ["commit", "-m", "#1878 feat: portable commit"] in [args for args, _ in runner.calls]


# TC-012: Save a named stash with untracked files and return its reference.
# Steps:
# 1. Provide a current story branch.
# 2. Save a stash with untracked files included.
# 3. Verify the labelled stash command and returned newest stash reference.
# Design reference: Task 1, AC-2.
def test_TC_012_Should_ReturnNewestStashReference_When_SavingNamedUntrackedWork() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-portable-git\n"),
            ("stash", "list"): ProcessResult(stdout="stash@{0}: On US/1878-portable-git: WIP on US/1878-portable-git: investigate\n"),
        }
    )

    result = core.GitCore(runner).stash_save(Path("repo"), "investigate", include_untracked=True)

    assert result.stash_ref == "stash@{0}"
    assert ["stash", "push", "--include-untracked", "-m", "WIP on US/1878-portable-git: investigate"] in [args for args, _ in runner.calls]


# TC-013: Stash and reapply dirty work around a successful default-branch merge.
# Steps:
# 1. Start on a story branch with uncommitted work.
# 2. Merge the detected default branch.
# 3. Verify dirty work is stashed before the update and reapplied after the merge commit.
# Design reference: Task 1, AC-2 and AC-12.
def test_TC_013_Should_ReapplyDirtyWork_When_DefaultBranchMergeSucceeds() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-portable-git\n"),
            ("status", "--porcelain"): ProcessResult(stdout=" M feature.py\n"),
            ("symbolic-ref", "refs/remotes/origin/HEAD"): ProcessResult(stdout="refs/remotes/origin/master\n"),
        }
    )

    result = core.GitCore(runner).merge_default(Path("repo"))

    commands = [args for args, _ in runner.calls]
    stash = ["stash", "push", "-m", "WIP on US/1878-portable-git: merge master"]
    assert result.ok is True
    assert commands.index(stash) < commands.index(["pull", "origin", "master", "--no-edit"]) < commands.index(["commit", "-m", "Merge branch 'master' into US/1878-portable-git"]) < commands.index(["stash", "pop", "stash@{0}"])


# TC-014: Restore dirty work and stop when the default-branch merge update fails.
# Steps:
# 1. Start on a story branch with uncommitted work.
# 2. Make the default-branch update fail.
# 3. Verify the stash is reapplied and no merge commit follows the failure.
# Design reference: Task 1, AC-2 and AC-12.
def test_TC_014_Should_ReapplyStashAndStop_When_DefaultBranchMergeUpdateFails() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-portable-git\n"),
            ("status", "--porcelain"): ProcessResult(stdout=" M feature.py\n"),
            ("symbolic-ref", "refs/remotes/origin/HEAD"): ProcessResult(stdout="refs/remotes/origin/master\n"),
            ("pull", "origin", "master", "--no-edit"): ProcessResult(returncode=1, stderr="update blocked"),
        }
    )

    result = core.GitCore(runner).merge_default(Path("repo"))

    commands = [args for args, _ in runner.calls]
    assert result.ok is False
    assert ["stash", "pop", "stash@{0}"] in commands
    assert ["add", "."] not in commands
    assert not any(args[:1] == ["commit"] for args in commands)


# TC-015: Execute confirmed safe management actions without deleting the current branch.
# Steps:
# 1. Provide one local-only branch, the current branch, and a stash.
# 2. Confirm the requested cleanup actions.
# 3. Verify only the eligible branch and stash are deleted.
# Design reference: Task 1, AC-12.
def test_TC_015_Should_DeleteOnlyEligibleBranchesAndStashes_When_ManagementIsConfirmed() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("branch", "-vv"): ProcessResult(stdout="  old 1234567 old work\n* current abcdef0 current work\n"),
            ("stash", "list"): ProcessResult(stdout="stash@{0}: WIP on current: work\n"),
        }
    )

    result = core.GitCore(runner).management_preview(Path("repo"), delete_local_only=True, clear_stashes=True, confirmed=True)

    commands = [args for args, _ in runner.calls]
    assert result.requires_confirmation is False
    assert ["branch", "-D", "old"] in commands
    assert ["branch", "-D", "current"] not in commands
    assert ["stash", "clear"] in commands


# TC-016: Preserve legacy staging within a successful default-branch merge.
# Steps:
# 1. Start on a story branch with uncommitted work.
# 2. Merge the detected default branch successfully.
# 3. Verify the merge stages changes after the update, before the merge commit, then restores the stash.
# Design reference: Task 1, AC-2 and AC-12.
def test_TC_016_Should_StageMergeChangesBeforeCommit_When_DefaultBranchMergeSucceeds() -> None:
    core = _portable_core()
    runner = RecordingRunner(
        {
            ("rev-parse", "--abbrev-ref", "HEAD"): ProcessResult(stdout="US/1878-portable-git\n"),
            ("status", "--porcelain"): ProcessResult(stdout=" M feature.py\n"),
            ("symbolic-ref", "refs/remotes/origin/HEAD"): ProcessResult(stdout="refs/remotes/origin/master\n"),
        }
    )

    core.GitCore(runner).merge_default(Path("repo"))

    commands = [args for args, _ in runner.calls]
    pull = ["pull", "origin", "master", "--no-edit"]
    stage = ["add", "."]
    commit = ["commit", "-m", "Merge branch 'master' into US/1878-portable-git"]
    restore = ["stash", "pop", "stash@{0}"]
    assert stage in commands, "Successful legacy-parity merges stage changes before committing"
    assert commands.index(pull) < commands.index(stage) < commands.index(commit) < commands.index(restore)
