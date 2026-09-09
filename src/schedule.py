"""
Формирование расписания и распределение по дням
"""

import pandas as pd
from typing import Dict, List, Tuple
from .config import WORKING_DAYS, AVG_SPEED
from .routing import road_distance, graph_is_available
from geopy.distance import geodesic


def calculate_cluster_diameter(cluster_points: pd.DataFrame) -> Tuple[float, float]:
    """
    Вычисляет диаметр кластера и время в пути
    
    Returns:
        (diameter_km, time_hours)
    """
    coords = list(zip(cluster_points['latitude'], cluster_points['longitude']))
    max_dist = 0
    
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            if graph_is_available():
                d = road_distance(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            else:
                d = geodesic(coords[i], coords[j]).kilometers
            if d > max_dist:
                max_dist = d
    
    time_hours = 2 * max_dist / AVG_SPEED if max_dist > 0 else 0
    return max_dist, time_hours


def process_clusters_by_manager(df: pd.DataFrame,
                                cluster_func,
                                eps_km: float = 25,
                                max_cluster_size: int = 12,
                                min_cluster_size: int = 8,
                                n_days: int = WORKING_DAYS) -> Dict:
    """
    Кластеризация точек по менеджерам и формирование кластеров
    
    Args:
        df: DataFrame с точками
        cluster_func: функция кластеризации
        eps_km: радиус кластеризации
        max_cluster_size: максимальный размер кластера
        min_cluster_size: минимальный размер кластера
        n_days: количество рабочих дней
        
    Returns:
        Словарь {manager: {cluster_id: cluster_info}}
    """
    clusters_by_manager = {}
    
    for manager in sorted(df['manager'].unique()):
        manager_df = df[df['manager'] == manager].copy()
        print(f"\n👤 Обработка менеджера {manager}: {len(manager_df)} точек")
        
        if len(manager_df) == 0:
            continue

        # Кластеризация
        raw_clusters = cluster_func(
            manager_df, eps_km, max_cluster_size, min_cluster_size, use_road=False
        )

        # Расчёт характеристик кластеров
        clusters_info = {}
        for cid, point_ids in raw_clusters.items():
            cluster_points = manager_df[manager_df['point_id'].isin(point_ids)]
            center_lat = cluster_points['latitude'].mean()
            center_lon = cluster_points['longitude'].mean()
            
            diameter, time_hours = calculate_cluster_diameter(cluster_points)
            
            clusters_info[cid] = {
                'points': point_ids,
                'center': (center_lat, center_lon),
                'diameter_km': diameter,
                'time_hours': time_hours
            }

        print(f"  Создано кластеров: {len(clusters_info)}")

        # Перенос точек с 2 посещениями
        clusters_info = _handle_two_visits(clusters_info, manager_df)

        # Оставляем только n_days кластеров с наименьшим диаметром
        if len(clusters_info) > n_days:
            sorted_clusters = sorted(clusters_info.items(), key=lambda x: x[1]['diameter_km'])[:n_days]
            clusters_info = dict(sorted_clusters)
            print(f"  Оставлено {len(clusters_info)} кластеров (по диаметру)")
        else:
            print(f"  Кластеров меньше {n_days}: {len(clusters_info)} (дни без заданий)")

        clusters_by_manager[manager] = clusters_info
        
        total_points = sum(len(info['points']) for info in clusters_info.values())
        print(f"  Всего кластеров: {len(clusters_info)}")
        print(f"  Всего точек в кластерах: {total_points}")
        if len(clusters_info) > 0:
            avg_diam = sum(info['diameter_km'] for info in clusters_info.values()) / len(clusters_info)
            avg_time = sum(info['time_hours'] for info in clusters_info.values()) / len(clusters_info)
            print(f"  Средний диаметр: {avg_diam:.1f} км, Среднее время: {avg_time:.2f} ч")

    return clusters_by_manager


def _handle_two_visits(clusters_info: Dict, manager_df: pd.DataFrame) -> Dict:
    """Перераспределяет точки с 2 посещениями"""
    two_visits_points = manager_df[manager_df['visits_per_month'] == 2]['point_id'].tolist()
    if not two_visits_points:
        return clusters_info
    
    print(f"  Точки с 2 посещениями: {len(two_visits_points)}")
    clusters_copy = {cid: info.copy() for cid, info in clusters_info.items()}
    
    for pid in two_visits_points:
        # Находим текущий кластер
        cur = None
        for cid, info in clusters_copy.items():
            if pid in info['points']:
                cur = cid
                break
        
        if cur is None:
            row = manager_df[manager_df['point_id'] == pid].iloc[0]
            new_id = max(clusters_copy.keys()) + 1 if clusters_copy else 0
            clusters_copy[new_id] = {
                'points': [pid],
                'center': (row['latitude'], row['longitude']),
                'diameter_km': 0,
                'time_hours': 0
            }
            continue

        row = manager_df[manager_df['point_id'] == pid].iloc[0]
        point_coords = (row['latitude'], row['longitude'])
        
        candidates = []
        for cid, info in clusters_copy.items():
            if cid != cur and len(info['points']) < len(clusters_info[0].get('points', [])) + 1:
                if graph_is_available():
                    dist_to_center = road_distance(
                        point_coords[0], point_coords[1],
                        info['center'][0], info['center'][1]
                    )
                else:
                    dist_to_center = geodesic(point_coords, info['center']).kilometers
                candidates.append((cid, dist_to_center))

        if candidates:
            candidates.sort(key=lambda x: x[1])
            target = candidates[0][0]
            clusters_copy[target]['points'].append(pid)
            
            updated_points = clusters_copy[target]['points']
            updated_df = manager_df[manager_df['point_id'].isin(updated_points)]
            new_center = (updated_df['latitude'].mean(), updated_df['longitude'].mean())
            clusters_copy[target]['center'] = new_center
            
            diameter, time_hours = calculate_cluster_diameter(updated_df)
            clusters_copy[target]['diameter_km'] = diameter
            clusters_copy[target]['time_hours'] = time_hours
        else:
            new_id = max(clusters_copy.keys()) + 1 if clusters_copy else 0
            clusters_copy[new_id] = {
                'points': [pid],
                'center': (row['latitude'], row['longitude']),
                'diameter_km': 0,
                'time_hours': 0
            }
    
    return clusters_copy


def assign_clusters_to_days(clusters_by_manager: Dict, n_days: int = WORKING_DAYS) -> Dict:
    """
    Распределяет кластеры по дням для всех менеджеров
    
    Returns:
        Словарь {day: {'clusters': [...], 'points': [...], 'total_time': ...}}
    """
    day_schedule = {
        day: {'clusters': [], 'points': [], 'total_time': 0}
        for day in range(1, n_days + 1)
    }
    
    for manager, clusters in clusters_by_manager.items():
        sorted_clusters = sorted(clusters.items(), key=lambda x: x[1]['time_hours'], reverse=True)
        
        if len(sorted_clusters) <= n_days:
            for i, (cid, info) in enumerate(sorted_clusters):
                day = i + 1
                day_schedule[day]['clusters'].append({
                    'manager': manager,
                    'cluster_id': cid,
                    'points': info['points'],
                    'center': info['center'],
                    'diameter_km': info['diameter_km'],
                    'time_hours': info['time_hours']
                })
                day_schedule[day]['total_time'] += info['time_hours']
                day_schedule[day]['points'].extend(info['points'])
        else:
            for cid, info in sorted_clusters:
                day_counts = {
                    d: sum(1 for c in day_schedule[d]['clusters'] if c['manager'] == manager)
                    for d in range(1, n_days + 1)
                }
                min_day = min(day_counts.keys(), key=lambda d: day_counts[d])
                if day_counts[min_day] >= 2:
                    min_day = min(day_counts.keys(), key=lambda d: day_schedule[d]['total_time'])
                
                day_schedule[min_day]['clusters'].append({
                    'manager': manager,
                    'cluster_id': cid,
                    'points': info['points'],
                    'center': info['center'],
                    'diameter_km': info['diameter_km'],
                    'time_hours': info['time_hours']
                })
                day_schedule[min_day]['total_time'] += info['time_hours']
                day_schedule[min_day]['points'].extend(info['points'])
    
    return day_schedule


def build_route(cluster_points: pd.DataFrame) -> List[str]:
    """
    Строит маршрут внутри кластера с использованием жадного алгоритма
    
    Returns:
        Список point_id в порядке обхода
    """
    if len(cluster_points) == 0:
        return []
    if len(cluster_points) == 1:
        return cluster_points['point_id'].tolist()
    
    coords = list(zip(cluster_points['latitude'], cluster_points['longitude']))
    point_ids = cluster_points['point_id'].tolist()
    
    unvisited = list(range(len(coords)))
    start = 0
    route = [start]
    unvisited.remove(start)
    
    while unvisited:
        last = route[-1]
        distances = []
        for idx in unvisited:
            if graph_is_available():
                d = road_distance(coords[last][0], coords[last][1], coords[idx][0], coords[idx][1])
            else:
                d = geodesic(coords[last], coords[idx]).kilometers
            distances.append((idx, d))
        nearest = min(distances, key=lambda x: x[1])[0]
        route.append(nearest)
        unvisited.remove(nearest)
    
    return [point_ids[i] for i in route]


def build_schedule(day_schedule: Dict, df_original: pd.DataFrame) -> pd.DataFrame:
    """
    Формирует итоговое расписание с порядком посещения точек
    
    Returns:
        DataFrame с расписанием
    """
    rows = []
    for day, data in day_schedule.items():
        for cluster in data['clusters']:
            manager = cluster['manager']
            cid = cluster['cluster_id']
            points = cluster['points']
            
            cluster_points = df_original[df_original['point_id'].isin(points)]
            route_order = build_route(cluster_points)
            
            for order, pid in enumerate(route_order, start=1):
                visits = df_original[df_original['point_id'] == pid]['visits_per_month'].iloc[0]
                rows.append({
                    'point_id': pid,
                    'manager': manager,
                    'visit_day': day,
                    'cluster_id': f"day{day}_m{manager}_c{cid}",
                    'order_in_route': order,
                    'visits_per_month': visits,
                    'cluster_diameter_km': round(cluster['diameter_km'], 1),
                    'cluster_time_hours': round(cluster['time_hours'], 2)
                })
    
    return pd.DataFrame(rows)