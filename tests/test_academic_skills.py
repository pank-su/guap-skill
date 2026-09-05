"""Offline contracts for the GUAP academic adapter and source references."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AcademicSkillContractTests(unittest.TestCase):
    def test_teacher_and_subject_notes_have_no_confidence_badges(self):
        references = ROOT / 'skills' / 'labflow-guap' / 'references'
        files = []
        for directory in ('teachers', 'subjects'):
            self.assertFalse((ROOT / 'skills' / 'guap-pro' / 'references' / directory).exists())
            self.assertTrue((references / directory / 'index.md').is_file())
            files.extend(sorted((references / directory).glob('*.md')))
        self.assertTrue(files)
        for path in files:
            with self.subTest(path=str(path.relative_to(ROOT))):
                self.assertIsNone(re.search(
                    r'\b(verified|confirmed|observed|user_note)\b|Evidence status',
                    path.read_text(encoding='utf-8'), re.I))

    def test_canonical_template_bytes_match_source_manifest(self):
        assets = ROOT / 'skills' / 'labflow-guap' / 'assets' / 'guap'
        manifest = json.loads((assets / 'source.json').read_text(encoding='utf-8'))
        self.assertEqual(set(manifest['files']), {'titlepage.typ', 'gost.typ'})
        for name, expected in manifest['files'].items():
            data = (assets / name).read_bytes()
            self.assertTrue(data)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected)

    def test_all_shipped_related_skills_resolve(self):
        skills = ROOT / 'skills'
        names = {path.parent.name for path in skills.glob('*/SKILL.md')}
        for path in skills.glob('*/SKILL.md'):
            text = path.read_text(encoding='utf-8')
            self.assertTrue(text.startswith('---\n'))
            frontmatter = text.split('---', 2)[1]
            match = re.search(r'related_skills:\s*\[([^\]]*)\]', frontmatter)
            if match:
                related = {item.strip() for item in match.group(1).split(',') if item.strip()}
                self.assertFalse(related - names, (str(path), related - names))


def load_tests(loader, tests, pattern):
    script = ROOT / 'skills' / 'labflow-guap' / 'scripts' / 'test_guap_template.py'
    spec = importlib.util.spec_from_file_location('guap_template_script_tests', script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests.addTests(loader.loadTestsFromModule(module))
    return tests


if __name__ == '__main__':
    unittest.main()
