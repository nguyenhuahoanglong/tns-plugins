"""Spec-first production allowlist regressions for DoD-1.5.

Source: .plans/code-review-runtime-scope-test-harness.md, Task 1 live-contract audit.
"""

from __future__ import annotations

import pytest

from review_harness.scope_manifest import classify_file


@pytest.mark.parametrize(
    "path",
    [
        ".codex/config.toml",
        "package.json",
        "pnpm-lock.yaml",
        "api/openapi.schema.json",
        "database/schema.xsd",
        "artifacts/review-input.opaque",
    ],
)
def test_tc_027_does_not_allow_findings_on_non_code_artifacts(path: str) -> None:
    """TC-027 / DoD-1.5: config, manifests, locks, schemas, and unknown types are not production.

    Steps:
      1. Supply a changed non-code artifact.
      2. Classify it for review scope.
      3. Verify it is not added to the production findings allowlist.
    """
    # Arrange / Act
    bucket, _ = classify_file(path)

    # Assert
    assert bucket != "production"


@pytest.mark.parametrize(
    "path",
    [
        "src/OrderService.cs",
        "src/order-service.ts",
        "src/OrderView.tsx",
        "src/order-service.js",
        "src/order_service.py",
        "scripts/Invoke-Review.ps1",
        "database/Release_1.0.sql",
    ],
)
def test_tc_028_allows_findings_on_supported_production_code(path: str) -> None:
    """TC-028 / DoD-1.5: supported executable source files remain production scope.

    Steps:
      1. Supply a supported production source path.
      2. Classify it for review scope.
      3. Verify it is allowed as production code.
    """
    # Arrange / Act / Assert
    assert classify_file(path) == ("production", "production_code")


@pytest.mark.parametrize("path", ["tests/OrderServiceTests.cs", "src/order.test.ts", "docs/runtime-policy.md"])
def test_tc_029_keeps_tests_and_documents_as_evidence(path: str) -> None:
    """TC-029 / DoD-1.5: tests and documents remain evidence-only.

    Steps:
      1. Supply a changed test or documentation path.
      2. Classify it for review scope.
      3. Verify it is evidence and cannot receive a finding.
    """
    # Arrange / Act
    bucket, _ = classify_file(path)

    # Assert
    assert bucket == "evidence"


def test_tc_030_classifies_harness_test_named_production_module_by_its_directory() -> None:
    """TC-030 / DoD-1.5: harness implementation names do not override directory scope.

    Steps:
      1. Classify the production harness module named test_gate.py.
      2. Classify the similarly named file inside the tests directory.
      3. Verify only the directory-scoped test file is evidence.
    """
    # Act / Assert
    assert classify_file("scripts/review_harness/test_gate.py") == ("production", "production_code")
    assert classify_file("scripts/review_harness/tests/test_gate.py") == ("evidence", "test_file")
