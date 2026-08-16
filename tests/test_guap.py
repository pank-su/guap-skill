from __future__ import annotations

import importlib.util
import sys
import unittest
from unittest.mock import patch
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/guap-pro/scripts/guap.py"
spec = importlib.util.spec_from_file_location("guap_cli", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ParserTests(unittest.TestCase):
    def test_task_list(self) -> None:
        html = """
        <table><tr><th>head</th></tr>
        <tr>
          <td><a href='/inside/student/tasks/123'>open</a></td>
          <td><a href='/inside/students/subjects/7'>Math</a></td><td>1</td>
          <td><a>Lab 1</a></td><td>—</td><td>0/5</td><td>Лабораторная работа</td>
          <td>20.03.2026</td><td>today</td><td><a href='/inside/profile/9'>Teacher</a></td>
        </tr></table>
        """
        result = module.parse_tasks(html)
        self.assertEqual(result[0]["id"], 123)
        self.assertEqual(result[0]["subject"], "Math")
        self.assertEqual(result[0]["points_max"], "5")

    def test_task_detail(self) -> None:
        html = """
        <h3 class='page__title'>Lab 1</h3>
        <h5>Тип: <span>Лабораторная работа</span></h5>
        <h5>Семестр: <span>2025/2026</span></h5>
        <h5>Предельная дата выполнения: <span>20.03.2026</span></h5>
        <h5>Описание задания</h5><p>Explain the method.</p>
        """
        result = module.parse_task(html, 123)
        self.assertEqual(result["id"], 123)
        self.assertEqual(result["deadline"], "20.03.2026")
        self.assertEqual(result["description"], "Explain the method.")

    def test_materials_and_profile(self) -> None:
        materials = module.parse_materials(
            "<table><tr><td><a href='/download/1'>file</a></td><td>Math</td><td>Guide</td><td>today</td><td>Teacher</td></tr></table>"
        )
        self.assertEqual(materials[0]["name"], "Guide")
        profile = module.parse_profile("<h3 class='text-center'>Student</h3><h5>Группа: <span>M412</span></h5>")
        self.assertEqual(profile["full_name"], "Student")
        self.assertEqual(profile["Группа"], "M412")

    def test_subjects_from_cards(self) -> None:
        html = """
        <div class='card shadow-sm mb-2'><div class='card-body'>
          <div class='float-end'><small>Экзамен</small><span>2026</span><span>осенний</span></div>
          <h5><a href='/inside/students/subjects/42'>Механика</a></h5>
          <p>Преподаватели: <a href='/inside/profile/7'>Иванов И.И.</a></p>
        </div></div>
        """
        result = module.parse_subjects(html)
        self.assertEqual(result[0]["id"], 42)
        self.assertEqual(result[0]["name"], "Механика")
        self.assertEqual(result[0]["type"], "Экзамен")
        self.assertEqual(result[0]["teachers"][0]["name"], "Иванов И.И.")

    def test_generic_table_records_map_headers(self) -> None:
        html = """
        <table><tr><th>Дисциплина</th><th>Оценка</th><th>Преподаватель</th></tr>
        <tr><td>Математика</td><td>5</td><td>Иванов И.И.</td></tr></table>
        """
        result = module.parse_table_records(html)
        self.assertEqual(result, [{"discipline": "Математика", "mark": "5", "teacher": "Иванов И.И."}])

    def test_schedule_records_preserve_date_and_rows(self) -> None:
        html = """
        <h3>Расписание занятий</h3>
        <table><tr><th>Пара</th><th>Время</th><th>Дисциплина</th></tr>
        <tr><td>1</td><td>09:00</td><td>Механика</td></tr></table>
        """
        result = module.parse_schedule(html, "2026-08-16")
        self.assertEqual(result["date"], "2026-08-16")
        self.assertEqual(result["lessons"][0]["discipline"], "Механика")

    def test_reports_and_notices_are_read_only_records(self) -> None:
        reports = module.parse_reports(
            "<table><tr><th>№</th><th>Задание</th><th>Статус</th></tr>"
            "<tr><td>1</td><td>Лабораторная</td><td>принят</td></tr></table>"
        )
        self.assertEqual(reports[0]["status"], "принят")
        notices = module.parse_notices(
            "<div class='card'><div class='card-header'>Важное</div>"
            "<div class='card-body'><h5>Срок сдачи</h5><p>До пятницы</p></div></div>"
        )
        self.assertEqual(notices[0]["title"], "Срок сдачи")

    def test_marks_from_grade_cards(self) -> None:
        html = """
        <div class='card shadow-sm mb-2'><div class='card-body'>
          <h5><a href='/inside/students/subjects/42'>Механика</a></h5>
          <div><div><span>5 семестр</span></div></div>
          <div><label>Тип контроля:</label><span>Экзамен</span></div>
          <div><label>Оценка:</label><span>отлично</span></div>
          <div><label>Преподаватель:</label><span>Иванов И.И.</span></div>
          <div><label>Дата сдачи экзамена/зачета:</label><span>03.10.2024</span></div>
          <div><label>З.Е.:</label><span>4</span></div>
        </div></div>
        """
        result = module.parse_marks(html)
        self.assertEqual(result[0]["subject"], "Механика")
        self.assertEqual(result[0]["mark"], "отлично")
        self.assertEqual(result[0]["semester"], 5)

    def test_subjects_command_uses_read_only_endpoint(self) -> None:
        with patch.object(module, "request", return_value="<div class='card'><h5><a href='/inside/students/subjects/42'>Механика</a></h5></div>") as request, patch.object(module, "output") as output:
            self.assertEqual(module.main(["pro", "subjects", "--format", "json"]), 0)
            request.assert_called_once_with("/inside/students/subjects", {})
            output.assert_called_once()

    def test_schedule_command_passes_date_and_filters(self) -> None:
        with patch.object(module, "request", return_value="<table><tr><th>Пара</th></tr></table>") as request, patch.object(module, "output"):
            self.assertEqual(module.main(["pro", "schedule", "--date", "2026-08-16", "--group", "215"]), 0)
            request.assert_called_once_with("/inside/students/classes/schedule/day/2026-08-16", {"group": 215})


if __name__ == "__main__":
    unittest.main()
