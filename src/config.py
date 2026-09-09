"""
Конфигурационные параметры сервиса геопланирования
"""

import os

# Параметры кластеризации
EPS_KM = 25
MAX_CLUSTER_SIZE = 12
MIN_CLUSTER_SIZE = 8
WORKING_DAYS = 22

# Скорость движения (км/ч)
AVG_SPEED = 60

# Город
CITY_CENTER_LAT = 56.3269
CITY_CENTER_LON = 44.0052

# Базовая директория (изменить под свою)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = r"D:\denis\geolocation"  # Указать путь к папке где лежат файлы

CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
DATA_PATH = os.path.join(BASE_DIR, "data", "data.csv")
GRAPHML_PATH = os.path.join(CACHE_DIR, "volga_graph.graphml")
ROAD_DIST_CACHE_FILE = os.path.join(CACHE_DIR, "road_dist_cache.json")

# Случайный seed
RANDOM_SEED = 42

# Создание директорий
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DATA_PATH) if os.path.dirname(DATA_PATH) else DATA_PATH, exist_ok=True)