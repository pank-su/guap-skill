# GUAP Skills

Skills для работы с личным кабинетом ГУАП и подготовки учебных работ в Hermes,
Claude Code, Codex CLI и OpenCode.

![guap-skill](banner.jpg)

## Возможности

- Задания, дедлайны, материалы и статусы отчётов.
- Предметы, преподаватели, оценки, расписание и объявления.
- Подготовка лабораторных и курсовых: от методички до отчёта и презентации.
- Шаблон отчёта с защищённым титульником ГУАП.

## Установка

```bash
npx skills add pank-su/guap-skill --copy
```

Выбери нужные skills:

- **guap-pro** — личный кабинет, задания и материалы.
- **labflow-guap** — подготовка учебных работ и генератор шаблона ГУАП.
- **guap-coursework-artifacts** — оформление курсовых, диаграмм и презентаций.

Для подготовки учебных работ также установи [Labflow](https://github.com/pank-su/labflow):

```bash
npx skills add pank-su/labflow --copy
```

Для глобальной установки добавь `--global`.

## Личный кабинет

```bash
python3 skills/guap-pro/scripts/guap.py pro check
python3 skills/guap-pro/scripts/guap.py pro tasks --format json
```

В Telegram вход выполняется через временную HTTPS-ссылку после твоего разрешения.
Пароль вводится на странице входа, а не в чате. Если сессия истекла, агент попросит
войти заново. Отправка отчётов и другие изменения требуют отдельного подтверждения.

## Шаблон лабораторной

Для сборки PDF нужен [Typst](https://typst.app/).

```bash
python3 skills/labflow-guap/scripts/guap_template.py init ./my-lab
python3 skills/labflow-guap/scripts/guap_template.py title ./my-lab --data ./title-data.json
python3 skills/labflow-guap/scripts/guap_template.py check ./my-lab
python3 skills/labflow-guap/scripts/guap_template.py build ./my-lab
```

Редактируй текст отчёта в `my-lab/index.typ`. Реквизиты титульника задаются командой
`title` через JSON. Ручные изменения защищённых файлов блокируют сборку.
Готовый отчёт появится в `my-lab/report.pdf`.

[Поля JSON и правила работы с шаблоном](skills/labflow-guap/references/protected-template.md).

## Разработка

```bash
python3 -m unittest discover -s tests -v
```

Проверки сборки PDF используют Typst и `pdftotext` из Poppler.

## Лицензия

MIT
