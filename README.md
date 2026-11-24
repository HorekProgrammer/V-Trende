# Веб-сервис для сбора и отображения популярных трендов

## Проблема

Современный человек хочет быть в курсе того, что сейчас популярно, но вынужден собирать эту информацию по десяткам разрозненных сайтов и приложений. На это уходит время, а часть трендов всё равно остаётся незамеченной. В результате пользователь либо тратит часы на поиск, либо пропускает важное.

## Требования

### Пользовательские сценарии

1. Пользователь заходит на главную страницу сайта, на которой располагается единая лента актуальных трендов из различных сфер, прокручивает страницу вниз, чтобы ознакомиться с полным списком, включающим музыку, игры, фильмы и стримеров. В результате пользователь получает список наиболее обсуждаемых событий и может быстро узнать, что сейчас пользуется наибольшей популярностью.

2. Пользователь заходит на главную страницу сайта. Он нажимает на выпадающий список категорий в верхней части страницы и выбирает «Игры». Открывается страница с трендами по категории «Игры».  Затем пользователь нажимает на кнопку «По новизне» в поле фильтров. В результате пользователь получает список актуальных игровых трендов, упорядоченных по времени появления, что позволяет ему быстрее найти подходящие и релевантные инфоповоды.

3. Пользователь, находясь на странице с трендами по категории «Фильмы» нажимает на карточку тренда и переходит на страницу, с детальным описанием конкретного тренда. Пользователь может видеть график изменения его популярности за определенный период. В результате пользователь может оценить, насколько событие сохраняет актуальность, понять растет ли к нему интерес или постепенно угасает.

### Масштаб системы

Оценка нагрузки составляет от 10 000 уникальных пользователей в сутки.

### Отказоустойчивость

Для обеспечения стабильности работы системы при сбоях внешних источников, мы применили Circuit Breaker и кэширование. 
Circuit Breaker позволяет избежать бесконечных повторных запросов к недоступному API. Если API становится недоступным, мы прекращаем попытки обращения после определённого количества неудачных запросов. Далее система периодически проверяет состояние API: если оно восстановилось и работает стабильно, то возобновляем нормальную работу. Если нет - продолжаем ждать с заданным интервалом.
Кэширование в этом случае выступает как страховка. При недоступности API мы отдаём последние актуальные данные (например, за предыдущий день). Circuit Breaker параллельно продолжает проверять восстановление соединения. Поскольку тренды у нас обновляются раз в неделю, такой подход не должен создавать критических проблем с актуальностью данных.

## Разработка архитектуры и детальное проектирование

### Анализ нагрузок

#### Расчет соотношения

Количество уникальных пользователей ≈ 10000

Среднее число сессий на пользователя ≈ 1.3

Среднее число просмотров страниц за сессию ≈ 4

Всего просмотров страниц в сутки = 10000 * 1.3 * 4 = 52000

К Read относится: просмотр главной ленты трендов, просмотр ленты по категории и сортировка, открытие страницы конкретного тренда, запрос истории популярности (график), повторные запросы при обновлении страницы.

Средний Read RPS = 52000 / 86400 = 0.6 запросов в секунду.

Пиковый с коэффициентом 5 = 3 запроса в секунду.

К Write относится: обновление текущих трендов и запись истории популярности. Еженедельное пакетное обновление трендов парсерами (300 объектов в неделю: 100 треков, 100 игр, 50 фильмов, 50 стримеров). Запись производится батчами раз в 7 дней и создает околонулевую постоянную нагрузку.

Исходя из этого 90–95% Read / 5–10% Write

#### Расчет объемов сетевого трафика

Запросов в сутки ≈ 52000

Средний размер одного ответа ≈ 20 КБ

52000 * 20 КБ = 1040000 ≈ 1.04 ГБ

Возьмем запас для возможных картинок / превью, повторные запросы и рост среднего размера ответа – ориентировочный исходящий трафик ≈ 1.5–2 ГБ в сутки. Требуемая средняя пропускная способность сети: (2 ГБ * 8 бит) / 86 400 сек ≈ 0.185 Мбит/с.

#### Расчет объемов дисковой системы

Размер одной строки записи ≈ 150 байт

300 трендов  *  52 недели  = 15600 записей за год

15600 * 5 = 78000 записей за 5 лет

78000 * 150 ≈ 11.16 Мб – общая история за 5 лет

### Архитектурные схемы

#### Context diagram

```mermaid
graph TB
    User("Пользователь<br/> [Person]")

    System{{"В Чарте<br/>[Software System]<br/>Веб-сервис для сбора<br/>и отображения трендов"}}

    Wordstat["API Вордстат<br/>[Software System]<br/>Аналитика поисковых<br/>запросов"]

    Music["Музыкальные платформы<br/>[Software System]<br/>Яндекс.Музыка, Звук,<br/>Shazam, VK"]

    Movie["Киноплатформы<br/>[Software System]<br/>Кинопоиск"]

    Game["Игровые платформы<br/>[Software System]<br/>Steam, Epic Games Store"]

    Stream["Стриминг<br/>[Software System]<br/>TwitchTracker"]

    User -.->|Просматривает тренды<br/>и графики| System

    System -.->|Запрашивает популярность<br/>ключевых слов| Wordstat
    System -.->|Собирает данные<br/>раз в неделю| Music
    System -.->|Собирает данные<br/>раз в неделю| Movie
    System -.->|Собирает данные<br/>раз в неделю| Game
    System -.->|Собирает данные<br/>раз в неделю| Stream

    style User fill:none,stroke:#06d6a0,stroke-width:3px
    style System fill:none,stroke:#A100FF,stroke-width:3px
    style Wordstat fill:none,stroke:#2757F5,stroke-width:3px
    style Music fill:none,stroke:#2757F5,stroke-width:3px
    style Movie fill:none,stroke:#2757F5,stroke-width:3px
    style Game fill:none,stroke:#2757F5,stroke-width:3px
    style Stream fill:none,stroke:#2757F5,stroke-width:3px

```

#### Container diagram

```mermaid
graph LR
    User("Пользователь<br/>[Person]")

    subgraph VCharte["В Чарте"]
        Frontend["Frontend<br/>[Container: JavaScript + React]<br/>Веб-интерфейс"]

        Parser["Parser / Worker<br/>[Container: Python + Playwright]<br/>Автономный скрипт еженедельного сбора данных"]

        Backend["Backend API<br/>[Container: Python]<br/>Обработка запросов,<br/>Circuit Breaker"]

        DB["Database<br/>[Container: PostgreSQL]<br/>Хранение данных пользователей и трендов"]
    end

    External["Внешние источники<br/>[External System]<br/>Яндекс, Кинопоиск,<br/>Steam, Twitch, Wordstat"]

    User -.->|Заходит на сайт| Frontend
    Frontend -->|Запрашивает данные| Backend
    Backend -->|Отдаёт данные| Frontend
    DB -->|Чтение данных| Backend
    Parser -->|Отправка данных| Backend
    Backend -->|Запись данных| DB
    Parser -.->|Запрос к источникам| External
    External -.->|Данные от источников| Parser
    Frontend -.->|Показывает интерфейс| User

    style User fill:none,stroke:#06d6a0,stroke-width:3px
    style Frontend fill:none,stroke:#A100FF,stroke-width:3px
    style Backend fill:none,stroke:#A100FF,stroke-width:3px
    style Parser fill:none,stroke:#A100FF,stroke-width:3px
    style DB fill:none,stroke:#A100FF,stroke-width:3px
    style External fill:none,stroke:#2757F5,stroke-width:3px
    style VCharte fill:none,stroke:#A100FF,stroke-width:2px

```

### Контракты API

#### Публичные эндпоинты:

| № | Метод | Эндпоинт | Описание |
|---|-------|----------|----------|
| 1 | GET | `/api/v1/health` | Проверка доступности API |
| 2 | GET | `/api/v1/weeks` | Список доступных недель |
| 3 | GET | `/api/v1/categories` | Список категорий и жанров |
| 4 | GET | `/api/v1/feed` | Главная лента |
| 5 | GET | `/api/v1/trends` | Общий список трендов |
| 6 | GET | `/api/v1/categories/{category}/trends` | Тренды по категории |
| 7 | GET | `/api/v1/trends/{trend_id}` | Детали тренда |
| 8 | GET | `/api/v1/trends/{trend_id}/history` | История позиций тренда |

#### Тренды

| № | Метод | Эндпоинт | Описание |
|---|-------|----------|----------|
| 1 | POST | `/api/v1/internal/update-trends` | Загрузка новых чартов от парсеров |
| 2 | POST | `/api/v1/internal/update-search-stats` | Загрузка статистики Wordstat |
| 3 | POST | `/api/v1/internal/update-game-audience-stats` | Загрузка статистики Whatstat |
| 4 | POST | `/api/v1/internal/publish-rankings` | Пересчет и публикация рейтинга |


### Проектирование данных

```mermaid
erDiagram
    category_settings {
        text category PK
        smallint top_limit
        smallint min_charts
    }

    chart_weights {
        text source PK
        text name PK
        numeric weight
    }

    charts {
        bigint id PK
        text source
        text name
        text category
        timestamp_with_time_zone created_at
    }

    chart_runs {
        bigint id PK
        bigint chart_id FK
        date week_start
        text status
        timestamp_with_time_zone started_at
        timestamp_with_time_zone finished_at
        text error
    }

    trend_history {
        bigint id PK
        bigint run_id FK
        bigint trend_id FK
        smallint position
    }

    genres {
        smallint id PK
        text category
        text name
    }

    trend_genres {
        bigint trend_id PK
        smallint genre_id PK
        text category
        smallint position
    }

    schema_migrations {
        text version PK
        text name
        text checksum
        timestamp_with_time_zone applied_at
    }

    trends {
        bigint id PK
        text category
        text title
        text subtitle
        text match_key
        timestamp_with_time_zone created_at
        smallint genre_id FK
        text search_query
        text cover_url
        text cover_source
        timestamp_with_time_zone genres_resolved_at
    }

    twitch_weekly_stats {
        bigint trend_id PK
        date week_start PK
        bigint total_followers
        numeric hours_streamed
        bigint average_viewers
        bigint peak_viewers
        bigint hours_watched
        bigint followers_gained
        numeric followers_per_hour
        timestamp_with_time_zone collected_at
    }

    trend_search_stats {
        bigint trend_id PK
        date week_start PK
        text query
        integer search_count
        timestamp_with_time_zone collected_at
    }

    trend_source_items {
        bigint id PK
        bigint trend_id FK
        text source
        text external_id
        text url
    }

    game_audience_stats {
        bigint trend_id PK
        date week_start PK
        text source_title
        text source_category_id
        text source_url
        integer position
        bigint average_viewers
        timestamp_with_time_zone collected_at
    }

    %% Связи
    charts ||--o{ chart_runs : "id -> chart_id"
    chart_runs ||--o{ trend_history : "id -> run_id"
    
    genres ||--o{ trend_genres : "id -> genre_id"
    trends ||--o{ trend_genres : "id -> trend_id"
    trends ||--o{ trend_history : "id -> trend_id"
    genres ||--o{ trends : "id -> genre_id"

    trends ||--o{ twitch_weekly_stats : "id -> trend_id"
    trends ||--o{ trend_search_stats : "id -> trend_id"
    trends ||--o{ trend_source_items : "id -> trend_id"
    trends ||--o{ game_audience_stats : "id -> trend_id"
```

## Масштабирование

### Схема масштабирования

```mermaid
graph LR
    User("Пользователь<br/>[Person]")

    Backend["Backend API<br/>[Container: Python]<br/>Обработка запросов,<br/>Circuit Breaker"]

    subgraph DB["PostgreSQL"]
        Primary["Primary<br/>[Container: PostgreSQL]<br/>Принимает запись"]
        Replica1["Replica 1<br/>[Container: PostgreSQL]<br/>Принимает чтение"]
        Replica2["Replica 2<br/>[Container: PostgreSQL]<br/>Принимает чтение"]
    end

    User -.->|Запрашивает тренды| Backend
    Backend -->|Запись| Primary
    Replica1 -->|Чтение| Backend
    Replica2 -->|Чтение| Backend
    Primary -->|Копирование данных| Replica1
    Primary -->|Копирование данных| Replica2

    style User fill:none,stroke:#06d6a0,stroke-width:3px
    style Backend fill:none,stroke:#A100FF,stroke-width:3px
    style Primary fill:none,stroke:#2757F5,stroke-width:3px
    style Replica1 fill:none,stroke:#2757F5,stroke-width:3px
    style Replica2 fill:none,stroke:#2757F5,stroke-width:3px
    style DB fill:none,stroke:#2757F5,stroke-width:2px
```

Ключевой характеристикой нашей системы является соотношение операций чтения и записи — 95% на 5%. Это означает, что подавляющая часть запросов приходится на чтение. При 100 000 пользователей количество таких запросов достигнет примерно 494 000 в сутки. Одна база данных не сможет эффективно обрабатывать такой объём операций чтения, поэтому мы добавляем реплики PostgreSQL. Главная база (primary) продолжает принимать операции записи, а две реплики (replica1, replica2) принимают на себя операции чтения. Это позволяет распределить нагрузку и сохранить скорость отклика на приемлемом уровне.
