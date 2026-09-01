"""Portable command-line entrypoint for the git-skill package."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field, is_dataclass
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from typing import Callable, Protocol, Sequence

from git_core import GitCore
from git_pr import GitPr


NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
NOT_IMPLEMENTED_EXIT_CODE = 2


@dataclass(frozen=True)
class CliResult:
    """Structured command result shared by the CLI and its verifier."""

    status: str
    exit_code: int
    header: str
    message: str
    details: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "exit_code": self.exit_code,
            "header": self.header,
            "message": self.message,
            "details": self.details,
        }


class Runner(Protocol):
    def run(self, args: list[str], cwd: Path): ...


AZ_MISSING_MESSAGE = (
    "Executable not found: az. Install the Azure CLI from https://aka.ms/installazurecli, "
    "add the DevOps extension ('az extension add --name azure-devops'), then run 'az login'."
)


def resolve_az() -> str | None:
    """Return the absolute Azure CLI path, or None when it is not installed.

    On Windows `az` is a batch shim (`az.cmd`) and subprocess.run uses CreateProcess, which does
    not apply PATHEXT — a bare "az" argv[0] raises FileNotFoundError even with the CLI installed.
    shutil.which does honour PATHEXT, so resolve through it and spawn the absolute path. `git` is
    deliberately left bare: CreateProcess resolves `.exe` implicitly, which is why it already works.
    """
    return shutil.which("az") or shutil.which("az.cmd")


class SubprocessRunner:
    """Production process boundary using argv arrays only."""

    def run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        # "az" stays the logical argv[0] sentinel everywhere upstream (git/az dispatch here,
        # PreviewRunner's mutating-argv gate, the injected test runners). Substitute the resolved
        # path only at the spawn, after the sentinel has been read.
        if args and args[0] == "az":
            resolved = resolve_az()
            if resolved is None:
                return subprocess.CompletedProcess(args, 127, "", AZ_MISSING_MESSAGE)
            command = [resolved, *args[1:]]
        else:
            command = ["git", *args]
        try:
            return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
        except FileNotFoundError:
            return subprocess.CompletedProcess(command, 127, "", f"Executable not found: {command[0]}")


class PreviewRunner:
    """Block mutating argv before they reach the supplied process boundary."""

    _MUTATING_GIT = {"add", "commit", "push", "checkout", "merge", "stash", "fetch"}

    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    def run(self, args: list[str], cwd: Path):
        if self._is_mutating(args):
            if args[0] == "fetch":
                # Preview planning needs a comparison ref but must not contact a remote.
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="Skipped during preview")
        return self._runner.run(args, cwd)

    @classmethod
    def _is_mutating(cls, args: list[str]) -> bool:
        if not args:
            return False
        if args[0] in cls._MUTATING_GIT:
            return True
        if args[:2] in (["branch", "-D"], ["branch", "-d"]):
            return True
        return args[:4] in (["az", "repos", "pr", "create"], ["az", "repos", "pr", "update"]) or args[:5] == ["az", "repos", "pr", "work-item", "add"]


Handler = Callable[[argparse.Namespace], CliResult]


def _not_implemented(header: str) -> CliResult:
    return CliResult(
        status=NOT_IMPLEMENTED,
        exit_code=NOT_IMPLEMENTED_EXIT_CODE,
        header=header,
        message=f"{header.lower()} behavior is not implemented.",
    )


def _repository(args: argparse.Namespace) -> Path:
    return Path(args.repository).resolve() if args.repository else Path.cwd()


def _runner(args: argparse.Namespace) -> Runner:
    return args.runner


def _core_result(header: str, value: object, *, dry_run: bool = False) -> CliResult:
    ok = bool(getattr(value, "ok", False))
    details = {
        key: item
        for key, item in vars(value).items()
        if item not in (None, "", (), [], {})
    }
    if dry_run:
        details.update({"dry_run": True, "mutated": False})
    details = {key: _json_value(item) for key, item in details.items()}
    return CliResult(
        status="OK" if ok else "ERROR",
        exit_code=0 if ok else 1,
        header=header,
        message=getattr(value, "message", "") or getattr(value, "error", "") or ("Completed" if ok else "Operation failed"),
        details=details,
    )


def _json_value(value: object) -> object:
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def _preview_result(header: str, core: GitCore, repository: Path) -> CliResult:
    context = core.context(repository, brief=True)
    return CliResult(
        status="OK",
        exit_code=0,
        header=header,
        message="Preview completed without mutation.",
        details={"dry_run": True, "mutated": False, "branch": context.branch, "staged_files": list(context.staged_files)},
    )


def handle_doctor(args: argparse.Namespace) -> CliResult:
    runner = _runner(args)
    repository = _repository(args)
    git = runner.run(["--version"], repository)
    azure = runner.run(["az", "--version"], repository)
    ok = git.returncode == 0 and azure.returncode == 0
    return CliResult(
        status="OK" if ok else "ERROR",
        exit_code=0 if ok else 1,
        header="DOCTOR",
        message="Read-only prerequisite check completed." if ok else "A required prerequisite is unavailable.",
        details={"git_available": git.returncode == 0, "azure_cli_available": azure.returncode == 0},
    )


def handle_context(args: argparse.Namespace) -> CliResult:
    context = GitCore(_runner(args)).context(_repository(args), args.brief)
    return CliResult(
        status="OK",
        exit_code=0,
        header="CONTEXT",
        message="Repository context collected.",
        details={
            "brief": args.brief,
            "branch": getattr(context, "branch", ""),
            "work_item_id": getattr(context, "work_item_id", None),
            "status": getattr(context, "status", ""),
            "staged_files": list(getattr(context, "staged_files", ())),
            "diff_stat": getattr(context, "diff_stat", ""),
        },
    )


def handle_commit(args: argparse.Namespace) -> CliResult:
    core = GitCore(_runner(args))
    repository = _repository(args)
    if args.dry_run:
        return _preview_result("COMMIT", core, repository)
    return _core_result("COMMIT", core.commit_push(repository, args.message or "", args.staged_only, args.no_prefix))


def handle_branch(args: argparse.Namespace) -> CliResult:
    core = GitCore(_runner(args))
    repository = _repository(args)
    if args.dry_run:
        return _preview_result("BRANCH", core, repository)
    return _core_result("BRANCH", core.new_branch(repository, args.name or "", args.preserve_dirty_default))


def handle_merge(args: argparse.Namespace) -> CliResult:
    core = GitCore(_runner(args))
    repository = _repository(args)
    if args.dry_run:
        return _preview_result("MERGE", core, repository)
    return _core_result("MERGE", core.merge_default(repository))


def handle_stash(args: argparse.Namespace) -> CliResult:
    core = GitCore(_runner(args))
    repository = _repository(args)
    if args.dry_run:
        return _preview_result("STASH", core, repository)
    return _core_result("STASH", core.stash_save(repository, args.description or "", args.include_untracked))


def handle_branches(args: argparse.Namespace) -> CliResult:
    core = GitCore(_runner(args))
    repository = _repository(args)
    if args.dry_run:
        return _preview_result("BRANCHES", core, repository)
    return _core_result("BRANCHES", core.management_preview(repository, args.delete_local_only, args.clear_stashes, args.confirm))


def handle_pr(args: argparse.Namespace) -> CliResult:
    description = args.description
    if args.description_file:
        try:
            description = Path(args.description_file).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            return CliResult("ERROR", 1, "PR", f"Could not read description file: {error}")
    preview = args.preview or args.dry_run
    runner: Runner = PreviewRunner(_runner(args)) if preview else _runner(args)
    result = GitPr(runner).create(
        _repository(args),
        args.target_branch,
        allow_no_work_items=args.allow_no_work_items,
        preview=preview,
        description=description,
        title=args.title,
        work_item_ids=tuple(args.work_items) if args.work_items is not None else None,
    )
    return _core_result("PR", result, dry_run=preview)


def _add_repository_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repository",
        help="Repository path. Defaults to the current directory.",
    )


def _add_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    handler: Handler,
) -> argparse.ArgumentParser:
    command = subparsers.add_parser(name, help=help_text, description=help_text)
    _add_repository_argument(command)
    command.set_defaults(handler=handler)
    return command


def build_parser() -> argparse.ArgumentParser:
    """Build the importable public parser without performing any operations."""

    parser = argparse.ArgumentParser(
        prog="git-skill",
        description="Portable Git workflow CLI.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    _add_command(subparsers, "doctor", "Check prerequisites and repository readiness.", handle_doctor)

    context = _add_command(subparsers, "context", "Show repository context.", handle_context)
    context.add_argument("--brief", action="store_true", help="Request concise context output.")

    commit = _add_command(subparsers, "commit", "Commit and push selected work.", handle_commit)
    commit.add_argument("message", nargs="?", help="Commit message.")
    commit.add_argument("--staged-only", action="store_true", help="Commit only already staged files.")
    commit.add_argument("--no-prefix", action="store_true", help="Do not infer a work-item prefix.")
    commit.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    branch = _add_command(subparsers, "branch", "Create a work branch.", handle_branch)
    branch.add_argument("name", nargs="?", help="New branch name.")
    branch.add_argument("--preserve-dirty-default", action="store_true", help="Preserve dirty default-branch work.")
    branch.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    merge = _add_command(subparsers, "merge", "Merge the default branch into the current branch.", handle_merge)
    merge.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    stash = _add_command(subparsers, "stash", "Save current work to a stash.", handle_stash)
    stash.add_argument("description", nargs="?", help="Stash description.")
    stash.add_argument("--include-untracked", action="store_true", help="Include untracked files.")
    stash.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    branches = _add_command(subparsers, "branches", "Preview or manage branches and stashes.", handle_branches)
    branches.add_argument("--delete-local-only", action="store_true", help="Delete eligible local-only branches.")
    branches.add_argument("--clear-stashes", action="store_true", help="Clear stashes.")
    branches.add_argument("--confirm", action="store_true", help="Confirm destructive actions.")
    branches.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    pr = _add_command(subparsers, "pr", "Preview or create a pull request.", handle_pr)
    pr.add_argument("--target-branch", help="Target branch override.")
    pr.add_argument("--title", help="Pull-request title override.")
    descriptions = pr.add_mutually_exclusive_group()
    descriptions.add_argument("--description", help="Pull-request description override.")
    descriptions.add_argument("--description-file", help="UTF-8 file containing the pull-request description.")
    pr.add_argument("--work-items", nargs="+", help="Explicit positive Azure DevOps work-item IDs.")
    pr.add_argument("--allow-no-work-items", action="store_true", help="Permit no linked work items.")
    pr.add_argument("--preview", action="store_true", help="Preview without mutation.")
    pr.add_argument("--dry-run", action="store_true", help="Preview without mutation.")

    return parser


def emit_result(result: CliResult) -> None:
    """Render exactly one header and one machine-readable result record."""

    print(f"=== {result.header} ===")
    print(f"RESULT: {json.dumps(result.to_dict(), separators=(',', ':'), sort_keys=True)}")


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler: Handler | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return NOT_IMPLEMENTED_EXIT_CODE
    args.runner = runner or SubprocessRunner()
    result = handler(args)
    emit_result(result)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
