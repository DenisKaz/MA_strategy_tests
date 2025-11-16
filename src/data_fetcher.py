"""
Модуль для загрузки OHLCV данных с криптовалютных бирж.
"""
import ccxt
import pandas as pd
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import logging

from .config import ExchangeConfig, FetchConfig, DATA_DIR

logger = logging.getLogger(__name__)


class DataFetcher:
    """
    Загружает исторические OHLCV данные с биржи и сохраняет в CSV.
    
    Параметры:
        exchange_config: конфигурация биржи
        fetch_config: конфигурация загрузки
    """
    
    def __init__(self, exchange_config: ExchangeConfig, fetch_config: FetchConfig):
        self.exchange_config = exchange_config
        self.fetch_config = fetch_config
        
        # Инициализация биржи
        exchange_class = getattr(ccxt, exchange_config.exchange_id)
        self.exchange = exchange_class({
            'enableRateLimit': exchange_config.enable_rate_limit,
            'apiKey': exchange_config.api_key,
            'secret': exchange_config.api_secret,
        })
        
        logger.info(f"Инициализирована биржа: {exchange_config.exchange_id}")
    
    def validate_symbols(self) -> List[str]:
        """Проверить наличие символов на бирже и вернуть валидные."""
        self.exchange.load_markets()
        available_symbols = []
        
        for symbol in self.fetch_config.symbols:
            if symbol in self.exchange.symbols:
                available_symbols.append(symbol)
                logger.debug(f"✓ Символ найден: {symbol}")
            else:
                logger.warning(f"✗ Символ НЕ найден: {symbol}")
        
        if not available_symbols:
            raise ValueError("Ни один из символов не найден на бирже!")
        
        return available_symbols
    
    def _fetch_ohlcv_all(self, symbol: str, timeframe: str, since: Optional[int] = None) -> pd.DataFrame:
        """
        Загрузить ВСЕ доступные OHLCV данные для пары/таймфрейма.
        
        Параметры:
            symbol: торговая пара (например, 'BTC/USDT')
            timeframe: таймфрейм ('1m', '5m', '1h', '1d', и т.д.)
            since: метка времени начала (мс) или None для начала с 0
        
        Возвращает:
            DataFrame с колонками: ts, open, high, low, close, volume, datetime (индекс)
        """
        all_bars = []
        now = self.exchange.milliseconds()
        fetch_since = since if since is not None else 0
        
        logger.info(f"Загрузка {symbol} {timeframe} (с {since or 'начала'})")
        
        request_count = 0
        while True:
            try:
                bars = self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe=timeframe,
                    since=fetch_since,
                    limit=self.fetch_config.limit_per_request,
                )
            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                logger.warning(f"Ошибка сети/биржи: {e}. Пробую ещё...")
                time.sleep(5)
                continue
            
            if not bars:
                logger.debug(f"  Нет новых данных, выход")
                break
            
            all_bars.extend(bars)
            request_count += 1
            
            if len(all_bars) >= self.fetch_config.max_candles:
                logger.info(f"  Достигнут лимит {self.fetch_config.max_candles} свечей")
                break
            
            last_ts = bars[-1][0]
            
            # Если достигли текущего времени — выход
            tf_ms = self.exchange.parse_timeframe(timeframe) * 1000
            if last_ts >= now - tf_ms:
                logger.debug(f"  Достигнуто текущее время")
                break
            
            fetch_since = last_ts + 1
            time.sleep(self.exchange.rateLimit / 1000)
            
            if request_count % 10 == 0:
                logger.info(f"  Загружено {len(all_bars)} свечей ({request_count} запросов)...")
        
        # Преобразование в DataFrame
        df = pd.DataFrame(all_bars, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
        df = df.set_index('datetime')
        df = df.sort_index()
        
        logger.info(f"  ✓ Загружено {len(df)} свечей за {request_count} запросов")
        return df
    
    def fetch_and_save(self, symbols: Optional[List[str]] = None) -> None:
        """
        Загрузить данные для всех пар/таймфреймов и сохранить в CSV.
        
        Параметры:
            symbols: список пар (если None, используется из конфига)
        """
        symbols = symbols or self.validate_symbols()
        
        # Вычислить with since для таймфреймов < 1d
        threshold_tf_seconds = self.exchange.parse_timeframe(self.fetch_config.timeframe_threshold)
        years_ms = self.fetch_config.years_of_history * 365 * 24 * 60 * 60 * 1000
        since_for_small_tf = self.exchange.milliseconds() - years_ms
        
        logger.info(f"Начинаю загрузку данных...")
        logger.info(f"  Пары: {symbols}")
        logger.info(f"  Таймфреймы: {self.fetch_config.timeframes}")
        
        total = len(symbols) * len(self.fetch_config.timeframes)
        current = 0
        
        for symbol in symbols:
            for tf in self.fetch_config.timeframes:
                current += 1
                tf_seconds = self.exchange.parse_timeframe(tf)
                
                # Определить since: для мелких TF — история, для крупных — с начала
                since = since_for_small_tf if tf_seconds < threshold_tf_seconds else None
                
                logger.info(f"[{current}/{total}] Загружаю {symbol} {tf}...")
                
                df = self._fetch_ohlcv_all(symbol, tf, since=since)
                
                # Сохранить в CSV
                safe_symbol = symbol.replace('/', '_')
                filename = f"{self.exchange_config.exchange_id}_{safe_symbol}_{tf}.csv"
                filepath = DATA_DIR / filename
                
                df.to_csv(filepath)
                logger.info(f"  → Сохранено: {filepath} ({len(df)} строк)")
        
        logger.info("✓ Загрузка завершена!")
