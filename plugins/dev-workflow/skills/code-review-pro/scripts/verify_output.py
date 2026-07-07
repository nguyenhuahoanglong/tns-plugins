#!/usr/bin/env python3
"""Verify code-review-pro v2 report and sidecar provenance."""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL = "code-review-pro v2.1.2"
PROFILES = {"Docs-only", "Tiny", "Pro"}
BRANCH_GATE_FIELDS = {
    "Status", "Branch", "Prefix", "Work Item ID", "Expected Type",
    "Actual Type", "Title", "State", "Source", "Reason",
}
BRANCH_GATE_SIDE_FIELDS = {
    "status", "branch", "prefix", "workItemId", "expectedType",
    "actualType", "title", "state", "source", "reason",
}


def field(text, name):
    matches = re.findall(rf"^\*\*{re.escape(name)}\*\*: (.+)$", text, re.MULTILINE)
    if len(matches) != 1:
        return None, f"{name} field appears {len(matches)} times"
    return matches[0].strip(), None


def add(results, ok, message):
    results.append(("PASS" if ok else "FAIL", message))


def records(value):
    if not value or value == "None":
        return []
    return [item.strip() for item in value.split(" | ") if item.strip()]


def bullet(text, name):
    match = re.search(
        rf"^- \*\*{re.escape(name)}\*\*: (.+)$",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else None


def section_bullets(text, heading):
    match = re.search(
        rf"^{re.escape(heading)}\s*(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        return {}
    return {
        name: value.strip()
        for name, value in re.findall(
            r"^- \*\*([^*]+)\*\*: (.+)$",
            match.group(1),
            re.MULTILINE,
        )
    }


def infer_sidecar(report):
    return report.with_name(f".{report.stem}.review-meta.json")


def evaluate(report_path, sidecar_path=None, expected_main_runtime=None):
    results = []
    report = Path(report_path)
    add(results, report.is_file(), f"report exists: {report}")
    if not report.is_file():
        return results

    text = report.read_text(encoding="utf-8")
    values = {}
    for name in ("Skill", "Review Profile", "Main Runtime", "Agents Triggered", "Agents Skipped"):
        value, error = field(text, name)
        add(results, error is None, error or f"{name} field appears exactly once")
        values[name] = value

    add(results, values["Skill"] == SKILL, f"Skill is {SKILL}")
    add(results, values["Review Profile"] in PROFILES, "Review Profile is valid")
    add(results, bool(re.fullmatch(r".+ / .+", values["Main Runtime"] or "")),
        "Main Runtime exposes model and effort or marks them not exposed")
    if expected_main_runtime:
        add(results, values["Main Runtime"] == expected_main_runtime,
            f"Main Runtime matches expected launch runtime: {expected_main_runtime}")
    add(results, bool(values["Agents Triggered"]), "Agents Triggered is populated")
    add(results, bool(values["Agents Skipped"]), "Agents Skipped is populated")
    for heading in (
        "## Review Classification",
        "## Branch Work Item Gate",
        "## Build Status",
        "## Requirement Validation",
        "## Summary",
        "## Detailed Findings",
    ):
        add(results, heading in text, f"{heading} section exists")

    sidecar = Path(sidecar_path) if sidecar_path else infer_sidecar(report)
    add(results, sidecar.is_file(), f"sidecar exists: {sidecar}")
    if not sidecar.is_file():
        return results

    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        add(results, isinstance(data, dict), "sidecar is a JSON object")
    except (OSError, json.JSONDecodeError) as exc:
        add(results, False, f"sidecar parses: {exc}")
        return results

    add(results, data.get("recordVersion") == 2, "recordVersion is 2")
    add(results, data.get("skillName") == "code-review-pro", "skillName is code-review-pro")
    add(results, data.get("skillVersion") == "2.1.2", "skillVersion is 2.1.2")
    add(results, data.get("reviewProfile") == values["Review Profile"],
        "reviewProfile matches report")
    required_sidecar = {
        "reviewKind", "classifier", "branchWorkItemGate", "runtime", "triggered", "skipped",
        "reposReviewed", "requirementMode", "reviewedCommit", "targetBranch",
        "workItemId", "scopeType", "scopeBase", "diffFingerprint",
        "standardsPaths", "exemplarMap", "reviewedFiles",
        "iteration", "reviewedAt",
        "prOnlyMode", "prMergePreview", "mergePreviewStrategy", "jsDepsStrategy",
    }
    add(results, required_sidecar <= set(data), "sidecar contains v2 follow-up fields")
    add(results, isinstance(data.get("reviewedCommit"), str) and bool(data["reviewedCommit"]),
        "reviewedCommit is populated")
    add(results, isinstance(data.get("targetBranch"), str) and bool(data["targetBranch"]),
        "targetBranch is populated")
    add(results, data.get("workItemId") is None or isinstance(data.get("workItemId"), int),
        "workItemId is integer or null")
    add(results, data.get("scopeType") in {"pr", "branch", "staged", "working", "files"},
        "scopeType is valid")
    add(results, isinstance(data.get("scopeBase"), str) and bool(data["scopeBase"]),
        "scopeBase is populated")
    add(results, isinstance(data.get("diffFingerprint"), str)
        and data["diffFingerprint"].startswith("sha256:")
        and len(data["diffFingerprint"]) > len("sha256:"),
        "diffFingerprint is populated SHA-256")
    # v2.1.0 — new sidecar fields
    scope_type = data.get("scopeType")
    pr_only_mode = data.get("prOnlyMode")
    merge_preview_strategy = data.get("mergePreviewStrategy")
    js_deps_strategy = data.get("jsDepsStrategy")

    valid_merge_preview = {"server-merge", "local-merge", "source-head"}
    valid_js_deps = {"link", "skip", "mixed", "none"}

    if scope_type == "pr":
        add(results,
            merge_preview_strategy in valid_merge_preview,
            "mergePreviewStrategy is valid for pr scope (server-merge, local-merge, source-head)")

    if pr_only_mode:
        add(results, scope_type == "pr",
            "PR-only mode requires pr scopeType")

    if js_deps_strategy is not None:
        add(results,
            js_deps_strategy in valid_js_deps,
            "jsDepsStrategy is valid (link, skip, mixed, none)")

    if js_deps_strategy in {"skip", "mixed"}:
        build_section = re.search(
            r"^## Build Status\s*(.*?)(?=^## |\Z)",
            text,
            re.MULTILINE | re.DOTALL,
        )
        has_js_skipped_row = bool(
            build_section and re.search(
                r"^\|\s*`[^`]+`\s*\|\s*JS-SKIPPED\s*\|",
                build_section.group(1),
                re.MULTILINE,
            )
        )
        add(results, has_js_skipped_row,
            "Build Status table contains JS-SKIPPED row when jsDepsStrategy is skip/mixed")

    review_profile = values.get("Review Profile")
    if review_profile == "Pro":
        scope_drift_section = re.search(r"### Scope Drift", text)
        scope_drift_bullet = re.search(
            r"^- \*\*Scope Drift\*\*:", text, re.MULTILINE
        )
        add(results, bool(scope_drift_section or scope_drift_bullet),
            "Pro report contains Scope Drift marker (### Scope Drift heading or - **Scope Drift**: bullet)")

    add(results, isinstance(data.get("standardsPaths"), list), "standardsPaths is a list")
    add(results, isinstance(data.get("exemplarMap"), dict), "exemplarMap is an object")
    add(results, isinstance(data.get("reviewedFiles"), list), "reviewedFiles is a list")
    add(results, isinstance(data.get("reviewedAt"), str) and bool(data["reviewedAt"]),
        "reviewedAt is populated")

    runtime = data.get("runtime", {})
    add(results, isinstance(runtime, dict)
        and {"main", "build", "requirement", "specialists"} <= set(runtime)
        and all(isinstance(value, str) and value for value in runtime.values()),
        "sidecar runtime contains populated v2 roles")
    add(results, isinstance(runtime, dict) and runtime.get("main") == values["Main Runtime"],
        "sidecar runtime.main matches report Main Runtime")
    triggered = data.get("triggered")
    skipped = data.get("skipped")
    add(results, isinstance(triggered, list), "sidecar triggered is a list")
    add(results, isinstance(skipped, list), "sidecar skipped is a list")
    if isinstance(triggered, list):
        add(results, triggered == records(values["Agents Triggered"]),
            "Triggered report records match sidecar")
    if isinstance(skipped, list):
        add(results, skipped == records(values["Agents Skipped"]),
            "Skipped report records match sidecar")

    gate_report = section_bullets(text, "## Branch Work Item Gate")
    add(results, BRANCH_GATE_FIELDS <= set(gate_report),
        "Branch Work Item Gate reports required fields")
    gate = data.get("branchWorkItemGate")
    add(results, isinstance(gate, dict) and BRANCH_GATE_SIDE_FIELDS <= set(gate),
        "sidecar branchWorkItemGate contains required fields")
    if isinstance(gate, dict) and BRANCH_GATE_SIDE_FIELDS <= set(gate):
        status = gate.get("status")
        add(results, status in {"PASS", "WARN", "FAIL", "SKIPPED"},
            "Branch Work Item Gate status is valid")
        mapping = {
            "Status": "status",
            "Branch": "branch",
            "Prefix": "prefix",
            "Work Item ID": "workItemId",
            "Expected Type": "expectedType",
            "Actual Type": "actualType",
            "Title": "title",
            "State": "state",
            "Source": "source",
            "Reason": "reason",
        }
        add(results, all(str(gate_report.get(label)) == str(gate.get(key))
                         for label, key in mapping.items()),
            "Branch Work Item Gate report fields match sidecar")
        triggered_records = triggered if isinstance(triggered, list) else []
        skipped_records = skipped if isinstance(skipped, list) else []
        build_runtime = runtime.get("build") if isinstance(runtime, dict) else None
        branch_trigger = f"Branch Work Item Gate({build_runtime}; branch work item convention)"
        branch_triggered = branch_trigger in triggered_records
        branch_skipped = any(item.startswith("Branch Work Item Gate(")
                             for item in skipped_records)
        if status in {"PASS", "WARN", "FAIL"}:
            add(results, branch_triggered,
                "Branch Work Item Gate uses Build Validator runtime when triggered")
            add(results, not branch_skipped,
                "Triggered Branch Work Item Gate is not also skipped")
        elif status == "SKIPPED":
            add(results, branch_skipped and not branch_triggered,
                "Skipped Branch Work Item Gate is recorded only in skipped actors")

    classifier = data.get("classifier", {})
    required = {"filesChanged", "changedLines", "docsOnly", "riskTriggers", "specialistTriggers"}
    add(results, isinstance(classifier, dict) and required <= set(classifier),
        "classifier contains required fields")
    if isinstance(classifier, dict) and required <= set(classifier):
        profile = values["Review Profile"]
        risks = classifier["riskTriggers"]
        types_valid = (
            isinstance(classifier["filesChanged"], int)
            and isinstance(classifier["changedLines"], int)
            and isinstance(classifier["docsOnly"], bool)
            and isinstance(risks, list)
            and isinstance(classifier["specialistTriggers"], dict)
        )
        add(results, types_valid, "classifier field types are valid")
        if not types_valid:
            return results

        report_files = bullet(text, "Files Changed")
        report_lines = bullet(text, "Changed Lines")
        report_docs = bullet(text, "Docs Only")
        report_risks = bullet(text, "Risk Triggers")
        report_specialists = bullet(text, "Specialist Triggers")
        add(results, report_files is not None and report_files.isdigit()
            and int(report_files) == classifier["filesChanged"],
            "report Files Changed matches sidecar classifier")
        add(results, report_lines is not None and report_lines.isdigit()
            and int(report_lines) == classifier["changedLines"],
            "report Changed Lines matches sidecar classifier")
        add(results, report_docs in {"true", "false"}
            and (report_docs == "true") == classifier["docsOnly"],
            "report Docs Only matches sidecar classifier")
        parsed_risks = [] if report_risks == "None" else records(report_risks)
        add(results, parsed_risks == risks,
            "report Risk Triggers match sidecar classifier")
        parsed_specialists = {}
        if report_specialists and report_specialists != "None":
            for item in records(report_specialists):
                if "=" in item:
                    reviewer, trigger = item.split("=", 1)
                    parsed_specialists.setdefault(reviewer, []).append(trigger)
        add(results, parsed_specialists == classifier["specialistTriggers"],
            "report Specialist Triggers match sidecar classifier")

        repos = data.get("reposReviewed")
        add(results, isinstance(repos, list), "reposReviewed is a list")
        triggered_records = triggered if isinstance(triggered, list) else []
        skipped_records = skipped if isinstance(skipped, list) else []
        build_records = [
            item for item in triggered_records
            if re.fullmatch(
                r"Build Validator\[[^\]]+\]\(.+ / .+; .+\)",
                item,
            )
        ]
        specialists = ("Security", "Performance", "Philosophy", "Standard")
        if profile == "Docs-only":
            add(results, classifier["docsOnly"] is True and risks == [],
                "Docs-only records docsOnly=true and no runtime risk")
            docs_allowed = {
                "Main(docs-only inline)",
                f"Branch Work Item Gate({runtime.get('build')}; branch work item convention)",
            }
            add(results, "Main(docs-only inline)" in triggered_records
                and all(item in docs_allowed for item in triggered_records),
                "Docs-only triggers main inline review plus optional branch gate only")
            for actor in ("Build Validator", "Requirement Validator", *[
                f"{name} Reviewer" for name in specialists
            ]):
                add(results, any(item.startswith(actor) for item in skipped_records),
                    f"Docs-only explains skipped {actor}")
        elif profile == "Tiny":
            tiny = (
                classifier["docsOnly"] is False
                and classifier["filesChanged"] <= 3
                and classifier["changedLines"] <= 100
                and risks == []
            )
            add(results, tiny, "Tiny obeys thresholds and has no risk triggers")
            add(results, "Main(Tiny all-lens)" in triggered_records,
                "Tiny triggers main all-lens review")
            add(results, isinstance(repos, list) and repos and len(build_records) == len(repos),
                "Tiny triggers one Build Validator per repo")
            for actor in ("Requirement Validator", *[
                f"{name} Reviewer" for name in specialists
            ]):
                add(results, not any(item.startswith(actor) for item in triggered_records),
                    f"Tiny does not trigger {actor}")
                add(results, any(item.startswith(actor) for item in skipped_records),
                    f"Tiny explains skipped {actor}")
        elif profile == "Pro":
            pro_required = (
                classifier["docsOnly"] is False
                and (
                    classifier["filesChanged"] > 3
                    or classifier["changedLines"] > 100
                    or bool(risks)
                )
            )
            add(results, pro_required, "Pro is non-docs and fails Tiny eligibility")
            add(results, data.get("requirementMode") in {"work-item", "regression-only"},
                "Pro records required requirement mode")
            add(results, isinstance(repos, list) and repos and len(build_records) == len(repos),
                "Pro triggers one Build Validator per repo")
            expected_requirement = (
                f"Requirement Validator({runtime.get('requirement')}; "
                f"{data.get('requirementMode')})"
            )
            add(results, expected_requirement in triggered_records,
                "Pro triggers dedicated Requirement Validator")
            for name in specialists:
                actor = f"{name} Reviewer"
                actor_triggered = any(item.startswith(
                    f"{actor}({runtime.get('specialists')}; "
                ) for item in triggered_records)
                actor_skipped = any(item.startswith(actor) for item in skipped_records)
                add(results, actor_triggered != actor_skipped,
                    f"Pro records {actor} exactly once as triggered or skipped")
                expected = actor in classifier["specialistTriggers"]
                add(results, not actor_triggered or expected,
                    f"Pro does not trigger unclassified {actor}")
                add(results, expected or actor_skipped,
                    f"Pro skips untriggered {actor}")

    add(results, isinstance(data.get("iteration"), int) and data["iteration"] >= 1,
        "iteration is a positive integer")
    add(results, data.get("reviewKind") in {"initial", "follow-up"},
        "reviewKind is initial or follow-up")
    return results


def render(results, dry_run=False):
    heading = "=== OUTPUT CHECK: code-review-pro v2 ==="
    if dry_run:
        heading += " [DRY RUN]"
    lines = [heading]
    for level, message in results:
        lines.append(f"{level:<4}  {message}")
    failures = sum(level == "FAIL" for level, _ in results)
    passes = sum(level == "PASS" for level, _ in results)
    lines.extend(["", f"Result: {failures} FAIL, {passes} PASS"])
    return "\n".join(lines), failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", help="Path to .CodeReview report")
    parser.add_argument("--sidecar", help="Path to v2 review sidecar")
    parser.add_argument("--expected-main-runtime",
                        help="Exact launch runtime expected in report and sidecar, e.g. 'gpt-5.5 / xhigh'")
    parser.add_argument("--dry-run", action="store_true", help="Validate read-only and label output")
    args = parser.parse_args(argv)
    text, failures = render(
        evaluate(args.report, args.sidecar, args.expected_main_runtime),
        args.dry_run,
    )
    print(text)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
