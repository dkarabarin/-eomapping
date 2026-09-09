"""
Загрузка и валидация данных
"""

import os
import pandas as pd
import numpy as np
from typing import Optional
from .config import DATA_PATH


def load_and_validate_data(filepath: Optional[str] = None) -> pd.DataFrame:
    """
    Загружает и валидирует данные из CSV-файла
    
    Ожидаемые колонки: point_id, latitude, longitude, visits_per_month
    Допускаются альтернативные названия: lat, lon, n_visits
    
    Args:
        filepath: путь к файлу CSV
        
    Returns:
        DataFrame с валидными данными
    """
    if filepath is None:
        filepath = DATA_PATH
        
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Файл не найден: {filepath}")
    
    df = pd.read_csv(filepath)
    
    # Переименование колонок
    rename_map = {}
    if 'lat' in df.columns and 'latitude' not in df.columns:
        rename_map['lat'] = 'latitude'
    if 'lon' in df.columns and 'longitude' not in df.columns:
        rename_map['lon'] = 'longitude'
    if 'n_visits' in df.columns and 'visits_per_month' not in df.columns:
        rename_map['n_visits'] = 'visits_per_month'
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
    
    required_cols = ['point_id', 'latitude', 'longitude', 'visits_per_month']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Отсутствуют обязательные колонки: {missing}")
    
    # Очистка данных
    df.dropna(subset=required_cols, inplace=True)
    df['point_id'] = df['point_id'].astype(str)
    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
    df['visits_per_month'] = pd.to_numeric(df['visits_per_month'], errors='coerce').astype('Int64')
    
    # Фильтрация по координатам
    df = df[(df['latitude'].between(-90, 90)) & (df['longitude'].between(-180, 180))]
    df = df[df['visits_per_month'] >= 1]
    
    # Удаление дубликатов
    df.drop_duplicates(subset='point_id', keep='first', inplace=True)
    
    # Ограничение визитов
    df['visits_per_month'] = df['visits_per_month'].clip(upper=2)
    
    return df.reset_index(drop=True)