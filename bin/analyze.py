#!/usr/bin/env python3
"""
Анализ отскоков от Moving Averages.

Алгоритм: перебор периодов SMA/EMA, поиск "ровных отскоков" (только хвостом),
проверка достижения цели и расчёт метрик (win_rate и т.д.).

Примеры запуска:
  python bin/analyze.py
  python bin/analyze.py --ma-min 5 --ma-max 100
  python bin/analyze.py --target 0.05 --alpha-wick 0.25
  python bin/analyze.py -v
"""
import sys
import argparse
import logging
from pathlib import Path

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import AnalysisConfig
from src.analyzer import Analyzer

# Настроить логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Анализировать отскоки от MA и находить оптимальные периоды',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python bin/analyze.py
  python bin/analyze.py --ma-min 10 --ma-max 100
  python bin/analyze.py --target 0.05 --alpha-wick 0.25 --n-pre 3
  python bin/analyze.py --ma-types SMA EMA --verbose
        """,
    )
    
    parser.add_argument(
        '--ma-min',
        type=int,
        default=5,
        help='Минимальный период MA (по умолчанию: 5)',
    )
    parser.add_argument(
        '--ma-max',
        type=int,
        default=233,
        help='Максимальный период MA (по умолчанию: 233)',
    )
    parser.add_argument(
        '--ma-types',
        nargs='+',
        choices=['SMA', 'EMA'],
        default=['SMA', 'EMA'],
        help='Типы средних для анализа (по умолчанию: SMA EMA)',
    )
    parser.add_argument(
        '--alpha-wick',
        type=float,
        default=0.30,
        help='Минимальная длина хвоста (доля размера свечи, по умолчанию: 0.30)',
    )
    parser.add_argument(
        '--n-pre',
        type=int,
        default=5,
        help='Количество свечей до касания без других касаний (по умолчанию: 5)',
    )
    parser.add_argument(
        '--n-post',
        type=int,
        default=5,
        help='Количество свечей после касания без других касаний (по умолчанию: 5)',
    )
    parser.add_argument(
        '--target',
        type=float,
        default=0.03,
        help='Целевое движение цены (доля, по умолчанию: 0.03 = 3%)',
    )
    parser.add_argument(
        '--max-lookahead',
        type=int,
        default=200,
        help='Максимум свечей вперёд для проверки цели (по умолчанию: 200)',
    )
    parser.add_argument(
        '--min-events',
        type=int,
        default=10,
        help='Минимум событий для значимого результата (по умолчанию: 10)',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Подробный лог',
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Создать конфиг
    analysis_config = AnalysisConfig(
        ma_period_min=args.ma_min,
        ma_period_max=args.ma_max,
        ma_types=args.ma_types,
        alpha_wick=args.alpha_wick,
        n_pre=args.n_pre,
        n_post=args.n_post,
        target_pct=args.target,
        max_lookahead=args.max_lookahead,
        min_events_for_significance=args.min_events,
    )
    
    # Выполнить анализ
    try:
        logger.info(f"Запуск анализа отскоков от MA...")
        logger.info(f"  Диапазон периодов: {args.ma_min}-{args.ma_max}")
        logger.info(f"  Типы MA: {', '.join(args.ma_types)}")
        logger.info(f"  Параметры отскока: alpha_wick={args.alpha_wick}, n_pre={args.n_pre}, n_post={args.n_post}")
        logger.info(f"  Целевое движение: {args.target*100:.1f}%")
        
        analyzer = Analyzer(analysis_config)
        results_df = analyzer.analyze_all_data()
        
        if not results_df.empty:
            logger.info("\n" + "="*100)
            logger.info("ТОП РЕЗУЛЬТАТОВ (отсортировано по win_rate):")
            logger.info("="*100)
            
            # Вывести топ-20
            top_results = results_df.head(20)
            logger.info(top_results.to_string(index=False))
            logger.info("="*100)
            logger.info(f"Всего найдено результатов: {len(results_df)}")
        else:
            logger.warning("Результатов не найдено")
        
        logger.info("✓ Анализ завершен успешно!")
        return 0
    
    except KeyboardInterrupt:
        logger.info("Анализ прервана пользователем")
        return 1
    except Exception as e:
        logger.error(f"✗ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
