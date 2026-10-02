#!/usr/bin/env python3
"""Tests for complete-resource planning and browser evidence rules."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import resource_set as subject  # noqa: E402


class RuntimeBoundaryTests(unittest.TestCase):
    def test_store_python_is_rejected_before_apply_can_touch_files(self):
        store = r"C:\Users\test\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.11_pkg\python.exe"
        with mock.patch.object(subject.sys, "platform", "win32"), mock.patch.object(subject.sys, "executable", store):
            with self.assertRaisesRegex(subject.ResourceSetError, "WINDOWS_STORE_PYTHON"):
                subject.apply_plan({})

    def test_native_windows_python_is_allowed(self):
        with mock.patch.object(subject.sys, "platform", "win32"), mock.patch.object(subject.sys, "executable", r"C:\Python312\python.exe"), mock.patch.object(subject.sys, "prefix", r"C:\Python312"):
            subject.ensure_native_filesystem_runtime()


ORIGIN = "https://ptqatemplate.crm5.dynamics.com"
CONTROL_DIR = "cc_Technosoft.Test.Grid.YanaGrid"
MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest><control namespace="Technosoft.Test.Grid" constructor="YanaGrid" version="1.2.3"
 display-name-key="Local_Label" description-key="Local_Description" control-type="virtual" api-version="1.3.18">
 <data-set name="dataset" display-name-key="Dataset" cds-data-set-options="displayViewSelector:true">
  <property-set name="account" of-type="SingleLine.Text" usage="bound" required="true" display-name-key="Account" />
 </data-set>
 <property name="enableQuickView" of-type="TwoOptions" usage="input" required="false" default-value="false" display-name-key="Enable" />
 <resources>
  <code path="bundle.js" order="1" />
  <css path="Styles/DatasetStyles.css" order="1" />
  <img path="Images/icon.svg" />
  <resx path="localized/YanaGrid.1033.resx" version="1.0.0" />
  <platform-library name="React" version="16.8.6" />
 </resources>
 <feature-usage><uses-feature name="WebAPI" required="true" /></feature-usage>
</control></manifest>"""
RESX = """<?xml version="1.0" encoding="utf-8"?>
<root>
 <data name="GridTitle"><value>Yana Grid</value></data>
 <data name="Required"><value>Required</value></data>
 <data name="Required"><value>Required</value></data>
</root>"""
RESX_1036 = RESX.replace("Yana Grid", "Grille Yana").replace("<value>Required</value>", "<value>Obligatoire</value>")
QUICKVIEW_MANIFEST = MANIFEST.replace(
    'namespace="Technosoft.Test.Grid" constructor="YanaGrid"',
    'namespace="Technosoft.Test.QuickView" constructor="YanaQuickView"',
).replace("localized/YanaGrid.1033.resx", "localized/YanaQuickView.1033.resx")


def write(path: Path, contents: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents if isinstance(contents, bytes) else contents.encode("utf-8"))


def build_tree(root: Path, manifest: str = MANIFEST) -> tuple[Path, Path]:
    output = root / "out" / "controls" / "YanaGrid"
    overrides = root / "overrides"
    output.mkdir(parents=True)
    overrides.mkdir()
    write(output / "ControlManifest.xml", manifest)
    write(output / "bundle.js", b"compiled bundle bytes")
    write(output / "bundle.js.map", b"debug source map")
    write(output / "bundle.js.LICENSE.txt", "license text")
    write(output / "Styles" / "DatasetStyles.css", '@import url("./Extra.css"); body{background:url("../Images/icon.svg")}')
    write(output / "Styles" / "Extra.css", '@import "./Nested.css"; @font-face{src:url("../Images/grid.woff2")}')
    write(output / "Styles" / "Nested.css", "body{color:#123}")
    write(output / "Images" / "icon.svg", "<svg></svg>")
    write(output / "Images" / "grid.woff2", b"font bytes")
    write(output / "localized" / "YanaGrid.1033.resx", RESX)
    write(output / "localized" / "YanaGrid.1036.resx", RESX_1036)
    write(output / "chunks" / "formatHelper.js", "window.formatHelper = true;")
    write(output / "docs" / "README.md", "not runtime")
    return output, overrides


def host_values(locale: int = 1033) -> dict[str, str]:
    if locale == 1036:
        return {"GridTitle": "Grille Yana", "Required": "Obligatoire"}
    return {"GridTitle": "Yana Grid", "Required": "Required"}


def mapping_for(output: Path, overrides: Path, *, include_resx: bool = False, include_host: bool = True) -> dict:
    inventory = subject.inspect_build(output)
    resources = []
    for asset in inventory["assets"]:
        artifact = asset["path"]
        if asset["kind"] == "resx" and not include_resx:
            continue
        override = overrides / CONTROL_DIR / Path(*Path(artifact).parts)
        write(override, f"old:{artifact}")
        if artifact == "bundle.js":
            suffix = "?build=js-cache"
        elif artifact == "Styles/DatasetStyles.css":
            suffix = "?build=independent-css-cache"
        else:
            suffix = "?build=asset-cache"
        resources.append({
            "artifact": artifact,
            "url": f"{ORIGIN}/WebResources/{CONTROL_DIR}/{artifact}{suffix}",
            "override_file": str(override),
        })
    mapping = {"schema_version": 2, "origin": ORIGIN, "resources": resources}
    if include_host:
        mapping["host_manifest"] = {
            "xml": MANIFEST,
            "source_url": f"{ORIGIN}/WebResources/{CONTROL_DIR}/ControlManifest.xml",
        }
        if not include_resx:
            mapping["host_resources"] = {
                artifact: {
                    "locale": locale,
                    "values": host_values(locale),
                    "source": "context.resources.getString",
                    "observed_at": "2026-09-29T12:00:00Z",
                }
                for artifact, locale in (
                    ("localized/YanaGrid.1033.resx", 1033),
                    ("localized/YanaGrid.1036.resx", 1036),
                )
            }
    return mapping


def observed_evidence(plan: dict, *, timestamp: str | None = None) -> dict:
    captured_at = timestamp or (datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    entries = []
    for resource in plan["resources"]:
        kind = resource["kind"]
        entry = {
            "url": resource["url"],
            "sha256": resource["sha256"],
            "method": "Debugger.getScriptSource" if kind == "code" else "Network.getResponseBody",
            "captured_at": captured_at,
            "captured_after_apply": True,
        }
        if entry["method"] == "Network.getResponseBody":
            entry.update({
                "request_id": f"request-{len(entries) + 1}",
                "resource_type": "Stylesheet" if kind == "css" else "Image" if kind == "image" else "Font" if resource["artifact"].endswith(".woff2") else "Other",
                "loaded_request": True,
            })
        entries.append(entry)
    host_resources = [
        {
            "artifact": item["artifact"],
            "locale": item["locale"],
            "values": host_values(item["locale"]),
            "source": item["source"],
            "observed_at": captured_at,
            "captured_after_apply": True,
        }
        for item in plan.get("host_parity", {}).get("resources", [])
        if item.get("status") == "VERIFIED"
    ]
    return {"plan_id": plan["plan_id"], "origin": plan["origin"], "resources": entries, "host_resources": host_resources}


class ResourceSetTests(unittest.TestCase):
    def setUp(self) -> None:
        # These tests exercise resource transaction behavior with temporary folders.
        # The dedicated RuntimeBoundaryTests above cover the platform guard itself.
        self._runtime_guard = mock.patch.object(subject, "ensure_native_filesystem_runtime")
        self._runtime_guard.start()
        self.addCleanup(self._runtime_guard.stop)

    def test_inspect_build_includes_manifest_css_and_css_referenced_runtime_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, _ = build_tree(Path(temporary))
            result = subject.inspect_build(output)
            assets = {item["path"]: item["kind"] for item in result["assets"]}
            self.assertEqual(assets["bundle.js"], "code")
            self.assertEqual(assets["Styles/DatasetStyles.css"], "css")
            self.assertEqual(assets["Images/icon.svg"], "image")
            self.assertEqual(assets["Images/grid.woff2"], "additional-runtime")
            self.assertEqual(assets["localized/YanaGrid.1033.resx"], "resx")
            self.assertEqual(assets["localized/YanaGrid.1036.resx"], "resx")
            self.assertEqual(assets["Styles/Extra.css"], "css")
            self.assertEqual(assets["Styles/Nested.css"], "css")
            self.assertEqual(assets["chunks/formatHelper.js"], "code")
            self.assertEqual([item["path"] for item in result["debug_assets"]], ["bundle.js.map"])
            ignored = {item["path"]: item["reason"] for item in result["ignored_files"]}
            self.assertIn("bundle.js.LICENSE.txt", ignored)
            self.assertIn("docs/README.md", ignored)

    def test_quickview_build_uses_manifest_identity_and_complete_asset_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "out" / "controls" / "YanaQuickView"
            overrides = root / "overrides"
            output.mkdir(parents=True)
            overrides.mkdir()
            write(output / "ControlManifest.xml", QUICKVIEW_MANIFEST)
            write(output / "bundle.js", b"quickview bundle")
            write(output / "Styles" / "DatasetStyles.css", "body{color:navy}")
            write(output / "Images" / "icon.svg", "<svg></svg>")
            write(output / "localized" / "YanaQuickView.1033.resx", RESX)
            inventory = subject.inspect_build(output)
            self.assertEqual(inventory["identity"]["constructor"], "YanaQuickView")
            self.assertEqual({item["path"] for item in inventory["assets"]}, {
                "bundle.js", "Styles/DatasetStyles.css", "Images/icon.svg", "localized/YanaQuickView.1033.resx",
            })

            control_dir = "cc_Technosoft.Test.QuickView.YanaQuickView"
            resources = []
            for asset in inventory["assets"]:
                artifact = asset["path"]
                destination = overrides / control_dir / artifact
                write(destination, b"previous bytes")
                resources.append({
                    "artifact": artifact,
                    "url": f"{ORIGIN}/webresources/{control_dir}/{artifact}?token={artifact}",
                    "override_file": str(destination),
                })
            mapping = {
                "schema_version": 2,
                "origin": ORIGIN,
                "control": "YanaQuickView",
                "resources": resources,
                "host_manifest": {
                    "xml": QUICKVIEW_MANIFEST,
                    "source_url": f"{ORIGIN}/webresources/{control_dir}/ControlManifest.xml",
                },
            }
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "READY")
            self.assertEqual(plan["deployed_identity"]["control_directory"], control_dir)
            self.assertEqual(len(plan["resources"]), len(inventory["assets"]))

    def test_variant_control_identity_must_match_all_observed_asset_urls(self) -> None:
        identity = subject.control_identity(MANIFEST)
        variant = "cc_Technosoft.Test.Grid.Long.YanaGrid"
        resolved = subject.resolve_deployed_identity({
            "resources": [{"url": f"{ORIGIN}/webresources/{variant}/bundle.js"}],
        }, identity)
        self.assertEqual(resolved["control_directory"], variant)
        with self.assertRaisesRegex(subject.ResourceSetError, "mix deployed control identities"):
            subject.resolve_deployed_identity({
                "resources": [
                    {"url": f"{ORIGIN}/webresources/{variant}/bundle.js"},
                    {"url": f"{ORIGIN}/webresources/cc_Technosoft.Test.Grid.Preview.YanaGrid/Styles/DatasetStyles.css"},
                ],
            }, identity)
        with self.assertRaisesRegex(subject.ResourceSetError, "namespace"):
            subject.resolve_deployed_identity({
                "resources": [{"url": f"{ORIGIN}/webresources/cc_Technosoft.Test.Other.Long.YanaGrid/bundle.js"}],
            }, identity)

    def test_css_can_have_independent_cache_token_and_complete_semantic_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            bundle = next(item for item in mapping["resources"] if item["artifact"] == "bundle.js")
            css = next(item for item in mapping["resources"] if item["artifact"].endswith(".css"))
            self.assertIn("js-cache", bundle["url"])
            self.assertIn("independent-css-cache", css["url"])
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "READY")
            self.assertEqual(plan["host_parity"]["status"], "VERIFIED")
            self.assertNotIn("localized/YanaGrid.1033.resx", [item["artifact"] for item in plan["resources"]])

    def test_missing_css_blocks_entire_plan_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            css = next(item for item in mapping["resources"] if item["artifact"].endswith(".css"))
            mapping["resources"].remove(css)
            before = {path: path.read_bytes() for path in overrides.rglob("*") if path.is_file()}
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "BLOCKED")
            receipt = subject.apply_plan(plan, allow_host_unverified=True)
            self.assertEqual(receipt["status"], "BLOCKED")
            client_assets = subject.apply_plan(plan, verification_scope="client-assets")
            self.assertEqual(client_assets["status"], "BLOCKED")
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_raw_resx_allowed_only_when_observed_url_ends_with_same_resx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides, include_resx=True)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "READY")
            self.assertIn("localized/YanaGrid.1033.resx", [item["artifact"] for item in plan["resources"]])

            bad = mapping_for(output, overrides, include_resx=True)
            item = next(item for item in bad["resources"] if item["artifact"].endswith(".resx"))
            item["url"] = f"{ORIGIN}/WebResources/{CONTROL_DIR}/strings.json?resx=1"
            with self.assertRaises(subject.ResourceSetError):
                subject.make_plan(output, ORIGIN, overrides, bad)

    def test_semantic_host_resx_missing_or_changed_strings_requires_deploy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            del mapping["host_resources"]["localized/YanaGrid.1033.resx"]["values"]["Required"]
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "BLOCKED")
            self.assertIn("NEEDS_DEPLOY_RESX_MISMATCH", [item["code"] for item in plan["blockers"]])
            self.assertEqual(subject.apply_plan(plan, allow_host_unverified=True)["status"], "BLOCKED")
            receipt = subject.apply_plan(plan, verification_scope="client-assets")
            self.assertEqual(receipt["status"], "ASSETS_APPLIED_NOT_DEPLOY_PARITY")
            self.assertEqual(receipt["plan"]["verification_scope"], "client-assets")
            self.assertIn("NEEDS_DEPLOY_RESX_MISMATCH", [item["code"] for item in receipt["warnings"]])
            evidence = observed_evidence(receipt["plan"])
            evidence.pop("host_resources", None)
            verified = subject.verify_runtime(receipt["plan"], evidence)
            self.assertEqual(verified["status"], "ASSETS_VERIFIED_NOT_DEPLOY_PARITY")
            self.assertIn("NEEDS_DEPLOY_RESX_MISMATCH", [item["code"] for item in verified["warnings"]])
            evidence["resources"].pop()
            self.assertEqual(subject.verify_runtime(receipt["plan"], evidence)["status"], "FAIL")

    def test_unknown_host_or_resx_allows_explicit_partial_debug_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides, include_host=False)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "BLOCKED")
            self.assertEqual(subject.apply_plan(plan)["status"], "BLOCKED")
            receipt = subject.apply_plan(plan, allow_host_unverified=True)
            self.assertEqual(receipt["status"], "ASSETS_APPLIED_NOT_DEPLOY_PARITY")
            result = subject.verify_runtime(receipt["plan"], observed_evidence(receipt["plan"]))
            self.assertEqual(result["status"], "ASSETS_VERIFIED_NOT_DEPLOY_PARITY")

    def test_host_contract_drift_is_hard_blocker_even_with_unverified_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            remote = MANIFEST.replace('of-type="TwoOptions"', 'of-type="SingleLine.Text"')
            mapping["host_manifest"]["xml"] = remote
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertEqual(plan["status"], "BLOCKED")
            self.assertIn("HOST_CONTRACT_MISMATCH", [item["code"] for item in plan["blockers"]])
            self.assertEqual(
                subject.apply_plan(plan, allow_host_unverified=True, verification_scope="client-parity")["status"],
                "BLOCKED",
            )
            receipt = subject.apply_plan(plan, verification_scope="client-assets")
            self.assertEqual(receipt["status"], "ASSETS_APPLIED_NOT_DEPLOY_PARITY")
            self.assertIn("HOST_CONTRACT_MISMATCH", [item["code"] for item in receipt["warnings"]])
            evidence = observed_evidence(receipt["plan"])
            evidence.pop("host_resources", None)
            self.assertEqual(
                subject.verify_runtime(receipt["plan"], evidence)["status"],
                "ASSETS_VERIFIED_NOT_DEPLOY_PARITY",
            )

    def test_host_contract_covers_nested_choices_external_services_and_resource_membership(self) -> None:
        variants = (
            MANIFEST.replace(
                '<property-set name="account" of-type="SingleLine.Text" usage="bound" required="true" display-name-key="Account" />',
                '<property-set name="account" of-type="SingleLine.Text" usage="bound" required="true" display-name-key="Account"><type-group name="numbers" /></property-set>',
            ),
            MANIFEST.replace(
                '<feature-usage><uses-feature name="WebAPI" required="true" /></feature-usage>',
                '<external-service-usage enabled="true"><domain>api.example.test</domain></external-service-usage><feature-usage><uses-feature name="WebAPI" required="true" /></feature-usage>',
            ),
            MANIFEST.replace('  <css path="Styles/DatasetStyles.css" order="1" />\n', ""),
        )
        for host_manifest in variants:
            with self.subTest(host_manifest=host_manifest[:80]), tempfile.TemporaryDirectory() as temporary:
                output, overrides = build_tree(Path(temporary))
                mapping = mapping_for(output, overrides)
                mapping["host_manifest"]["xml"] = host_manifest
                plan = subject.make_plan(output, ORIGIN, overrides, mapping)
                self.assertIn("HOST_CONTRACT_MISMATCH", [item["code"] for item in plan["blockers"]])

    def test_path_escape_and_url_identity_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            mapping["resources"][0]["artifact"] = "../bundle.js"
            with self.assertRaises(subject.ResourceSetError):
                subject.make_plan(output, ORIGIN, overrides, mapping)

            mapping = mapping_for(output, overrides)
            mapping["resources"][0]["url"] = f"{ORIGIN}/WebResources/cc_Wrong.Control/bundle.js?v=1"
            with self.assertRaises(subject.ResourceSetError):
                subject.make_plan(output, ORIGIN, overrides, mapping)

            mapping = mapping_for(output, overrides)
            mapping["resources"][0]["override_file"] = str(Path(temporary) / "outside.js")
            write(Path(mapping["resources"][0]["override_file"]), "outside")
            with self.assertRaises(subject.ResourceSetError):
                subject.make_plan(output, ORIGIN, overrides, mapping)

    def test_symlinked_build_or_override_resource_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            outside = Path(temporary) / "outside.js"
            write(outside, "outside")
            link = output / "linked.js"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable in this Windows environment")
            with self.assertRaises(subject.ResourceSetError):
                subject.inspect_build(output)

        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            outside = Path(temporary) / "outside.js"
            write(outside, "outside")
            item = mapping["resources"][0]
            override = Path(item["override_file"])
            override.unlink()
            try:
                override.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable in this Windows environment")
            with self.assertRaises(subject.ResourceSetError):
                subject.make_plan(output, ORIGIN, overrides, mapping)

    def test_case_colliding_build_paths_are_rejected_when_filesystem_allows_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, _ = build_tree(Path(temporary))
            first = output / "Assets" / "icon.png"
            second = output / "assets" / "ICON.png"
            write(first, b"a")
            try:
                write(second, b"b")
            except OSError:
                self.skipTest("Filesystem cannot create case-distinct sibling paths")
            found = subject._enumerate_files(output)
            folded = [item[0].casefold() for item in found]
            if len(folded) != len(set(folded)):
                with self.assertRaises(subject.ResourceSetError):
                    subject.inspect_build(output)
            else:
                self.skipTest("Filesystem aliases case-only paths")

    def test_duplicate_mapping_is_blocked_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            mapping["resources"].append(dict(mapping["resources"][0]))
            before = {path: path.read_bytes() for path in overrides.rglob("*") if path.is_file()}
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            self.assertIn("MAPPING_DUPLICATE_ARTIFACT", [item["code"] for item in plan["blockers"]])
            self.assertEqual(subject.apply_plan(plan)["status"], "BLOCKED")
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_plan_detects_source_and_destination_drift(self) -> None:
        for drift_target in ("source", "destination"):
            with self.subTest(drift_target=drift_target), tempfile.TemporaryDirectory() as temporary:
                output, overrides = build_tree(Path(temporary))
                mapping = mapping_for(output, overrides)
                plan = subject.make_plan(output, ORIGIN, overrides, mapping)
                resource = plan["resources"][0]
                target = Path(resource["source"] if drift_target == "source" else resource["override_file"])
                write(target, "drifted")
                with self.assertRaises(subject.ResourceSetError):
                    subject.apply_plan(plan)

    def test_dry_run_validates_every_resource_but_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            before = {path: path.read_bytes() for path in overrides.rglob("*") if path.is_file()}
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            receipt = subject.apply_plan(plan, dry_run=True)
            self.assertEqual(receipt["status"], "DRY_RUN_READY")
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_replacement_failure_rolls_back_every_previously_replaced_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            before = {path: path.read_bytes() for path in overrides.rglob("*") if path.is_file()}
            original_replace = subject.os.replace
            replacement_count = 0

            def fail_second(source: str | Path, destination: str | Path) -> None:
                nonlocal replacement_count
                replacement_count += 1
                if replacement_count == 2:
                    raise OSError("injected replacement failure")
                original_replace(source, destination)

            with mock.patch.object(subject.os, "replace", side_effect=fail_second):
                with self.assertRaisesRegex(subject.ResourceSetError, "original files restored"):
                    subject.apply_plan(plan)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            self.assertEqual(list(overrides.rglob("*.stage")), [])
            self.assertEqual(list(overrides.rglob("*.backup")), [])

    def test_rollback_failure_preserves_original_recovery_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            before = {path: path.read_bytes() for path in overrides.rglob("*") if path.is_file()}
            original_replace = subject.os.replace
            calls = 0

            def fail_replace_and_rollback(source: str | Path, destination: str | Path) -> None:
                nonlocal calls
                calls += 1
                if calls in {2, 3}:
                    raise OSError(f"injected failure {calls}")
                original_replace(source, destination)

            with mock.patch.object(subject.os, "replace", side_effect=fail_replace_and_rollback):
                with self.assertRaisesRegex(subject.ResourceSetError, "preserved recovery copy") as caught:
                    subject.apply_plan(plan)
            preserved = list(overrides.rglob("*.backup"))
            self.assertEqual(len(preserved), 1)
            recovery_original = next(original for original in before if preserved[0].name.startswith(f".{original.name}."))
            self.assertEqual(preserved[0].read_bytes(), before[recovery_original])
            self.assertIn(str(preserved[0]), str(caught.exception))

    def test_manifest_drift_after_plan_creation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            write(output / "ControlManifest.xml", MANIFEST.replace('version="1.2.3"', 'version="1.2.4"'))
            # Version-only changes do not affect host contract, but frozen manifest bytes still changed.
            with self.assertRaises(subject.ResourceSetError):
                subject.apply_plan(plan)

    def test_runtime_verification_requires_every_exact_fresh_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            receipt = subject.apply_plan(plan)
            applied_plan = receipt["plan"]
            evidence = observed_evidence(applied_plan)
            result = subject.verify_runtime(applied_plan, evidence)
            self.assertEqual(result["status"], "CLIENT_RESOURCES_VERIFIED")

            missing = dict(evidence, resources=evidence["resources"][:-1])
            self.assertEqual(subject.verify_runtime(applied_plan, missing)["status"], "FAIL")

            wrong = {**evidence, "resources": [dict(item) for item in evidence["resources"]]}
            wrong["resources"][0]["sha256"] = "0" * 64
            self.assertEqual(subject.verify_runtime(applied_plan, wrong)["status"], "FAIL")

            wrong_plan = {**evidence, "plan_id": "another-plan"}
            self.assertEqual(subject.verify_runtime(applied_plan, wrong_plan)["status"], "FAIL")

            collector_error = {**evidence, "errors": ["response body unavailable"]}
            self.assertEqual(subject.verify_runtime(applied_plan, collector_error)["status"], "FAIL")

            collector_missing = {**evidence, "missing_urls": [evidence["resources"][0]["url"]]}
            self.assertEqual(subject.verify_runtime(applied_plan, collector_missing)["status"], "FAIL")

            stale = observed_evidence(applied_plan, timestamp="2000-01-01T00:00:00Z")
            self.assertEqual(subject.verify_runtime(applied_plan, stale)["status"], "FAIL")

            missing_host = {**evidence, "host_resources": []}
            self.assertEqual(subject.verify_runtime(applied_plan, missing_host)["status"], "FAIL")

            changed_host = {**evidence, "host_resources": [dict(item) for item in evidence["host_resources"]]}
            changed_host["host_resources"][0]["values"] = {"GridTitle": "Changed", "Required": "Required"}
            self.assertEqual(subject.verify_runtime(applied_plan, changed_host)["status"], "FAIL")

            stale_host = {**evidence, "host_resources": [dict(item) for item in evidence["host_resources"]]}
            stale_host["host_resources"][0]["observed_at"] = "2000-01-01T00:00:00Z"
            self.assertEqual(subject.verify_runtime(applied_plan, stale_host)["status"], "FAIL")

    def test_css_text_serialization_cannot_verify_and_network_response_must_be_loaded_stylesheet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output, overrides = build_tree(Path(temporary))
            mapping = mapping_for(output, overrides)
            plan = subject.make_plan(output, ORIGIN, overrides, mapping)
            receipt = subject.apply_plan(plan)
            applied_plan = receipt["plan"]
            evidence = observed_evidence(applied_plan)
            css_observation = next(item for item in evidence["resources"] if item["url"].endswith(".css?build=independent-css-cache"))

            css_text_only = {**evidence, "resources": [dict(item) for item in evidence["resources"]]}
            css_item = next(item for item in css_text_only["resources"] if item["url"] == css_observation["url"])
            css_item["method"] = "CSS.getStyleSheetText"
            self.assertEqual(subject.verify_runtime(applied_plan, css_text_only)["status"], "FAIL")

            wrong_type = {**evidence, "resources": [dict(item) for item in evidence["resources"]]}
            css_item = next(item for item in wrong_type["resources"] if item["url"] == css_observation["url"])
            css_item["resource_type"] = "Other"
            self.assertEqual(subject.verify_runtime(applied_plan, wrong_type)["status"], "FAIL")

            no_request_id = {**evidence, "resources": [dict(item) for item in evidence["resources"]]}
            css_item = next(item for item in no_request_id["resources"] if item["url"] == css_observation["url"])
            css_item["request_id"] = ""
            self.assertEqual(subject.verify_runtime(applied_plan, no_request_id)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
