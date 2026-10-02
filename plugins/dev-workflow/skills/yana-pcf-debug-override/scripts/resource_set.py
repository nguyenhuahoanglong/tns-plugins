#!/usr/bin/env python3
"""Manifest-driven YanaGrid runtime resource planning and override verification.

This module never mutates a Dataverse environment. It plans a complete set of
local browser resources, applies that set transactionally inside a granted
Chrome Overrides directory, and verifies browser-observed content separately.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import stat
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit


class ResourceSetError(ValueError):
    """Invalid build, mapping, plan, or runtime evidence."""


def ensure_native_filesystem_runtime() -> None:
    """Reject Store Python, whose redirected writes can be invisible to Chrome."""
    runtime_paths = f"{sys.executable}\n{sys.prefix}".lower()
    if sys.platform == "win32" and "pythonsoftwarefoundation.python." in runtime_paths:
        raise ResourceSetError(
            "WINDOWS_STORE_PYTHON: this runtime can redirect LocalAppData writes away from Chrome. "
            "Run the helper with an explicitly resolved non-Store Python executable; "
            "do not use disk hashes from this runtime as override proof."
        )


_MANIFEST_NAME = "ControlManifest.xml"
_COPYABLE_KINDS = {"code", "css", "image", "resx", "additional-runtime"}
_DEBUG_KIND = "debug-only"
_HOST_UNKNOWN_CODES = {"HOST_UNVERIFIED", "RESX_UNVERIFIED"}
_HOST_PARITY_CODES = _HOST_UNKNOWN_CODES | {
    "HOST_CONTRACT_MISMATCH",
    "NEEDS_DEPLOY_RESX_MISMATCH",
}
_RUNTIME_METHODS = {
    "code": {"Debugger.getScriptSource"},
    # CSSOM serialization is not byte-stable; compare actual loaded response bytes.
    "css": {"Network.getResponseBody"},
    "image": {"Network.getResponseBody"},
    "resx": {"Network.getResponseBody"},
    "additional-runtime": {
        "Network.getResponseBody",
    },
    "debug-only": {
        "Debugger.getScriptSource",
        "Network.getResponseBody",
    },
}
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE | re.DOTALL)
_CSS_IMPORT = re.compile(r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1", re.IGNORECASE)
_LICENSE_SUFFIX = ".LICENSE.txt"
_REPARSE_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_ATTRIBUTE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _inside(path: Path, root: Path, label: str, *, must_exist: bool = True) -> Path:
    """Resolve a child without accepting traversal or a symlinked component."""
    try:
        root_abs = root.resolve(strict=True)
    except OSError as exc:
        raise ResourceSetError(f"{label} root does not exist: {root}") from exc
    if _is_link_or_reparse(root):
        raise ResourceSetError(f"{label} root cannot be a symlink: {root}")
    candidate = path if path.is_absolute() else root_abs / path
    try:
        relative = candidate.relative_to(root_abs)
    except ValueError as exc:
        raise ResourceSetError(f"{label} must stay inside {root_abs}: {path}") from exc
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise ResourceSetError(f"{label} contains traversal: {path}")

    current = root_abs
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise ResourceSetError(f"{label} path cannot contain symlinks: {current}")
    try:
        resolved = candidate.resolve(strict=must_exist)
    except OSError as exc:
        raise ResourceSetError(f"{label} does not exist: {candidate}") from exc
    try:
        resolved.relative_to(root_abs)
    except ValueError as exc:
        raise ResourceSetError(f"{label} resolves outside {root_abs}: {candidate}") from exc
    return resolved


def _safe_artifact(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ResourceSetError(f"Artifact must be a non-empty POSIX relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ResourceSetError(f"Artifact path contains traversal or is absolute: {value!r}")
    if path.as_posix() != value:
        raise ResourceSetError(f"Artifact path is not canonical: {value!r}")
    return path


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _xml_root(xml: str | bytes | Path) -> ET.Element:
    if isinstance(xml, Path):
        try:
            data = xml.read_bytes()
        except OSError as exc:
            raise ResourceSetError(f"Cannot read manifest XML: {xml}") from exc
    elif isinstance(xml, bytes):
        data = xml
    elif isinstance(xml, str):
        if xml.lstrip().startswith("<"):
            data = xml.encode("utf-8")
        else:
            path = Path(xml)
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise ResourceSetError("Manifest XML must be XML text or an existing file path.") from exc
    else:
        raise ResourceSetError("Manifest XML must be XML text, bytes, or a path.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise ResourceSetError(f"Invalid ControlManifest.xml: {exc}") from exc


def normalize_host_contract(xml: str | bytes | Path) -> dict[str, Any]:
    """Return canonical host-facing PCF contract, excluding labels and build versions."""
    root = _xml_root(xml)
    control = next((element for element in root.iter() if _tag(element) == "control"), None)
    if control is None:
        raise ResourceSetError("ControlManifest.xml has no <control> element.")
    ignored_labels = {"display-name-key", "description-key"}

    def canonical(element: ET.Element) -> dict[str, Any]:
        attributes = dict(element.attrib)
        for label in ignored_labels:
            attributes.pop(label, None)
        if _tag(element) == "control":
            attributes.pop("version", None)
        if _tag(element) == "resx":
            attributes.pop("version", None)
        children = [canonical(child) for child in list(element)]
        # Resource order attributes define CSS/code precedence; sequence still
        # stays represented by the ordered child list. Other declaration order
        # has no host meaning, so sort it to avoid formatting-only differences.
        if _tag(element) != "resources":
            children.sort(key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
        return {
            "tag": _tag(element),
            "attributes": dict(sorted(attributes.items())),
            "text": (element.text or "").strip(),
            "children": children,
        }

    return {"control_tree": canonical(control)}


def control_identity(xml: str | bytes | Path) -> dict[str, str]:
    """Read build namespace/constructor needed to scope observed resource URLs."""
    manifest = _xml_root(xml)
    control = next((element for element in manifest.iter() if _tag(element) == "control"), None)
    if control is None:
        raise ResourceSetError("ControlManifest.xml has no <control> element.")
    namespace = control.attrib.get("namespace", "")
    constructor = control.attrib.get("constructor", "")
    if not namespace or not constructor:
        raise ResourceSetError("ControlManifest.xml must define control namespace and constructor.")
    return {
        "namespace": namespace,
        "constructor": constructor,
        "control_type": control.attrib.get("control-type", ""),
        "control_directory": f"cc_{namespace}.{constructor}",
    }


def _manifest_assets(root: Path, manifest: ET.Element) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    identity = control_identity(ET.tostring(manifest, encoding="utf-8"))
    control = next((element for element in manifest.iter() if _tag(element) == "control"), None)
    if control is None:
        raise ResourceSetError("ControlManifest.xml has no <control> element.")

    declared: list[dict[str, Any]] = []
    resources_element = next((item for item in control if _tag(item) == "resources"), None)
    if resources_element is None:
        raise ResourceSetError("ControlManifest.xml has no <resources> section.")
    kinds = {"code": "code", "css": "css", "img": "image", "resx": "resx"}
    seen: set[str] = set()
    for element in resources_element:
        tag = _tag(element)
        if tag == "platform-library":
            continue
        artifact = element.attrib.get("path")
        if not artifact:
            if tag in kinds:
                raise ResourceSetError(f"Manifest <{tag}> resource is missing path.")
            continue
        safe = _safe_artifact(artifact)
        folded = safe.as_posix().casefold()
        if folded in seen:
            raise ResourceSetError(f"Manifest contains duplicate resource path: {artifact}")
        seen.add(folded)
        file_path = _inside(root / Path(*safe.parts), root, "Manifest resource")
        actual_rel = file_path.relative_to(root).as_posix()
        if actual_rel != safe.as_posix():
            raise ResourceSetError(f"Manifest resource path case mismatch: {artifact} != {actual_rel}")
        kind = kinds.get(tag, _runtime_kind(safe.as_posix()))
        declared.append(_asset_record(root, file_path, safe.as_posix(), kind))
    if not any(item["kind"] == "code" for item in declared):
        raise ResourceSetError("ControlManifest.xml declares no code resource.")
    return identity, declared


def _runtime_kind(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix in {".js", ".mjs"}:
        return "code"
    if suffix == ".css":
        return "css"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}:
        return "image"
    if suffix == ".resx":
        return "resx"
    return "additional-runtime"


def _asset_record(root: Path, path: Path, artifact: str, kind: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "path": artifact,
        "kind": kind,
        "sha256": _sha256(path),
        "size": stat.st_size,
    }


def _enumerate_files(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    folded: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if _is_link_or_reparse(path):
            raise ResourceSetError(f"Build output contains symlink: {path}")
        if not path.is_file():
            continue
        resolved = _inside(path, root, "Build output file")
        relative = resolved.relative_to(root).as_posix()
        key = relative.casefold()
        if key in folded and folded[key] != relative:
            raise ResourceSetError(f"Build output has case-colliding paths: {folded[key]} and {relative}")
        folded[key] = relative
        files.append((relative, resolved))
    return files


def _css_local_references(css_path: Path, css_rel: PurePosixPath) -> set[str]:
    try:
        text = css_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ResourceSetError(f"Cannot read CSS runtime resource: {css_path}") from exc
    references: set[str] = set()
    values = [match.group(2).strip() for match in _CSS_URL.finditer(text)]
    values.extend(match.group(2).strip() for match in _CSS_IMPORT.finditer(text))
    for value in values:
        if not value or value.startswith(("data:", "http:", "https:", "//", "#", "blob:")):
            continue
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            continue
        path_part = unquote(parsed.path, errors="strict")
        if not path_part or path_part.startswith(("/", "\\")) or "\\" in path_part:
            continue
        combined = PurePosixPath(css_rel.parent, path_part)
        normalized: list[str] = []
        for part in combined.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if not normalized:
                    raise ResourceSetError(f"CSS resource escapes build output: {value!r} in {css_rel}")
                normalized.pop()
            else:
                normalized.append(part)
        if normalized:
            references.add(PurePosixPath(*normalized).as_posix())
    return references


def inspect_build(output_dir: Path) -> dict[str, Any]:
    """Inventory manifest resources and local CSS dependencies in a PCF build."""
    output_dir = Path(output_dir)
    if _is_link_or_reparse(output_dir):
        raise ResourceSetError(f"Build output cannot be a symlink: {output_dir}")
    try:
        root = output_dir.resolve(strict=True)
    except OSError as exc:
        raise ResourceSetError(f"Build output directory not found: {output_dir}") from exc
    if not root.is_dir():
        raise ResourceSetError(f"Build output is not a directory: {root}")
    files = _enumerate_files(root)
    by_rel = {relative: path for relative, path in files}
    manifest_path = root / _MANIFEST_NAME
    if _MANIFEST_NAME not in by_rel:
        raise ResourceSetError(f"Build output missing {_MANIFEST_NAME}: {root}")
    manifest = _xml_root(manifest_path)
    identity, assets = _manifest_assets(root, manifest)
    declared_paths = {item["path"] for item in assets}

    css_queue = [item["path"] for item in assets if item["kind"] == "css"]
    scanned_css: set[str] = set()
    while css_queue:
        css_artifact = css_queue.pop()
        if css_artifact in scanned_css:
            continue
        scanned_css.add(css_artifact)
        css_path = by_rel.get(css_artifact)
        if css_path is None:
            raise ResourceSetError(f"CSS resource missing from build output: {css_artifact}")
        references = _css_local_references(css_path, PurePosixPath(css_artifact))
        for artifact in sorted(references):
            path = by_rel.get(artifact)
            if path is None:
                raise ResourceSetError(f"CSS references missing local runtime asset: {artifact}")
            if artifact == _MANIFEST_NAME:
                raise ResourceSetError("CSS must not reference ControlManifest.xml.")
            if artifact not in declared_paths:
                assets.append(_asset_record(root, path, artifact, _runtime_kind(artifact)))
                declared_paths.add(artifact)
            if _runtime_kind(artifact) == "css":
                css_queue.append(artifact)

    ignored_files: list[dict[str, str]] = []
    debug_assets: list[dict[str, Any]] = []
    all_files: list[dict[str, Any]] = []
    for relative, path in files:
        if relative == _MANIFEST_NAME or relative in declared_paths:
            continue
        suffix = path.suffix.lower()
        if suffix == ".map":
            record = _asset_record(root, path, relative, _DEBUG_KIND)
            all_files.append(record)
            debug_assets.append(record)
        elif path.name.casefold().endswith(_LICENSE_SUFFIX.casefold()):
            ignored_files.append({"path": relative, "reason": "license notice; not a browser runtime resource"})
        elif suffix in {".md", ".rst"} or path.name.casefold() in {"readme", "readme.txt"}:
            ignored_files.append({"path": relative, "reason": "documentation; not a browser runtime resource"})
        else:
            record = _asset_record(root, path, relative, _runtime_kind(relative))
            assets.append(record)
            declared_paths.add(relative)
            all_files.append(record)

    return {
        "status": "INSPECTED",
        "output_dir": str(root),
        "manifest": {
            "path": _MANIFEST_NAME,
            "sha256": _sha256(manifest_path),
        },
        "identity": identity,
        "host_contract": normalize_host_contract(manifest_path),
        "assets": sorted(assets, key=lambda item: item["path"].casefold()),
        "debug_assets": sorted(debug_assets, key=lambda item: item["path"].casefold()),
        "ignored_files": sorted(ignored_files, key=lambda item: item["path"].casefold()),
        "all_files": sorted(all_files, key=lambda item: item["path"].casefold()),
    }


def _normalize_origin(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResourceSetError("Origin must be a non-empty HTTPS origin.")
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ResourceSetError(f"Origin must be HTTPS: {value!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ResourceSetError("Origin cannot contain credentials.")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ResourceSetError(f"Origin cannot contain path, query, or fragment: {value!r}")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ResourceSetError(f"Invalid origin port: {value!r}") from exc
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    suffix = f":{port}" if port and port != 443 else ""
    return f"https://{host}{suffix}"


def _origin_of_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ResourceSetError(f"Mapped URL must be absolute HTTPS: {value!r}")
    if parsed.username is not None or parsed.password is not None:
        raise ResourceSetError("Mapped URL cannot contain credentials.")
    if parsed.fragment:
        raise ResourceSetError("Mapped URL cannot contain a fragment.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ResourceSetError(f"Invalid mapped URL port: {value!r}") from exc
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    suffix = f":{port}" if port and port != 443 else ""
    return f"https://{host}{suffix}"


def resolve_deployed_identity(mapping: dict[str, Any], build_identity: dict[str, Any]) -> dict[str, str]:
    """Resolve one observed base/variant control identity and bind it to this build."""
    constructor = build_identity.get("constructor")
    base_namespace = build_identity.get("namespace")
    if not isinstance(constructor, str) or not constructor or not isinstance(base_namespace, str) or not base_namespace:
        raise ResourceSetError("Build identity lacks namespace or constructor.")

    supplied = mapping.get("deployed_identity")
    if isinstance(supplied, str):
        control_directory = supplied
        observed_constructor = constructor
    elif isinstance(supplied, dict):
        control_directory = supplied.get("control_directory")
        observed_constructor = supplied.get("constructor", constructor)
        supplied_namespace = supplied.get("namespace")
        if supplied_namespace is not None and not isinstance(supplied_namespace, str):
            raise ResourceSetError("deployed_identity.namespace must be a string.")
    elif supplied is None:
        control_directory = None
        observed_constructor = constructor
    else:
        raise ResourceSetError("deployed_identity must be a control directory or identity object.")

    if observed_constructor != constructor:
        raise ResourceSetError("Mapped control constructor does not match the selected build.")

    observed_directories: set[str] = set()
    for item in mapping.get("resources", []):
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        try:
            decoded = unquote(urlsplit(item["url"]).path, errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            raise ResourceSetError(f"Mapped URL has invalid path encoding: {item.get('url')}") from exc
        candidates = [
            part for part in decoded.split("/")
            if part.startswith("cc_") and part.endswith("." + constructor)
        ]
        if len(candidates) != 1:
            raise ResourceSetError(
                f"Mapped URL must identify exactly one {constructor} control directory: {item['url']}"
            )
        observed_directories.add(candidates[0])

    if len(observed_directories) > 1:
        raise ResourceSetError("Resource mappings mix deployed control identities.")
    if control_directory is None:
        control_directory = next(iter(observed_directories), build_identity.get("control_directory"))
    elif observed_directories and observed_directories != {control_directory}:
        raise ResourceSetError("deployed_identity does not match the observed resource URLs.")
    if not isinstance(control_directory, str) or not control_directory.startswith("cc_"):
        raise ResourceSetError("deployed_identity.control_directory is missing or invalid.")

    suffix = "." + constructor
    if not control_directory.endswith(suffix):
        raise ResourceSetError("Mapped control directory has a different constructor from the build.")
    namespace = control_directory[3:-len(suffix)]
    allowed_namespace = namespace == base_namespace or bool(
        re.fullmatch(re.escape(base_namespace) + r"(?:\.[A-Za-z0-9_]+)?", namespace)
    )
    if not allowed_namespace:
        raise ResourceSetError(
            f"Mapped control namespace must match {base_namespace!r} or its single variant suffix."
        )
    if isinstance(supplied, dict) and supplied.get("namespace") not in {None, namespace}:
        raise ResourceSetError("deployed_identity.namespace disagrees with control_directory.")
    return {
        "namespace": namespace,
        "constructor": constructor,
        "control_directory": control_directory,
    }


def _validate_resource_url(
    url: str,
    origin: str,
    identity: dict[str, Any],
    artifact: str,
    control_directory: str | None = None,
) -> None:
    if _origin_of_url(url) != origin:
        raise ResourceSetError(f"Mapped URL must use exact origin {origin}: {url}")
    parsed = urlsplit(url)
    if re.search(r"%(?![0-9A-Fa-f]{2})", parsed.path):
        raise ResourceSetError(f"Mapped URL has malformed percent encoding: {url}")
    try:
        decoded = unquote(parsed.path, errors="strict")
    except UnicodeDecodeError as exc:
        raise ResourceSetError(f"Mapped URL has invalid path encoding: {url}") from exc
    if "\\" in decoded or "\x00" in decoded:
        raise ResourceSetError(f"Mapped URL path contains invalid characters: {url}")
    parts = [part for part in decoded.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise ResourceSetError(f"Mapped URL path contains traversal segments: {url}")
    control_dir = control_directory or identity["control_directory"]
    artifact_parts = list(_safe_artifact(artifact).parts)
    matching = [index for index, part in enumerate(parts) if part == control_dir]
    if not matching:
        raise ResourceSetError(
            f"Mapped URL must include exact control directory {control_dir!r}: {url}"
        )
    if not any(parts[index + 1 :] == artifact_parts for index in matching):
        raise ResourceSetError(f"Mapped URL path must end with exact artifact {artifact!r}: {url}")


def validate_mapping_destinations(mapping: dict[str, Any], overrides_dir: Path) -> None:
    """Check existing mapped files are inside the selected Overrides root before source refresh/build."""
    overrides_root = Path(overrides_dir)
    if _is_link_or_reparse(overrides_root):
        raise ResourceSetError(f"Overrides directory cannot be a symlink: {overrides_root}")
    try:
        overrides_root = overrides_root.resolve(strict=True)
    except OSError as exc:
        raise ResourceSetError(f"Overrides directory does not exist: {overrides_dir}") from exc
    if not overrides_root.is_dir():
        raise ResourceSetError(f"Overrides path is not a directory: {overrides_root}")
    resources = mapping.get("resources")
    if not isinstance(resources, list):
        raise ResourceSetError("Mapping.resources must be a list of observed URL mappings.")
    for item in resources:
        if not isinstance(item, dict):
            raise ResourceSetError("Each mapping.resources entry must be an object.")
        value = item.get("override_file")
        if not isinstance(value, str) or not value:
            raise ResourceSetError("Every resource mapping must name an existing DevTools override file.")
        destination = _inside(Path(value), overrides_root, "Override file")
        if not destination.is_file():
            raise ResourceSetError(f"Override file is not a file: {destination}")


def _load_host_manifest(value: Any) -> ET.Element | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ResourceSetError("mapping.host_manifest must be an object.")
    xml = value.get("xml")
    if xml is None:
        return None
    return _xml_root(xml)


def _resx_values(path: Path) -> dict[str, str]:
    root = _xml_root(path)
    values: dict[str, str] = {}
    for element in root.iter():
        if _tag(element) != "data":
            continue
        key = element.attrib.get("name")
        value = next((child for child in element if _tag(child) == "value"), None)
        if not key or value is None:
            continue
        value_text = "".join(value.itertext())
        if key in values and values[key] != value_text:
            raise ResourceSetError(f"RESX contains conflicting duplicate key {key!r}: {path}")
        values[key] = value_text
    return values


def _locale_from_artifact(artifact: str) -> int | None:
    match = re.search(r"\.(\d+)\.resx$", artifact, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _parse_time(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ResourceSetError(f"{label} must be an ISO-8601 timestamp.")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ResourceSetError(f"{label} must be an ISO-8601 timestamp.") from exc
    if result.tzinfo is None:
        raise ResourceSetError(f"{label} must include a timezone.")
    return result.astimezone(timezone.utc)


def _add_blocker(blockers: list[dict[str, str]], code: str, message: str) -> None:
    if not any(item["code"] == code and item["message"] == message for item in blockers):
        blockers.append({"code": code, "message": message})


def make_plan(output_dir: Path, origin: str, overrides_dir: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    """Freeze resource hashes and explicit URL-to-override mappings for one origin."""
    inventory = inspect_build(Path(output_dir))
    normalized_origin = _normalize_origin(origin)
    if not isinstance(mapping, dict) or mapping.get("schema_version") != 2:
        raise ResourceSetError("Mapping must use schema_version 2.")
    mapping_origin = _normalize_origin(mapping.get("origin", ""))
    if mapping_origin != normalized_origin:
        raise ResourceSetError(f"Mapping origin does not match requested origin: {mapping_origin}")
    if not isinstance(mapping.get("resources"), list):
        raise ResourceSetError("Mapping.resources must be a list of observed URL mappings.")
    deployed_identity = resolve_deployed_identity(mapping, inventory["identity"])
    validate_mapping_destinations(mapping, overrides_dir)
    overrides_root = Path(overrides_dir).resolve(strict=True)

    blockers: list[dict[str, str]] = []
    asset_by_path = {item["path"]: item for item in inventory["assets"]}
    debug_by_path = {item["path"]: item for item in inventory["debug_assets"]}
    allowed_artifacts = set(asset_by_path) | set(debug_by_path)
    supplied: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    seen_destinations: set[str] = set()
    for item in mapping["resources"]:
        if not isinstance(item, dict):
            raise ResourceSetError("Each mapping.resources entry must be an object.")
        artifact = item.get("artifact")
        safe = _safe_artifact(artifact)
        artifact = safe.as_posix()
        if artifact not in allowed_artifacts:
            _add_blocker(blockers, "MAPPING_UNKNOWN_ARTIFACT", f"Mapping contains unknown artifact: {artifact}")
            continue
        key = artifact.casefold()
        if key in {existing.casefold() for existing in supplied}:
            _add_blocker(blockers, "MAPPING_DUPLICATE_ARTIFACT", f"Duplicate mapping for artifact: {artifact}")
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            raise ResourceSetError(f"Mapping URL missing for artifact {artifact}.")
        _validate_resource_url(
            url, normalized_origin, inventory["identity"], artifact,
            deployed_identity["control_directory"],
        )
        if url in seen_urls:
            _add_blocker(blockers, "MAPPING_DUPLICATE_URL", f"Duplicate observed URL: {url}")
        seen_urls.add(url)
        override_value = item.get("override_file")
        if not isinstance(override_value, str) or not override_value:
            raise ResourceSetError(f"override_file missing for artifact {artifact}.")
        override_candidate = Path(override_value)
        override_path = _inside(override_candidate, overrides_root, "Override file")
        if not override_path.is_file():
            raise ResourceSetError(f"Override file is not a file: {override_path}")
        dest_key = os.path.normcase(str(override_path)).casefold()
        if dest_key in seen_destinations:
            _add_blocker(blockers, "MAPPING_DUPLICATE_DESTINATION", f"Multiple artifacts map to {override_path}")
        seen_destinations.add(dest_key)
        supplied[artifact] = {
            "artifact": artifact,
            "source": str(Path(inventory["output_dir"]) / Path(*safe.parts)),
            "url": url,
            "override_file": str(override_path),
            "sha256": asset_by_path.get(artifact, debug_by_path.get(artifact, {})).get("sha256"),
            "before_sha256": _sha256(override_path),
            "kind": asset_by_path.get(artifact, debug_by_path.get(artifact, {})).get("kind"),
        }

    resources: list[dict[str, Any]] = []
    for artifact, asset in sorted(asset_by_path.items(), key=lambda pair: pair[0].casefold()):
        record = supplied.get(artifact)
        if record is None:
            # A manifest RESX is packaged as platform localization data in many
            # PCF hosts, rather than fetched as a browser URL. Require a raw
            # override only when a real observed .resx request was mapped;
            # otherwise host strings are compared semantically below.
            if asset["kind"] != "resx":
                _add_blocker(blockers, "RESOURCE_MAPPING_MISSING", f"No exact URL/override mapping for runtime resource: {artifact}")
        else:
            resources.append(record)
    for artifact in sorted(set(supplied) - set(asset_by_path), key=str.casefold):
        # Source maps are optional; include only when user explicitly mapped them.
        resources.append(supplied[artifact])

    host_parity: dict[str, Any] = {"status": "UNVERIFIED", "details": []}
    host_manifest = mapping.get("host_manifest")
    if not isinstance(host_manifest, dict) or not host_manifest.get("xml"):
        _add_blocker(blockers, "HOST_UNVERIFIED", "No captured deployed ControlManifest.xml; host contract is unknown.")
    else:
        source_url = host_manifest.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            raise ResourceSetError("host_manifest.source_url is required with captured XML.")
        if _origin_of_url(source_url) != normalized_origin:
            raise ResourceSetError("host_manifest.source_url must use the mapped origin.")
        remote_root = _load_host_manifest(host_manifest)
        remote_contract = normalize_host_contract(ET.tostring(remote_root, encoding="utf-8"))
        host_parity["manifest_source_url"] = source_url
        if remote_contract != inventory["host_contract"]:
            host_parity["status"] = "MISMATCH"
            host_parity["details"].append("Deployed host contract differs from local build manifest.")
            _add_blocker(blockers, "HOST_CONTRACT_MISMATCH", "Deployed control contract differs; local assets cannot simulate this build safely.")
        else:
            host_parity["status"] = "CONTRACT_VERIFIED"
            host_parity["details"].append("Host contract matches local manifest.")

    resx_assets = [item for item in inventory["assets"] if item["kind"] == "resx"]
    host_resx = mapping.get("host_resources", {})
    if host_resx is None:
        host_resx = {}
    if not isinstance(host_resx, dict):
        raise ResourceSetError("mapping.host_resources must be an object.")
    known_resx_paths = {item["path"] for item in resx_assets}
    for artifact in host_resx:
        if artifact not in known_resx_paths:
            _add_blocker(blockers, "HOST_RESOURCE_UNKNOWN", f"Host resource evidence has no local RESX asset: {artifact}.")
    resx_results: list[dict[str, Any]] = []
    for asset in resx_assets:
        artifact = asset["path"]
        local_values = _resx_values(Path(inventory["output_dir"]) / Path(*_safe_artifact(artifact).parts))
        raw_mapped = supplied.get(artifact)
        if raw_mapped is not None and unquote(urlsplit(raw_mapped["url"]).path, errors="strict").endswith(artifact):
            resx_results.append({"artifact": artifact, "status": "RAW_RESOURCE_MAPPED"})
            continue
        observed = host_resx.get(artifact)
        if observed is None:
            _add_blocker(blockers, "RESX_UNVERIFIED", f"No captured host string values for {artifact} and no raw .resx request mapping.")
            resx_results.append({"artifact": artifact, "status": "UNVERIFIED"})
            continue
        if not isinstance(observed, dict):
            raise ResourceSetError(f"Host resource evidence for {artifact} must be an object.")
        locale = observed.get("locale")
        expected_locale = _locale_from_artifact(artifact)
        values = observed.get("values")
        source = observed.get("source")
        observed_at = observed.get("observed_at")
        _parse_time(observed_at, f"host_resources.{artifact}.observed_at")
        if source != "context.resources.getString":
            raise ResourceSetError(
                f"Host resource evidence for {artifact} must come from context.resources.getString."
            )
        if locale != expected_locale:
            _add_blocker(blockers, "NEEDS_DEPLOY_RESX_MISMATCH", f"Host locale {locale!r} does not match local {artifact} locale {expected_locale!r}.")
            resx_results.append({"artifact": artifact, "status": "MISMATCH"})
            continue
        if not isinstance(values, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in values.items()):
            raise ResourceSetError(f"Host resource values for {artifact} must map strings to strings.")
        if values != local_values:
            _add_blocker(blockers, "NEEDS_DEPLOY_RESX_MISMATCH", f"Host strings differ from local build resource: {artifact}.")
            resx_results.append({"artifact": artifact, "status": "MISMATCH"})
        else:
            values_digest = _digest_bytes(
                json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            resx_results.append({
                "artifact": artifact,
                "status": "VERIFIED",
                "source": source,
                "locale": locale,
                "observed_at": observed_at,
                "values_sha256": values_digest,
            })
    if host_parity["status"] == "CONTRACT_VERIFIED" and all(
        item["status"] in {"RAW_RESOURCE_MAPPED", "VERIFIED"} for item in resx_results
    ):
        host_parity["status"] = "VERIFIED"
    host_parity["resources"] = resx_results

    blockers.sort(key=lambda item: (item["code"], item["message"]))
    status = "BLOCKED" if blockers else "READY"
    return {
        "schema_version": 2,
        "plan_id": str(uuid.uuid4()),
        "created_at": _now(),
        "status": status,
        "output_dir": inventory["output_dir"],
        "origin": normalized_origin,
        "overrides_dir": str(overrides_root),
        "build_identity": inventory["identity"],
        "deployed_identity": deployed_identity,
        "control": mapping.get("control"),
        "build_manifest_sha256": inventory["manifest"]["sha256"],
        "host_contract": inventory["host_contract"],
        "host_parity": host_parity,
        "blockers": blockers,
        "resources": resources,
        "optional_debug_assets": inventory["debug_assets"],
        "ignored_files": inventory["ignored_files"],
    }


def _effective_blockers(
    plan: dict[str, Any], allow_host_unverified: bool, verification_scope: str
) -> list[dict[str, str]]:
    blockers = plan.get("blockers")
    if not isinstance(blockers, list):
        raise ResourceSetError("Plan.blockers must be a list.")
    if verification_scope == "client-assets":
        blockers = [item for item in blockers if item.get("code") not in _HOST_PARITY_CODES]
    elif allow_host_unverified:
        blockers = [item for item in blockers if item.get("code") not in _HOST_UNKNOWN_CODES]
    return blockers


def _validate_plan_files(plan: dict[str, Any]) -> list[tuple[dict[str, Any], Path, Path]]:
    output_dir = Path(plan.get("output_dir", ""))
    overrides_dir = Path(plan.get("overrides_dir", ""))
    if not output_dir.is_dir() or not overrides_dir.is_dir():
        raise ResourceSetError("Plan source or Overrides directory disappeared.")
    manifest = _inside(output_dir / _MANIFEST_NAME, output_dir, "Plan manifest")
    if not manifest.is_file() or _sha256(manifest) != plan.get("build_manifest_sha256"):
        raise ResourceSetError("ControlManifest.xml drift since plan creation.")
    seen: set[str] = set()
    validated: list[tuple[dict[str, Any], Path, Path]] = []
    for resource in plan.get("resources", []):
        if not isinstance(resource, dict):
            raise ResourceSetError("Plan resource must be an object.")
        artifact = _safe_artifact(resource.get("artifact", "")).as_posix()
        source = _inside(Path(resource.get("source", "")), output_dir, "Plan source")
        expected_source = _inside(output_dir / Path(*_safe_artifact(artifact).parts), output_dir, "Plan artifact")
        if source != expected_source:
            raise ResourceSetError(f"Plan source does not match artifact path: {artifact}")
        destination = _inside(Path(resource.get("override_file", "")), overrides_dir, "Override file")
        if not source.is_file() or not destination.is_file():
            raise ResourceSetError(f"Plan source or override is not a file: {artifact}")
        if _sha256(source) != resource.get("sha256"):
            raise ResourceSetError(f"Source drift since plan creation: {artifact}")
        if _sha256(destination) != resource.get("before_sha256"):
            raise ResourceSetError(f"Override drift since plan creation: {destination}")
        key = os.path.normcase(str(destination)).casefold()
        if key in seen:
            raise ResourceSetError(f"Plan maps multiple resources to one override file: {destination}")
        seen.add(key)
        validated.append((resource, source, destination))
    mandatory = [item for item in plan.get("resources", []) if item.get("kind") in _COPYABLE_KINDS]
    if not mandatory:
        raise ResourceSetError("Plan contains no copyable runtime resources.")
    return validated


def apply_plan(
    plan: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_host_unverified: bool = False,
    verification_scope: str = "client-parity",
) -> dict[str, Any]:
    """Replace complete planned set and restore originals if any write/check fails."""
    ensure_native_filesystem_runtime()
    if not isinstance(plan, dict) or plan.get("schema_version") != 2:
        raise ResourceSetError("Plan must use schema_version 2.")
    if verification_scope not in {"client-assets", "client-parity"}:
        raise ResourceSetError("verification_scope must be 'client-assets' or 'client-parity'.")
    plan_for_apply = dict(plan)
    plan_for_apply["verification_scope"] = verification_scope
    host_warnings = [
        item for item in plan.get("blockers", [])
        if isinstance(item, dict) and item.get("code") in _HOST_PARITY_CODES
    ]
    blockers = _effective_blockers(plan_for_apply, allow_host_unverified, verification_scope)
    if blockers:
        return {
            "status": "BLOCKED",
            "plan_id": plan.get("plan_id"),
            "blockers": blockers,
            "warnings": host_warnings,
            "plan": plan_for_apply,
        }
    validated = _validate_plan_files(plan_for_apply)
    bypassed_unknown = bool(host_warnings) or verification_scope == "client-assets"
    if dry_run:
        status = "DRY_RUN_ASSETS_ONLY" if bypassed_unknown else "DRY_RUN_READY"
        return {
            "status": status,
            "plan_id": plan["plan_id"],
            "resources": [{"artifact": resource["artifact"], "sha256": resource["sha256"]} for resource, _, _ in validated],
            "blockers": plan.get("blockers", []),
            "warnings": host_warnings,
            "plan": plan_for_apply,
        }

    transaction_id = uuid.uuid4().hex
    staged: list[tuple[dict[str, Any], Path, Path, Path, Path]] = []
    temporary_paths: list[Path] = []
    replaced: list[tuple[dict[str, Any], Path, Path, Path]] = []
    try:
        # Stage and back up every destination before the first visible replacement.
        for resource, source, destination in validated:
            if _sha256(source) != resource["sha256"]:
                raise ResourceSetError(f"Source drift while staging: {resource['artifact']}")
            if _sha256(destination) != resource["before_sha256"]:
                raise ResourceSetError(f"Override drift while staging: {destination}")
            stage = destination.with_name(f".{destination.name}.{transaction_id}.stage")
            backup = destination.with_name(f".{destination.name}.{transaction_id}.backup")
            temporary_paths.extend((stage, backup))
            shutil.copyfile(source, stage)
            shutil.copyfile(destination, backup)
            if _sha256(stage) != resource["sha256"] or _sha256(backup) != resource["before_sha256"]:
                raise ResourceSetError(f"Staged hash validation failed: {resource['artifact']}")
            staged.append((resource, source, destination, stage, backup))

        for resource, source, destination, stage, backup in staged:
            if _sha256(source) != resource["sha256"]:
                raise ResourceSetError(f"Source drift before replacement: {resource['artifact']}")
            if _sha256(destination) != resource["before_sha256"]:
                raise ResourceSetError(f"Override drift before replacement: {destination}")
            os.replace(stage, destination)
            replaced.append((resource, destination, stage, backup))
            if _sha256(destination) != resource["sha256"]:
                raise ResourceSetError(f"Replacement hash mismatch: {resource['artifact']}")

        applied_resources: list[dict[str, str]] = []
        for resource, _, destination, _, _ in staged:
            digest = _sha256(destination)
            if digest != resource["sha256"]:
                raise ResourceSetError(f"Final override hash mismatch: {resource['artifact']}")
            applied_resources.append({
                "artifact": resource["artifact"],
                "url": resource["url"],
                "sha256": digest,
            })

        cleanup_warnings: list[str] = []
        for _, _, _, _, backup in staged:
            try:
                backup.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                cleanup_warnings.append(f"Could not remove transaction backup {backup}: {cleanup_exc}")
        applied_at = _now()
        plan_with_time = dict(plan_for_apply)
        plan_with_time["applied_at"] = applied_at
        status = "ASSETS_APPLIED_NOT_DEPLOY_PARITY" if bypassed_unknown else "ASSETS_APPLIED"
        return {
            "status": status,
            "applied_at": applied_at,
            "plan": plan_with_time,
            "resources": applied_resources,
            "warnings": host_warnings,
            "cleanup_warnings": cleanup_warnings,
            "statement": "Local override files copied; receipt is not proof of browser loading or Dataverse deployment.",
        }
    except Exception as exc:
        rollback_errors: list[str] = []
        preserve_backups: set[Path] = set()
        for _, destination, stage, backup in reversed(replaced):
            try:
                if backup.exists():
                    expected_digest = next(
                        resource["before_sha256"]
                        for resource, _, candidate, _, candidate_backup in staged
                        if candidate == destination and candidate_backup == backup
                    )
                    if _sha256(backup) != expected_digest:
                        preserve_backups.add(backup)
                        rollback_errors.append(f"backup hash mismatch for {destination}; preserved recovery copy {backup}")
                        continue
                    os.replace(backup, destination)
                else:
                    rollback_errors.append(f"backup missing for {destination}")
            except OSError as rollback_exc:
                preserve_backups.add(backup)
                rollback_errors.append(f"{destination}: {rollback_exc}; preserved recovery copy {backup}")
        for temporary in temporary_paths:
            if temporary in preserve_backups:
                continue
            try:
                temporary.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                rollback_errors.append(f"cleanup {temporary}: {cleanup_exc}")
        if rollback_errors:
            raise ResourceSetError(
                f"Override transaction failed ({exc}); rollback also failed: {'; '.join(rollback_errors)}"
            ) from exc
        if isinstance(exc, ResourceSetError):
            raise
        raise ResourceSetError(f"Override transaction failed; original files restored: {exc}") from exc


def verify_runtime(plan: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Verify browser-observed content for every planned URL after local apply."""
    if not isinstance(plan, dict) or plan.get("schema_version") != 2:
        raise ResourceSetError("Verification needs schema_version 2 plan or receipt.plan.")
    if not plan.get("applied_at"):
        raise ResourceSetError("Verification requires an applied plan with applied_at.")
    verification_scope = plan.get("verification_scope", "client-parity")
    if verification_scope not in {"client-assets", "client-parity"}:
        raise ResourceSetError("verification_scope must be 'client-assets' or 'client-parity'.")
    origin = _normalize_origin(plan.get("origin", ""))
    if not isinstance(evidence, dict) or _normalize_origin(evidence.get("origin", "")) != origin:
        raise ResourceSetError("Runtime evidence origin does not match the applied plan.")
    if evidence.get("plan_id") is not None and evidence.get("plan_id") != plan.get("plan_id"):
        return {
            "status": "FAIL",
            "plan_id": plan.get("plan_id"),
            "verified": [],
            "missing": [],
            "mismatches": [{"url": "", "reason": "Runtime evidence plan_id does not match applied plan."}],
        }
    if evidence.get("errors") or evidence.get("missing_urls"):
        return {
            "status": "FAIL",
            "plan_id": plan.get("plan_id"),
            "verified": [],
            "missing": list(evidence.get("missing_urls") or []),
            "mismatches": [
                {"url": "", "reason": f"Collector reported errors: {evidence.get('errors')}"}
            ] if evidence.get("errors") else [],
        }
    observations = evidence.get("resources")
    if not isinstance(observations, list):
        raise ResourceSetError("Runtime evidence.resources must be a list.")
    expected = {resource["url"]: resource for resource in plan.get("resources", [])}
    observed_by_url: dict[str, dict[str, Any]] = {}
    for item in observations:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            raise ResourceSetError("Each runtime evidence resource needs an exact URL.")
        url = item["url"]
        if url not in expected:
            raise ResourceSetError(f"Runtime evidence contains unexpected URL: {url}")
        if url in observed_by_url:
            raise ResourceSetError(f"Runtime evidence duplicates URL: {url}")
        observed_by_url[url] = item

    applied_at = _parse_time(plan["applied_at"], "plan.applied_at")
    missing: list[str] = []
    mismatches: list[dict[str, str]] = []
    verified: list[dict[str, str]] = []
    for url, resource in expected.items():
        item = observed_by_url.get(url)
        if item is None:
            missing.append(url)
            continue
        if item.get("captured_after_apply") is not True:
            mismatches.append({"url": url, "reason": "Evidence is not marked as captured after apply."})
            continue
        captured_at = _parse_time(item.get("captured_at"), f"evidence timestamp for {url}")
        if captured_at < applied_at:
            mismatches.append({"url": url, "reason": "Evidence timestamp predates override apply."})
            continue
        if item.get("sha256") != resource.get("sha256"):
            mismatches.append({"url": url, "reason": "Browser-observed SHA-256 differs from planned build resource."})
            continue
        method = item.get("method")
        if method not in _RUNTIME_METHODS.get(resource.get("kind"), set()):
            mismatches.append({"url": url, "reason": f"Unsupported evidence method for {resource.get('kind')}: {method!r}."})
            continue
        if method == "Network.getResponseBody":
            request_id = item.get("request_id")
            resource_type = item.get("resource_type")
            if not isinstance(request_id, str) or not request_id.strip():
                mismatches.append({"url": url, "reason": "Network response evidence needs request_id from the loaded request."})
                continue
            if not isinstance(resource_type, str) or not resource_type.strip():
                mismatches.append({"url": url, "reason": "Network response evidence needs the observed resource_type."})
                continue
            if resource.get("kind") == "css" and resource_type != "Stylesheet":
                mismatches.append({"url": url, "reason": "CSS evidence must come from a loaded Stylesheet request."})
                continue
            if resource.get("kind") == "image" and resource_type != "Image":
                mismatches.append({"url": url, "reason": "Image evidence must come from a loaded Image request."})
                continue
            if resource.get("kind") == "additional-runtime" and resource_type in {"Fetch", "XHR"}:
                mismatches.append({"url": url, "reason": "Additional runtime evidence must be loaded browser resource, not Fetch/XHR."})
                continue
            if item.get("loaded_request") is not True:
                mismatches.append({"url": url, "reason": "Network response must belong to an observed loaded request."})
                continue
        verified.append({"artifact": resource["artifact"], "url": url, "sha256": item["sha256"], "method": method})

    semantic_resx = [
        item for item in plan.get("host_parity", {}).get("resources", []) if item.get("status") == "VERIFIED"
    ] if verification_scope == "client-parity" else []
    if verification_scope == "client-parity":
        observed_host_resources = evidence.get("host_resources", [])
        if not isinstance(observed_host_resources, list):
            raise ResourceSetError("Runtime evidence.host_resources must be a list.")
        host_by_artifact: dict[str, dict[str, Any]] = {}
        for item in observed_host_resources:
            if not isinstance(item, dict) or not isinstance(item.get("artifact"), str):
                raise ResourceSetError("Each runtime host resource needs an artifact path.")
            if item["artifact"] in host_by_artifact:
                raise ResourceSetError(f"Runtime host evidence duplicates artifact: {item['artifact']}")
            host_by_artifact[item["artifact"]] = item
        for expected_resx in semantic_resx:
            artifact = expected_resx["artifact"]
            item = host_by_artifact.get(artifact)
            if item is None:
                missing.append(f"host resource:{artifact}")
                continue
            if item.get("captured_after_apply") is not True:
                mismatches.append({"url": f"host resource:{artifact}", "reason": "Host strings were not observed after apply."})
                continue
            observed_at = _parse_time(item.get("observed_at"), f"host resource timestamp for {artifact}")
            if observed_at < applied_at:
                mismatches.append({"url": f"host resource:{artifact}", "reason": "Host strings were observed before override apply."})
                continue
            if item.get("source") != expected_resx.get("source") or item.get("locale") != expected_resx.get("locale"):
                mismatches.append({"url": f"host resource:{artifact}", "reason": "Host resource source or locale differs from plan."})
                continue
            values = item.get("values")
            if not isinstance(values, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in values.items()):
                mismatches.append({"url": f"host resource:{artifact}", "reason": "Host resource evidence has invalid string values."})
                continue
            values_digest = _digest_bytes(
                json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if values_digest != expected_resx.get("values_sha256"):
                mismatches.append({"url": f"host resource:{artifact}", "reason": "Host strings changed after planning."})

    if missing or mismatches:
        return {
            "status": "FAIL",
            "plan_id": plan.get("plan_id"),
            "verified": verified,
            "missing": missing,
            "mismatches": mismatches,
        }
    host_warnings = [
        item for item in plan.get("blockers", [])
        if isinstance(item, dict) and item.get("code") in _HOST_PARITY_CODES
    ]
    unknown_host = any(item.get("code") in _HOST_UNKNOWN_CODES for item in plan.get("blockers", []))
    if verification_scope == "client-assets" or unknown_host or plan.get("host_parity", {}).get("status") != "VERIFIED":
        status = "ASSETS_VERIFIED_NOT_DEPLOY_PARITY"
    else:
        status = "CLIENT_RESOURCES_VERIFIED"
    return {
        "status": status,
        "plan_id": plan.get("plan_id"),
        "verified": verified,
        "missing": [],
        "mismatches": [],
        "warnings": host_warnings,
        "verification_scope": verification_scope,
        "statement": "Client resources observed in this browser match the local build; this does not prove a Dataverse deployment.",
    }
