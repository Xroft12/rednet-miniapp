# Айрин ♥ RedNET MiniApp

Красивый быстрый Telegram Mini App / web-лаунчер для доступа к безопасным командам Hermes и сценариям RedNET.

## Что внутри

- мобильный тёмный UI в стиле RedNET operator center;
- поиск команд и сценариев;
- категории: Hermes, Настройки, Автоматизация, Админка, Секреты, RedNET, Дом, Работа, Медиа;
- отдельный админский блок: gateway, логи, очереди, сеть, MiniApp, Docker-агенты, локальный резерв, портал, публикация VK/Google;
- безопасная передача одноразового секрета агенту с TTL, целью, типом, подтверждением и очисткой формы;
- избранное через `localStorage`;
- командная палитра `Ctrl/⌘ + K`;
- Telegram WebApp payload через `Telegram.WebApp.sendData(JSON.stringify(...))`;
- локальный fallback: кнопка **Отправить** копирует JSON-намерение, кнопка **Копировать** копирует человекочитаемую команду;
- защитный confirm для `danger`-команд;
- все админские действия являются намерениями для агента, а не прямым выполнением системных операций.

## Payload contract

MiniApp не отправляет shell и не выполняет команды сам. Он отправляет намерение:

```json
{
  "source": "rednet-miniapp",
  "type": "command",
  "id": "status",
  "command": "/status",
  "title": "Статус сессии",
  "safety": "safe",
  "ts": "2026-06-09T00:00:00.000Z"
}
```

Hermes Telegram gateway уже умеет принимать `web_app_data`, нормализовать payload и прокидывать результат в обычный gateway-pipeline. Для `safety: danger` он превращает запрос в текст с требованием явного подтверждения Ивана, а не исполняет рискованное действие напрямую.

Для одноразового секрета используется отдельный payload:

```json
{
  "source": "rednet-miniapp",
  "type": "secret_transfer",
  "id": "secret-transfer",
  "title": "Одноразовая передача секрета",
  "safety": "secret",
  "ephemeral": true,
  "ttl_seconds": 900,
  "target": "airin",
  "secret_kind": "password",
  "message": "Одноразовый секрет для агента...",
  "ts": "2026-06-09T00:00:00.000Z"
}
```

MiniApp не сохраняет значение секрета в `localStorage`, очищает поле после отправки, при скрытии страницы и по ручной кнопке **Очистить**. При этом важно: если секрет отправлен через Telegram WebApp, он уже попадает в текущий агентский контур и должен обрабатываться агентом по протоколу одноразового использования.

## Локальный запуск

Из папки проекта:

```bash
python -m http.server 8787
```

Открыть:

```text
http://127.0.0.1:8787/
```

## Проверка

```bash
python scripts/verify-miniapp.py
```

Проверка делает:

- наличие `index.html` / `manifest.webmanifest`;
- проверку обязательных Telegram WebApp маркеров;
- проверку админского реестра и контура одноразового секрета;
- извлечение inline JS и `node --check`;
- подсчёт каталога команд.

## Установка в Telegram bot menu

Нужен публичный HTTPS URL MiniApp. После деплоя:

```bash
python scripts/install-telegram-menu.py https://xroft12.github.io/rednet-miniapp/
```

Скрипт берёт `TELEGRAM_BOT_TOKEN` только из окружения или Hermes `.env`, не печатает токен, вызывает Telegram Bot API `setChatMenuButton`, затем проверяет через `getChatMenuButton`.

## Деплой на GitHub Pages

Ожидаемый URL после публикации:

```text
https://xroft12.github.io/rednet-miniapp/
```

Минимальная последовательность:

```bash
git init
git add .
git commit -m "feat: add RedNET Telegram MiniApp launcher"
gh repo create Xroft12/rednet-miniapp --public --source=. --remote=origin --push
gh api repos/Xroft12/rednet-miniapp/pages -X POST -f 'source[branch]=main' -f 'source[path]=/'
```

Если Pages уже включён, достаточно push в `main` и дождаться обновления.

## Безопасность

- Секретов, токенов и паролей в MiniApp нет.
- Значения, введенные в форму секрета, не пишутся в `localStorage` и не остаются в DOM после очистки.
- Browser/frontend не является источником авторизации.
- Рискованные действия требуют backend-side подтверждения Ивана.
- Перезапуск Hermes Gateway не должен идти через прямой `/restart` без явного разрешения; в RedNET используется безопасный внешний запускатель.
