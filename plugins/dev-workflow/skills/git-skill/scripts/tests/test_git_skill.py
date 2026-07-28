"""Task 3 CLI and verifier contract tests.

Registry: .plans/portable-git-daily-report-dev-workflow.git.test-cases.md
Design: portable-git-daily-report-dev-workflow.md, Task 3 (AC-1, AC-4, AC-12, AC-13).
TC-036 is the durable public-surface baseline. TC-038 through TC-044
deliberately specify the not-yet-wired portable CLI and verifier behavior.
"""

# Test registry: .plans/portable-git-daily-report-dev-workflow.git.test-cases.md
# Subject: portable git-skill CLI and self-verifier

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import git_skill
import verify_output


@dataclass(frozen=True)
class ProcessResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class RecordingRunner:
    """Injected process boundary: no subprocess, Git, or Azure call is made."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path]] = []

    def run(self, args: list[str], cwd: Path) -> ProcessResult:
        self.calls.append((args, cwd))
        if args[:3] == ["rev-parse", "--abbrev-ref", "HEAD"]:
            return ProcessResult(stdout="US/1234-cli-contract\n")
        if args[:2] == ["status", "--porcelain"]:
            return ProcessResult(stdout=" M untouched.txt\n")
        if args[:3] == ["diff", "--staged", "--name-only"]:
            return ProcessResult(stdout="selected.txt\n")
        if args[:3] == ["diff", "--staged", "--stat"]:
            return ProcessResult(stdout=" selected.txt | 1 +\n")
        if args[:3] == ["remote", "get-url", "origin"]:
            return ProcessResult(stdout="https://dev.azure.com/org/project/_git/repo\n")
        if args[:2] == ["branch", "-r"]:
            return ProcessResult(stdout="  origin/dev\n  origin/master\n")
        if args[:2] == ["log", "origin/dev..US/1234-cli-contract"]:
            return ProcessResult(stdout="#5678 contract\n")
        return ProcessResult()


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {path.relative_to(directory).as_posix(): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


# TC-036: Public surface — setup: use entrypoints from an unrelated directory;
# action: compile/import modules, ask for help, and parse every public subcommand;
# verification: help succeeds, all commands remain exposed, and help does not alter the filesystem.
def test_TC_036_Should_ExposePortablePublicSurface_When_InvokedFromUnrelatedWorkingDirectory(tmp_path: Path) -> None:
    for module_path in (SCRIPTS / "git_skill.py", SCRIPTS / "verify_output.py"):
        compile(module_path.read_text(encoding="utf-8"), str(module_path), "exec")
    commands = ("doctor", "context", "commit", "branch", "merge", "stash", "branches", "pr")
    parser = git_skill.build_parser()
    assert {parser.parse_args([command]).command for command in commands} == set(commands)
    before = _snapshot(tmp_path)
    cli_help = subprocess.run([sys.executable, "-B", str(SCRIPTS / "git_skill.py"), "--help"], cwd=tmp_path, text=True, capture_output=True)
    verifier_help = subprocess.run([sys.executable, "-B", str(SCRIPTS / "verify_output.py"), "--help"], cwd=tmp_path, text=True, capture_output=True)
    assert cli_help.returncode == verifier_help.returncode == 0
    assert "COMMAND" in cli_help.stdout and "--result" in verifier_help.stdout
    assert _snapshot(tmp_path) == before


# TC-037: Deterministic routing — setup: build the public parser; action: select every command;
# verification: each subcommand is assigned its intended, named public handler.
@pytest.mark.parametrize(
    ("argv", "expected_handler"),
    [
        (["doctor"], "handle_doctor"), (["context", "--brief"], "handle_context"),
        (["commit", "message", "--staged-only"], "handle_commit"),
        (["branch", "US/1234-contract"], "handle_branch"), (["merge"], "handle_merge"),
        (["stash", "contract", "--include-untracked"], "handle_stash"),
        (["branches", "--delete-local-only", "--confirm"], "handle_branches"),
        (["pr", "--preview"], "handle_pr"),
    ],
)
def test_TC_037_Should_AssignNamedHandler_When_ParserReceivesEachPublicSubcommand(argv: list[str], expected_handler: str) -> None:
    parsed = git_skill.build_parser().parse_args(argv)

    assert parsed.handler is getattr(git_skill, expected_handler)


def _is_mutating_argv(argv: list[str]) -> bool:
    """Classify only commands that can alter repository or Azure state."""
    if not argv:
        return False
    if argv[0] in {"add", "commit", "push", "checkout", "merge", "stash", "fetch"}:
        return True
    if argv[:2] == ["branch", "-D"] or argv[:2] == ["branch", "-d"]:
        return True
    if argv[:4] == ["az", "repos", "pr", "create"] or argv[:4] == ["az", "repos", "pr", "update"]:
        return True
    return argv[:5] == ["az", "repos", "pr", "work-item", "add"]


# TC-038: Result contract — setup: request a safe context operation; action: render its result;
# verification: stdout has one stable section header and a machine-readable complete result schema.
def test_TC_038_Should_EmitStructuredResultAndStableHeader_When_CommandSucceeds(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = git_skill.main(["context", "--brief", "--repository", str(tmp_path)], runner=RecordingRunner())

    output = capsys.readouterr().out.splitlines()
    payload = json.loads(next(line.removeprefix("RESULT: ") for line in output if line.startswith("RESULT: ")))
    assert exit_code == 0
    assert output[0] == "=== CONTEXT ==="
    assert payload["status"] == "OK"
    assert payload["exit_code"] == 0
    assert {"status", "exit_code", "header", "message", "details"} <= payload.keys()


# TC-039: Preview safety — setup: snapshot a disposable directory and inject the process boundary;
# action: request every mutation-capable dry-run/preview; verification: discovery may read Git/PR state,
# but no mutating argv is sent and the filesystem remains unchanged.
@pytest.mark.parametrize("argv", [
    ["commit", "message", "--dry-run"], ["branch", "US/1234-contract", "--dry-run"],
    ["merge", "--dry-run"], ["stash", "contract", "--dry-run"],
    ["branches", "--delete-local-only", "--confirm", "--dry-run"], ["pr", "--preview"],
])
def test_TC_039_Should_NotMutate_When_DryRunOrPreviewIsRequested(argv: list[str], tmp_path: Path) -> None:
    runner = RecordingRunner()
    before = _snapshot(tmp_path)

    exit_code = git_skill.main([*argv, "--repository", str(tmp_path)], runner=runner)

    assert exit_code == 0
    assert not [call for call, _ in runner.calls if _is_mutating_argv(call)]
    assert _snapshot(tmp_path) == before


# TC-040: Core mapping — setup: replace GitCore with a boundary fake; action: use each core command;
# verification: CLI forwards parsed inputs to the exact portable core method.
@pytest.mark.parametrize(
    ("argv", "method", "expected"),
    [
        (["context", "--brief"], "context", (True,)),
        (["commit", "message", "--staged-only", "--no-prefix"], "commit_push", ("message", True, True)),
        (["branch", "US/1234-contract", "--preserve-dirty-default"], "new_branch", ("US/1234-contract", True)),
        (["merge"], "merge_default", ()), (["stash", "note", "--include-untracked"], "stash_save", ("note", True)),
        (["branches", "--delete-local-only", "--clear-stashes", "--confirm"], "management_preview", (True, True, True)),
    ],
)
def test_TC_040_Should_ForwardParsedArgumentsToGitCore_When_CoreCommandRuns(argv: list[str], method: str, expected: tuple[object, ...], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[object, ...]]] = []

    class FakeCore:
        def __init__(self, runner: RecordingRunner) -> None: pass
        def __getattr__(self, name: str):
            def invoke(repository: Path, *arguments: object):
                calls.append((name, arguments))
                return type("Result", (), {"ok": True, "message": "ok", "error": "", "__dict__": {}})()
            return invoke

    monkeypatch.setattr(git_skill, "GitCore", FakeCore)
    assert git_skill.main([*argv, "--repository", str(tmp_path)], runner=RecordingRunner()) == 0
    assert calls == [(method, expected)]


# TC-041: PR mapping — setup: replace GitPr with a boundary fake; action: request preview/create;
# verification: CLI forwards target, description, no-work-item, and preview intent exactly once.
def test_TC_041_Should_ForwardParsedArgumentsToGitPr_When_PrCommandRuns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str | None, bool, bool, str | None]] = []

    class FakePr:
        def __init__(self, runner: RecordingRunner) -> None: pass
        def create(self, repository: Path, target_branch: str | None = None, *, allow_no_work_items: bool = False, preview: bool = False, description: str | None = None):
            calls.append((repository, target_branch, allow_no_work_items, preview, description))
            return type("Result", (), {"ok": True, "preview": preview, "error": "", "__dict__": {}})()

    monkeypatch.setattr(git_skill, "GitPr", FakePr)
    assert git_skill.main(["pr", "--target-branch", "dev", "--description", "Contract", "--allow-no-work-items", "--preview", "--repository", str(tmp_path)], runner=RecordingRunner()) == 0
    assert calls == [(tmp_path, "dev", True, True, "Contract")]


# TC-042: Verifier result schema — setup: supply a complete CLI result; action: verify it;
# verification: invalid schema fails closed and valid schema reports VERIFY success without a new mutation.
def test_TC_042_Should_ValidateCliResultSchema_When_VerifyingStructuredResult(tmp_path: Path) -> None:
    valid = {"status": "OK", "exit_code": 0, "header": "CONTEXT", "message": "ok", "details": {}}
    invalid = {"status": "OK", "header": "CONTEXT"}

    assert verify_output.verify_result(valid, repository=tmp_path).exit_code == 0
    assert verify_output.verify_result(invalid, repository=tmp_path).exit_code != 0


# TC-043: Postconditions — setup: inject read-only repository evidence; action: verify a mutation result;
# verification: expected touched files and Azure work-item links must all be present.
def test_TC_043_Should_FailVerification_When_ExpectedFilesOrWorkItemLinksAreMissing(tmp_path: Path) -> None:
    result = {"status": "OK", "exit_code": 0, "header": "PR", "message": "created", "details": {"touched_files": ["changed.txt"], "work_item_ids": ["5678"]}}

    verified = verify_output.verify_result(result, repository=tmp_path, expected_files=["changed.txt", "missing.txt"], expected_work_items=["5678", "9999"])

    assert verified.exit_code != 0
    assert "missing.txt" in verified.message and "9999" in verified.message


# TC-044: Dry-run invariants — setup: snapshot repository evidence; action: verify a dry-run result;
# verification: verifier performs read-only checks and rejects any reported mutation.
def test_TC_044_Should_RejectReportedMutation_When_VerifyingDryRunInvariant(tmp_path: Path) -> None:
    before = _snapshot(tmp_path)
    result = {"status": "OK", "exit_code": 0, "header": "COMMIT", "message": "preview", "details": {"dry_run": True, "mutated": True}}

    verified = verify_output.verify_result(result, repository=tmp_path, dry_run=True)

    assert verified.exit_code != 0
    assert "dry-run" in verified.message.lower()
    assert _snapshot(tmp_path) == before
