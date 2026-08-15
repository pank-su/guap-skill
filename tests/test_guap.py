from __future__ import annotations

import unittest

from guap import materials_list, profile_data, task_detail, task_list


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
        result = task_list(html)
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
        result = task_detail(html, 123)
        self.assertEqual(result["id"], 123)
        self.assertEqual(result["deadline"], "20.03.2026")
        self.assertEqual(result["description"], "Explain the method.")

    def test_materials_and_profile(self) -> None:
        materials = materials_list(
            "<table><tr><td><a href='/download/1'>file</a></td><td>Math</td><td>Guide</td><td>today</td><td>Teacher</td></tr></table>"
        )
        self.assertEqual(materials[0]["name"], "Guide")
        profile = profile_data("<h3 class='text-center'>Student</h3><h5>Группа: <span>M412</span></h5>")
        self.assertEqual(profile["full_name"], "Student")
        self.assertEqual(profile["Группа"], "M412")


if __name__ == "__main__":
    unittest.main()
