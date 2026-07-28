"""Portable pull-request planning via an injected Git/Azure CLI runner.

The module deliberately has no subprocess or browser dependency.  Callers own
the process boundary by supplying an object with ``run(argv, cwd=Path)``.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Protocol
from urllib.parse import unquote


class Runner(Protocol):
    def run(self, args: list[str], cwd: Path): ...


@dataclass(frozen=True)
class AzureDevOpsRemote:
    organization: str
    project: str
    repository: str


@dataclass(frozen=True)
class PrPlan:
    organization: str
    project: str
    repository: str
    source_branch: str
    target_branch: str
    comparison_ref: str
    title: str
    description: str
    work_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class PrResult:
    ok: bool
    plan: PrPlan | None = None
    pull_request_id: int | None = None
    preview: bool = False
    cleanup_refused: bool = False
    cleanup_complete: bool = False
    error: str = ""


def parse_azure_devops_remote(remote_url: str) -> AzureDevOpsRemote | None:
    """Parse supported HTTPS and SSH Azure DevOps origin URL forms."""
    value = remote_url.strip()
    patterns = (
        r"(?:https://(?:[^@/]+@)?dev\.azure\.com/)([^/]+)/([^/]+)/_git/([^/\s]+)",
        r"(?:git@ssh\.dev\.azure\.com:)?v3/([^/]+)/([^/]+)/([^/\s]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            return AzureDevOpsRemote(*(unquote(part) for part in match.groups()))
    return None


def format_pr_title(branch: str) -> str:
    """Derive the legacy title format from a work-item branch name."""
    match = re.search(r"(?:^|/)(?:US/)?(\d+)[-/](.+)$", branch, re.IGNORECASE)
    if not match:
        return f"Merge {branch}"
    summary = match.group(2).replace("-", " ").strip()
    return f"#{match.group(1)} {summary}"


def resolve_description(*, explicit: str | None, review: str | None, template: str | None, fallback: str) -> str:
    return next((value for value in (explicit, review, template, fallback) if value), fallback)


class GitPr:
    def __init__(self, runner: Runner) -> None:
        self._runner = runner

    def _run(self, repository: Path, *args: str):
        return self._runner.run(list(args), cwd=repository)

    @staticmethod
    def _ok(result) -> bool:
        return result.returncode == 0

    @staticmethod
    def _json(result):
        if not result.stdout.strip():
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def _target(self, repository: Path, source: str, requested: str | None) -> str:
        if requested:
            return requested
        remotes = self._run(repository, "branch", "-r")
        branches = remotes.stdout.splitlines() if self._ok(remotes) else []
        if source == "dev":
            return "master" if any(line.strip() == "origin/master" for line in branches) else "main"
        for candidate in ("dev", "master", "main"):
            if any(line.strip() == f"origin/{candidate}" for line in branches):
                return candidate
        return "master"

    @staticmethod
    def _task_ids(subjects: str) -> tuple[str, ...]:
        found: set[str] = set()
        for subject in subjects.splitlines():
            match = re.match(r"\s*#(\d+)\s+.+$", subject) or re.match(r"\s*(\d+)[-\s]+.+$", subject)
            if match:
                found.add(match.group(1))
        return tuple(sorted(found, key=int))

    @staticmethod
    def _repository_description(repository: Path, source_branch: str) -> tuple[str | None, str | None]:
        """Return the first repository-local review or template description."""
        safe_branch = re.sub(r'[\\/:*?"<>|]+', "-", source_branch)
        candidates = (
            repository / ".CodeReview" / f"{safe_branch}.md",
            repository / ".azuredevops" / "pull_request_template.md",
            repository / ".github" / "pull_request_template.md",
        )
        for candidate in candidates:
            if candidate.is_file():
                content = candidate.read_text(encoding="utf-8")
                if candidate.parent.name == ".CodeReview":
                    return content, None
                return None, content
        return None, None

    def plan(self, repository: Path, target_branch: str | None = None, *, description: str | None = None) -> PrPlan:
        remote = self._run(repository, "remote", "get-url", "origin")
        info = parse_azure_devops_remote(remote.stdout) if self._ok(remote) else None
        branch = self._run(repository, "rev-parse", "--abbrev-ref", "HEAD")
        source = branch.stdout.strip() if self._ok(branch) else ""
        target = self._target(repository, source, target_branch)
        comparison = f"origin/{target}"
        fetched = self._run(repository, "fetch", "origin", target, "--quiet")
        if not self._ok(fetched):
            comparison = target
        elif not self._ok(self._run(repository, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{target}")):
            comparison = target
        commits = self._run(repository, "log", f"{comparison}..{source}", "--pretty=format:%s")
        task_ids = self._task_ids(commits.stdout) if self._ok(commits) else ()
        fallback = f"Merge {source} into {target}"
        review, template = self._repository_description(repository, source)
        return PrPlan(
            info.organization if info else "", info.project if info else "", info.repository if info else "",
            source, target, comparison, format_pr_title(source),
            resolve_description(explicit=description, review=review, template=template, fallback=fallback), task_ids,
        )

    def create(self, repository: Path, target_branch: str | None = None, *, allow_no_work_items: bool = False,
               preview: bool = False, description: str | None = None) -> PrResult:
        plan = self.plan(repository, target_branch, description=description)
        if not plan.work_item_ids and not allow_no_work_items:
            return PrResult(False, plan=plan, error="No task work item IDs found in source-branch commit subjects")
        if preview:
            return PrResult(True, plan=plan, preview=True)
        if not all((plan.organization, plan.project, plan.repository)):
            return PrResult(False, plan=plan, error="Could not parse Azure DevOps information from origin remote")
        return self.create_from_plan(repository, plan)

    def create_from_plan(self, repository: Path, plan: PrPlan) -> PrResult:
        args = ["az", "repos", "pr", "create", "--org", f"https://dev.azure.com/{plan.organization}",
                "--project", plan.project, "--repository", plan.repository, "--source-branch", plan.source_branch,
                "--target-branch", plan.target_branch, "--title", plan.title, "--description", plan.description]
        if plan.work_item_ids:
            args += ["--work-items", *plan.work_item_ids]
        args += ["--output", "json"]
        result = self._run(repository, *args)
        data = self._json(result)
        if not self._ok(result) or not isinstance(data, dict) or not data.get("pullRequestId"):
            return PrResult(False, plan=plan, error=(result.stderr.strip() or "PR create did not return a pull request ID"))
        return PrResult(True, plan=plan, pull_request_id=int(data["pullRequestId"]))

    def verify_metadata(self, repository: Path, pull_request_id: int, organization_url: str, expected_title: str,
                        expected_description: str, expected_work_item_ids: tuple[str, ...]) -> PrResult:
        identifier = str(pull_request_id)
        show_args = ("az", "repos", "pr", "show", "--id", identifier, "--org", organization_url, "--output", "json")
        links_args = ("az", "repos", "pr", "work-item", "list", "--id", identifier, "--org", organization_url, "--output", "json")
        show, links = self._run(repository, *show_args), self._run(repository, *links_args)
        data, linked = self._json(show), self._json(links)
        if not self._ok(show) or not self._ok(links) or not isinstance(data, dict) or not isinstance(linked, list):
            return PrResult(False, pull_request_id=pull_request_id, error="Could not query PR metadata")
        if data.get("title", "").strip() != expected_title.strip():
            updated = self._run(repository, "az", "repos", "pr", "update", "--id", identifier, "--org", organization_url, "--title", expected_title, "--output", "none")
            if not self._ok(updated): return PrResult(False, pull_request_id=pull_request_id, error=updated.stderr.strip())
        if data.get("description", "").strip() != expected_description.strip():
            updated = self._run(repository, "az", "repos", "pr", "update", "--id", identifier, "--org", organization_url, "--description", expected_description, "--output", "none")
            if not self._ok(updated): return PrResult(False, pull_request_id=pull_request_id, error=updated.stderr.strip())
        present = {str(item.get("id")) for item in linked if isinstance(item, dict) and item.get("id") is not None}
        missing = [item for item in expected_work_item_ids if item not in present]
        if missing:
            added = self._run(repository, "az", "repos", "pr", "work-item", "add", "--id", identifier, "--org", organization_url, "--work-items", *missing, "--output", "none")
            if not self._ok(added): return PrResult(False, pull_request_id=pull_request_id, error=added.stderr.strip())
        # Mutations succeeded; a second read is the only trustworthy confirmation.
        final_show, final_links = self._run(repository, *show_args), self._run(repository, *links_args)
        final_data, final_linked = self._json(final_show), self._json(final_links)
        final_ids = {str(item.get("id")) for item in final_linked} if isinstance(final_linked, list) else set()
        valid = (self._ok(final_show) and self._ok(final_links) and isinstance(final_data, dict)
                 and isinstance(final_linked, list)
                 and final_data.get("title", "").strip() == expected_title.strip()
                 and final_data.get("description", "").strip() == expected_description.strip()
                 and final_ids == set(expected_work_item_ids))
        return PrResult(valid, pull_request_id=pull_request_id, error="" if valid else "PR metadata repair verification failed")

    def auto_merge(self, repository: Path, pull_request_id: int, organization_url: str, target_branch: str,
                   source_branch: str) -> PrResult:
        shown = self._run(repository, "az", "repos", "pr", "show", "--id", str(pull_request_id), "--org", organization_url, "--output", "json")
        data = self._json(shown)
        status = data.get("mergeStatus") if isinstance(data, dict) else None
        if not self._ok(shown) or status in {"conflicts", "failure"}:
            return PrResult(False, pull_request_id=pull_request_id, error=f"PR auto-merge unavailable: {status or 'unknown'}")
        return PrResult(True, pull_request_id=pull_request_id)

    def auto_merge_and_sync(self, repository: Path, pull_request_id: int, organization_url: str, target_branch: str) -> PrResult:
        initial = self.auto_merge(repository, pull_request_id, organization_url, target_branch, "")
        if not initial.ok: return initial
        requested = self._run(repository, "az", "repos", "pr", "update", "--id", str(pull_request_id), "--org", organization_url, "--auto-complete", "true", "--output", "none")
        if not self._ok(requested): return PrResult(False, pull_request_id=pull_request_id, error=requested.stderr.strip())
        completed = self._run(repository, "az", "repos", "pr", "show", "--id", str(pull_request_id), "--org", organization_url, "--output", "json")
        data = self._json(completed)
        if not self._ok(completed) or not isinstance(data, dict) or data.get("status") != "completed":
            return PrResult(False, pull_request_id=pull_request_id, error="PR auto-merge did not complete")
        return self.sync_and_cleanup(repository, target_branch, "", confirmed_cleanup=False)

    def sync_and_cleanup(self, repository: Path, target_branch: str, source_branch: str, *, confirmed_cleanup: bool) -> PrResult:
        checkout = self._run(repository, "checkout", target_branch)
        if not self._ok(checkout): return PrResult(False, error="Target synchronization failed")
        pulled = self._run(repository, "pull", "origin", target_branch)
        if not self._ok(pulled): return PrResult(False, error="Target synchronization failed")
        if not confirmed_cleanup:
            return PrResult(True, cleanup_refused=True)
        local = self._run(repository, "branch", "-D", source_branch)
        if not self._ok(local): return PrResult(False, error=local.stderr.strip() or "Source branch cleanup failed")
        remote = self._run(repository, "push", "origin", "--delete", source_branch)
        if not self._ok(remote): return PrResult(False, error=remote.stderr.strip() or "Source branch cleanup failed")
        return PrResult(True, cleanup_complete=True)
