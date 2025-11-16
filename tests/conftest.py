"""
Pytest fixtures for MA Strategy Tests
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import ExchangeConfig, FetchConfig, AnalysisConfig
from src.analyzer import Analyzer


@pytest.fixture
def sample_ohlcv_dataframe():
    """
    Create a sample OHLCV DataFrame with realistic data for testing.
    
    Returns a DataFrame with 1000 rows, starting from 2024-01-01,
    with OHLCV data and a datetime index.
    """
    dates = pd.date_range(start='2024-01-01', periods=1000, freq='1h', tz='UTC')
    
    # Create somewhat realistic OHLCV data
    np.random.seed(42)
    base_price = 60000
    returns = np.random.normal(0.0001, 0.005, 1000)
    close_prices = base_price * np.cumprod(1 + returns)
    
    df = pd.DataFrame({
        'datetime': dates,
        'open': close_prices * (1 + np.random.uniform(-0.002, 0.002, 1000)),
        'high': close_prices * (1 + np.abs(np.random.uniform(0, 0.01, 1000))),
        'low': close_prices * (1 - np.abs(np.random.uniform(0, 0.01, 1000))),
        'close': close_prices,
        'volume': np.random.uniform(100, 1000, 1000),
    })
    
    # Ensure OHLC constraints
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    df.set_index('datetime', inplace=True)
    return df


@pytest.fixture
def sample_wick_touch_dataframe():
    """
    Create a DataFrame with explicit wick-touch patterns.
    
    This is used to test is_wick_touch() detection.
    Pattern: SMA at 100, with candles that touch it via wick only.
    """
    data = []
    
    # Create 100 candles with clear wick-touch pattern
    for i in range(100):
        if i % 10 == 5:  # Every 10th candle is a wick-touch
            # Bullish touch: body above MA, wick below
            body_min = 101
            body_max = 102
            low = 99.5  # 50% of 1-point candle size = 0.5
            high = body_max
        else:
            # Normal candles
            low = 98 + i % 5
            high = low + 3
            body_min = low + 1
            body_max = high - 0.5
        
        data.append({
            'open': body_min,
            'close': body_max,
            'high': high,
            'low': low,
            'volume': 100,
        })
    
    df = pd.DataFrame(data)
    df['datetime'] = pd.date_range(start='2024-01-01', periods=100, freq='1h', tz='UTC')
    df.set_index('datetime', inplace=True)
    return df


@pytest.fixture
def analysis_config():
    """Create a default AnalysisConfig for testing."""
    return AnalysisConfig(
        ma_period_min=5,
        ma_period_max=50,
        ma_types=['SMA', 'EMA'],
        alpha_wick=0.30,
        n_pre=5,
        n_post=5,
        target_pct=0.03,
        max_lookahead=200,
    )


@pytest.fixture
def analyzer(analysis_config):
    """Create an Analyzer instance with default config."""
    return Analyzer(analysis_config)


@pytest.fixture
def exchange_config():
    """Create a default ExchangeConfig for testing."""
    return ExchangeConfig(
        exchange_id='bybit',
        enable_rate_limit=True,
    )


@pytest.fixture
def fetch_config():
    """Create a default FetchConfig for testing."""
    return FetchConfig(
        symbols=['BTC/USDT'],
        timeframes=['1h', '1d'],
        limit_per_request=100,
        max_history_years=1,
        max_candles_per_request=10000,
    )


@pytest.fixture
def sample_csv_file(tmp_path, sample_ohlcv_dataframe):
    """
    Create a temporary CSV file with sample OHLCV data.
    
    Returns the path to the CSV file.
    """
    csv_path = tmp_path / "test_data.csv"
    sample_ohlcv_dataframe.to_csv(csv_path)
    return csv_path
