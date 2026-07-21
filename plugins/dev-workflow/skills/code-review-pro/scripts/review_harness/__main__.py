"""Package command dispatcher for the shared review harness."""
from __future__ import annotations

import argparse
from collections.abc import Callable
import sys

from . import claude_statusline_bridge, claude_statusline_setup, runtime_preflight, scope_manifest, test_gate


COMMANDS: dict[str, Callable[[list[str] | None], int]] = {
    "runtime-preflight": runtime_preflight.main,
    "scope-manifest": scope_manifest.main,
    "discover-tests": test_gate.discover_tests_main,
    "test-gate": test_gate.main,
    "statusline-bridge": claude_statusline_bridge.main,
    "statusline-setup": claude_statusline_setup.main,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Shared code-review harness commands.")
    parser.add_argument("command", choices=COMMANDS)
    arguments = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(arguments[:1])
    return COMMANDS[args.command](arguments[1:])


if __name__ == "__main__":
    raise SystemExit(main())
