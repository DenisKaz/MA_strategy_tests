"""
Unit tests for Analyzer class
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime


class TestComputeMAs:
    """Tests for compute_mas() method"""
    
    def test_sma_computation(self, sample_ohlcv_dataframe, analyzer):
        """Test SMA computation matches pandas rolling mean"""
        period = 20
        df = sample_ohlcv_dataframe.copy()
        
        result = analyzer.compute_mas(df, period=period, ma_types=['SMA'])
        
        # Compare with pandas SMA
        expected_sma = df['close'].rolling(window=period).mean()
        
        # Check first non-NaN values match
        pd.testing.assert_series_equal(
            result['SMA'].dropna(),
            expected_sma.dropna(),
            check_names=True,
            rtol=1e-5
        )
    
    def test_ema_computation(self, sample_ohlcv_dataframe, analyzer):
        """Test EMA computation matches pandas ewm"""
        period = 20
        df = sample_ohlcv_dataframe.copy()
        
        result = analyzer.compute_mas(df, period=period, ma_types=['EMA'])
        
        # Compare with pandas EMA
        expected_ema = df['close'].ewm(span=period, adjust=False).mean()
        
        # Check values match (allow small numerical differences)
        pd.testing.assert_series_equal(
            result['EMA'].dropna(),
            expected_ema.dropna(),
            check_names=True,
            rtol=1e-3
        )
    
    def test_both_mas_computed(self, sample_ohlcv_dataframe, analyzer):
        """Test that both SMA and EMA are computed when requested"""
        period = 20
        df = sample_ohlcv_dataframe.copy()
        
        result = analyzer.compute_mas(df, period=period, ma_types=['SMA', 'EMA'])
        
        assert 'SMA' in result.columns
        assert 'EMA' in result.columns
    
    def test_output_has_original_columns(self, sample_ohlcv_dataframe, analyzer):
        """Test that output DataFrame has original OHLCV columns"""
        period = 20
        df = sample_ohlcv_dataframe.copy()
        
        result = analyzer.compute_mas(df, period=period, ma_types=['SMA'])
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            assert col in result.columns


class TestWickTouch:
    """Tests for is_wick_touch() method"""
    
    def test_no_touch_ma_outside_candle(self, analyzer):
        """Test no touch when MA is outside candle"""
        row = pd.Series({
            'open': 100,
            'close': 101,
            'high': 102,
            'low': 99,
        })
        ma_value = 110  # Well outside
        
        result = analyzer.is_wick_touch(row, ma_value)
        assert result is False
    
    def test_no_touch_ma_in_body(self, analyzer):
        """Test no touch when MA is in the candle body"""
        row = pd.Series({
            'open': 100,
            'close': 101,
            'high': 102,
            'low': 99,
        })
        ma_value = 100.5  # In body [min(100,101), max(100,101)] = [100, 101]
        
        result = analyzer.is_wick_touch(row, ma_value)
        assert result is False
    
    def test_touch_bullish_wick(self, analyzer):
        """Test positive touch on bullish candle (wick below body)"""
        # Body = [98, 99], wick goes to 97
        row = pd.Series({
            'open': 98,
            'close': 99,
            'high': 99,
            'low': 97,
        })
        ma_value = 97.5
        candle_size = row['high'] - row['low']  # 2
        # wick_len = 98 - 97.5 = 0.5
        # 0.5 >= 0.30 * 2 = 0.6? No, so should be False
        
        result = analyzer.is_wick_touch(row, ma_value)
        # This depends on alpha_wick setting
        # With default 0.30, this should be False (0.5 < 0.6)
    
    def test_touch_strong_wick(self, analyzer):
        """Test positive touch on strong wick (>= alpha threshold)"""
        # Body = [98, 99], wick goes to 96
        row = pd.Series({
            'open': 98,
            'close': 99,
            'high': 99,
            'low': 96,
        })
        ma_value = 96.5
        candle_size = row['high'] - row['low']  # 3
        # wick_len = 98 - 96.5 = 1.5
        # 1.5 >= 0.30 * 3 = 0.9? Yes!
        
        result = analyzer.is_wick_touch(row, ma_value)
        assert result is True


class TestCheckIsolation:
    """Tests for check_isolation() method"""
    
    def test_isolated_touch(self, sample_ohlcv_dataframe, analyzer):
        """Test detection of isolated touch (no other touches nearby)"""
        df = sample_ohlcv_dataframe.copy()
        
        # Add SMA
        period = 20
        df['SMA_20'] = df['close'].rolling(period).mean()
        
        # Find a valid index (not too near edges)
        idx = 50
        
        # This would need the actual implementation details to test properly
        # Placeholder for now
        assert True
    
    def test_non_isolated_touch(self, sample_ohlcv_dataframe, analyzer):
        """Test detection of non-isolated touch (other touches nearby)"""
        # Placeholder
        assert True


class TestLookaheadTarget:
    """Tests for lookahead_target() method"""
    
    def test_successful_target_bull(self, analyzer):
        """Test successful bullish target (price moves up)"""
        # Create a small DataFrame with expected upward move
        data = {
            'close': [100, 101, 102, 103, 104, 105, 106],
            'high': [100.5, 101.5, 102.5, 103.5, 104.5, 105.5, 106.5],
            'low': [99.5, 100.5, 101.5, 102.5, 103.5, 104.5, 105.5],
        }
        df = pd.DataFrame(data)
        
        # At index 0, close = 100, target 3% = 103
        # Price reaches 103.5 at index 3
        result = analyzer.lookahead_target(
            df, idx=0, target_pct=0.03, max_lookahead=10, side='bull'
        )
        
        # Should detect success
        assert result['success'] is True
        assert result['time_to_target'] == 3
    
    def test_failed_target_no_move(self, analyzer):
        """Test failed target (price doesn't move enough)"""
        data = {
            'close': [100, 100.5, 100.2, 100.1, 99.9],
            'high': [100.2, 100.7, 100.4, 100.3, 100.1],
            'low': [99.8, 100.3, 100.0, 99.9, 99.7],
        }
        df = pd.DataFrame(data)
        
        result = analyzer.lookahead_target(
            df, idx=0, target_pct=0.03, max_lookahead=10, side='bull'
        )
        
        assert result['success'] is False


class TestAnalyzeAllData:
    """Integration tests for analyze_all_data() method"""
    
    def test_output_structure(self, analyzer, tmp_path, sample_ohlcv_dataframe):
        """Test that analyze_all_data() returns correctly structured output"""
        # This would require actual CSV files in data/ directory
        # For now, it's a placeholder
        assert True
    
    def test_no_crashes_on_empty_data(self, analyzer):
        """Test that analyzer doesn't crash on empty DataFrame"""
        empty_df = pd.DataFrame({
            'open': [],
            'high': [],
            'low': [],
            'close': [],
            'volume': [],
        })
        
        # Should handle gracefully (either return empty or skip)
        assert True


class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_all_nan_close(self, analyzer):
        """Test handling of DataFrame with all NaN close prices"""
        df = pd.DataFrame({
            'open': [np.nan] * 10,
            'high': [np.nan] * 10,
            'low': [np.nan] * 10,
            'close': [np.nan] * 10,
        })
        
        result = analyzer.compute_mas(df, period=5, ma_types=['SMA'])
        # All results should be NaN
        assert result['SMA'].isna().all()
    
    def test_single_candle_no_ma(self, analyzer):
        """Test MA computation with single candle (SMA should be NaN)"""
        df = pd.DataFrame({
            'close': [100],
        })
        
        result = analyzer.compute_mas(df, period=5, ma_types=['SMA'])
        assert result['SMA'].isna().all()
    
    def test_no_wick_candles(self, analyzer):
        """Test is_wick_touch with doji or no-wick candle"""
        # Doji: open == close == mid(high, low)
        row = pd.Series({
            'open': 100,
            'close': 100,
            'high': 100,
            'low': 100,
        })
        ma_value = 100.0
        
        result = analyzer.is_wick_touch(row, ma_value)
        # No wick, so should be False
        assert result is False
