"""
Кластеризация точек с использованием DBSCAN и балансировка кластеров
"""

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from geopy.distance import geodesic
from typing import Dict, List, Optional
import pandas as pd
import warnings

from .config import EPS_KM, MAX_CLUSTER_SIZE, MIN_CLUSTER_SIZE, RANDOM_SEED
from .routing import road_distance, graph_is_available
from .utils import save_road_cache

warnings.filterwarnings('ignore')


def split_cluster_strict(point_ids: List[str], 
                         df_points: pd.DataFrame, 
                         max_size: int) -> List[List[str]]:
    """
    Разбивает кластер на подкластеры с использованием KMeans,
    если размер превышает max_size
    """
    if len(point_ids) <= max_size:
        return [point_ids]
    
    cluster_df = df_points[df_points['point_id'].isin(point_ids)]
    coords_sub = cluster_df[['latitude', 'longitude']].values
    n_clusters = int(np.ceil(len(point_ids) / max_size))
    kmeans = KMeans(n_clusters=n_clusters, random_state=RANDOM_SEED, n_init=10)
    labels_sub = kmeans.fit_predict(coords_sub)
    
    sub_clusters = {}
    for idx, label_sub in enumerate(labels_sub):
        sub_point_id = cluster_df.iloc[idx]['point_id']
        sub_clusters.setdefault(label_sub, []).append(sub_point_id)
    
    result = []
    for sub_points in sub_clusters.values():
        if len(sub_points) <= max_size:
            result.append(sub_points)
        else:
            result.extend(split_cluster_strict(sub_points, df_points, max_size))
    return result


def cluster_points_dbscan_final(df_points: pd.DataFrame,
                                eps_km: float = EPS_KM,
                                max_cluster_size: int = MAX_CLUSTER_SIZE,
                                min_cluster_size: int = MIN_CLUSTER_SIZE,
                                use_road: bool = False) -> Dict[int, List[str]]:
    """
    Кластеризация точек с помощью DBSCAN с последующим разбиением и объединением кластеров
    
    Args:
        df_points: DataFrame с точками
        eps_km: радиус кластеризации в км
        max_cluster_size: максимальный размер кластера
        min_cluster_size: минимальный размер кластера для объединения
        use_road: использовать дорожные расстояния (медленно) или геодезические
    
    Returns:
        Словарь {cluster_id: [point_id, ...]}
    """
    if len(df_points) == 0:
        return {}
    
    coords = df_points[['latitude', 'longitude']].values
    n = len(coords)

    # DBSCAN кластеризация
    if use_road and graph_is_available():
        print("  Вычисление дорожной матрицы расстояний...")
        dist_matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(i + 1, n):
                geo_dist = geodesic((coords[i][0], coords[i][1]), 
                                   (coords[j][0], coords[j][1])).kilometers
                if geo_dist > eps_km * 2:
                    dist_matrix[i, j] = geo_dist
                    dist_matrix[j, i] = geo_dist
                else:
                    d = road_distance(coords[i][0], coords[i][1], 
                                     coords[j][0], coords[j][1])
                    dist_matrix[i, j] = d
                    dist_matrix[j, i] = d
        db = DBSCAN(eps=eps_km, min_samples=1, metric='precomputed')
        labels = db.fit_predict(dist_matrix)
        save_road_cache()
    else:
        coords_rad = np.radians(coords)
        eps_rad = eps_km / 111.32
        db = DBSCAN(eps=eps_rad, min_samples=1, metric='haversine')
        labels = db.fit_predict(coords_rad)

    # Группировка по кластерам
    clusters = {}
    for idx, label in enumerate(labels):
        point_id = df_points.iloc[idx]['point_id']
        clusters.setdefault(label, []).append(point_id)

    print(f"  DBSCAN (eps={eps_km}км) создал {len(clusters)} кластеров")
    sizes = [len(pts) for pts in clusters.values()]
    if sizes:
        print(f"  Размеры: от {min(sizes)} до {max(sizes)}, средний {sum(sizes)/len(sizes):.1f}")

    # Разбиение больших кластеров
    final_clusters = {}
    new_id = 0
    for label, point_ids in clusters.items():
        for sub_points in split_cluster_strict(point_ids, df_points, max_cluster_size):
            final_clusters[new_id] = sub_points
            new_id += 1
    print(f"  После разбиения больших: {len(final_clusters)} кластеров")

    # Объединение маленьких кластеров
    used = set()
    merged = {}
    sorted_clusters = sorted(final_clusters.items(), key=lambda x: len(x[1]))
    
    for cid, pts in sorted_clusters:
        if cid in used:
            continue
        if len(pts) < min_cluster_size:
            cluster_df = df_points[df_points['point_id'].isin(pts)]
            center = (cluster_df['latitude'].mean(), cluster_df['longitude'].mean())
            best_dist = float('inf')
            best_cid = None
            
            for oid, opts in sorted_clusters:
                if oid == cid or oid in used:
                    continue
                if len(opts) + len(pts) > max_cluster_size:
                    continue
                other_df = df_points[df_points['point_id'].isin(opts)]
                other_center = (other_df['latitude'].mean(), other_df['longitude'].mean())
                
                if use_road and graph_is_available():
                    d = road_distance(center[0], center[1], other_center[0], other_center[1])
                else:
                    d = geodesic(center, other_center).kilometers
                    
                if d < best_dist:
                    best_dist = d
                    best_cid = oid
                    
            if best_cid is not None:
                merged[best_cid] = final_clusters[best_cid] + pts
                used.add(cid)
                used.add(best_cid)
            else:
                merged[cid] = pts
                used.add(cid)
        else:
            if cid not in used:
                merged[cid] = pts
                used.add(cid)
    
    print(f"  После объединения маленьких: {len(merged)} кластеров")

    # Финальная обработка
    final_result = {}
    new_id = 0
    for cid, pts in merged.items():
        if len(pts) <= max_cluster_size:
            final_result[new_id] = pts
            new_id += 1
        else:
            for sub in split_cluster_strict(pts, df_points, max_cluster_size):
                final_result[new_id] = sub
                new_id += 1

    sizes = [len(pts) for pts in final_result.values()]
    if sizes:
        print(f"  Финальные размеры: от {min(sizes)} до {max(sizes)}, средний {sum(sizes)/len(sizes):.1f}")
        print(f"  Кластеров с размером > {max_cluster_size}: {sum(1 for s in sizes if s > max_cluster_size)}")
        print(f"  Кластеров с размером < {min_cluster_size}: {sum(1 for s in sizes if s < min_cluster_size)}")
    
    return final_result