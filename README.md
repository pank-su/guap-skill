# guap-pro

**Гуаповский Agent Skill для Hermes, Claude Code, Codex CLI и OpenCode.**

`guap-pro` даёт агенту доступ к данным личного кабинета ГУАП и помогает использовать
их вместе с общим workflow [`labflow`](https://github.com/pank-su/labflow).

## Возможности

- задания, дедлайны и статусы отчётов;
- дисциплины и карточки предметов;
- оценки и зачётная книжка;
- расписание;
- объявления;
- преподаватели и связанные references;
- материалы и отчёты;
- правила подготовки к защите по преподавателям и дисциплинам.

Скрипты используют только стандартную библиотеку Python. Установка пакетов и сборка
не нужны. MCP-сервера в репозитории нет.

## Установка

Для Claude Code, Codex CLI и OpenCode запусти команду из каталога проекта или с
`--global` для установки пользователю:

```bash
npx skills add pank-su/guap-skill --skill guap-pro --copy
```

Установщик покажет доступные harness’ы. Выбери нужный инструмент и подтверди
установку через `yes`.

Для Hermes:

```bash
hermes skills install https://raw.githubusercontent.com/pank-su/guap-skill/main/skills/guap-pro/SKILL.md --name guap-pro
```

Подробная инструкция для разных режимов установки находится в
[`INSTALL.md`](INSTALL.md).

## Авторизация

В Telegram Hermes сначала спрашивает разрешение на использование аккаунта ГУАП.
Для удалённого входа используется временная HTTPS-страница в
`scripts/relay.py`. Пользователь вводит пароль сам; relay не сохраняет пароль и
не отправляет его в Telegram. Сессионные cookies хранятся в Hermes home с правами
`0600`.

Для локального запуска CLI достаточно выполнить проверку сессии:

```bash
python3 skills/guap-pro/scripts/guap.py pro check
```

Если ГУАП сбросил сессию, skill возвращает `reauth_required` и просит повторно
авторизоваться. Отправка отчётов и другие изменяющие действия требуют отдельного
подтверждения.

## Связь с labflow

`labflow` остаётся универсальным workflow: контекст задания, код, вычисления,
отчёт и self-review. `guap-pro` добавляет только специфику ГУАП и текущие данные
личного кабинета. Требования вуза не добавляются в общий репозиторий.

## Структура

```text
skills/guap-pro/
├── SKILL.md
├── scripts/
│   ├── guap.py
│   └── relay.py
├── references/
│   ├── teachers/
│   └── subjects/
└── assets/
    └── banner-prompt.md
```

Промпт для генерации баннера: [`assets/banner-prompt.md`](assets/banner-prompt.md).

## Лицензия

MIT
