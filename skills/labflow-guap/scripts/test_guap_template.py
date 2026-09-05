#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("guap_template.py")


class GuapTemplateCliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        env = os.environ.copy()
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
        )

    def init_project(self, root):
        project = Path(root) / "report"
        result = self.run_cli("init", project)
        self.assertEqual(result.returncode, 0, result.stderr)
        return project

    def write_data(self, root, value):
        data = Path(root) / "metadata-input.json"
        data.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return data

    def complete_metadata(self, **overrides):
        # Fictional fixture values only; never use these in a submitted report.
        value = {
            "title": "Демонстрационный отчёт",
            "authors": ["Тестовый студент"],
            "teachers": ["Тестовый преподаватель"],
            "date": "2026-09-05",
            "education": "ГУАП",
            "department": "Тестовая кафедра",
            "position": "доцент",
            "documentName": "ОТЧЁТ ПО ЛАБОРАТОРНОЙ РАБОТЕ",
            "group": "ТЕСТ-01",
            "city": "Санкт-Петербург",
            "object": "Тестовая дисциплина",
        }
        value.update(overrides)
        return value

    def test_init_creates_protected_project_without_overwriting_index(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "report"
            project.mkdir()
            index = project / "index.typ"
            index.write_text("#let user_content = [Keep me]\n", encoding="utf-8")

            result = self.run_cli("init", project)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(index.read_text(encoding="utf-8"), "#let user_content = [Keep me]\n")
            self.assertTrue((project / ".guap" / "titlepage.typ").is_file())
            self.assertTrue((project / ".guap" / "gost.typ").is_file())
            self.assertTrue((project / ".guap" / "main.typ").is_file())
            self.assertTrue((project / ".guap" / "metadata.json").is_file())
            self.assertTrue((project / ".guap" / "lock.json").is_file())
            metadata = json.loads((project / ".guap" / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["title"], "")
            self.assertEqual(metadata["authors"], [])
            self.assertEqual(metadata["date"], "")

    def test_init_refuses_existing_protected_collision(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            before = (project / ".guap" / "metadata.json").read_bytes()
            result = self.run_cli("init", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("refusing to overwrite", result.stderr)
            self.assertEqual((project / ".guap" / "metadata.json").read_bytes(), before)

    def test_hand_editing_index_is_allowed_but_protected_mutation_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            index = project / "index.typ"
            index.write_text("= User body\nThis is editable.\n", encoding="utf-8")
            self.assertEqual(self.run_cli("check", project).returncode, 0)

            protected = project / ".guap" / "gost.typ"
            protected.write_bytes(protected.read_bytes() + b"\n// tampered\n")
            result = self.run_cli("check", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("differs from the canonical asset", result.stderr)

    def test_missing_and_symlinked_protected_files_are_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            (project / ".guap" / "lock.json").unlink()
            result = self.run_cli("check", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lock.json", result.stderr)

        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            lock = project / ".guap" / "lock.json"
            lock.unlink()
            try:
                lock.symlink_to(project / "index.typ")
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            result = self.run_cli("check", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not be a symlink", result.stderr)

    def test_manual_metadata_change_is_blocked_before_title_update(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            metadata_path = project / ".guap" / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["title"] = "manual edit"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            data = self.write_data(temp, {"title": "legitimate update"})
            result = self.run_cli("title", project, "--data", data)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lock.json", result.stderr)

    def test_fixed_driver_mutation_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            main = project / ".guap" / "main.typ"
            main.write_bytes(main.read_bytes() + b"\n// tampered\n")
            result = self.run_cli("build", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("main.typ", result.stderr)

    def test_valid_title_update_merges_fields_and_preserves_json_text(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            value = self.complete_metadata(title="Title with #raw() and ] brackets")
            data = self.write_data(temp, value)
            result = self.run_cli("title", project, "--data", data)
            self.assertEqual(result.returncode, 0, result.stderr)
            stored = json.loads((project / ".guap" / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, value)
            self.assertEqual(self.run_cli("check", project).returncode, 0)

    def test_unknown_field_and_invalid_date_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            unknown = self.write_data(temp, {"title": "x", "not_allowed": "#eval()"})
            result = self.run_cli("title", project, "--data", unknown)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown metadata field", result.stderr)

            invalid = self.write_data(temp, {"date": "2026-02-30"})
            result = self.run_cli("title", project, "--data", invalid)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("valid ISO date", result.stderr)

    def test_build_requires_complete_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            result = self.run_cli("build", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("required metadata", result.stderr)
            self.assertFalse((project / "report.pdf").exists())

    @unittest.skipUnless(shutil.which("typst"), "Typst is required")
    def test_build_does_not_replace_existing_pdf_after_compile_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            data = self.write_data(temp, self.complete_metadata())
            self.assertEqual(self.run_cli("title", project, "--data", data).returncode, 0)
            first = self.run_cli("build", project)
            self.assertEqual(first.returncode, 0, first.stderr)
            output = project / "report.pdf"
            before = output.read_bytes()
            (project / "index.typ").write_text("#let = invalid\n", encoding="utf-8")
            failed = self.run_cli("build", project)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("was not replaced", failed.stderr)
            self.assertEqual(output.read_bytes(), before)

    def test_build_rejects_existing_report_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            data = self.write_data(temp, self.complete_metadata())
            self.assertEqual(self.run_cli("title", project, "--data", data).returncode, 0)
            try:
                (project / "report.pdf").symlink_to(project / "index.typ")
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            result = self.run_cli("build", project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report.pdf", result.stderr)
            self.assertTrue((project / "report.pdf").is_symlink())

    @unittest.skipUnless(shutil.which("typst") and shutil.which("pdftotext"), "Typst and pdftotext are required")
    def test_build_smoke_compiles_fixture_metadata_and_body(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.init_project(temp)
            (project / "index.typ").write_text("= Проверочный отчёт\nТестовая строка.\n", encoding="utf-8")
            data = self.write_data(
                temp,
                self.complete_metadata(title="#let injected = [NO EXECUTION] and ] brackets"),
            )
            self.assertEqual(self.run_cli("title", project, "--data", data).returncode, 0)
            result = self.run_cli("build", project)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = project / "report.pdf"
            self.assertTrue(output.is_file())
            self.assertGreater(output.stat().st_size, 0)
            extracted = subprocess.run(
                ["pdftotext", str(output), "-"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            self.assertIn("#let injected = [NO EXECUTION] and ] brackets", extracted.stdout)
            self.assertIn("Проверочный отчёт", extracted.stdout)
            self.assertIn("Тестовая строка.", extracted.stdout)
            self.assertNotIn("titlepage(", extracted.stdout)
            self.assertNotIn("read(\"../index.typ\")", extracted.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
