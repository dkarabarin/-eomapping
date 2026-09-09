"""
Вспомогательные функции для сохранения результатов
"""

import os
import pandas as pd
from typing import Dict

from .config import OUTPUT_DIR


def save_results(schedule_df: pd.DataFrame, 
                 day_schedule: Dict,
                 clusters_by_manager: Dict) -> None:
    """
    Сохраняет результаты в CSV-файлы
    
    Args:
        schedule_df: расписание
        day_schedule: расписание по дням
        clusters_by_manager: кластеры по менеджерам
    """
    # Расписание
    schedule_csv = os.path.join(OUTPUT_DIR, "schedule_final.csv")
    schedule_df.to_csv(schedule_csv, index=False, encoding='utf-8-sig')
    print(f"✅ Расписание сохранено в {schedule_csv}")

    # Статистика по дням
    stats = []
    for day, data in day_schedule.items():
        if data['clusters']:
            stats.append({
                'day': day,
                'clusters': len(data['clusters']),
                'points': len(data['points']),
                'time_hours': round(data['total_time'], 2)
            })
    stats_df = pd.DataFrame(stats)
    stats_csv = os.path.join(OUTPUT_DIR, "daily_stats_final.csv")
    stats_df.to_csv(stats_csv, index=False, encoding='utf-8-sig')
    print(f"✅ Статистика сохранена в {stats_csv}")

    # Информация о кластерах
    cluster_info = []
    for manager, clusters in clusters_by_manager.items():
        for cid, info in clusters.items():
            cluster_info.append({
                'manager': manager,
                'cluster_id': cid,
                'points_count': len(info['points']),
                'diameter_km': round(info['diameter_km'], 1),
                'time_hours': round(info['time_hours'], 2),
                'center_lat': round(info['center'][0], 5),
                'center_lon': round(info['center'][1], 5)
            })
    cluster_df = pd.DataFrame(cluster_info)
    cluster_csv = os.path.join(OUTPUT_DIR, "clusters_info_final.csv")
    cluster_df.to_csv(cluster_csv, index=False, encoding='utf-8-sig')
    print(f"✅ Информация о кластерах сохранена в {cluster_csv}")

    print(f"\n📊 Итоговая статистика:")
    print(f"  Всего записей в расписании: {len(schedule_df)}")
    print(f"  Всего дней с заданиями: {len(stats)}")
    print(f"  Всего кластеров: {sum(len(c) for c in day_schedule.values() if c['clusters'])}")


def print_cluster_stats(clusters: Dict) -> None:
    """Выводит статистику по кластерам"""
    sizes = [len(pts) for pts in clusters.values()]
    if sizes:
        print(f"Размеры: мин={min(sizes)}, макс={max(sizes)}, сред={sum(sizes)/len(sizes):.1f}")