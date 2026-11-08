"""Regression for the 0.5.2 ZIP's mismatched fleet version, which blocked startup."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("package_builder", ROOT / "tools/build-local-package.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PackageHeaderTests(unittest.TestCase):
    def package(self, root, fleet_version):
        headers = {
            "evejs-launcher.mod.json": {"version": "0.5.2"},
            "fleet.json": {"version": fleet_version, "clientBuild": 3396210},
            "visual-resources.json": {"version": "0.5.2", "build": 3396210, "files": {}},
        }
        for name, data in headers.items():
            (root / name).write_text(json.dumps(data), encoding="utf-8")
        (root / "loader.js").write_text("// test loader\n", encoding="utf-8")
        return tuple(headers) + ("loader.js",)

    def test_052_mismatch_is_rejected_before_archive_creation(self):
        with tempfile.TemporaryDirectory(prefix="hauler-package-test-") as directory:
            root = Path(directory).resolve()
            self.assertEqual(root.parent, Path(tempfile.gettempdir()).resolve())
            files = self.package(root, "0.5.1")
            output = root / "release.zip"
            with patch.object(builder, "ROOT", root), patch.object(builder, "PACKAGE_FILES", files):
                with self.assertRaisesRegex(ValueError, r"Release version mismatch: .*fleet.json=0.5.1"):
                    builder.build(root, output)
            self.assertFalse(output.exists())

    def test_matching_package_preserves_versions_and_disabled_loader(self):
        with tempfile.TemporaryDirectory(prefix="hauler-package-test-") as directory:
            root = Path(directory).resolve()
            self.assertEqual(root.parent, Path(tempfile.gettempdir()).resolve())
            files = self.package(root, "0.5.2")
            output = root / "release.zip"
            with patch.object(builder, "ROOT", root), patch.object(builder, "PACKAGE_FILES", files):
                builder.build(root, output)
            with zipfile.ZipFile(output) as archive:
                self.assertNotIn("loader.js", archive.namelist())
                self.assertIn("loader.js.disabled", archive.namelist())
                for name in files[:-1]:
                    self.assertEqual(json.loads(archive.read(name))["version"], "0.5.2")


if __name__ == "__main__":
    unittest.main()
