"""
Модуль для работы с дорожным графом и расчёта расстояний
"""

import os
import json
import glob
import networkx as nx
import osmnx as ox
import pandas as pd
from geopy.distance import geodesic
from typing import Optional, Tuple, Dict
import warnings

from .config import CACHE_DIR, GRAPHML_PATH, ROAD_DIST_CACHE_FILE

warnings.filterwarnings('ignore')

# Глобальные переменные для кеша
_graph = None
_road_cache = {}
_nearest_node_cache = {}


def graph_is_available() -> bool:
    """Проверяет, загружен ли дорожный граф"""
    return _graph is not None


def clean_graph_for_graphml(graph):
    """Удаляет из графа атрибуты, не сериализуемые в GraphML"""
    if graph is None:
        return None
    
    # Очистка атрибутов узлов
    for node, data in list(graph.nodes(data=True)):
        for key in list(data.keys()):
            val = data[key]
            if val is None or isinstance(val, (list, dict, set, tuple)):
                del data[key]
            elif not isinstance(val, (int, float, str, bool)):
                del data[key]
    
    # Очистка атрибутов рёбер
    for u, v, key, data in list(graph.edges(data=True, keys=True)):
        for key_attr in list(data.keys()):
            val = data[key_attr]
            if val is None or isinstance(val, (list, dict, set, tuple)):
                del data[key_attr]
            elif not isinstance(val, (int, float, str, bool)):
                del data[key_attr]
    
    return graph


def find_pbf_file(base_dir: str) -> Optional[str]:
    """Находит PBF-файл в директории"""
    pattern = os.path.join(base_dir, "*.osm.pbf")
    files = glob.glob(pattern)
    return files[0] if files else None


def build_bbox_from_points(df_points: pd.DataFrame, buffer_km: float = 50) -> Optional[Tuple]:
    """Строит bbox по точкам с буфером"""
    if df_points.empty:
        return None
    lat_min, lat_max = df_points['latitude'].min(), df_points['latitude'].max()
    lon_min, lon_max = df_points['longitude'].min(), df_points['longitude'].max()
    buffer_deg = buffer_km / 111.0
    return (lat_min - buffer_deg, lon_min - buffer_deg,
            lat_max + buffer_deg, lon_max + buffer_deg)


def load_graph(df_points: Optional[pd.DataFrame] = None) -> Optional[nx.Graph]:
    """
    Загружает дорожный граф из кеша, PBF или интернета
    
    Args:
        df_points: DataFrame с точками для построения bbox
        
    Returns:
        NetworkX граф или None
    """
    global _graph
    
    # 1. Попытка загрузить из кеша GraphML
    if os.path.exists(GRAPHML_PATH):
        try:
            print(f"🔄 Загрузка графа из GraphML: {GRAPHML_PATH}")
            graph = nx.read_graphml(GRAPHML_PATH)
            print(f"✅ Граф загружен из кеша. Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
            _graph = graph
            return graph
        except Exception as e:
            print(f"⚠️ Ошибка загрузки GraphML: {e}. Кеш будет пересоздан.")
            try:
                os.remove(GRAPHML_PATH)
            except:
                pass

    # 2. Загрузка из PBF через pyrosm
    pbf_path = find_pbf_file(os.path.dirname(GRAPHML_PATH))
    if pbf_path and os.path.getsize(pbf_path) > 50 * 1024 * 1024:
        try:
            from pyrosm import OSM
            
            if df_points is not None and not df_points.empty:
                bbox = build_bbox_from_points(df_points, buffer_km=30)
                if bbox:
                    south, west, north, east = bbox
                    bbox_list = [west, south, east, north]
                    print(f"   Загрузка только области bbox: {bbox_list}")
                    osm = OSM(pbf_path, bounding_box=bbox_list)
                else:
                    osm = OSM(pbf_path)
            else:
                osm = OSM(pbf_path)
            
            nodes, edges = osm.get_network(network_type='driving', nodes=True)
            if nodes is not None and edges is not None and not edges.empty:
                graph = osm.to_graph(nodes, edges, graph_type='networkx')
                if graph is not None and len(graph.nodes) > 0:
                    print(f"✅ Граф загружен из PBF (pyrosm). Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
                    graph_clean = clean_graph_for_graphml(graph)
                    try:
                        nx.write_graphml(graph_clean, GRAPHML_PATH)
                        print(f"✅ Граф сохранён в кеш: {GRAPHML_PATH}")
                    except:
                        pass
                    _graph = graph_clean
                    return graph_clean
        except Exception as e:
            print(f"   ❌ Ошибка pyrosm: {e}")

    # 3. Загрузка через интернет (OSMnx)
    if df_points is not None and not df_points.empty:
        bbox = build_bbox_from_points(df_points, buffer_km=50)
        if bbox:
            south, west, north, east = bbox
            print(f"🔄 Загрузка графа по bbox (север={north:.2f}, юг={south:.2f}, восток={east:.2f}, запад={west:.2f})")
            endpoints = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
                "https://overpass.openstreetmap.fr/api/interpreter"
            ]
            for endpoint in endpoints:
                try:
                    print(f"   Эндпоинт: {endpoint}")
                    ox.settings.overpass_endpoint = endpoint
                    ox.settings.timeout = 1200
                    ox.settings.max_retries = 10
                    try:
                        graph = ox.graph_from_bbox(
                            north=north, south=south, east=east, west=west,
                            network_type='drive', simplify=True
                        )
                    except TypeError:
                        graph = ox.graph_from_bbox(north, south, east, west,
                                                   network_type='drive', simplify=True)
                    if graph is not None and len(graph.nodes) > 0:
                        print(f"✅ Граф загружен по bbox. Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
                        graph_clean = clean_graph_for_graphml(graph)
                        nx.write_graphml(graph_clean, GRAPHML_PATH)
                        _graph = graph_clean
                        return graph_clean
                except Exception as e:
                    print(f"   ⚠️ Ошибка: {e}")
                    continue

    print("❌ Все попытки загрузки графа не удались. Будут использованы прямые линии.")
    return None


def load_road_cache():
    """Загружает кеш дорожных расстояний из файла"""
    global _road_cache
    if os.path.exists(ROAD_DIST_CACHE_FILE):
        try:
            with open(ROAD_DIST_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Безопасное преобразование ключей
            _road_cache = {}
            for k, v in data.items():
                try:
                    # Парсим строку вида "(lat1, lon1, lat2, lon2)"
                    coords = eval(k)
                    if isinstance(coords, tuple) and len(coords) == 4:
                        _road_cache[coords] = v
                except:
                    continue
            print(f"✅ Загружено {len(_road_cache)} записей кеша дорожных расстояний.")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки кеша: {e}. Будет создан новый кеш.")
            _road_cache = {}
    else:
        print("ℹ️ Файл кеша дорожных расстояний не найден. Будет создан новый.")


def save_road_cache():
    """Сохраняет кеш дорожных расстояний в файл"""
    global _road_cache
    try:
        cache_str_keys = {str(k): v for k, v in _road_cache.items()}
        with open(ROAD_DIST_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_str_keys, f, ensure_ascii=False, indent=2)
        print(f"✅ Кеш дорожных расстояний сохранён ({len(_road_cache)} записей).")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения кеша: {e}")


def get_nearest_node(lat: float, lon: float):
    """Возвращает ближайший узел графа с кешированием"""
    global _nearest_node_cache, _graph
    key = (round(lat, 6), round(lon, 6))
    if key not in _nearest_node_cache and _graph is not None:
        _nearest_node_cache[key] = ox.distance.nearest_nodes(_graph, lon, lat)
    return _nearest_node_cache.get(key)


def road_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Возвращает расстояние между точками по дорогам, либо по прямой
    
    Returns:
        Расстояние в километрах
    """
    global _graph, _road_cache
    
    if _graph is None:
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers

    key = (round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6))
    if key in _road_cache:
        return _road_cache[key]
    
    rev_key = (key[2], key[3], key[0], key[1])
    if rev_key in _road_cache:
        return _road_cache[rev_key]

    try:
        node1 = get_nearest_node(lat1, lon1)
        node2 = get_nearest_node(lat2, lon2)
        if node1 is not None and node2 is not None and nx.has_path(_graph, node1, node2):
            dist_m = nx.shortest_path_length(_graph, node1, node2, weight='length')
            dist_km = dist_m / 1000.0
        else:
            dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers
    except Exception:
        dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers

    _road_cache[key] = dist_km
    return dist_km