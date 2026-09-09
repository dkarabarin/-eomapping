"""
Модуль для загрузки PBF-файлов с OpenStreetMap
"""

import os
import sys
import requests
import time
from tqdm import tqdm
from typing import Optional

# Импортируем пути из config
from .config import PBF_PATH, PBF_DOWNLOAD_URL, PBF_FILENAME, DATA_DIR


def download_file(url: str, filename: str, chunk_size: int = 8192) -> bool:
    """
    Скачивает файл с отображением прогресса
    
    Args:
        url: URL для скачивания
        filename: путь для сохранения файла
        chunk_size: размер чанка для скачивания
        
    Returns:
        True если скачивание успешно, иначе False
    """
    try:
        print(f"📥 Начинаем скачивание: {url}")
        print(f"📁 Сохранение в: {filename}")
        
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Проверяем, существует ли частично скачанный файл
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            headers = {'Range': f'bytes={file_size}-'}
            print(f"   Продолжаем загрузку с {file_size / (1024*1024):.1f} МБ")
        else:
            file_size = 0
            headers = {}
        
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0)) + file_size
        
        # Режим дозагрузки
        mode = 'ab' if file_size > 0 else 'wb'
        
        with open(filename, mode) as f:
            with tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                desc="Скачивание",
                initial=file_size,
                bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]'
            ) as pbar:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))
        
        # Проверяем размер
        final_size = os.path.getsize(filename)
        if final_size >= total_size - 1024:  # Допускаем небольшую погрешность
            print(f"✅ Файл успешно скачан: {filename}")
            print(f"   Размер: {final_size / (1024*1024):.2f} МБ")
            return True
        else:
            print(f"⚠️ Файл скачан не полностью. {final_size / (1024*1024):.1f} МБ из {total_size / (1024*1024):.1f} МБ")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка скачивания: {e}")
        return False
    except Exception as e:
        print(f"❌ Непредвиденная ошибка: {e}")
        return False


def find_alternative_urls() -> list:
    """
    Возвращает список альтернативных URL для скачивания
    """
    return [
        "https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf",
        "https://download.openstreetmap.fr/extracts/europe/russia/volga-fed-district-latest.osm.pbf",
        "https://ftp-stud.hs-esslingen.de/pub/Mirrors/download.openstreetmap.org/extracts/europe/russia/volga-fed-district-latest.osm.pbf"
    ]


def check_pbf_file() -> bool:
    """
    Проверяет наличие PBF-файла
    
    Returns:
        True если файл существует и его размер > 50 МБ
    """
    if not os.path.exists(PBF_PATH):
        print(f"❌ PBF-файл не найден: {PBF_PATH}")
        return False
    
    file_size_mb = os.path.getsize(PBF_PATH) / (1024 * 1024)
    if file_size_mb < 50:
        print(f"⚠️ PBF-файл слишком мал: {file_size_mb:.1f} МБ (ожидается >50 МБ)")
        print(f"   Возможно, файл поврежден. Удалите его и скачайте заново.")
        return False
    
    print(f"✅ PBF-файл найден: {PBF_PATH}")
    print(f"   Размер: {file_size_mb:.1f} МБ")
    return True


def download_pbf(force: bool = False) -> bool:
    """
    Загружает PBF-файл, если он отсутствует или поврежден
    
    Args:
        force: принудительная перезагрузка
        
    Returns:
        True если файл доступен
    """
    # Проверяем существование файла
    if os.path.exists(PBF_PATH) and not force:
        if check_pbf_file():
            return True
        else:
            print("🔄 Файл поврежден, скачиваем заново...")
            # Удаляем поврежденный файл
            try:
                os.remove(PBF_PATH)
            except:
                pass
    
    # Проверяем наличие папки data
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"📁 Создана папка: {DATA_DIR}")
    
    # Пробуем скачать с основного URL
    print(f"\n📥 Скачивание PBF-файла для Приволжского федерального округа...")
    print(f"   Файл: {PBF_FILENAME}")
    print(f"   Размер файла: ~150-200 МБ")
    print(f"   Это может занять несколько минут...")
    print(f"   Папка сохранения: {DATA_DIR}")
    print()
    
    success = download_file(PBF_DOWNLOAD_URL, PBF_PATH)
    
    if not success:
        print("\n⚠️ Основной URL недоступен, пробуем альтернативные...")
        alternative_urls = find_alternative_urls()
        
        for url in alternative_urls:
            print(f"\n🔄 Пробуем: {url}")
            success = download_file(url, PBF_PATH)
            if success:
                break
            time.sleep(2)
    
    if success:
        return check_pbf_file()
    else:
        print("\n❌ Не удалось скачать PBF-файл.")
        print(f"\n📝 Вы можете скачать его вручную:")
        print(f"   1. Перейдите на: {PBF_DOWNLOAD_URL}")
        print(f"   2. Сохраните файл как: {PBF_FILENAME}")
        print(f"   3. Поместите в папку: {DATA_DIR}")
        print(f"   (Полный путь: {PBF_PATH})")
        return False


def get_pbf_file() -> Optional[str]:
    """
    Возвращает путь к PBF-файлу, загружая его при необходимости
    
    Returns:
        Путь к файлу или None
    """
    if check_pbf_file():
        return PBF_PATH
    
    print("\n⚠️ PBF-файл не найден или поврежден.")
    print(f"   Ожидаемый путь: {PBF_PATH}")
    response = input("\nХотите скачать его автоматически? (y/n): ")
    
    if response.lower() == 'y':
        if download_pbf():
            return PBF_PATH
        else:
            return None
    else:
        print(f"\nℹ️ Поместите файл {PBF_FILENAME} в папку {DATA_DIR}")
        print(f"   Или скачайте вручную с: {PBF_DOWNLOAD_URL}")
        return None


if __name__ == "__main__":
    # Тестовый запуск
    print("=" * 60)
    print("ПРОВЕРКА PBF-ФАЙЛА")
    print("=" * 60)
    print(f"📁 Папка данных: {DATA_DIR}")
    print(f"📄 Ожидаемый файл: {PBF_FILENAME}")
    print("=" * 60)
    
    pbf_file = get_pbf_file()
    if pbf_file:
        print(f"\n✅ Файл готов к использованию: {pbf_file}")
    else:
        print("\n❌ Файл не найден. Скачайте его вручную.")