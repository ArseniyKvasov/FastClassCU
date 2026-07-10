# FastClass — чек-лист запуска

Быстрый запуск всего монорепозитория описан в [DEPLOYMENT.md](DEPLOYMENT.md).
Стек не привязан к конкретному домену, nginx или TLS-провайдеру: эти элементы
настраиваются снаружи, если нужны для конкретного окружения.

## Сервисы

| Сервис | Host-порт по умолчанию | БД | Redis | Health endpoints | Миграции |
|---|---:|---|---|---|---|
| `frontend-service` | 8080 | — | — | `/health`, `/ready` | — |
| `auth-service` | 8001 | Postgres | Redis | `/health`, `/ready` | `auth-migrate` |
| `ai-assistant-service` | 8002 | Postgres | Redis | `/health`, `/ready` | `ai-assistant-migrate` |
| `content-service` | 8003 | Postgres | Redis | `/health`, `/ready` | `content-migrate` |
| `classroom-service` | 8004 | Postgres | Redis | `/health`, `/ready` | `classroom-migrate` |
| `assignments-service` | 8005 | Postgres | Redis | `/health`, `/ready` | `assignments-migrate` |
| `answers-service` | 8006 | Postgres | Redis | `/health`, `/ready` | `answers-migrate` |
| `collaboration-service` | 8007 | Postgres | Redis | `/health`, `/ready` | `collaboration-migrate` |
| `analytics-service` | 8010 | Postgres | Redis | `/health`, `/ready` | `analytics-migrate` |

Все порты настраиваются в корневом `.env`. Приложения внутри контейнеров всегда
слушают `8000`, а Compose публикует назначенный host-порт.

## Сеть

Все сервисы опубликованы на localhost для разработки и диагностики, но их
внутренние запросы идут по Docker DNS:

| Откуда | Куда | Назначение |
|---|---|---|
| `frontend-service` | `auth-service`, `content-service`, `classroom-service`, `assignments-service` | BFF API для SPA |
| `answers-service` | `content-service`, `auth-service`, `classroom-service`, `assignments-service` | ответы и авторизация |
| `assignments-service` | `classroom-service` | проверка участников класса |
| `ai-assistant-service` | `content-service`, `auth-service` | создание уроков |
| `collaboration-service` | `answers-service`, `auth-service`, `classroom-service`, `assignments-service` | совместное редактирование |
| все event producers/consumers | `analytics-redis` | Redis Streams event bus |

## Файлы данных

- `.env` — единственный runtime-конфиг всего стека; не коммитится.
- `auth-service/keys/private.pem` — ключ подписи JWT; принадлежит только
  auth-сервису и не коммитится.
- `auth-service/keys/public.pem` — публичный ключ, монтируется read-only во
  все сервисы, которым он нужен.
- `content-service/storage`, `answers-service/storage`,
  `analytics-service/storage` — локальные хранилища файлов.

## Публичное окружение

Перед публикацией:

1. Замените development-секреты в корневом `.env` случайными значениями.
2. Укажите фактический browser URL в `PUBLIC_BASE_URL`.
3. Включите `COOKIE_SECURE=true` для HTTPS.
4. При необходимости задайте `COOKIE_DOMAIN`, `CORS_ORIGINS` и
   `PUBLIC_WS_BASE_URL` для вашей схемы доменов и reverse proxy.
5. Настройте внешний TLS/reverse proxy отдельно от репозитория.
