#!/usr/bin/env python3
"""
Скрипт для загрузки OHLCV данных с биржи.
Использование: python bin/fetch.py [--exchange bybit] [--symbols BTC/USDT ETH/USDT] [--years 1]
"""
import sys
import argparse
import logging
from pathlib import Path

# Добавить src в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import (
    DEFAULT_EXCHANGE_CONFIG,
    DEFAULT_FETCH_CONFIG,
    ExchangeConfig,
    FetchConfig,
)
from src.data_fetcher import DataFetcher

# Настроить логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description='Загрузить OHLCV данные с криптовалютной биржи',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python bin/fetch.py
  python bin/fetch.py --exchange bybit --symbols BTC/USDT ETH/USDT
  python bin/fetch.py --years 2 --limit 1000
        """,
    )
    
    parser.add_argument(
        '--exchange',
        default=DEFAULT_EXCHANGE_CONFIG.exchange_id,
        help='ID биржи (bybit, binance, kraken, и т.д.)',
    )
    
    parser.add_argument(
        '--symbols',
        nargs='+',
        default=DEFAULT_FETCH_CONFIG.symbols,
        help='Торговые пары (например: BTC/USDT ETH/USDT)',
    )
    
    parser.add_argument(
        '--timeframes',
        nargs='+',
        default=DEFAULT_FETCH_CONFIG.timeframes,
        help='Таймфреймы (1m 5m 1h 1d и т.д.)',
    )
    
    parser.add_argument(
        '--years',
        type=int,
        default=DEFAULT_FETCH_CONFIG.max_history_years,
        help='Глубина истории в годах для всех таймфреймов (по умолчанию: 4)',
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=DEFAULT_FETCH_CONFIG.limit_per_request,
        help='Лимит свечей на один запрос к бирже (по умолчанию: 1000)',
    )
    
    parser.add_argument(
        '--max-candles',
        type=int,
        default=DEFAULT_FETCH_CONFIG.max_candles_per_request,
        help='Максимум свечей в одной загрузке (по умолчанию: 500000)',
    )

    parser.add_argument(
        '--stream',
        action='store_true',
        default=DEFAULT_FETCH_CONFIG.stream_write,
        help='Включить потоковую запись CSV по частям (рекомендуется для больших TF)',
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный лог',
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Создать конфиги
    exchange_config = ExchangeConfig(
        exchange_id=args.exchange,
        enable_rate_limit=True,
    )
    
    fetch_config = FetchConfig(
        symbols=args.symbols,
        timeframes=args.timeframes,
        limit_per_request=args.limit,
        max_candles_per_request=args.max_candles,
        max_history_years=args.years,
        stream_write=args.stream,
    )
    
    # Выполнить загрузку
    try:
        fetcher = DataFetcher(exchange_config, fetch_config)
        fetcher.fetch_and_save()
        logger.info("✓ Успешно!")
        return 0
    except Exception as e:
        logger.error(f"✗ Ошибка: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
