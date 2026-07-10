# FastClass

> Платформа для создания интерактивных уроков по английскому языку.

FastClass объединяет создание учебных материалов, работу с классами и
заданиями, ответы учеников, совместное редактирование и AI-инструменты в одном
наборе сервисов. Весь проект запускается единым Docker Compose-стеком.

## Возможности

| | |
|---|---|
| 📚 | Создание, хранение и переиспользование уроков и материалов |
| 👥 | Управление классами, учениками и приглашениями |
| 📝 | Назначения, дедлайны и ответы учеников |
| ✍️ | Совместное редактирование письменных работ в реальном времени |
| ✨ | Генерация материалов и подсказок с помощью AI |
| 📊 | Аналитика активности и качества материалов |

## Архитектура

```mermaid
flowchart TB
    Browser([🌐 Браузер]) --> Frontend[Frontend Service<br/>SPA + BFF]

    subgraph Platform[FastClass platform]
        Frontend --> Auth[🔐 Auth Service]
        Frontend --> Content[📚 Content Service]
        Frontend --> Classroom[👥 Classroom Service]
        Frontend --> Assignments[📝 Assignments Service]

        Content --> Answers[✍️ Answers Service]
        Classroom --> Assignments
        Assignments --> Answers
        Answers <--> Collaboration[🤝 Collaboration Service<br/>Yjs / CRDT]

        Content <--> AI[✨ AI Assistant Service]
        Auth -. events .-> Analytics[📊 Analytics Service]
        Content -. events .-> Analytics
        Classroom -. events .-> Analytics
        Assignments -. events .-> Analytics
        Answers -. events .-> Analytics
        AI -. events .-> Analytics
    end

    Auth --> OAuth[OAuth / OIDC providers]
    Classroom --> LiveKit[LiveKit]
    Classroom --> Whiteboard[Whiteboard]
    AI --> LLM[LLM & AI providers]

    classDef entry fill:#2563eb,color:#fff,stroke:#1d4ed8,stroke-width:2px;
    classDef core fill:#eff6ff,color:#1e3a8a,stroke:#60a5fa,stroke-width:1.5px;
    classDef supporting fill:#f0fdf4,color:#14532d,stroke:#4ade80,stroke-width:1.5px;
    classDef external fill:#fff7ed,color:#9a3412,stroke:#fb923c,stroke-width:1.5px;

    class Browser,Frontend entry;
    class Auth,Content,Classroom,Assignments,Answers,Collaboration,AI,Analytics core;
    class OAuth,LiveKit,Whiteboard,LLM external;
```

> Сплошные линии обозначают синхронные API-вызовы, пунктирные — события,
> поступающие в аналитический контур.

## Сервисы

| Сервис | Назначение |
|---|---|
| **Auth Service** | Идентификация пользователей: гостевой доступ и вход через подключаемых OAuth/OIDC-провайдеров. Поддерживаются Yandex и VK; другие провайдеры, включая CU ID, добавляются конфигурацией. |
| **Frontend Service** | Точка входа для браузера и BFF-слой: раздаёт frontend, хранит сессию в HTTP-only cookie и проксирует запросы к API. |
| **Content Service** | Управляет учебными материалами: уроками, копиями, файлами и обработкой загруженных материалов. |
| **Classroom Service** | Управляет классами и составом учеников; интегрируется с внешними whiteboard- и LiveKit-сервисами. |
| **Assignments Service** | Назначает материалы ученикам и классам, отслеживает дедлайны и отправляет уведомления через WebSocket. |
| **Answers Service** | Хранит ответы, черновики и статусы сдачи, принимает снимки совместного редактирования. |
| **Collaboration Service** | Обеспечивает совместное редактирование письменных ответов в реальном времени на базе Yjs/CRDT. |
| **AI Assistant Service** | Создаёт учебный контент с помощью LLM: черновики уроков, подсказки, изображения и результаты AI-генераций. |
| **Analytics Service** | Собирает аналитику пользовательской активности и качества материалов для администраторов. |

## Быстрый запуск

**Требования:** Docker Engine и Docker Compose v2.

```bash
# 1. Создать runtime-конфигурацию
cp .env.example .env

# 2. Указать OAuth-данные и заменить development-секреты перед публичным запуском

# 3. Собрать и запустить весь стек
docker compose up --build -d
```

Compose автоматически создаёт JWT-ключи и выполняет миграции БД до старта
приложений.

### Полезные команды

```bash
# Состояние контейнеров
docker compose ps

# Логи всего стека
docker compose logs -f

# Логи одного сервиса
docker compose logs -f frontend-service

# Остановить стек
docker compose down

# Остановить стек и удалить локальные данные PostgreSQL
docker compose down -v
```

После запуска frontend по умолчанию доступен по адресу
[`http://localhost:8080`](http://localhost:8080).

## Конфигурация

Единый конфигурационный файл — [`.env.example`](.env.example). В нём задаются:

- OAuth-провайдеры и публичные URL;
- секреты межсервисного взаимодействия;
- cookie и CORS;
- host-порты;
- LiveKit, Whiteboard и AI-интеграции;
- OpenTelemetry.

Перед размещением в публичной среде обязательно замените все development-секреты
случайными значениями, укажите публичные `PUBLIC_BASE_URL` и
`AUTH_SERVICE_PUBLIC_BASE_URL`, а для HTTPS включите `COOKIE_SECURE=true`.

Подробнее по инфраструктурным требованиям — в [CHECKLIST.md](CHECKLIST.md).

## Контакты

По вопросам проекта: Telegram [@Arseniy1904](https://t.me/Arseniy1904).
