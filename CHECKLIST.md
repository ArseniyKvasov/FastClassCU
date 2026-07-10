# FastClass — чек-лист деплоя (Deployment Checklist)

Целевой домен (target domain): `fastclass.culab.ru`. Быстрый локальный
запуск каждого сервиса — в [DEPLOYMENT.md](DEPLOYMENT.md).

Монорепозиторий (monorepo) из 9 независимо деплоящихся сервисов
(8 Python/FastAPI + 1 Node). Публично из интернета должен смотреть **только
`frontend-service`**, остальные — внутренние API за приватной сетью.

## 1. Чек-лист по каждому сервису (per-service checklist)

| Сервис (service) | Публичный URL | Только внутри сети (internal only) | Читает `PORT` из окружения | БД (DB) | Redis | `/health` | `/ready` | Команда миграции (migration command) |
|---|---|---|---|---|---|---|---|---|
| `frontend-service` | `https://fastclass.culab.ru` | — | ✅, по умолчанию (default) 8000 | — | — | ✅ | ✅ | — (нет БД) |
| `auth-service` | — | ✅ | ✅ | Postgres | — | ✅ | ✅ | `alembic upgrade head` (контейнер `auth-migrate`) |
| `content-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`content-migrate`) |
| `classroom-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`classroom-migrate`) |
| `assignments-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`assignments-migrate`) |
| `answers-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`answers-migrate`) |
| `analytics-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`analytics-migrate`) |
| `ai-assistant-service` | — | ✅ | ✅ | Postgres | Redis | ✅ | ✅ | `alembic upgrade head` (`ai-assistant-migrate`) |
| `collaboration-service` | — | ✅ | ✅ (умел изначально / already supported it) | Postgres | Redis | ✅ | ⚠️ только `/health`, `/ready` нет | `npm run migrate` (`collaboration-migrate`) |

Примечания (notes):
- Каждый контейнер слушает порт из `PORT` (fallback — `8000`, если
  переменная не задана; в `docker-compose.yml` она не выставлена, поэтому
  локальная разработка не меняется). На проде `PORT` задаёт сама
  хостинг-платформа.
- Health-эндпоинты — это `/health` (liveness, без проверки зависимостей) и
  `/ready` (readiness, проверяет БД/Redis/ключи). **Не** `/healthz`/`/readyz`
  — пробы (probes) load balancer/оркестратора нужно указывать именно на эти
  пути.
- `answers-service` и `collaboration-service` сегодня не вызываются
  напрямую бэкендом `frontend-service` (см. §2) — только `auth`, `content`,
  `classroom`, `assignments`. Если фронтенд (SPA) в итоге будет ходить к ним
  прямо из браузера (например WebSocket для совместного редактирования) —
  их тоже придётся сделать публичными. Уточнить у того, кто занимается
  фронтенд-интеграцией, прежде чем фиксировать разбиение public/internal
  выше.

## 2. Матрица сетевого доступа (Network access matrix)

Составлена по переменным `*_SERVICE_BASE_URL` из `.env.example` каждого
сервиса.

| Откуда (from) | Куда (to) | Зачем (why) |
|---|---|---|
| `frontend-service` | `auth-service`, `content-service`, `classroom-service`, `assignments-service` | BFF-проксирование для SPA |
| `answers-service` | `content-service`, `auth-service` | получение контента задания/ключа ответа, проверка токенов |
| `assignments-service` | `classroom-service`, `auth-service` | таргетинг заданий, список учеников класса |
| `classroom-service` | `auth-service`, LiveKit (внешний), Whiteboard (внешний) | видеозвонки и доска — оба теперь отдельные репозитории |
| `ai-assistant-service` | `content-service`, `auth-service`, GigaChat, Pollinations, OpenRouter, AI Gateway (Cloudflare Workers) | провайдеры генерации уроков, все внешние |
| `collaboration-service` | `answers-service`, `auth-service`, `classroom-service`, `assignments-service` | синхронизация совместного редактирования (Yjs) |
| `analytics-service` | нет прямых вызовов — читает события из Redis Streams (event bus) | сквозная аналитика по событиям других сервисов |
| `content-service` | `auth-service` (только публичный ключ, без живого запроса) | проверка JWT |
| `auth-service` | Yandex OAuth, VK OAuth (внешние) | вход через соцсети |

## 3. Переменные окружения (environment variables)

Полный список переменных для каждого сервиса — в его собственном
`.env.example`:

`ai-assistant-service/.env.example`, `analytics-service/.env.example`,
`answers-service/.env.example`, `assignments-service/.env.example`,
`auth-service/.env.example`, `classroom-service/.env.example`,
`content-service/.env.example`, `frontend-service/.env.example`,
`collaboration-service/.env.example`.

Во всех уже задокументирована `PORT=8000` — на проде переопределяется
хостинг-платформой при необходимости. Какие переменные обязательно
заполнить руками для конкретных интеграций — см. таблицу в
[DEPLOYMENT.md](DEPLOYMENT.md#что-обязательно-поменять-в-env-required-values).

## 4. Файлы для монтирования (files to mount)

| Путь (path) | Сервисы (services) | Зачем (purpose) |
|---|---|---|
| `.env` | все (all) | секреты и конфиг, никогда не коммитится |
| `keys/public.pem` | `content-service` и `analytics-service` (монтируется напрямую из `../auth-service/keys`), а также свои копии у `frontend-service`, `ai-assistant-service`, `answers-service`, `assignments-service`, `auth-service`, `classroom-service`, `collaboration-service` | локальная проверка RS256 JWT от `auth-service` |
| `keys/private.pem` | только `auth-service` | подпись JWT — никогда не передаётся другим сервисам |
| `auth-service/providers.yaml`, `auth-service/service_clients.yaml` | `auth-service` | конфиг OAuth-провайдеров, реестр service-клиентов |
| `storage/` | `content-service`, `answers-service`, `analytics-service` (экспорты) | загруженные файлы / артефакты экспорта |

Между сервисами расшаривается только публичный ключ; приватный ключ
`auth-service` никогда не покидает его собственный контейнер.

## Порты (ports)

Хост:контейнер (host:container), пригодится и для `curl localhost:<port>/health`:

| Сервис (service) | Порт приложения (app port) | Порт БД (DB port) | Порт Redis |
|---|---|---|---|
| `auth-service` | 8001 | 5433 | — |
| `ai-assistant-service` | 8002 | 5438 | 6385 |
| `content-service` | 8003 | 5434 | 6383 |
| `classroom-service` | 8004 | 5435 | 6380 |
| `assignments-service` | 8005 | 5436 | 6381 |
| `answers-service` | 8006 | 5437 | 6382 |
| `collaboration-service` | 8007 | 5439 | 6384 |
| `analytics-service` | 8010 | 5440 | 6390 |
| `frontend-service` | 8080 | — | — |

## Миграции (migrations)

Каждый сервис с базой данных запускает миграции отдельным одноразовым
контейнером (`<service>-migrate`), который должен успешно завершиться
(`service_completed_successfully`) прежде, чем стартует сам сервис — это
прописано в `depends_on` каждого `docker-compose.yml`. Ни в одном
`Dockerfile` `CMD` миграции больше не запускаются.

Запустить миграции вручную (например, перед раскаткой новой версии без
перезапуска работающего контейнера приложения):

```bash
docker compose run --rm auth-migrate            # или <service>-migrate для любого сервиса
docker compose run --rm collaboration-migrate    # выполняет `npm run migrate`
```

Раньше `collaboration-service` выполнял свои SQL-миграции
(`migrations/001_init.sql` через `runMigrations()`) прямо внутри
`server.ts` при каждом старте процесса — этот вызов убран; миграции теперь
запускаются только из `collaboration-migrate` (`npm run migrate` →
`src/migrate.ts`).

## PORT на проде (PORT in production)

`PORT` должна **выставлять сама хостинг-платформа** (Cloud Run, Render,
Railway, k8s и т.д.). Все Dockerfile по умолчанию используют `8000`, если
`PORT` не задана, поэтому поведение локального `docker compose` не
меняется — переопределять `PORT` нужно только если платформа требует
конкретное значение.
