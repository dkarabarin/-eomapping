"""
Сервис геопланирования

Модуль для автоматического распределения географических точек 
по дням месяца и формирования кластеров для ежедневного обхода.
"""

from .config import *
from .data_loader import load_and_validate_data
from .clustering import cluster_points_dbscan_final
from .routing import load_graph, load_road_cache, save_road_cache, road_distance
from .schedule import process_clusters_by_manager, assign_clusters_to_days, build_schedule
from .visualize import build_final_map, RoutePlanner
from .utils import save_results

__version__ = "2.0.0"