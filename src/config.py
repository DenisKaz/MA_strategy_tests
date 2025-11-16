"""
Конфигурация приложения: параметры биржи, таймфреймы, пути, пороги анализа.
"""
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional

# Корневая директория проекта
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RESULTS_DIR = PROJECT_ROOT / 'results'

# Убедиться, что директории существуют
DATA_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)


@dataclass
class ExchangeConfig:
    """Конфигурация биржи"""
    exchange_id: str = 'bybit'
    enable_rate_limit: bool = True
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


@dataclass
class FetchConfig:
    """Конфигурация загрузки данных"""
    symbols: List[str] = field(default_factory=lambda: ['BTC/USDT', 'ETH/USDT'])
    timeframes: List[str] = field(default_factory=lambda: ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '1d'])
    limit_per_request: int = 1000  # Лимит свечей на запрос
    max_history_years: int = 4     # Максимальная глубина истории в годах (для всех таймфреймов)
    # Примечание: реальное количество свечей зависит от таймфрейма
    # 1m за 4 года ≈ 2M свечей; 1d за 4 года ≈ 1400 свечей
    max_candles_per_request: int = 500000  # Максимум свечей в одной выгрузке (на случай прерываний)


@dataclass
class AnalysisConfig:
    """Конфигурация анализа отскоков от MA"""
    # Диапазон периодов для перебора
    ma_period_min: int = 5
    ma_period_max: int = 233
    
    # Типы средних для анализа
    ma_types: List[str] = field(default_factory=lambda: ['SMA', 'EMA'])
    
    # Параметры определения отскока
    alpha_wick: float = 0.30  # Минимальная длина хвоста: 30% размера свечи
    n_pre: int = 5  # Количество свечей до, не касавшихся MA
    n_post: int = 5  # Количество свечей после, не касавшихся MA (тестовая метрика)
    
    # Параметры теста "достижения цели"
    target_pct: float = 0.03  # 3% движения от цены закрытия
    max_lookahead: Optional[int] = 200  # Максимум свечей вперёд для проверки (None = до конца)
    
    # Пороги значимости
    min_events_for_significance: int = 10  # Минимум событий для считывания результата
    
    output_format: str = 'csv'     # csv или json


# Глобальные конфиги (можно переопределять при запуске)
DEFAULT_EXCHANGE_CONFIG = ExchangeConfig()
DEFAULT_FETCH_CONFIG = FetchConfig()
DEFAULT_ANALYSIS_CONFIG = AnalysisConfig()
