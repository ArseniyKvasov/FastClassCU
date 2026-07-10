# FastClass — быстрый старт

Весь FastClass запускается из корня репозитория одной командой Docker Compose.
Никаких nginx, certbot или заранее заданного домена в репозитории нет: внешний
домен, TLS и reverse proxy при необходимости настраиваются вне проекта.

## Требования

- Docker Engine и Docker Compose v2 (`docker compose version`)

## Запуск

```bash
cp .env.example .env
# заполните OAuth и замените development-секреты перед публичным запуском
docker compose up --build -d
```

Compose сам создаёт RS256-ключи для `auth-service`, передаёт публичный ключ
остальным сервисам и запускает миграции до старта приложений. Приватный ключ
остаётся только в `auth-service/keys/private.pem` и не коммитится.

Просмотреть состояние контейнеров:

```bash
docker compose ps
docker compose logs -f
```

Остановить стек:

```bash
docker compose down
```

Чтобы вместе с контейнерами удалить данные локальных PostgreSQL:

```bash
docker compose down -v
```

## Что заполнить в `.env`

### Обязательно для публичного запуска

- `PUBLIC_BASE_URL` — URL frontend-service, который видит браузер. OAuth
  callback строится как `<PUBLIC_BASE_URL>/auth/<provider>/callback`. Для
  стандартного локального запуска это `http://localhost:8080`.
- `AUTH_SERVICE_PUBLIC_BASE_URL` — внешний URL auth-service. Браузер сначала
  открывает этот адрес для OAuth login, поэтому он должен быть доступен извне.
- `OAUTH_STATE_SECRET`
- `ANSWERS_SERVICE_CLIENT_SECRET`
- `AI_ASSISTANT_SERVICE_CLIENT_SECRET`
- `COLLABORATION_SERVICE_CLIENT_SECRET`
- `COLLAB_TOKEN_SECRET`
- `WHITEBOARD_JWT_SECRET`, если используется whiteboard.

Сгенерировать значение можно так:

```bash
openssl rand -hex 32
```

При работе по HTTPS также поставьте `COOKIE_SECURE=true`. `COOKIE_DOMAIN`
оставьте пустым, если cookie должна быть привязана только к текущему хосту;
задайте домен только для намеренно общего cookie между поддоменами.

### OAuth и внешние интеграции

- `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET` — включают вход через Яндекс.
- `VK_CLIENT_ID`, `VK_CLIENT_SECRET` — включают вход через VK.
- `LIVEKIT_*` и `WHITEBOARD_*` — нужны только для соответствующих внешних
  сервисов.
- AI provider credentials необязательны, пока `USE_MOCK_PROVIDERS=true`.

Полный список с безопасными локальными дефолтами находится в
[`.env.example`](.env.example).

## Адреса после запуска

Все сервисы опубликованы на host-портах, поэтому их удобно проверять напрямую:

| Сервис | Адрес |
|---|---|
| `frontend-service` | `http://localhost:8080` |
| `auth-service` | `http://localhost:8001` |
| `ai-assistant-service` | `http://localhost:8002` |
| `content-service` | `http://localhost:8003` |
| `classroom-service` | `http://localhost:8004` |
| `assignments-service` | `http://localhost:8005` |
| `answers-service` | `http://localhost:8006` |
| `collaboration-service` | `http://localhost:8007` |
| `analytics-service` | `http://localhost:8010` |

Для большинства сервисов доступны `/health` и `/ready`; у
`collaboration-service` есть `/health` и `/ready`.

Внутри Docker Compose сервисы используют DNS-имена Compose (`auth-service`,
`content-service` и т.д.), а не `localhost`. Поэтому изменение host-портов в
`.env` не ломает их внутреннее взаимодействие.

## Миграции

Миграции выполняются одноразовыми контейнерами автоматически. При необходимости
их можно повторить вручную из корня репозитория:

```bash
docker compose run --rm auth-migrate
docker compose run --rm collaboration-migrate
```

Для остальных сервисов используйте соответствующее имя
`<service>-migrate`.
