

"""
Скрипт для ручного скачивания PBF-файла в папку data
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.download_pbf import download_pbf, check_pbf_file
from src.config import PBF_PATH, DATA_DIR, PBF_FILENAME


def main():
    print("=" * 60)
    print("📥 СКАЧИВАНИЕ PBF-ФАЙЛА")
    print("=" * 60)
    print(f"📁 Папка сохранения: {DATA_DIR}")
    print(f"📄 Имя файла: {PBF_FILENAME}")
    print("=" * 60)
    
    # Проверяем существующий файл
    if check_pbf_file():
        print(f"\n✅ Файл уже существует: {PBF_PATH}")
        response = input("\nХотите скачать заново? (y/n): ")
        if response.lower() != 'y':
            print("\nℹ️ Используйте существующий файл.")
            return
    
    print("\n🔄 Начинаем скачивание...")
    print("   (Файл будет сохранен в папку data/)")
    print()
    
    if download_pbf(force=True):
        print("\n" + "=" * 60)
        print("✅ Скачивание завершено успешно!")
        print("=" * 60)
        check_pbf_file()
    else:
        print("\n" + "=" * 60)
        print("❌ Скачивание не удалось.")
        print("=" * 60)
        print(f"\n📝 Попробуйте скачать файл вручную:")
        print(f"   1. Откройте: https://download.geofabrik.de/russia/volga-fed-district-latest.osm.pbf")
        print(f"   2. Сохраните файл как: {PBF_FILENAME}")
        print(f"   3. Поместите в папку: {DATA_DIR}")
        print(f"   (Полный путь: {PBF_PATH})")


if __name__ == "__main__":
    main()