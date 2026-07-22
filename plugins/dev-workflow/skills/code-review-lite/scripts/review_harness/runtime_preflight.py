#!/usr/bin/env python3
"""Fail-closed runtime and session attestation for code reviews."""
from __future__ import annotations
import argparse, json, os, re, tempfile, time
from pathlib import Path
from typing import Any

POLICY_PATH = Path(__file__).with_name("runtime-policy.json")
EFFORTS = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4, "ultra": 5}
TIERS = {"codex": {"luna": 0, "terra": 1, "sol": 2}, "claude": {"haiku": 0, "sonnet": 1, "opus": 2}}
_TRANSCRIPT_PATH_KEY = "_transcriptPath"
def _blocked(reason: str, **values: Any) -> dict[str, Any]: return {"status": "blocked", "reasonCode": reason, **values}
def _load_policy(path: Path | None) -> dict[str, Any]: return json.loads((path or POLICY_PATH).read_text(encoding="utf-8"))
def parse_model_id(host: str, model_id: str) -> dict[str, Any]:
    host, raw = host.lower().strip(), model_id.strip()
    match = re.fullmatch(r"gpt-(\d+)\.(\d+)-([a-z]+)", raw.lower()) if host == "codex" else re.fullmatch(r"claude-([a-z]+)-(\d+)(?:[.-](\d+))?", raw.lower()) if host == "claude" else None
    generation = ([int(match.group(1)), int(match.group(2))] if host == "codex" else [int(match.group(2))] + ([int(match.group(3))] if match.group(3) else [])) if match else []
    return {"host": host, "modelId": model_id, "generation": generation, "tier": match.group(3 if host == "codex" else 1) if match else "unknown"}
def evaluate_runtime(host: str, model_id: str, effort: str, *, policy_path: Path | None = None) -> dict[str, Any]:
    if not host or not model_id or not effort: return _blocked("missing_runtime_evidence", host=host, modelId=model_id, effort=effort)
    host, effort = host.lower().strip(), effort.lower().strip(); policy = _load_policy(policy_path)
    if host not in policy: return _blocked("unknown_host", host=host, modelId=model_id, effort=effort)
    parsed = parse_model_id(host, model_id); tier = parsed["tier"]
    if not parsed["generation"]: return _blocked("unknown_model", host=host, modelId=model_id, effort=effort)
    if tier not in TIERS[host]: return _blocked("unknown_tier", host=host, modelId=model_id, effort=effort)
    if parsed["generation"] < policy[host]["minimumGeneration"]: return _blocked("generation_below_minimum", host=host, modelId=model_id, effort=effort)
    if TIERS[host][tier] < TIERS[host][policy[host]["minimumTier"]]: return _blocked("tier_below_minimum", host=host, modelId=model_id, effort=effort)
    if effort not in EFFORTS: return _blocked("unknown_effort", host=host, modelId=model_id, effort=effort)
    if EFFORTS[effort] < EFFORTS[policy["minimumEffort"]]: return _blocked("effort_below_minimum", host=host, modelId=model_id, effort=effort)
    recommended = TIERS[host][tier] >= TIERS[host][policy[host]["recommendedTier"]] and EFFORTS[effort] >= EFFORTS[policy["recommendedEffort"]]
    return {"status":"pass", "host":host, "modelId":model_id, "effort":effort, "generation":parsed["generation"], "tier":tier, "recommended": recommended, "recommendationMet": recommended}
def _records(root: Path, filename_hint: str | None = None) -> list[tuple[Path, list[dict[str, Any]]]]:
    output=[]
    paths = sorted(root.rglob(f"*{filename_hint}*.json*")) if root.exists() and filename_hint else []
    if not paths and root.exists():
        paths = sorted(root.rglob("*.json*"))
    for p in paths:
        try: output.append((p, [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.suffix == ".jsonl" else [json.loads(p.read_text(encoding="utf-8"))]))
        except (OSError, json.JSONDecodeError): pass
    return output
def _matching_codex_rollouts(thread_id: str, sessions_root: Path) -> list[tuple[Path, list[dict[str, Any]]]]:
    matches=[]
    for path, records in _records(sessions_root, thread_id):
        metas=[r for r in records if r.get("type") == "session_meta" and isinstance(r.get("payload"),dict) and r["payload"].get("id") == thread_id]
        legacy=[r for r in records if r.get("threadId", r.get("thread_id", r.get("sessionId", r.get("session_id")))) == thread_id]
        if metas or legacy: matches.append((path, records))
    return matches
def _codex_transcript_path(thread_id: str, sessions_root: Path) -> Path | None:
    matches=_matching_codex_rollouts(thread_id, sessions_root)
    if not matches: return None
    def latest_timestamp(item: tuple[Path, list[dict[str, Any]]]) -> str:
        _, records=item
        turns=[r for r in records if r.get("type") == "turn_context" and isinstance(r.get("payload"),dict)]
        return max((str(r.get("timestamp", "")) for r in turns or records), default="")
    return max(matches, key=latest_timestamp)[0]
def resolve_codex_runtime(thread_id: str, sessions_root: Path) -> dict[str, Any]:
    # Modern rollout JSONL is scoped by session_meta.payload.id; legacy records stay supported.
    candidates=[]
    for path, records in _matching_codex_rollouts(thread_id, sessions_root):
        metas=[r for r in records if r.get("type") == "session_meta" and isinstance(r.get("payload"),dict) and r["payload"].get("id") == thread_id]
        if metas:
            turns=[r for r in records if r.get("type") == "turn_context" and isinstance(r.get("payload"),dict)]
            if turns: candidates.extend((path, r) for r in turns)
        else:
            candidates.extend((path, r) for r in records if r.get("threadId", r.get("thread_id", r.get("sessionId", r.get("session_id")))) == thread_id)
    if not candidates: return _blocked("missing_runtime_evidence", host="codex", sessionId=thread_id, crossChecks=[])
    transcript_path, latest=max(candidates, key=lambda item: str(item[1].get("timestamp", "")))
    p=latest.get("payload", latest)
    coll=p.get("collaboration_mode", {}) if isinstance(p.get("collaboration_mode"),dict) else {}
    model, effort = p.get("model", p.get("modelId", p.get("model_id"))), p.get("effort", p.get("reasoningEffort", p.get("reasoning_effort")))
    coll_model, coll_effort = coll.get("model"), coll.get("reasoning_effort")
    if ((coll_model not in (None, "") and str(coll_model).lower() != str(model or "").lower())
            or (coll_effort not in (None, "") and str(coll_effort).lower() != str(effort or "").lower())):
        return _blocked("conflicting_runtime_evidence", host="codex", sessionId=thread_id, crossChecks=[])
    # Legacy duplicate field agreement is still fail closed.
    models={str(p[k]).lower() for k in ("modelId","model","model_id") if p.get(k) not in (None,"")}; efforts={str(p[k]).lower() for k in ("effort","reasoningEffort","reasoning_effort") if p.get(k) not in (None,"")}
    if len(models)>1 or len(efforts)>1: return _blocked("conflicting_runtime_evidence", host="codex", sessionId=thread_id, crossChecks=[])
    result=evaluate_runtime("codex", str(model or ""), str(effort or ""))
    trust={"trustLevel":"verified"} if result.get("status")=="pass" else {}
    return {**result,"sessionId":thread_id,"thinkingEnabled":p.get("thinkingEnabled"),"source":"codex-rollout","crossChecks":["threadId","latest-turn-context","duplicate-runtime-fields"],"freshness":"current",_TRANSCRIPT_PATH_KEY:str(transcript_path),**trust}
def _latest_assistant(path: Path) -> dict[str, Any] | None:
    try: records=[json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError): return None
    found=[r for r in records if r.get("type")=="assistant" or (isinstance(r.get("message"),dict) and r["message"].get("role")=="assistant")]
    return found[-1] if found else None
def resolve_claude_runtime(attestation_root: Path, cwd: Path, *, max_age_seconds: int = 120) -> dict[str, Any]:
    files=[p for p in attestation_root.glob("*.json") if p.is_file()]
    if not files: return _blocked("missing_runtime_evidence",host="claude",crossChecks=[])
    mt=max(p.stat().st_mtime for p in files); candidates=[p for p in files if p.stat().st_mtime == mt]
    if time.time()-mt > max_age_seconds: return _blocked("stale_runtime_evidence",host="claude",freshness="stale",crossChecks=[])
    if len(candidates)!=1: return _blocked("ambiguous_runtime_evidence",host="claude",crossChecks=[])
    try: e=json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return _blocked("missing_runtime_evidence",host="claude",crossChecks=[])
    allowed={"host","sessionId","modelId","effort","thinkingEnabled","cwd","transcriptPath"}
    if set(e)-allowed or e.get("host")!="claude": return _blocked("conflicting_runtime_evidence",host="claude",crossChecks=[])
    if any(not isinstance(e.get(key), str) or not e.get(key) for key in ("sessionId","cwd","transcriptPath")):
        return _blocked("missing_session_evidence",host="claude",crossChecks=[])
    if Path(e["cwd"]).resolve() != cwd.resolve(): return _blocked("cwd_mismatch",host="claude",crossChecks=[])
    assistant=_latest_assistant(Path(e["transcriptPath"]))
    if not assistant: return _blocked("transcript_mismatch",host="claude",crossChecks=[])
    msg=assistant.get("message",{}) if isinstance(assistant.get("message"),dict) else {}
    sid=assistant.get("sessionId", msg.get("sessionId")); transcript_cwd=assistant.get("cwd", msg.get("cwd"))
    transcript_model=msg.get("model", assistant.get("modelId", assistant.get("model")))
    transcript_effort=msg.get("effort", assistant.get("effort"))
    if sid != e.get("sessionId"): return _blocked("transcript_mismatch",host="claude",crossChecks=[])
    if not isinstance(transcript_cwd,str) or Path(transcript_cwd).resolve()!=cwd.resolve(): return _blocked("cwd_mismatch",host="claude",crossChecks=[])
    if str(transcript_model or "").lower() != str(e.get("modelId") or "").lower(): return _blocked("transcript_model_mismatch",host="claude",crossChecks=[])
    if str(transcript_effort or "").lower() != str(e.get("effort") or "").lower(): return _blocked("transcript_effort_mismatch",host="claude",crossChecks=[])
    result=evaluate_runtime("claude",str(e.get("modelId", "")),str(e.get("effort", "")))
    checks=["attestation-schema","sessionId","cwd","transcript-model","transcript-effort"]
    trust={"trustLevel":"verified"} if result.get("status")=="pass" else {}
    return {**result,"sessionId":e.get("sessionId"),"thinkingEnabled":e.get("thinkingEnabled"),"source":"claude-statusline","crossChecks":checks,"freshness":"current",_TRANSCRIPT_PATH_KEY:e["transcriptPath"],**trust}
def evaluate_session(transcript_path: Path, *, allow_existing_session: bool=False) -> dict[str, Any]:
    try: records=[json.loads(x) for x in transcript_path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError,json.JSONDecodeError): return _blocked("missing_session_evidence",sessionStatus="unknown",overrideRecorded=False)
    # Modern Codex rollouts have lifecycle records.  Their injected user envelopes
    # are bootstrap context, not prior tasks, so count task boundaries instead.
    modern_rollout = any(r.get("type") == "session_meta" and isinstance(r.get("payload"), dict) for r in records)
    lifecycle = [
        r for r in records
        if r.get("type") == "event_msg"
        and isinstance(r.get("payload"), dict)
        and r["payload"].get("type") in {"task_started", "task_complete"}
    ]
    if modern_rollout and lifecycle:
        started = [r for r in lifecycle if r["payload"].get("type") == "task_started"]
        # The last active task is current. Any earlier completed or started task
        # is a real task boundary; user-message/bootstrap envelopes do not alter it.
        existing = len(started) > 1 or any(
            r["payload"].get("type") == "task_complete" for r in lifecycle[:-1]
        )
        if existing and not allow_existing_session:
            return {"status":"confirmation-required","sessionStatus":"existing","overrideRecorded":False}
        return {"status":"pass","sessionStatus":"existing" if existing else "fresh","overrideRecorded":bool(existing and allow_existing_session)}

    users=[]; assistant_seen=False
    for r in records:
        payload = r.get("payload", {}) if isinstance(r.get("payload"), dict) else {}
        if payload.get("type") == "message":
            msg = payload
        elif isinstance(r.get("message"), dict):
            msg = r["message"]
        else:
            msg = r
        role=msg.get("role",r.get("role")); content=msg.get("content",r.get("content"))
        if role=="user" and content: users.append(r)
        elif role=="assistant": assistant_seen=True
    rollout=modern_rollout
    existing=len(users)>1 and assistant_seen or (len(users)==1 and "message" not in users[0] and not rollout)
    if existing and not allow_existing_session:return {"status":"confirmation-required","sessionStatus":"existing","overrideRecorded":False}
    return {"status":"pass","sessionStatus":"existing" if existing else "fresh","overrideRecorded":bool(existing and allow_existing_session)}
def _write_json_atomically(output_path: Path, value: dict[str, Any]) -> None:
    """Persist evidence through a same-directory temporary file and replacement."""
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

def run_preflight(*,host:str="auto",allow_existing_session:bool=False,output_path:Path|None=None,model:str|None=None,effort:str|None=None)->dict[str,Any]:
    # Advisory, never-block ladder: (1) verified attestation -> real capability + session verdict;
    # (2) self-reported model/effort when attestation is unavailable; (3) unknown otherwise.
    # `evaluate_runtime`/`_blocked`/resolver cross-checks stay pure signals; only this function
    # decides the final advisory-vs-pass status.
    selected=os.environ.get("CODE_REVIEW_HOST",host).lower(); selected="codex" if selected=="auto" and os.environ.get("CODEX_THREAD_ID") else "claude" if selected=="auto" else selected
    sessions_root=Path(os.environ.get("CODEX_SESSIONS_ROOT", Path.home() / ".codex" / "sessions"))
    attestation_root=Path(os.environ.get("CLAUDE_ATTESTATION_ROOT", Path.home() / ".claude" / "review-attestations"))
    thread_id=os.environ.get("CODEX_THREAD_ID","")
    resolver=resolve_codex_runtime(thread_id,sessions_root) if selected=="codex" else resolve_claude_runtime(attestation_root,Path.cwd()) if selected=="claude" else _blocked("unknown_host",host=selected)
    bound_transcript=resolver.pop(_TRANSCRIPT_PATH_KEY,None)
    self_model=model or os.environ.get("CODE_REVIEW_MODEL"); self_effort=effort or os.environ.get("CODE_REVIEW_EFFORT")
    if bound_transcript is not None or resolver.get("status")=="pass":
        # Evidence reached evaluate_runtime, i.e. provenance itself was verified (attestation/rollout
        # cross-checks passed) even if the model/effort turned out to be below the recommended bar.
        result={**resolver,"trustLevel":"verified"}
        result.setdefault("recommendationMet", bool(result.get("recommended", False)))
        if resolver.get("status")=="pass":
            transcript=Path(bound_transcript) if isinstance(bound_transcript,str) and bound_transcript else Path(os.environ["CODE_REVIEW_TRANSCRIPT"]) if selected=="codex" and os.environ.get("CODE_REVIEW_TRANSCRIPT") else _codex_transcript_path(thread_id,sessions_root) if selected=="codex" else None
            session=evaluate_session(transcript,allow_existing_session=allow_existing_session) if transcript else {**_blocked("missing_session_evidence",sessionStatus="unknown",overrideRecorded=False),"status":"advisory"}
            result.update(session)
            if result.get("status")=="pass" and not result.get("recommendationMet",False): result["status"]="advisory"
        else:
            result["status"]="advisory"; result["recommendationMet"]=False
    elif self_model and self_effort:
        evaluated=evaluate_runtime(selected,self_model,self_effort)
        result={**evaluated,"trustLevel":"self-reported","status":"advisory","recommendationMet":evaluated.get("status")=="pass" and bool(evaluated.get("recommended"))}
    else:
        result={"status":"advisory","trustLevel":"unknown","recommendationMet":False,"modelId":None,"effort":None}
        if resolver.get("reasonCode"): result["reasonCode"]=resolver["reasonCode"]
    if output_path: _write_json_atomically(output_path, result)
    return result
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser();p.add_argument("--host",default="auto",choices=["auto","codex","claude"]);p.add_argument("--allow-existing-session",action="store_true");p.add_argument("--output",type=Path);p.add_argument("--model");p.add_argument("--effort");a=p.parse_args(argv)
    r=run_preflight(host=a.host,allow_existing_session=a.allow_existing_session,output_path=a.output,model=a.model,effort=a.effort);print(json.dumps(r,sort_keys=True));return 0 if r.get("status") in ("pass","advisory") else 2
if __name__=="__main__": raise SystemExit(main())
