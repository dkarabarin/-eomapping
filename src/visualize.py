"""
Визуализация маршрутов и кластеров на карте
"""

import os
import json
import hashlib
import time
from typing import List, Tuple, Dict, Optional
import requests
import folium
from folium.plugins import GroupedLayerControl
import pandas as pd

from .config import CITY_CENTER_LAT, CITY_CENTER_LON, WORKING_DAYS, OUTPUT_DIR
from .routing import road_distance, graph_is_available
from .schedule import build_route


class RoutePlanner:
    """Планировщик маршрутов с кешированием OSRM-запросов"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join(os.path.dirname(OUTPUT_DIR), "cache")
        self.cache_file = os.path.join(self.cache_dir, "route_cache.json")
        self.cache = self._load_cache()
        self.total_requests = 0
        self.cache_hits = 0
        self.total_time = 0
        self.osrm_url = "https://router.project-osrm.org/route/v1/driving/"

    def _load_cache(self) -> Dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _get_cache_key(self, coords: List[Tuple[float, float]]) -> str:
        coord_str = "|".join([f"{lat:.6f},{lon:.6f}" for lat, lon in coords])
        return hashlib.md5(coord_str.encode()).hexdigest()

    def get_route_info(self, coords: List[Tuple[float, float]]) -> Dict:
        """
        Получает информацию о маршруте (геометрия, время, расстояние)
        
        Returns:
            Словарь с ключами: geometry, duration, distance, from_cache
        """
        if len(coords) < 2:
            return {
                'geometry': coords,
                'duration': 0,
                'distance': 0,
                'from_cache': False
            }
        
        cache_key = self._get_cache_key(coords)
        if cache_key in self.cache:
            self.cache_hits += 1
            result = self.cache[cache_key]
            result['from_cache'] = True
            return result
        
        self.total_requests += 1
        start_time = time.time()
        
        try:
            coord_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
            url = f"{self.osrm_url}{coord_str}"
            params = {
                'geometries': 'geojson',
                'overview': 'full',
                'steps': 'false'
            }
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and data.get('routes'):
                    route = data['routes'][0]
                    geometry = [(lat, lon) for lon, lat in route['geometry']['coordinates']]
                    duration = route['duration']
                    distance = route['distance'] / 1000
                else:
                    geometry = coords
                    duration = 0
                    distance = 0
            else:
                geometry = coords
                duration = 0
                distance = 0
        except Exception as e:
            print(f"  ⚠️ Ошибка маршрутизации: {e}")
            geometry = coords
            duration = 0
            distance = 0
        
        elapsed = time.time() - start_time
        self.total_time += elapsed
        
        result = {
            'geometry': geometry,
            'duration': duration,
            'distance': distance,
            'from_cache': False
        }
        self.cache[cache_key] = result
        self._save_cache()
        return result

    def get_stats(self) -> Dict:
        return {
            'total_requests': self.total_requests,
            'cache_hits': self.cache_hits,
            'hit_rate': self.cache_hits / max(1, self.total_requests + self.cache_hits),
            'total_time': self.total_time
        }


def build_final_map(df_original: pd.DataFrame, 
                    day_schedule: Dict,
                    clusters_by_manager: Dict) -> folium.Map:
    """
    Строит интерактивную карту с маршрутами
    
    Args:
        df_original: DataFrame с точками
        day_schedule: расписание по дням
        clusters_by_manager: кластеры по менеджерам
        
    Returns:
        folium.Map
    """
    manager_colors = {0: 'red', 1: 'blue', 2: 'green'}
    manager_names = {0: 'Менеджер 0', 1: 'Менеджер 1', 2: 'Менеджер 2'}
    
    center_lat = df_original['latitude'].mean()
    center_lon = df_original['longitude'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles='OpenStreetMap')

    # Центр города
    folium.Marker(
        location=[CITY_CENTER_LAT, CITY_CENTER_LON],
        popup="🏙️ Старт (центр города)",
        icon=folium.Icon(color='darkred', icon='home', prefix='fa')
    ).add_to(m)
    folium.Circle(
        location=[CITY_CENTER_LAT, CITY_CENTER_LON],
        radius=5000, color='darkred', fill=False, weight=1, opacity=0.3,
        popup='Радиус 5 км от центра'
    ).add_to(m)

    route_planner = RoutePlanner()
    groups = {}

    # Группировка по менеджерам
    for manager in sorted(df_original['manager'].unique()):
        group_name = manager_names[manager]
        group_layers = []
        
        for day in range(1, WORKING_DAYS + 1):
            if day not in day_schedule:
                continue
            cluster = None
            for c in day_schedule[day]['clusters']:
                if c['manager'] == manager:
                    cluster = c
                    break
            if cluster is None:
                continue
            
            layer = folium.FeatureGroup(name=f"День {day}", show=False)
            _add_route_to_layer(layer, cluster, day, manager, df_original,
                              route_planner, manager_colors, manager_names)
            layer.add_to(m)
            group_layers.append(layer)
        
        if group_layers:
            groups[group_name] = group_layers

    # Группа "Все менеджеры"
    group_all = "Все менеджеры"
    all_layers = []
    for day in range(1, WORKING_DAYS + 1):
        if day not in day_schedule or not day_schedule[day]['clusters']:
            continue
        layer = folium.FeatureGroup(name=f"День {day}", show=False)
        for cluster in day_schedule[day]['clusters']:
            manager = cluster['manager']
            _add_route_to_layer(layer, cluster, day, manager, df_original,
                              route_planner, manager_colors, manager_names)
        layer.add_to(m)
        all_layers.append(layer)
    if all_layers:
        groups[group_all] = all_layers

    GroupedLayerControl(groups, collapsed=False).add_to(m)

    # Вывод статистики
    stats = route_planner.get_stats()
    print(f"\n📊 Статистика маршрутизации:")
    print(f"  Всего запросов: {stats['total_requests']}")
    print(f"  Из кеша: {stats['cache_hits']} ({stats['hit_rate']*100:.1f}%)")
    print(f"  Время запросов: {stats['total_time']:.2f} сек")
    
    return m


def _add_route_to_layer(layer: folium.FeatureGroup, cluster: Dict, day: int, manager: int,
                        df_original: pd.DataFrame, route_planner: RoutePlanner,
                        manager_colors: Dict, manager_names: Dict):
    """Добавляет маршрут на слой карты"""
    point_ids = cluster['points']
    points_df = df_original[df_original['point_id'].isin(point_ids)]
    route_order = build_route(points_df)
    route_locations = []
    
    for pid in route_order:
        point = df_original[df_original['point_id'] == pid].iloc[0]
        route_locations.append((point['latitude'], point['longitude']))
    
    # Рисуем маршрут
    if len(route_locations) > 1:
        try:
            route_info = route_planner.get_route_info(route_locations)
            if route_info.get('duration', 0) > 0 or route_info.get('from_cache', False):
                if route_info['geometry'] != route_locations:
                    folium.PolyLine(
                        locations=route_info['geometry'],
                        color=manager_colors.get(manager, 'black'),
                        weight=4,
                        opacity=0.9,
                        popup=f"🚗 День {day}, {manager_names[manager]}, {route_info['duration']/60:.1f} мин по дорогам"
                    ).add_to(layer)
                else:
                    folium.PolyLine(
                        locations=route_locations,
                        color=manager_colors.get(manager, 'black'),
                        weight=3,
                        opacity=0.5,
                        dash_array='5, 5',
                        popup=f"День {day}, {manager_names[manager]} (прямая линия)"
                    ).add_to(layer)
            else:
                folium.PolyLine(
                    locations=route_locations,
                    color=manager_colors.get(manager, 'black'),
                    weight=3,
                    opacity=0.5,
                    dash_array='5, 5',
                    popup=f"День {day}, {manager_names[manager]} (прямая линия)"
                ).add_to(layer)
        except Exception as e:
            print(f"  ⚠️ Ошибка для дня {day}, менеджера {manager}: {e}")
            folium.PolyLine(
                locations=route_locations,
                color=manager_colors.get(manager, 'black'),
                weight=3,
                opacity=0.5,
                dash_array='5, 5',
                popup=f"День {day}, {manager_names[manager]} (прямая линия)"
            ).add_to(layer)
    else:
        if route_locations:
            folium.PolyLine(
                locations=[[CITY_CENTER_LAT, CITY_CENTER_LON], route_locations[0]],
                color=manager_colors.get(manager, 'black'),
                weight=3,
                opacity=0.5,
                dash_array='5, 5',
                popup=f"День {day}, {manager_names[manager]} (1 точка)"
            ).add_to(layer)
    
    # Отмечаем точки
    for idx, pid in enumerate(route_order, start=1):
        point = df_original[df_original['point_id'] == pid].iloc[0]
        popup_text = f"""
            <b>№{idx}</b><br>
            <b>ID:</b> {pid}<br>
            <b>День:</b> {day}<br>
            <b>{manager_names[manager]}</b><br>
            <b>Координаты:</b> ({point['latitude']:.5f}, {point['longitude']:.5f})
        """
        folium.Marker(
            location=[point['latitude'], point['longitude']],
            popup=popup_text,
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    background-color: {manager_colors.get(manager, 'black')};
                    color: white;
                    border-radius: 50%;
                    width: 26px;
                    height: 26px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 11px;
                    font-weight: bold;
                    border: 2px solid white;
                    box-shadow: 0 0 5px rgba(0,0,0,0.5);
                ">
                    {idx}
                </div>
                """
            )
        ).add_to(layer)