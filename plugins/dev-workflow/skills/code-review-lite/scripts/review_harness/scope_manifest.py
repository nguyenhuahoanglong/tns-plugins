#!/usr/bin/env python3
"""Classify changed files into production review and evidence-only buckets."""
from __future__ import annotations
import argparse
import json
import os
import tempfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable

BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".dll", ".exe", ".woff", ".woff2", ".ttf", ".mp3", ".mp4"}
DOCUMENT_EXTENSIONS = {".md", ".rst", ".txt", ".docx", ".xlsx", ".pptx"}
GENERATED_FOLDERS = {"dist", "build", "coverage", ".next", "out", "bin", "obj"}
VENDOR_FOLDERS = {"vendor", "node_modules", "third_party", "third-party", "packages"}
PRODUCTION_EXTENSIONS = {".cs", ".ts", ".tsx", ".js", ".jsx", ".py", ".ps1", ".psm1", ".sql", ".java", ".go", ".rb", ".php", ".rs", ".c", ".h", ".cpp", ".hpp", ".swift", ".kt", ".kts", ".fs", ".fsx", ".vb"}

def classify_file(path: str) -> tuple[str, str]:
    normalized = path.replace("\\", "/").lstrip("./")
    item = PurePosixPath(normalized); parts = {part.lower() for part in item.parts}; suffix = item.suffix.lower(); name = item.name.lower()
    is_harness_test_gate = len(item.parts) >= 2 and item.parts[-2].lower() == "review_harness" and name == "test_gate.py"
    if suffix in BINARY_EXTENSIONS: return "excluded", "binary_file"
    if parts & VENDOR_FOLDERS: return "excluded", "vendor_code"
    if parts & GENERATED_FOLDERS or name.endswith((".min.js", ".generated.cs", ".g.cs", ".designer.cs")): return "excluded", "generated_output"
    if suffix in DOCUMENT_EXTENSIONS or "docs" in parts: return "evidence", "documentation"
    if not is_harness_test_gate and ("tests" in parts or "test" in parts or name.startswith("test_") or name.endswith(("_test.py", ".test.ts", ".spec.ts", ".spec.tsx", ".test.js"))): return "evidence", "test_file"
    if suffix in PRODUCTION_EXTENSIONS: return "production", "production_code"
    return "evidence", "non_code_artifact"

def build_scope_manifest(paths: Iterable[str]) -> dict[str, Any]:
    classified = []
    for path in paths:
        bucket, reason = classify_file(path); classified.append({"path": path.replace("\\", "/"), "classification": bucket, "reasonCode": reason})
    production = [item["path"] for item in classified if item["classification"] == "production"]
    evidence = [item["path"] for item in classified if item["classification"] == "evidence"]
    excluded = [item["path"] for item in classified if item["classification"] == "excluded"]
    return {"status": "pass" if production else "no-production-code", "files": classified, "productionFiles": production, "evidenceFiles": evidence, "excludedFiles": excluded}

def _write_json_atomically(output_path: Path, value: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output_path.stem}-", suffix=".tmp", dir=str(output_path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(temporary_name).replace(output_path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a production-only review scope manifest.")
    parser.add_argument("--output", type=Path)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args(argv)
    result = build_scope_manifest(args.paths)
    if args.output:
        _write_json_atomically(args.output, result)
    print(json.dumps(result, sort_keys=True)); return 0
if __name__ == "__main__": raise SystemExit(main())
