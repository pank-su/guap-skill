"""Synthetic profile contracts; no private coursework or network."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/labflow-guap/scripts/work_profiles.py"


class WorkProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()

    def compile(self, profile, *args, ok=True, dest=None):
        output = self.base / (dest or profile)
        run = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "compile",
                "--profile",
                profile,
                "--output-dir",
                str(output),
                *map(str, args),
            ],
            capture_output=True,
            text=True,
        )
        if ok:
            self.assertEqual(run.returncode, 0, run.stderr)
            return json.loads((output / "contract.json").read_text()), output
        self.assertNotEqual(run.returncode, 0)
        self.assertNotIn("Traceback", run.stderr)
        return run

    def test_attributed_override_conflicts_block_until_explicit_exception(self):
        path = self.base / "overrides.json"

        def record(value, source):
            return {"value": value, "source": source, "locator": "line 1"}

        overrides = {
            "methodology": {"table_pt": record(15, "current-method.txt")},
            "user": {"table_pt": record(16, "current-user-correction.txt")},
            "accepted_exceptions": [],
        }
        path.write_text(json.dumps(overrides))
        self.compile("physics", "--overrides", path, ok=False)
        self.assertTrue(
            (self.base / "physics/contract.json").is_file(),
            "source conflict must produce a blocked contract",
        )
        blocked = json.loads((self.base / "physics/contract.json").read_text())
        self.assertEqual(blocked["status"], "blocked")
        self.assertFalse((self.base / "physics/style.typ").exists())
        overrides["accepted_exceptions"] = ["table_pt"]
        path.write_text(json.dumps(overrides))
        contract, _ = self.compile("physics", "--overrides", path, dest="accepted")
        self.assertEqual(contract["rules"]["table_pt"], 16)
        self.assertEqual(contract["provenance"]["table_pt"]["tier"], "user")
        self.assertTrue(contract["conflicts"][0]["accepted"])

    def test_scope_and_format_do_not_invent_unrelated_phases(self):
        revision, _ = self.compile("physics", "--scope", "revision")
        self.assertEqual(revision["plan"]["phases"], ["report", "verify"])
        csv, path = self.compile("calculation", "--format", "csv")
        self.assertEqual(csv["plan"]["phases"], ["context", "math", "verify", "review"])
        self.assertFalse((path / "style.typ").exists())
        coursework, _ = self.compile("coursework", "--domain", "code")
        self.assertIn("code", coursework["plan"]["phases"])

    def test_typst_style_really_applies_body_and_table_sizes(self):
        import pymupdf

        _, folder = self.compile("physics")
        document = self.base / "sample.typ"
        document.write_text(
            '#import "physics/style.typ": profile-style\n#show: profile-style\nBodyMarker\n#table(columns: 2, [TableMarker], [Value])',
            encoding="utf-8",
        )
        pdf = self.base / "sample.pdf"
        run = subprocess.run(
            ["typst", "compile", str(document), str(pdf)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        with pymupdf.open(pdf) as doc:
            spans = [
                s
                for page in doc
                for b in page.get_text("dict")["blocks"]
                if "lines" in b
                for line in b["lines"]
                for s in line["spans"]
            ]
            self.assertTrue(
                any(
                    "BodyMarker" in s["text"] and abs(s["size"] - 14) < 0.05
                    for s in spans
                )
            )
            self.assertTrue(
                any(
                    "TableMarker" in s["text"] and abs(s["size"] - 16) < 0.05
                    for s in spans
                )
            )
            self.assertTrue(
                all("Times" in s["font"] for s in spans if "Marker" in s["text"])
            )
        before = (folder / "contract.json").read_bytes()
        self.compile("physics", ok=False)
        self.assertEqual(before, (folder / "contract.json").read_bytes())

    def test_intermediate_ancestor_symlink_rejected_before_creation(self):
        real = self.base / "real"
        real.mkdir()
        link = self.base / "link"
        link.symlink_to(real, target_is_directory=True)

        self.compile("physics", ok=False, dest="link/intermediate/profile")
        self.assertFalse((real / "intermediate").exists())

    def test_invalid_overrides_and_protected_destination_rejected(self):
        for key, value in [
            ("author", "Old author"),
            ("table_pt", True),
            ("rounding_decimals", -1),
        ]:
            source = self.base / (key + ".json")
            source.write_text(
                json.dumps(
                    {
                        "methodology": {
                            key: {
                                "value": value,
                                "source": "fixture",
                                "locator": "line 1",
                            }
                        },
                        "user": {},
                        "accepted_exceptions": [],
                    }
                )
            )
            self.compile("calculation", "--overrides", source, ok=False, dest=key)
            self.assertFalse((self.base / key).exists())
        self.compile("calculation", ok=False, dest=".guap/generated-profile")
        self.assertFalse((self.base / ".guap").exists())

    def test_profiles_have_distinct_rules_and_no_stale_content(self):
        physics, _ = self.compile("physics")
        calculation, _ = self.compile("calculation")
        self.assertEqual(physics["rules"]["table_pt"], 16)
        self.assertEqual(calculation["rules"]["table_pt"], 14)
        self.assertEqual(physics["rules"]["rounding_decimals"], 1)
        self.assertFalse(calculation["rules"]["materials_list"])
        self.assertEqual(physics["rules"]["sections"][0], "Протокол")
        self.assertNotIn("author", physics)
        self.assertNotIn("content", physics)
        coursework, _ = self.compile("coursework")
        lecture, output = self.compile("lecture")
        self.assertTrue(coursework["rules"]["first_level_new_page"])
        self.assertEqual(
            lecture["plan"]["phases"], ["context", "notes", "verify", "review"]
        )
        self.assertFalse((output / "style.typ").exists())


if __name__ == "__main__":
    unittest.main()
