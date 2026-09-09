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

from .config import (
    CACHE_DIR, 
    GRAPHML_PATH, 
    ROAD_DIST_CACHE_FILE, 
    PBF_PATH, 
    PBF_FILENAME, 
    DATA_DIR
)
from .download_pbf import check_pbf_file, download_pbf

warnings.filterwarnings('ignore')

# Глобальные переменные для кеша
_graph = None
_road_cache = {}
_nearest_node_cache = {}


def graph_is_available() -> bool:
    """
    Проверяет, загружен ли дорожный граф
    
    Returns:
        True если граф загружен, иначе False
    """
    return _graph is not None


def clean_graph_for_graphml(graph):
    """
    Удаляет из графа атрибуты, не сериализуемые в GraphML
    
    Args:
        graph: NetworkX граф
        
    Returns:
        Очищенный граф
    """
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


def find_pbf_file() -> Optional[str]:
    """
    Находит PBF-файл в папке data
    
    Returns:
        Путь к PBF-файлу или None
    """
    # Проверяем основной путь
    if os.path.exists(PBF_PATH):
        return PBF_PATH
    
    # Ищем в папке data все .osm.pbf файлы
    pattern = os.path.join(DATA_DIR, "*.osm.pbf")
    files = glob.glob(pattern)
    if files:
        # Если найден другой PBF-файл, используем его
        print(f"   Найден альтернативный PBF-файл: {os.path.basename(files[0])}")
        return files[0]
    
    return None


def build_bbox_from_points(df_points: pd.DataFrame, buffer_km: float = 50) -> Optional[Tuple]:
    """
    Строит bbox по точкам с буфером
    
    Args:
        df_points: DataFrame с точками
        buffer_km: буфер в километрах
        
    Returns:
        Кортеж (south, west, north, east) или None
    """
    if df_points.empty:
        return None
    
    lat_min, lat_max = df_points['latitude'].min(), df_points['latitude'].max()
    lon_min, lon_max = df_points['longitude'].min(), df_points['longitude'].max()
    
    # Конвертация км в градусы (приблизительно)
    buffer_deg = buffer_km / 111.0
    
    return (
        lat_min - buffer_deg,  # south
        lon_min - buffer_deg,  # west
        lat_max + buffer_deg,  # north
        lon_max + buffer_deg   # east
    )


def ensure_pbf_file() -> Optional[str]:
    """
    Проверяет наличие PBF-файла, при необходимости загружает его
    
    Returns:
        Путь к PBF-файлу или None
    """
    # Проверяем наличие файла
    if os.path.exists(PBF_PATH):
        file_size_mb = os.path.getsize(PBF_PATH) / (1024 * 1024)
        if file_size_mb > 50:
            print(f"✅ PBF-файл найден: {PBF_PATH} ({file_size_mb:.1f} МБ)")
            return PBF_PATH
        else:
            print(f"⚠️ PBF-файл поврежден (размер {file_size_mb:.1f} МБ)")
            # Удаляем поврежденный файл
            try:
                os.remove(PBF_PATH)
                print("   Поврежденный файл удален")
            except:
                pass
    
    # Спрашиваем пользователя
    print(f"\n⚠️ PBF-файл {PBF_FILENAME} не найден в папке {DATA_DIR}")
    response = input("Хотите скачать его автоматически? (y/n): ")
    
    if response.lower() == 'y':
        from .download_pbf import download_pbf
        if download_pbf():
            return PBF_PATH
        else:
            return None
    else:
        print(f"\nℹ️ Вы можете скачать файл вручную:")
        print(f"   1. Перейдите на: https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf")
        print(f"   2. Сохраните файл как: {PBF_FILENAME}")
        print(f"   3. Поместите в папку: {DATA_DIR}")
        return None


def load_graph(df_points: Optional[pd.DataFrame] = None) -> Optional[nx.Graph]:
    """
    Загружает дорожный граф из кеша, PBF или интернета
    
    Стратегия загрузки:
    1. Попытка загрузить из кеша GraphML (быстро)
    2. Если кеша нет - загрузка из PBF через pyrosm
    3. Если PBF нет - загрузка через интернет (OSMnx)
    4. Если интернет недоступен - использование прямых линий
    
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

    # 2. Проверяем наличие PBF-файла
    print("\n🔄 Проверка PBF-файла...")
    
    # Проверяем существование и размер
    if os.path.exists(PBF_PATH):
        file_size_mb = os.path.getsize(PBF_PATH) / (1024 * 1024)
        if file_size_mb < 50:
            print(f"⚠️ PBF-файл слишком мал ({file_size_mb:.1f} МБ), скачиваем заново...")
            from .download_pbf import download_pbf
            download_pbf(force=True)
    else:
        print(f"ℹ️ PBF-файл не найден в {DATA_DIR}")
        print("   Попытка автоматического скачивания...")
        from .download_pbf import download_pbf
        if not download_pbf():
            print("   ⚠️ Не удалось скачать PBF. Будет использован интернет-запрос.")
    
    # 3. Загрузка из PBF через pyrosm
    pbf_path = find_pbf_file()
    
    if pbf_path and os.path.getsize(pbf_path) > 50 * 1024 * 1024:
        print(f"\n🔄 Загрузка графа из PBF: {pbf_path}")
        try:
            from pyrosm import OSM
            
            # Если есть точки, загружаем только область вокруг них
            if df_points is not None and not df_points.empty:
                bbox = build_bbox_from_points(df_points, buffer_km=30)
                if bbox:
                    south, west, north, east = bbox
                    bbox_list = [west, south, east, north]
                    print(f"   Загрузка только области bbox: [{west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}]")
                    osm = OSM(pbf_path, bounding_box=bbox_list)
                else:
                    osm = OSM(pbf_path)
            else:
                osm = OSM(pbf_path)
            
            # Загрузка дорожной сети
            print("   Извлечение дорожной сети...")
            nodes, edges = osm.get_network(network_type='driving', nodes=True)
            
            if nodes is not None and edges is not None and not edges.empty:
                print(f"   Узлов: {len(nodes)}, рёбер: {len(edges)}")
                graph = osm.to_graph(nodes, edges, graph_type='networkx')
                
                if graph is not None and len(graph.nodes) > 0:
                    print(f"✅ Граф загружен из PBF (pyrosm). Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
                    
                    # Очищаем и сохраняем в кеш
                    graph_clean = clean_graph_for_graphml(graph)
                    try:
                        nx.write_graphml(graph_clean, GRAPHML_PATH)
                        print(f"✅ Граф сохранён в кеш: {GRAPHML_PATH}")
                    except Exception as e:
                        print(f"⚠️ Не удалось сохранить GraphML: {e}")
                    
                    _graph = graph_clean
                    return graph_clean
                else:
                    print("   ❌ Не удалось построить граф из PBF (пустой граф).")
            else:
                print("   ❌ Не удалось получить узлы/рёбра из PBF.")
        except ImportError as e:
            print(f"   ❌ Библиотека pyrosm не установлена: {e}")
            print("   Установите: pip install pyrosm")
        except Exception as e:
            print(f"   ❌ Ошибка загрузки из PBF: {e}")
    else:
        if pbf_path:
            print(f"   ⚠️ PBF-файл слишком мал: {os.path.getsize(pbf_path) / (1024*1024):.1f} МБ")
        else:
            print("   ⚠️ PBF-файл не найден")
    
    # 4. Загрузка через интернет (запасной вариант)
    print("\n🔄 Загрузка графа через интернет (запасной вариант)...")
    print("   Это может занять несколько минут...")
    
    if df_points is not None and not df_points.empty:
        bbox = build_bbox_from_points(df_points, buffer_km=50)
        if bbox:
            south, west, north, east = bbox
            print(f"   Загрузка по bbox: north={north:.4f}, south={south:.4f}, east={east:.4f}, west={west:.4f}")
            
            # Список эндпоинтов Overpass API
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
                    
                    # Пробуем разные версии API
                    try:
                        # Новый синтаксис (именованные аргументы)
                        graph = ox.graph_from_bbox(
                            north=north, 
                            south=south, 
                            east=east, 
                            west=west,
                            network_type='drive', 
                            simplify=True
                        )
                    except TypeError:
                        # Старый синтаксис (позиционные аргументы)
                        graph = ox.graph_from_bbox(
                            north, south, east, west,
                            network_type='drive', 
                            simplify=True
                        )
                    
                    if graph is not None and len(graph.nodes) > 0:
                        print(f"✅ Граф загружен по bbox. Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
                        graph_clean = clean_graph_for_graphml(graph)
                        try:
                            nx.write_graphml(graph_clean, GRAPHML_PATH)
                            print(f"✅ Граф сохранён в кеш: {GRAPHML_PATH}")
                        except Exception as e:
                            print(f"⚠️ Не удалось сохранить GraphML: {e}")
                        _graph = graph_clean
                        return graph_clean
                    else:
                        print("   ❌ Пустой граф.")
                except Exception as e:
                    print(f"   ⚠️ Ошибка: {e}")
                    continue
    
    # 5. Загрузка области по умолчанию (Нижегородская область)
    try:
        print("🔄 Загрузка Нижегородской области через интернет...")
        ox.settings.overpass_endpoint = "https://overpass-api.de/api/interpreter"
        ox.settings.timeout = 1200
        ox.settings.max_retries = 10
        
        graph = ox.graph_from_place(
            'Нижегородская область, Россия', 
            network_type='drive', 
            simplify=True
        )
        
        if graph is not None and len(graph.nodes) > 0:
            print(f"✅ Граф загружен для области. Узлов: {len(graph.nodes)}, рёбер: {len(graph.edges)}")
            graph_clean = clean_graph_for_graphml(graph)
            try:
                nx.write_graphml(graph_clean, GRAPHML_PATH)
                print(f"✅ Граф сохранён в кеш: {GRAPHML_PATH}")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить GraphML: {e}")
            _graph = graph_clean
            return graph_clean
    except Exception as e:
        print(f"   ⚠️ Не удалось загрузить область: {e}")

    print("\n❌ Все попытки загрузки графа не удались. Будут использованы прямые линии.")
    print("   Для более точных маршрутов:")
    print("   1. Установите pyrosm: pip install pyrosm")
    print(f"   2. Скачайте PBF-файл в папку {DATA_DIR}")
    return None


def load_road_cache():
    """
    Загружает кеш дорожных расстояний из файла
    """
    global _road_cache
    if os.path.exists(ROAD_DIST_CACHE_FILE):
        try:
            with open(ROAD_DIST_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Преобразуем строковые ключи обратно в кортежи
            _road_cache = {}
            for k, v in data.items():
                try:
                    # Безопасное преобразование строки в кортеж
                    # Ожидаемый формат: "(lat1, lon1, lat2, lon2)"
                    if k.startswith('(') and k.endswith(')'):
                        # Удаляем скобки и разбиваем по запятым
                        parts = k[1:-1].split(', ')
                        if len(parts) == 4:
                            key = (float(parts[0]), float(parts[1]), 
                                   float(parts[2]), float(parts[3]))
                            _road_cache[key] = v
                except (ValueError, TypeError) as e:
                    # Пропускаем некорректные ключи
                    continue
            
            print(f"✅ Загружено {len(_road_cache)} записей кеша дорожных расстояний.")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки кеша: {e}. Будет создан новый кеш.")
            _road_cache = {}
    else:
        print("ℹ️ Файл кеша дорожных расстояний не найден. Будет создан новый.")


def save_road_cache():
    """
    Сохраняет кеш дорожных расстояний в файл
    """
    global _road_cache
    try:
        # Преобразуем кортежи в строки для JSON-сериализации
        cache_str_keys = {}
        for k, v in _road_cache.items():
            if isinstance(k, tuple) and len(k) == 4:
                # Форматируем с высокой точностью
                key_str = f"({k[0]:.6f}, {k[1]:.6f}, {k[2]:.6f}, {k[3]:.6f})"
                cache_str_keys[key_str] = v
        
        with open(ROAD_DIST_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_str_keys, f, ensure_ascii=False, indent=2)
        
        print(f"✅ Кеш дорожных расстояний сохранён ({len(_road_cache)} записей).")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения кеша: {e}")


def get_nearest_node(lat: float, lon: float):
    """
    Возвращает ближайший узел графа с кешированием
    
    Args:
        lat: широта
        lon: долгота
        
    Returns:
        ID узла в графе или None
    """
    global _nearest_node_cache, _graph
    
    if _graph is None:
        return None
    
    key = (round(lat, 6), round(lon, 6))
    
    if key not in _nearest_node_cache:
        try:
            _nearest_node_cache[key] = ox.distance.nearest_nodes(_graph, lon, lat)
        except Exception:
            _nearest_node_cache[key] = None
    
    return _nearest_node_cache.get(key)


def road_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Возвращает расстояние между точками по дорогам, либо по прямой
    
    Стратегия:
    1. Если граф загружен - пробуем найти кратчайший путь по дорогам
    2. Если дороги нет или граф не загружен - используем геодезическое расстояние
    
    Args:
        lat1, lon1: координаты первой точки
        lat2, lon2: координаты второй точки
        
    Returns:
        Расстояние в километрах
    """
    global _graph, _road_cache
    
    # Если граф не загружен - сразу считаем по прямой
    if _graph is None:
        return geodesic((lat1, lon1), (lat2, lon2)).kilometers

    # Округляем координаты для ключа кеша
    key = (round(lat1, 6), round(lon1, 6), round(lat2, 6), round(lon2, 6))
    
    # Проверяем кеш в обе стороны
    if key in _road_cache:
        return _road_cache[key]
    
    rev_key = (key[2], key[3], key[0], key[1])
    if rev_key in _road_cache:
        return _road_cache[rev_key]

    try:
        # Получаем ближайшие узлы графа
        node1 = get_nearest_node(lat1, lon1)
        node2 = get_nearest_node(lat2, lon2)
        
        # Если узлы найдены и есть путь между ними
        if node1 is not None and node2 is not None:
            if nx.has_path(_graph, node1, node2):
                # Вычисляем кратчайший путь по длине
                dist_m = nx.shortest_path_length(_graph, node1, node2, weight='length')
                dist_km = dist_m / 1000.0
            else:
                # Если пути нет - используем прямую
                dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers
        else:
            # Если узлы не найдены - используем прямую
            dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers
            
    except Exception as e:
        # В случае любой ошибки - используем прямую
        # print(f"   ⚠️ Ошибка road_distance: {e}")
        dist_km = geodesic((lat1, lon1), (lat2, lon2)).kilometers

    # Сохраняем в кеш
    _road_cache[key] = dist_km
    return dist_km


def calculate_matrix_distances(coords: list, eps_km: float = 25) -> Tuple[np.ndarray, bool]:
    """
    Вычисляет матрицу расстояний между точками
    
    Args:
        coords: список кортежей (lat, lon)
        eps_km: порог для использования дорожных расстояний
        
    Returns:
        Матрица расстояний и флаг использования дорог
    """
    import numpy as np
    
    n = len(coords)
    dist_matrix = np.zeros((n, n))
    use_road = graph_is_available()
    
    for i in range(n):
        for j in range(i + 1, n):
            # Сначала вычисляем геодезическое расстояние
            geo_dist = geodesic(coords[i], coords[j]).kilometers
            
            # Если точки далеко друг от друга - используем геодезическое
            if geo_dist > eps_km * 2:
                dist_matrix[i, j] = geo_dist
                dist_matrix[j, i] = geo_dist
            elif use_road:
                # Если близко - пробуем дорожное расстояние
                d = road_distance(coords[i][0], coords[i][1], 
                                 coords[j][0], coords[j][1])
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d
            else:
                dist_matrix[i, j] = geo_dist
                dist_matrix[j, i] = geo_dist
    
    return dist_matrix, use_road


def get_cluster_diameter(cluster_points: pd.DataFrame) -> Tuple[float, float]:
    """
    Вычисляет диаметр кластера и время в пути
    
    Args:
        cluster_points: DataFrame с точками кластера
        
    Returns:
        (diameter_km, time_hours)
    """
    coords = list(zip(cluster_points['latitude'], cluster_points['longitude']))
    max_dist = 0
    
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            if graph_is_available():
                d = road_distance(coords[i][0], coords[i][1], 
                                 coords[j][0], coords[j][1])
            else:
                d = geodesic(coords[i], coords[j]).kilometers
            
            if d > max_dist:
                max_dist = d
    
    # Время в пути: туда и обратно (2 * диаметр / скорость)
    from .config import AVG_SPEED
    time_hours = 2 * max_dist / AVG_SPEED if max_dist > 0 else 0
    
    return max_dist, time_hours