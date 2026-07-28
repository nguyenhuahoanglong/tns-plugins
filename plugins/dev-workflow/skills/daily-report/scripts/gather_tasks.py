"""Render active Azure DevOps tasks for the daily report."""
import argparse
import json

from ado_client import gather_current_tasks
from lib_common import load_config


class PortableConfigurationError(ValueError):
    """Configuration failure that remains compatible with the command-line API."""


def normalize_exported_items(items, active_states):
    """Normalize captured task records without performing any external work."""
    states = {state.lower() for state in active_states}
    tasks, skipped = [], []
    for item in items if isinstance(items, list) else [items]:
        record = {
            "id": item.get("Id"), "title": (item.get("Title") or "").strip(),
            "state": item.get("State"), "project": item.get("ProjectName"),
            "type": item.get("WorkItemType"),
        }
        (tasks if (record["state"] or "").lower() in states else skipped).append(record)
    tasks.sort(key=lambda record: record["id"] or 0, reverse=True)
    return tasks, skipped


def gather(config, *, runner=None):
    if "organization" not in config["ado"]:
        raise PortableConfigurationError("portable ADO configuration requires organization")
    result = gather_current_tasks(config, runner=runner)
    return result["tasks"], result["skipped"]


def format_bullets(tasks):
    return "\n".join(f"- #{task['id']} {task['title']}" for task in tasks)


def format_gather_output(result):
    tasks = result["tasks"]
    skipped = result["skipped"]
    lines = ["=== ACTIVE TASKS (in-progress) ===", format_bullets(tasks) if tasks else "(none found in active states)"]
    if skipped:
        states = ", ".join(sorted({record["state"] for record in skipped}))
        lines.extend(["", f"=== SKIPPED (other states: {states}) ==="])
        lines.extend(f"- #{record['id']} {record['title']}  [{record['state']}]" for record in skipped)
    lines.extend(["", "=== TASKS_JSON ===", json.dumps(result, ensure_ascii=False, separators=(",", ":"))])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()
    result = gather_current_tasks(load_config(args.config))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_gather_output(result), end="")


if __name__ == "__main__":
    main()
