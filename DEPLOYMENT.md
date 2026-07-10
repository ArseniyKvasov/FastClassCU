# FastClass — быстрый старт (Quick Start)

Инструкция по локальному запуску каждого из 9 сервисов через Docker Compose.
Чек-лист для деплоя (URL, сеть, ресурсы и т.д.) — в отдельном файле
[CHECKLIST.md](CHECKLIST.md).

## Требования (Prerequisites)

- Docker + Docker Compose v2 (`docker compose version`)

## Шаг 0. Сгенерировать JWT-ключи (один раз на весь проект)

Все сервисы проверяют JWT-токены пользователей публичным ключом
`auth-service`, поэтому ключи нужны раньше всего. `keys/` во всех сервисах
в `.gitignore` — их нет в свежем клоне репозитория, сгенерировать нужно
самому:

```bash
cd auth-service
docker run --rm -v "$(pwd):/app" -w /app python:3.12-slim \
  sh -c "pip install --quiet cryptography && python scripts/generate_keys.py"
```

Это создаст `auth-service/keys/private.pem` (приватный, только для
`auth-service`, никому не передавать) и `auth-service/keys/public.pem`
(публичный).

Скопируйте `public.pem` в `keys/` каждого сервиса, который проверяет
JWT-токены сам (у `content-service` и `analytics-service` это не нужно — их
`docker-compose.yml` уже монтирует ключ напрямую из `auth-service/keys`):

```bash
for svc in ai-assistant-service answers-service assignments-service \
           classroom-service frontend-service collaboration-service; do
  mkdir -p "../$svc/keys"
  cp keys/public.pem "../$svc/keys/public.pem"
done
```

## Общие принципы

- Приложение слушает порт из переменной `PORT` (по умолчанию `8000` внутри
  контейнера); наружу `docker-compose.yml` пробрасывает свой порт для
  каждого сервиса — таблица портов в
  [CHECKLIST.md § Порты](CHECKLIST.md#порты-ports).
- Собранный образ автоматически сначала прогонит миграции БД в отдельном
  одноразовом контейнере (`<service>-migrate`), и только потом стартует сам
  сервис — подробнее в
  [CHECKLIST.md § Миграции](CHECKLIST.md#миграции-migrations).
- `DATABASE_URL`, `REDIS_URL`, `EVENT_BUS_REDIS_URL` и т.п. уже настроены на
  имена контейнеров (`db`, `redis`) внутри docker-сети каждого сервиса —
  трогать не нужно.
- Ключи для service-to-service JWT (`SERVICE_CLIENT_SECRET` у вызывающего
  сервиса и соответствующий `<SERVICE>_SERVICE_CLIENT_SECRET` в
  `auth-service/.env`) должны совпадать — сгенерируйте любую случайную
  строку и подставьте в оба места. Ниже это отмечено отдельно там, где
  применимо.

## Порядок запуска (Startup order)

Жёсткого требования нет (переменные с адресами других сервисов читаются
лениво, при обращении, а не при старте), но для первого локального прогона
удобно поднимать в таком порядке: `auth-service` → остальные внутренние
сервисы в любом порядке → `frontend-service` последним.

---

## 1. `auth-service`

```bash
cd auth-service
cp .env.example .env
cp providers.yaml.example providers.yaml
```

`providers.yaml` в `.gitignore` (это реальный конфиг OAuth-провайдеров, не
секрет сам по себе — секреты в нём подставляются из `.env` через
`${YANDEX_CLIENT_ID}` и т.п.), поэтому на свежем клоне его нет — `Dockerfile`
не соберётся без этого шага.

Переменные для заполнения в `.env` (остальное уже рабочий дефолт для
локальной разработки):

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `YANDEX_CLIENT_ID`, `YANDEX_CLIENT_SECRET` | нет | вход через Яндекс (Yandex OAuth); без них просто не будет этой кнопки входа |
| `VK_CLIENT_ID`, `VK_CLIENT_SECRET` | нет | вход через VK (VK OAuth) |
| `ANSWERS_SERVICE_CLIENT_SECRET` | да, если запускаете `answers-service` | должна совпадать с `SERVICE_CLIENT_SECRET` в `answers-service/.env` |
| `AI_ASSISTANT_SERVICE_CLIENT_SECRET` | да, если запускаете `ai-assistant-service` | должна совпадать с `SERVICE_CLIENT_SECRET` в `ai-assistant-service/.env` |
| `COLLABORATION_SERVICE_CLIENT_SECRET` | да, если запускаете `collaboration-service` | должна совпадать с `SERVICE_CLIENT_SECRET` в `collaboration-service/.env` |
| `OAUTH_STATE_SECRET` | рекомендуется сменить | по умолчанию `dev-insecure-change-me` — для прод-развёртывания заменить на случайную строку |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | нет | адрес OpenTelemetry-коллектора; пусто = трейсинг выключен |

```bash
docker compose up --build
curl http://localhost:8001/health
curl http://localhost:8001/ready
```

---

## 2. `ai-assistant-service`

```bash
cd ai-assistant-service
cp .env.example .env
```

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `SERVICE_CLIENT_SECRET` | да | должна совпадать с `AI_ASSISTANT_SERVICE_CLIENT_SECRET` в `auth-service/.env` |
| `GIGACHAT_CLIENT_ID`, `GIGACHAT_CLIENT_SECRET` | нет | резервный провайдер генерации (GigaChat); при `USE_MOCK_PROVIDERS=true` (дефолт) не нужны вовсе |
| `POLLINATIONS_API_KEY`, `OPENROUTER_API_KEY`, `FLUX_BASE_URL`, `FLUX_API_KEY` | нет | провайдеры генерации изображений |
| `AI_GATEWAY_URL`, `AI_GATEWAY_SECRET` | нет | Cloudflare AI Gateway (проксирует часть провайдеров) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | нет | адрес OpenTelemetry-коллектора |

```bash
docker compose up --build
curl http://localhost:8002/health
curl http://localhost:8002/ready
```

---

## 3. `content-service`

```bash
cd content-service
cp .env.example .env
```

Пустых переменных, требующих ручного заполнения, нет — кроме опционального
`OTEL_EXPORTER_OTLP_ENDPOINT` (адрес OpenTelemetry-коллектора, можно
оставить пустым). Ключ (`keys/public.pem`) сервис берёт напрямую из
`../auth-service/keys` — отдельно копировать не нужно (см. Шаг 0).

```bash
docker compose up --build
curl http://localhost:8003/health
curl http://localhost:8003/ready
```

---

## 4. `classroom-service`

```bash
cd classroom-service
cp .env.example .env
```

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | нет | видеозвонки (LiveKit — отдельный репозиторий/сервис); без них видеозвонки не заработают, но сервис запустится |
| `WHITEBOARD_SERVICE_API_KEY` | нет | интеграция с доской (Whiteboard — отдельный репозиторий/сервис) |
| `WHITEBOARD_JWT_SECRET` | рекомендуется сменить | по умолчанию `dev-insecure-change-me` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | нет | адрес OpenTelemetry-коллектора |

```bash
docker compose up --build
curl http://localhost:8004/health
curl http://localhost:8004/ready
```

---

## 5. `assignments-service`

```bash
cd assignments-service
cp .env.example .env
```

Пустых переменных, требующих ручного заполнения, нет — кроме опционального
`OTEL_EXPORTER_OTLP_ENDPOINT`.

```bash
docker compose up --build
curl http://localhost:8005/health
curl http://localhost:8005/ready
```

---

## 6. `answers-service`

```bash
cd answers-service
cp .env.example .env
```

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `SERVICE_CLIENT_SECRET` | да | должна совпадать с `ANSWERS_SERVICE_CLIENT_SECRET` в `auth-service/.env` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | нет | адрес OpenTelemetry-коллектора |

```bash
docker compose up --build
curl http://localhost:8006/health
curl http://localhost:8006/ready
```

---

## 7. `collaboration-service`

```bash
cd collaboration-service
cp .env.example .env
```

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `SERVICE_CLIENT_SECRET` | да | должна совпадать с `COLLABORATION_SERVICE_CLIENT_SECRET` в `auth-service/.env` |
| `COLLAB_TOKEN_SECRET` | рекомендуется сменить | по умолчанию `replace-me` |
| `CORS_ORIGINS` | да, если фронтенд обращается напрямую | адрес(а) SPA, которым разрешён доступ к WebSocket |

```bash
docker compose up --build
curl http://localhost:8007/health
```

⚠️ У `collaboration-service` нет эндпоинта `/ready`, только `/health`.

---

## 8. `analytics-service`

```bash
cd analytics-service
cp .env.example .env
```

Пустых переменных, требующих ручного заполнения, нет — кроме опционального
`OTEL_EXPORTER_OTLP_ENDPOINT`. Ключ (`keys/public.pem`) сервис берёт
напрямую из `../auth-service/keys` — отдельно копировать не нужно
(см. Шаг 0).

```bash
docker compose up --build
curl http://localhost:8010/health
curl http://localhost:8010/ready
```

---

## 9. `frontend-service` (запускать последним)

```bash
cd frontend-service
cp .env.example .env
```

| Переменная (variable) | Обязательна? | Для чего |
|---|---|---|
| `CORS_ALLOW_ORIGINS` | нет | нужен, только если фронтенд обращается с другого домена, чем сам `frontend-service` |
| `COOKIE_DOMAIN` | да, на проде | домен, для которого будут выставляться cookie сессии (`fastclass.culab.ru`) |
| `COOKIE_SECURE` | да, на проде | сменить `false` → `true`, сервис работает по HTTPS |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | нет | адрес OpenTelemetry-коллектора |

```bash
docker compose up --build
curl http://localhost:8080/health
curl http://localhost:8080/ready
```
