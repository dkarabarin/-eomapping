# Сервис геопланирования

Программный модуль для автоматического распределения географических точек по дням месяца и формирования кластеров для ежедневного обхода.

---

## Возможности

- Распределение точек по количеству требуемых посещений в месяц
- Формирование кластеров точек для обслуживания за один день
- Визуализация кластеров и маршрутов на интерактивной карте
- Экспорт результатов в CSV

---

## Установка

```bash
pip install -r requirements.txt
```

---

## Входные данные

CSV-файл со следующими полями:

| Поле | Тип | Описание |
|---|---|---|
| `point_id` | string | Уникальный идентификатор точки |
| `latitude` | float | Широта |
| `longitude` | float | Долгота |
| `visits_per_month` | integer | Количество посещений в месяц |
| `manager` | integer | ID менеджера (опционально) |

---

## Использование

### Базовый пример

```python
from src import (
    load_and_validate_data,
    load_graph,
    load_road_cache,
    cluster_points_dbscan_final,
    process_clusters_by_manager,
    assign_clusters_to_days,
    build_schedule,
    build_final_map,
    save_results
)

# Загрузка данных
df = load_and_validate_data('data/data.csv')

# Загрузка дорожного графа
graph = load_graph(df)
load_road_cache()

# Кластеризация по менеджерам
clusters_by_manager = process_clusters_by_manager(
    df, cluster_points_dbscan_final
)

# Распределение по дням
day_schedule = assign_clusters_to_days(clusters_by_manager)

# Формирование расписания
schedule_df = build_schedule(day_schedule, df)

# Сохранение результатов
save_results(schedule_df, day_schedule, clusters_by_manager)

# Визуализация
route_map = build_final_map(df, day_schedule, clusters_by_manager)
route_map.save('outputs/route_map.html')
```

### Запуск через Jupyter Notebook

См. `notebooks/geolocation_v2.ipynb`

---

## Параметры конфигурации

Все параметры находятся в `src/config.py`:

| Параметр | Описание |
|---|---|
| `EPS_KM` | Радиус кластеризации (км) |
| `MAX_CLUSTER_SIZE` | Максимальное количество точек в кластере |
| `MIN_CLUSTER_SIZE` | Минимальное количество точек в кластере |
| `WORKING_DAYS` | Количество рабочих дней в месяце |
| `AVG_SPEED` | Средняя скорость движения (км/ч) |

---

## Структура проекта

```
├── run.py                        # СКРИПТ ЗАПУСКА 
├── src/                          # Папка с исходным кодом
│   ├── __init__.py
│   ├── config.py
│   ├── data_loader.py
│   ├── clustering.py
│   ├── routing.py
│   ├── schedule.py
│   ├── visualize.py
│   └── utils.py
├── notebooks/                    # Папка с Jupyter ноутбуками
│   └── geolocation_v2.ipynb
├── data/                         # Папка с данными
│   └── data.csv                  # Входной файл с точками
├── cache/                        # Папка для кеша (создаётся автоматически)
├── outputs/                      # Папка для результатов (создаётся автоматически)
├── requirements.txt              # Зависимости
└── README.md                     # Документация
```

---

## Выходные данные

| Файл | Описание |
|---|---|
| `schedule_final.csv` | Полное расписание с порядком посещения |
| `daily_stats_final.csv` | Статистика по дням |
| `clusters_info_final.csv` | Информация о кластерах |
| `route_map_final.html` | Интерактивная карта с маршрутами |

---

## Вид карты

<img width="1903" height="1020" alt="image" src="https://github.com/user-attachments/assets/632e56a2-d65d-43d3-b3aa-23ef1424386c" />

