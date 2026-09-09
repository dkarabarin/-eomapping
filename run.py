
"""
Скрипт запуска сервиса геопланирования
"""

import os
import sys
import webbrowser

# Добавляем путь к src в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import (
    load_and_validate_data,
    load_graph,
    load_road_cache,
    save_road_cache,
    cluster_points_dbscan_final,
    process_clusters_by_manager,
    assign_clusters_to_days,
    build_schedule,
    build_final_map,
    save_results
)
from src.config import DATA_PATH, OUTPUT_DIR, PBF_PATH, DATA_DIR
from src.download_pbf import check_pbf_file, download_pbf


def check_data_files():
    """Проверяет наличие всех необходимых файлов"""
    print("\n📁 Проверка файлов...")
    print(f"   Папка данных: {DATA_DIR}")
    
    # Проверка папки data
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        print(f"   ✅ Создана папка: {DATA_DIR}")
    
    # Проверка файла данных
    if not os.path.exists(DATA_PATH):
        print(f"❌ Файл с данными не найден: {DATA_PATH}")
        print("   Создайте файл data/data.csv с необходимыми данными")
        return False
    
    print(f"✅ Данные найдены: {DATA_PATH}")
    print(f"   Размер: {os.path.getsize(DATA_PATH) / 1024:.1f} КБ")
    
    # Проверка PBF файла
    print(f"\n📄 Проверка PBF-файла: {PBF_PATH}")
    if os.path.exists(PBF_PATH):
        file_size_mb = os.path.getsize(PBF_PATH) / (1024 * 1024)
        if file_size_mb > 50:
            print(f"✅ PBF-файл найден ({file_size_mb:.1f} МБ)")
        else:
            print(f"⚠️ PBF-файл слишком мал ({file_size_mb:.1f} МБ)")
            response = input("   Хотите скачать заново? (y/n): ")
            if response.lower() == 'y':
                if not download_pbf(force=True):
                    print("   ⚠️ Не удалось скачать PBF. Будет использован интернет-запрос.")
    else:
        print(f"⚠️ PBF-файл не найден в папке {DATA_DIR}")
        response = input("   Хотите скачать его автоматически? (y/n): ")
        if response.lower() == 'y':
            if not download_pbf():
                print("   ⚠️ Не удалось скачать PBF. Будет использован интернет-запрос.")
        else:
            print("   ⚠️ Будет использован интернет-запрос (может быть медленно)")
    
    print("\n" + "-" * 60)
    return True


def main():
    """Основная функция запуска"""
    print("=" * 60)
    print("🚀 ЗАПУСК СЕРВИСА ГЕОПЛАНИРОВАНИЯ")
    print("=" * 60)
    
    # Проверка файлов
    if not check_data_files():
        print("\n❌ Запуск прерван из-за ошибок с файлами")
        return
    
    # 1. Загрузка данных
    print("\n📂 Шаг 1: Загрузка данных...")
    try:
        df_original = load_and_validate_data(DATA_PATH)
        print(f"✅ Загружено {len(df_original)} точек")
        print(f"   Менеджеры: {sorted(df_original['manager'].unique())}")
        print(f"   Колонки: {list(df_original.columns)}")
    except FileNotFoundError as e:
        print(f"❌ Ошибка: {e}")
        print("   Убедитесь, что файл data/data.csv существует")
        return
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {e}")
        return
    
    # 2. Загрузка дорожного графа
    print("\n🗺️ Шаг 2: Загрузка дорожного графа...")
    graph = load_graph(df_original)
    if graph is not None:
        print(f"✅ Граф загружен ({len(graph.nodes)} узлов, {len(graph.edges)} рёбер)")
    else:
        print("⚠️ Граф не загружен, будут использоваться прямые линии")
    
    # 3. Загрузка кеша расстояний
    print("\n💾 Шаг 3: Загрузка кеша расстояний...")
    load_road_cache()
    
    # 4. Кластеризация
    print("\n🔄 Шаг 4: Кластеризация точек...")
    clusters_by_manager = process_clusters_by_manager(
        df_original,
        cluster_points_dbscan_final
    )
    
    # 5. Распределение по дням
    print("\n📅 Шаг 5: Распределение по дням...")
    day_schedule = assign_clusters_to_days(clusters_by_manager)
    
    # Вывод статистики по дням
    print("\n📊 Статистика по дням:")
    for day in sorted(day_schedule.keys()):
        data = day_schedule[day]
        if data['clusters']:
            managers = sorted(set(c['manager'] for c in data['clusters']))
            print(f"  День {day:2d}: {len(data['clusters']):2d} кластеров, "
                  f"{len(data['points']):3d} точек, "
                  f"{data['total_time']:.2f} ч, менеджеры: {managers}")
        else:
            print(f"  День {day:2d}: нет заданий")
    
    # 6. Формирование расписания
    print("\n📋 Шаг 6: Формирование расписания...")
    schedule_df = build_schedule(day_schedule, df_original)
    print(f"✅ Сформировано {len(schedule_df)} записей")
    
    # 7. Сохранение результатов
    print("\n💾 Шаг 7: Сохранение результатов...")
    save_results(schedule_df, day_schedule, clusters_by_manager)
    
    # 8. Визуализация
    print("\n🗺️ Шаг 8: Построение карты...")
    if len(schedule_df) > 0:
        try:
            route_map = build_final_map(df_original, day_schedule, clusters_by_manager)
            output_map = os.path.join(OUTPUT_DIR, "route_map_final.html")
            route_map.save(output_map)
            print(f"✅ Карта сохранена: {output_map}")
            
            # Открытие в браузере
            try:
                webbrowser.open(output_map)
                print("🌐 Карта открыта в браузере")
            except:
                print(f"📂 Откройте файл вручную: {output_map}")
        except Exception as e:
            print(f"⚠️ Ошибка при построении карты: {e}")
    else:
        print("⚠️ Нет данных для построения карты")
    
    # 9. Сохранение кеша
    print("\n💾 Шаг 9: Сохранение кеша...")
    save_road_cache()
    
    # Итог
    print("\n" + "=" * 60)
    print("✅ РАБОТА ЗАВЕРШЕНА УСПЕШНО!")
    print("=" * 60)
    print(f"\n📁 Результаты сохранены в папке: {OUTPUT_DIR}")
    print("   - schedule_final.csv - полное расписание")
    print("   - daily_stats_final.csv - статистика по дням")
    print("   - clusters_info_final.csv - информация о кластерах")
    print("   - route_map_final.html - интерактивная карта")
    
    # Вывод информации о файлах
    print(f"\n📦 Файлы в папке data:")
    if os.path.exists(DATA_PATH):
        print(f"   ✅ data.csv - {os.path.getsize(DATA_PATH) / 1024:.1f} КБ")
    if os.path.exists(PBF_PATH):
        pbf_size = os.path.getsize(PBF_PATH) / (1024 * 1024)
        print(f"   ✅ {