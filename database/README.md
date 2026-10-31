# База данных

PostgreSQL 16. Адрес задаётся в `.env`: `DATABASE_URL=postgresql://user:password@localhost:5432/vtrende`.

## Первый запуск

```bash
pip install -r requirements.txt
python -m database.migrate          # создать схему
python -m database.seed             # по желанию: 12 недель тестовых данных
```

Если база уже создана из старого `database/schema.sql`, сначала отметьте его применённым:
`python -m database.migrate --baseline 001`, затем `python -m database.migrate`.

## Еженедельное обновление

```bash
python -m parser.run_all --save        # 1. собрать 13 чартов в data/outbox/
python -m database.load_outbox         # 2. загрузить в базу и пересчитать рейтинг
python -m parser.wordstat_batch --save # 3. Wordstat для объектов топов недели
python -m database.load_outbox         # 4. загрузить Wordstat
```

Повторный запуск любого шага за ту же неделю не создаёт дублей.

## Миграции

Файлы `migrations/NNN_описание.sql` применяются по порядку, каждый один раз и в своей транзакции.
Применённый файл менять нельзя (это проверяется по контрольной сумме): любое изменение схемы — новый файл.

| Файл | Что делает |
|---|---|
| `001_init.sql` | исходная схема: пользователи, тренды, чарты, запуски, позиции |
| `002_genres.sql` | справочник жанров; `trends.genre_id` (пока пусто, источник — нейросеть) |
| `003_wordstat.sql` | `trend_search_stats`, ручная фраза `trends.search_query` |
| `004_rankings.sql` | правила рейтинга `category_settings`, материализованный рейтинг и представления |
| `008_covers.sql` | обложки: `trends.cover_url` и `cover_source`, поле `cover_url` в представлениях карточек |

## Представления для выдачи

| Представление | Для чего |
|---|---|
| `v_category_top_latest` | актуальный топ категории: место, прошлое место, пик, недели в топе, новинка, Wordstat |
| `v_category_top` | то же за любую неделю (`WHERE week_start = ...`) |
| `v_main_feed` | смешанная лента главной, упорядочена по Wordstat (`feed_rank`) |
| `v_chart_top` | топ отдельного чарта с позицией на прошлой неделе |
| `v_trend_history` | точки графика тренда по неделям |

Общий топ категории — средняя позиция по чартам категории; объект должен быть минимум
в `category_settings.min_charts` чартах. Неудачные сборы в расчёте не участвуют.
Рейтинг хранится в `mv_category_rank` и пересчитывается после загрузки чартов.

## Тесты

Тесты на PostgreSQL запускаются, если задан `TEST_DATABASE_URL` (отдельная база —
тесты удаляют в ней все данные). В GitHub Actions база поднимается автоматически.
