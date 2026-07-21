#!/usr/bin/env python3
"""Discover and execute deterministic unit-test evidence."""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

def _declaration(content: str, suffix: str, active_class: str | None) -> tuple[str | None, str | None]:
    """Return (class name, callable symbol) only for declaration-shaped text."""
    class_match=re.match(r"\s*(?:(?:export|public|private|protected|internal|abstract|sealed|static|partial|default)\s+)*class\s+([A-Za-z_$]\w*)",content)
    if class_match: return class_match.group(1),None
    stripped=content.strip()
    if suffix==".py":
        match=re.match(r"\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(",content)
        method=bool(content[:len(content)-len(content.lstrip())])
    elif suffix==".ps1":
        match=re.match(r"\s*function\s+([A-Za-z_]\w*(?:-[A-Za-z_]\w*)*)",content,re.I);method=False
    elif suffix==".cs":
        if re.match(r"(?:return|if|for|foreach|while|switch|catch|using|throw|new)\b",stripped): return None,None
        match=re.match(r"\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|extern|new|partial)\s+)*(?:[A-Za-z_]\w*(?:[.<>,\[\]?]\w*)*\s+)+([A-Za-z_]\w*)\s*(?:<[^>]+>)?\s*\(",content)
        method=bool(active_class)
    else:
        if re.match(r"(?:if|for|while|switch|catch|return|throw|new|typeof)\b",stripped): return None,None
        match=re.match(r"\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$]\w*)\s*\(",content)
        if not match:
            match=re.match(r"\s*(?:(?:public|private|protected|static|async|abstract|override|get|set)\s+)*([A-Za-z_$]\w*)\s*(?:<[^>]+>)?\s*\(",content)
        if not match:
            match=re.match(r"\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$]\w*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$]\w*)\s*=>",content)
        method=bool(active_class)
    if not match: return None,None
    name=match.group(1)
    return None,f"{active_class}.{name}" if method and active_class else name

def extract_changed_symbols(diff_text: str, source_path: str) -> list[str]:
    """Extract changed declarations, including enclosing unified-diff hunk context."""
    symbols: list[str]=[];active_class: str|None=None;enclosing: str|None=None;suffix=Path(source_path).suffix.lower()
    def add(symbol: str | None) -> None:
        if symbol and symbol not in symbols: symbols.append(symbol)
    for line in diff_text.splitlines():
        if line.startswith("@@"):
            active_class=None;enclosing=None
            context=line.split("@@",2)[-1].strip()
            class_name,symbol=_declaration(context,suffix,active_class)
            if class_name: active_class=class_name
            if symbol: enclosing=symbol
            continue
        if line.startswith(("diff --git","index ","---","+++")) or not line: continue
        prefix=line[0]
        if prefix not in {"+"," ","-"}: continue
        content=line[1:]
        if prefix!="-":
            class_name,symbol=_declaration(content,suffix,active_class)
            if class_name:
                active_class=class_name;enclosing=None
            elif symbol:
                enclosing=symbol
                if prefix=="+": add(symbol)
        if prefix=="+" and not symbol and not class_name: add(enclosing)
    return symbols

def discover_tests(repo: Path, production_files: Iterable[str], changed_symbols: Iterable[str]) -> dict[str, Any]:
    symbols = list(changed_symbols); test_paths = sorted(path for path in repo.rglob("*") if path.is_file() and (any(part.lower().endswith(".tests") for part in path.parts) or "__tests__" in {part.lower() for part in path.parts} or ".test." in path.name.lower() or ".spec." in path.name.lower() or path.name.lower().startswith("test_") or "test" in path.name.lower()))
    direct: list[str] = []; affected: list[str] = []
    source_stems = {Path(path).stem.lower() for path in production_files}
    for test in test_paths:
        try: text = test.read_text(encoding="utf-8", errors="ignore")
        except OSError: continue
        relative = str(test.relative_to(repo))
        if any(symbol.split(".")[-1] in text for symbol in symbols): direct.append(relative)
        elif any(stem in test.stem.lower() or stem in text.lower() for stem in source_stems): affected.append(relative)
    if symbols and not direct:
        return {"status": "advisory", "advisory": "use-unit-testing", "directTests": [], "affectedTests": affected, "changedSymbols": symbols}
    return {"status": "pass", "advisory": None, "directTests": direct, "affectedTests": affected, "changedSymbols": symbols}

def _counts(output: str) -> dict[str, int]:
    dotnet={key.lower():int(value) for key,value in re.findall(r"\b(Failed|Passed|Skipped)\s*:\s*(\d+)\b",output,re.I)}
    if dotnet: return {key:dotnet.get(key,0) for key in ("passed","failed","skipped")}
    ran=re.search(r"\bRan\s+(\d+)\s+tests?\b",output,re.I)
    if ran:
        total=int(ran.group(1));failed_summary=re.search(r"\bFAILED\s*\(([^)]*)\)",output,re.I);ok_summary=re.search(r"\bOK\s*(?:\(([^)]*)\))?",output,re.I)
        details=(failed_summary or ok_summary).group(1) if failed_summary or ok_summary else ""
        fields={key.lower():int(value) for key,value in re.findall(r"\b(failures|errors|skipped)\s*=\s*(\d+)\b",details or "",re.I)}
        failed=fields.get("failures",0)+fields.get("errors",0);skipped=fields.get("skipped",0)
        return {"passed":max(total-failed-skipped,0),"failed":failed,"skipped":skipped}
    values={}
    for key in ("passed","failed","skipped"):
        matches=re.findall(r"\b(\d+)\s+"+key+r"\b",output,re.I);values[key]=int(matches[-1]) if matches else 0
    return values

def run_test_command(command: list[str], cwd: Path, *, timeout_seconds: int = 600, log_limit: int = 12000) -> dict[str, Any]:
    started = time.monotonic();timed_out=False
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or ""); stderr = (error.stderr or "") + "\ncommand timed out"; code = 124;timed_out=True
    if isinstance(stdout, bytes): stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes): stderr = stderr.decode(errors="replace")
    return {"status": "timeout" if timed_out else "pass" if code == 0 else "fail", "command": command, "exitCode": code, "durationMs": int((time.monotonic()-started)*1000), "counts": _counts(stdout + "\n" + stderr), "stdout": stdout[:log_limit], "stderr": stderr[:log_limit], "logsTruncated": len(stdout) > log_limit or len(stderr) > log_limit}

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

def discover_tests_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover direct and affected tests for changed production code.")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--production-file", action="append", required=True)
    parser.add_argument("--symbol", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = discover_tests(args.repo, args.production_file, args.symbol)
    if args.output:
        _write_json_atomically(args.output, result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"pass", "advisory"} else 2

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a unit-test command and emit deterministic evidence.")
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--output", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command: parser.error("command is required after --")
    result = run_test_command(command, args.cwd, timeout_seconds=args.timeout_seconds)
    if args.output:
        _write_json_atomically(args.output, result)
    print(json.dumps(result, sort_keys=True)); return 0 if result["status"] == "pass" else 2
if __name__ == "__main__": raise SystemExit(main())
