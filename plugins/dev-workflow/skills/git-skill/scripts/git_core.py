"""Portable, injectable Git operations used by the git-skill CLI.

All Git interaction passes through the supplied runner so callers can provide a
subprocess boundary in production and a recording boundary in tests.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Protocol


class Runner(Protocol):
    def run(self, args: list[str], cwd: Path): ...


@dataclass(frozen=True)
class GitContext:
    branch: str
    work_item_id: str | None
    status: str
    staged_files: tuple[str, ...]
    diff_stat: str


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    message: str = ""
    default_branch: str | None = None
    stash_ref: str | None = None
    error: str = ""


@dataclass(frozen=True)
class ManagementPreview:
    branches: list[str] = field(default_factory=list)
    stashes: list[str] = field(default_factory=list)
    requires_confirmation: bool = False
    ok: bool = True


class GitCore:
    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    def _run(self, repository: Path, *args: str):
        return self._runner.run(list(args), cwd=repository)

    @staticmethod
    def _ok(result) -> bool:
        return result.returncode == 0

    def _branch(self, repository: Path) -> tuple[str | None, str]:
        result = self._run(repository, "rev-parse", "--abbrev-ref", "HEAD")
        if not self._ok(result):
            return None, result.stderr.strip()
        return result.stdout.strip(), ""

    def _default_branch(self, repository: Path) -> str:
        remote_head = self._run(repository, "symbolic-ref", "refs/remotes/origin/HEAD")
        if self._ok(remote_head):
            value = remote_head.stdout.strip().rsplit("/", 1)[-1]
            if value:
                return value
        remotes = self._run(repository, "branch", "-r")
        if self._ok(remotes) and re.search(r"^\s*origin/main\s*$", remotes.stdout, re.M):
            return "main"
        return "master"

    @staticmethod
    def _work_item(branch: str) -> str | None:
        match = re.search(r"(?:^|/)(?:US/)?(\d+)(?:[-/]|$)", branch, re.I)
        if match:
            return match.group(1)
        match = re.search(r"\b(\d+)\b", branch)
        return match.group(1) if match else None

    def context(self, repository: Path, brief: bool = False) -> GitContext:
        branch, _ = self._branch(repository)
        status = self._run(repository, "status", "--porcelain")
        staged = self._run(repository, "diff", "--staged", "--name-only")
        stat = self._run(repository, "diff", "--staged", "--stat")
        return GitContext(
            branch=branch or "",
            work_item_id=self._work_item(branch or ""),
            status=status.stdout.rstrip(),
            staged_files=tuple(line for line in staged.stdout.splitlines() if line),
            diff_stat=stat.stdout.rstrip(),
        )

    def commit_push(self, repository: Path, message: str, staged_only: bool = False, no_prefix: bool = False) -> OperationResult:
        branch, error = self._branch(repository)
        if not branch:
            return OperationResult(False, error=error or "Could not determine current branch")
        if not staged_only:
            result = self._run(repository, "add", ".")
            if not self._ok(result):
                return OperationResult(False, error=result.stderr.strip())
        staged = self._run(repository, "diff", "--staged", "--name-only")
        if not self._ok(staged):
            return OperationResult(False, error=staged.stderr.strip())
        if not staged.stdout.strip():
            return OperationResult(False, error="No staged changes to commit")
        work_item = self._work_item(branch)
        if work_item and not no_prefix and not re.match(r"^#\d+\b", message):
            message = f"#{work_item} {message}"
        committed = self._run(repository, "commit", "-m", message)
        if not self._ok(committed):
            return OperationResult(False, message=message, error=committed.stderr.strip())
        pushed = self._run(repository, "push", "origin", "HEAD")
        return OperationResult(self._ok(pushed), message=message, error="" if self._ok(pushed) else pushed.stderr.strip())

    def new_branch(self, repository: Path, branch_name: str, preserve_dirty_default: bool = False) -> OperationResult:
        current, error = self._branch(repository)
        default = self._default_branch(repository)
        dirty = self._run(repository, "status", "--porcelain")
        stash_ref = None
        if preserve_dirty_default and current == default and dirty.stdout.strip():
            stash = self._run(repository, "stash", "push", "--include-untracked", "-m", f"WIP on {current}: create {branch_name}")
            if not self._ok(stash):
                return OperationResult(False, default_branch=default, error=stash.stderr.strip())
            stash_ref = "stash@{0}"
        checkout = self._run(repository, "checkout", default)
        if not self._ok(checkout):
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=checkout.stderr.strip())
        pulled = self._run(repository, "pull", "origin", default)
        if not self._ok(pulled):
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=pulled.stderr.strip())
        created = self._run(repository, "checkout", "-b", branch_name)
        if not self._ok(created):
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=created.stderr.strip())
        if stash_ref:
            reapplied = self._run(repository, "stash", "pop", stash_ref)
            if not self._ok(reapplied):
                return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=reapplied.stderr.strip())
        return OperationResult(True, default_branch=default, stash_ref=stash_ref)

    def stash_save(self, repository: Path, description: str, include_untracked: bool = False) -> OperationResult:
        branch, error = self._branch(repository)
        if not branch:
            return OperationResult(False, error=error or "Could not determine current branch")
        args = ["stash", "push"]
        if include_untracked:
            args.append("--include-untracked")
        args.extend(["-m", f"WIP on {branch}: {description}"])
        saved = self._runner.run(args, cwd=repository)
        if not self._ok(saved):
            return OperationResult(False, error=saved.stderr.strip())
        listed = self._run(repository, "stash", "list")
        ref = listed.stdout.split(":", 1)[0].strip() if self._ok(listed) and listed.stdout.strip() else None
        return OperationResult(True, stash_ref=ref)

    def merge_default(self, repository: Path) -> OperationResult:
        branch, error = self._branch(repository)
        if not branch:
            return OperationResult(False, error=error or "Could not determine current branch")
        default = self._default_branch(repository)
        dirty = self._run(repository, "status", "--porcelain")
        stash_ref = None
        if dirty.stdout.strip():
            saved = self._run(repository, "stash", "push", "-m", f"WIP on {branch}: merge {default}")
            if not self._ok(saved):
                return OperationResult(False, default_branch=default, error=saved.stderr.strip())
            stash_ref = "stash@{0}"
        updated = self._run(repository, "pull", "origin", default, "--no-edit")
        if not self._ok(updated):
            if stash_ref:
                self._run(repository, "stash", "pop", stash_ref)
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=updated.stderr.strip())
        staged = self._run(repository, "add", ".")
        if not self._ok(staged):
            if stash_ref:
                self._run(repository, "stash", "pop", stash_ref)
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=staged.stderr.strip())
        committed = self._run(repository, "commit", "-m", f"Merge branch '{default}' into {branch}")
        if not self._ok(committed):
            if stash_ref:
                self._run(repository, "stash", "pop", stash_ref)
            return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=committed.stderr.strip())
        if stash_ref:
            reapplied = self._run(repository, "stash", "pop", stash_ref)
            if not self._ok(reapplied):
                return OperationResult(False, default_branch=default, stash_ref=stash_ref, error=reapplied.stderr.strip())
        return OperationResult(True, default_branch=default, stash_ref=stash_ref)

    def management_preview(self, repository: Path, delete_local_only: bool = False, clear_stashes: bool = False, confirmed: bool = False) -> ManagementPreview:
        branch_result = self._run(repository, "branch", "-vv")
        stash_result = self._run(repository, "stash", "list")
        branches: list[str] = []
        for line in branch_result.stdout.splitlines():
            current = line.startswith("*")
            tokens = line.lstrip("* ").split()
            if tokens and not current and "[" not in line:
                branches.append(tokens[0])
        stashes = [line.split(":", 1)[0] for line in stash_result.stdout.splitlines() if line.startswith("stash@{")]
        needs_confirmation = bool((delete_local_only and branches) or (clear_stashes and stashes))
        if not confirmed:
            return ManagementPreview(branches, stashes, needs_confirmation)
        if delete_local_only:
            for branch in branches:
                self._run(repository, "branch", "-D", branch)
        if clear_stashes and stashes:
            self._run(repository, "stash", "clear")
        return ManagementPreview(branches, stashes, False)
