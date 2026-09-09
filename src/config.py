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

# Базовая директория
# укажите полный путь:
BASE_DIR = r"D:\denis\geolocation"

# Папка с данными (здесь будут и data.csv, и PBF-файл)
DATA_DIR = os.path.join(BASE_DIR, "data")

# Пути к файлам в папке data
DATA_PATH = os.path.join(DATA_DIR, "data.csv")
PBF_FILENAME = "volga-fed-district-260831.osm.pbf"
PBF_PATH = os.path.join(DATA_DIR, PBF_FILENAME)

# Папки для кеша и результатов
CACHE_DIR = os.path.join(BASE_DIR, "cache")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# GraphML кеш (сохраняется в cache)
GRAPHML_PATH = os.path.join(CACHE_DIR, "volga_graph.graphml")
ROAD_DIST_CACHE_FILE = os.path.join(CACHE_DIR, "road_dist_cache.json")

# Случайный seed
RANDOM_SEED = 42


# Создание директорий
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)