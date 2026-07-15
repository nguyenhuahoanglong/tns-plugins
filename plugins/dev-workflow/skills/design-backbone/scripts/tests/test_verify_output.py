#!/usr/bin/env python3
"""Tests for design-backbone output verifier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_output as vo  # noqa: E402


DESIGN = """# Order Backbone

## Requirements

| Requirement ID | Requirement | Required Coverage |
|---|---|---|
| REQ-1 | Complete order workflow | happy |

## Existing Flow

`Worker.Run` calls `OrderWorkflow.Execute`, which owns orchestration and emits final result.

## Touchpoint Matrix

| Requirement IDs | Path | Symbol | Action | Justification |
|---|---|---|---|---|
| REQ-1 | src/Workflow.cs | Execute | modify | Existing production workflow owner and caller seam. |

## Runtime Readiness

| Concern | Decision | Verification | Evidence Path | Evidence Symbol |
|---|---|---|---|---|
| entrypoint | Use existing worker entrypoint | Run local worker smoke test | src/Workflow.cs | EntryPoint |
| dependency wiring | Register provider through existing composition root | Resolve service graph test | src/Workflow.cs | ConfigureDependencies |
| local mock | Explicit local-only deterministic provider | Assert local provider selected | src/Workflow.cs | CreateLocalMock |
| production isolation | Production startup rejects mock registration | Assert startup rejection | src/Workflow.cs | RejectProductionMock |
| end-to-end workflow | Run through final order result | Assert final result emitted | src/Workflow.cs | Execute |

## Testing Decision

| Decision | Rationale | Verification |
|---|---|---|
| selected | User requested spec-first tests | Run readiness and completion suites |

## Test Coverage Matrix

| Requirement ID | Test Path | Test Name | Category | Initial State | Coverage |
|---|---|---|---|---|---|
| READINESS | tests/WorkflowTests.cs | LocalWorkflowRuns | readiness | green | happy |
| REQ-1 | tests/WorkflowTests.cs | CompletesOrder | completion | red | happy |
"""

SKIPPED_DESIGN = DESIGN.replace(
    "| selected | User requested spec-first tests | Run readiness and completion suites |",
    "| skipped | User chose build and local workflow verification | Build and run local happy path |",
).split("\n## Test Coverage Matrix", 1)[0] + "\n"


CS_SOURCE = """public sealed class OrderWorkflow {
 public void EntryPoint() { }
 public void ConfigureDependencies() { }
 public void CreateLocalMock() { }
 public void RejectProductionMock() { }
 public void Execute() { }
}
"""

CS_TEST = """public sealed class WorkflowTests {
 public void EntryPointRuns() { }
 public void ServiceGraphResolves() { }
 public void LocalProviderSelected() { }
 public void ProductionRejectsMocks() { }
 public void LocalWorkflowRuns() { }
 public void CompletesOrder() { }
}
"""

TS_SOURCE = "\n".join(f"export function {name}() {{}}" for name in (
    "EntryPoint", "ConfigureDependencies", "CreateLocalMock", "RejectProductionMock", "Execute"
))
TS_TEST = "\n".join(f'test("{name}", () => {{}});' for name in (
    "EntryPointRuns", "ServiceGraphResolves", "LocalProviderSelected",
    "ProductionRejectsMocks", "LocalWorkflowRuns", "CompletesOrder"
))
PY_SOURCE = "\n".join(f"def {name}():\n    pass" for name in (
    "EntryPoint", "ConfigureDependencies", "CreateLocalMock", "RejectProductionMock", "Execute"
))
PY_TEST = "\n".join(f"def test_{name}():\n    pass" for name in (
    "EntryPointRuns", "ServiceGraphResolves", "LocalProviderSelected",
    "ProductionRejectsMocks", "LocalWorkflowRuns", "CompletesOrder"
))
JAVA_SOURCE = "class Workflow { " + " ".join(f"void {name}() {{}}" for name in (
    "EntryPoint", "ConfigureDependencies", "CreateLocalMock", "RejectProductionMock", "Execute"
)) + " }"
JAVA_TEST = "class WorkflowTest { " + " ".join(f"void {name}() {{}}" for name in (
    "EntryPointRuns", "ServiceGraphResolves", "LocalProviderSelected",
    "ProductionRejectsMocks", "LocalWorkflowRuns", "CompletesOrder"
)) + " }"


def _project(
    tmp_path: Path,
    runtime_rel: str = "src/Workflow.cs",
    test_rel: str = "tests/WorkflowTests.cs",
    source_content: str = CS_SOURCE,
    test_content: str = CS_TEST,
) -> tuple[Path, Path]:
    source = tmp_path / runtime_rel
    source.parent.mkdir(parents=True)
    source.write_text(source_content, encoding="utf-8")
    tests = tmp_path / test_rel
    tests.parent.mkdir(parents=True)
    tests.write_text(test_content, encoding="utf-8")
    design = tmp_path / "backbone.md"
    design.write_text(
        DESIGN.replace("src/Workflow.cs", runtime_rel).replace("tests/WorkflowTests.cs", test_rel),
        encoding="utf-8",
    )
    return tmp_path, design


def _failures(root: Path, design: Path) -> list[str]:
    return [message for level, message in vo.evaluate(root, design) if level == "FAIL"]


def test_valid_backbone_passes(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    assert _failures(root, design) == []


def test_skipped_tests_pass_without_matrix_or_test_files(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(SKIPPED_DESIGN, encoding="utf-8")
    (root / "tests" / "WorkflowTests.cs").unlink()
    assert _failures(root, design) == []


def test_selected_tests_require_test_matrix(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.split("\n## Test Coverage Matrix", 1)[0] + "\n", encoding="utf-8")
    assert any("selected testing requires" in failure for failure in _failures(root, design))


def test_skipped_tests_reject_test_matrix(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(
        DESIGN.replace(
            "| selected | User requested spec-first tests | Run readiness and completion suites |",
            "| skipped | User chose workflow verification | Build and run local happy path |",
        ),
        encoding="utf-8",
    )
    assert any("skipped testing must omit" in failure for failure in _failures(root, design))


def test_invalid_testing_decision_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| selected | User requested", "| optional | User requested"), encoding="utf-8")
    assert any("must be 'selected' or 'skipped'" in failure for failure in _failures(root, design))


@pytest.mark.parametrize(
    ("runtime_rel", "test_rel", "source_content", "test_content"),
    [
        ("src/Workflow.cs", "tests/WorkflowTests.cs", CS_SOURCE, CS_TEST),
        ("src/workflow.ts", "tests/workflow.test.ts", TS_SOURCE, TS_TEST),
        ("src/workflow.js", "tests/workflow.spec.js", TS_SOURCE, TS_TEST),
        ("src/workflow.py", "tests/test_workflow.py", PY_SOURCE, PY_TEST),
        ("src/main/java/Workflow.java", "src/test/java/WorkflowTest.java", JAVA_SOURCE, JAVA_TEST),
    ],
)
def test_common_runtime_and_test_sources_pass(
    tmp_path: Path,
    runtime_rel: str,
    test_rel: str,
    source_content: str,
    test_content: str,
) -> None:
    root, design = _project(tmp_path, runtime_rel, test_rel, source_content, test_content)
    assert _failures(root, design) == []


def test_documentation_cannot_supply_runtime_or_test_evidence(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    evidence = root / "evidence.md"
    evidence.write_text(CS_SOURCE + CS_TEST, encoding="utf-8")
    design.write_text(
        design.read_text(encoding="utf-8")
        .replace("src/Workflow.cs", "evidence.md")
        .replace("tests/WorkflowTests.cs", "evidence.md"),
        encoding="utf-8",
    )
    failures = _failures(root, design)
    assert any("path is not eligible runtime source" in failure for failure in failures)
    assert any("evidence path must be eligible" in failure for failure in failures)
    assert any("path is not eligible test source" in failure for failure in failures)
    assert any("REQ-1: no runtime touchpoint" in failure for failure in failures)


def test_missing_required_section_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("## Existing Flow", "### Existing Flow"), encoding="utf-8")
    assert any("missing required" in failure for failure in _failures(root, design))


def test_invalid_touchpoint_action_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| modify |", "| create |"), encoding="utf-8")
    assert any("invalid action" in failure for failure in _failures(root, design))


def test_new_touchpoint_without_justification_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(
        DESIGN.replace("| modify | Existing production workflow owner and caller seam. |", "| new | TBD |"),
        encoding="utf-8",
    )
    assert any("justification is required" in failure for failure in _failures(root, design))


def test_missing_referenced_path_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("src/Workflow.cs", "src/Missing.cs"), encoding="utf-8")
    assert any("file does not exist" in failure for failure in _failures(root, design))


def test_touchpoint_unknown_requirement_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| REQ-1 | src/Workflow.cs", "| REQ-X | src/Workflow.cs"), encoding="utf-8")
    failures = _failures(root, design)
    assert any("unknown requirement id: REQ-X" in failure for failure in failures)
    assert any("REQ-1: no runtime touchpoint" in failure for failure in failures)


def test_requirement_without_runtime_touchpoint_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    updated = DESIGN.replace(
        "| REQ-1 | Complete order workflow | happy |",
        "| REQ-1 | Complete order workflow | happy |\n| REQ-2 | Audit order | happy |",
    ).replace(
        "| REQ-1 | tests/WorkflowTests.cs | CompletesOrder | completion | red | happy |",
        "| REQ-1 | tests/WorkflowTests.cs | CompletesOrder | completion | red | happy |\n"
        "| REQ-2 | tests/WorkflowTests.cs | CompletesOrder | completion | red | happy |",
    )
    design.write_text(updated, encoding="utf-8")
    assert any("REQ-2: no runtime touchpoint" in failure for failure in _failures(root, design))


def test_missing_touchpoint_symbol_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| Execute | modify |", "| MissingMethod | modify |"), encoding="utf-8")
    assert any("touchpoint src/Workflow.cs: symbol not found" in failure for failure in _failures(root, design))


def test_missing_readiness_evidence_path_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(
        design.read_text(encoding="utf-8").replace("| src/Workflow.cs | EntryPoint |", "| config/Missing.json | EntryPoint |", 1),
        encoding="utf-8",
    )
    assert any("runtime readiness 'entrypoint': file does not exist" in failure for failure in _failures(root, design))


def test_missing_readiness_evidence_symbol_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(design.read_text(encoding="utf-8").replace("| EntryPoint |", "| MissingEvidence |", 1), encoding="utf-8")
    assert any("evidence symbol not found: MissingEvidence" in failure for failure in _failures(root, design))


def test_missing_test_name_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| CompletesOrder | completion |", "| MissingCompletionTest | completion |"), encoding="utf-8")
    assert any("test name not found: MissingCompletionTest" in failure for failure in _failures(root, design))


def test_empty_runtime_and_test_classes_fail_traceability(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    (root / "src" / "Workflow.cs").write_text("public sealed class OrderWorkflow { }\n", encoding="utf-8")
    (root / "tests" / "WorkflowTests.cs").write_text("public sealed class WorkflowTests { }\n", encoding="utf-8")
    failures = _failures(root, design)
    assert any("touchpoint src/Workflow.cs: symbol not found" in failure for failure in failures)
    assert any("test name not found" in failure for failure in failures)


def test_unmapped_requirement_coverage_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("| REQ-1 | tests/WorkflowTests.cs", "| REQ-X | tests/WorkflowTests.cs"), encoding="utf-8")
    failures = _failures(root, design)
    assert any("unknown requirement" in failure for failure in failures)
    assert any("missing completion coverage" in failure for failure in failures)


def test_missing_test_category_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(
        DESIGN.replace("| READINESS | tests/WorkflowTests.cs | LocalWorkflowRuns | readiness | green | happy |\n", ""),
        encoding="utf-8",
    )
    assert any("no readiness tests" in failure for failure in _failures(root, design))


def test_local_mock_must_be_deterministic_and_local_only(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(DESIGN.replace("Explicit local-only deterministic provider", "Use a mock provider"), encoding="utf-8")
    assert any("deterministic and local-only" in failure for failure in _failures(root, design))


def test_runtime_placeholder_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    (root / "src" / "Workflow.cs").write_text(
        "public void Execute() { throw new NotImplementedException(); }\n", encoding="utf-8"
    )
    assert any("placeholder implementation" in failure for failure in _failures(root, design))


def test_skipped_test_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    (root / "tests" / "WorkflowTests.cs").write_text(
        '[Fact(Skip = "later")] public void LocalWorkflowRuns() { }\n', encoding="utf-8"
    )
    assert any("skip/inconclusive" in failure for failure in _failures(root, design))


def test_wrong_initial_test_state_fails(tmp_path: Path) -> None:
    root, design = _project(tmp_path)
    design.write_text(
        DESIGN.replace("| REQ-1 | tests/WorkflowTests.cs | CompletesOrder | completion | red |", "| REQ-1 | tests/WorkflowTests.cs | CompletesOrder | completion | green |"),
        encoding="utf-8",
    )
    assert any("completion test must start red" in failure for failure in _failures(root, design))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
