import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "detect_test_framework.py"
SPEC = importlib.util.spec_from_file_location("detect_test_framework", SCRIPT)
detector = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(detector)


class DetectTestFrameworkTests(unittest.TestCase):
    def make_file(self, root, relative, content=""):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_preserves_csharp_framework_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.make_file(root, "src/OrderService.cs")
            self.make_file(root, "App.sln")
            self.make_file(root, "tests/App.Tests.csproj", '''<Project><ItemGroup>
                <PackageReference Include="xunit" /><PackageReference Include="NSubstitute" />
                <PackageReference Include="FluentAssertions" />
                <PackageReference Include="Microsoft.NET.Test.Sdk" />
                </ItemGroup></Project>''')
            result = detector.detect(target)[0]
            self.assertEqual("C# .NET", result["stack"])
            self.assertEqual("xUnit + NSubstitute + FluentAssertions", result["framework"])
            self.assertEqual('dotnet test --collect:"XPlat Code Coverage"', result["run"])

    def test_preserves_react_and_pcf_detection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.make_file(root, "src/Grid.tsx")
            self.make_file(root, "package.json", json.dumps({"devDependencies": {"vitest": "1"}}))
            self.make_file(root, "vitest.config.ts")
            react = detector.detect(target)[0]
            self.assertEqual("React / TypeScript", react["stack"])
            self.assertEqual("Vitest", react["framework"])
            self.make_file(root, "ControlManifest.Input.xml")
            pcf = detector.detect(target)[0]
            self.assertEqual("PCF (TypeScript)", pcf["stack"])
            self.assertEqual("references/pcf-testing.md", pcf["reference"])

    def test_node_test_scan_stays_within_detected_project_root(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp)
            root = parent / "project"
            target = self.make_file(root, "src/Widget.ts")
            self.make_file(root, "package.json", "{}")
            expected = self.make_file(root, "tests/Widget.test.ts")
            outside = self.make_file(parent, "outside/Other.test.ts")

            result = detector.detect(target)[0]

            self.assertEqual([str(expected)], result["existing_tests"])
            self.assertNotIn(str(outside), result["existing_tests"])

    def test_ancestor_scan_rejects_recursive_patterns(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "within a detected project root"):
                detector._glob_up(Path(temp), "**/*.test.*")

    def test_reports_nested_instruction_candidates_in_deterministic_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.make_file(root, "src/feature/Widget.ts")
            self.make_file(root, "package.json", "{}")
            self.make_file(root, "AGENTS.md")
            nested = self.make_file(root, "src/AGENTS.md")
            self.make_file(root, "CLAUDE.md")
            nested_claude = self.make_file(root, "src/CLAUDE.md")
            self.make_file(root, "tests/README.md")
            self.make_file(root, "tests/Widget.test.ts")
            self.make_file(root, "vitest.config.ts")

            text, code = detector.report(target, detector.detect(target))
            self.assertEqual(0, code)
            self.assertLess(text.index(str(nested)), text.index(str(root / "AGENTS.md")))
            self.assertLess(text.index(str(nested_claude)), text.index(str(root / "CLAUDE.md")))
            self.assertLess(text.index("\nAGENTS.md candidates:"),
                            text.index("\ntool instruction candidates:"))
            self.assertLess(text.index("\ntool instruction candidates:"),
                            text.index("\ntest documentation:"))
            self.assertIn("instruction precedence: explicit user instructions", text)

    def test_reports_single_owner_and_ambiguous_owners_without_selecting_one(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = self.make_file(root, "src/Widget.ts")
            self.make_file(root, "package.json", "{}")
            owner = self.make_file(root, "tests/Widget.test.ts")
            context = detector.discover_context(target, detector.detect(target))
            self.assertEqual([str(owner)], context["test_owner_candidates"])
            self.assertEqual("canonical owner candidate", context["owner_resolution"])

            second = self.make_file(root, "components/Widget.spec.ts")
            context = detector.discover_context(target, detector.detect(target))
            self.assertEqual([str(second), str(owner)], sorted(context["test_owner_candidates"]))
            self.assertEqual("ambiguous — user direction required", context["owner_resolution"])

    def test_dry_run_is_accepted_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_file(root, "package.json", "{}")
            self.assertEqual(0, detector.main([str(root), "--dry-run"]))


if __name__ == "__main__":
    unittest.main()
