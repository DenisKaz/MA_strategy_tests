"""
Модуль для анализа данных OHLCV: расчёт индикаторов, анализ отскоков от MA.

Алгоритм:
- Перебор периодов SMA/EMA в диапазоне [ma_period_min, ma_period_max]
- Поиск "отскоков" (wick touch) от каждого MA:
  * Только хвост свечи касается MA (не тело)
  * Длина хвоста >= alpha_wick * размер свечи
  * До и после касания минимум N_pre/N_post свечей без касаний
- Проверка "достижения цели": цена ушла на >= target_pct% и не вернулась
- Расчёт метрик: win_rate, кол-во событий, среднее движение, drawdown
"""
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

from .config import AnalysisConfig, DATA_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Анализирует OHLCV данные на основе отскоков от Moving Averages.
    
    Параметры:
        analysis_config: конфигурация анализа
    """
    
    def __init__(self, analysis_config: AnalysisConfig):
        self.config = analysis_config
    
    def compute_mas(self, df: pd.DataFrame, period: int, ma_types: List[str]) -> pd.DataFrame:
        """
        Рассчитать SMA и/или EMA для заданного периода.
        
        Параметры:
            df: DataFrame с колонкой 'close'
            period: период MA
            ma_types: список типов ['SMA', 'EMA'] или только один
        
        Возвращает:
            DataFrame с добавленными колонками SMA_<period> и/или EMA_<period>
        """
        df = df.copy()
        if 'SMA' in ma_types:
            df[f'SMA_{period}'] = df['close'].rolling(window=period).mean()
        if 'EMA' in ma_types:
            df[f'EMA_{period}'] = df['close'].ewm(span=period, adjust=False).mean()
        return df
    
    def is_wick_touch(self, df_row: pd.Series, ma_value: float) -> int:
        """
        Проверить, касается ли свеча MA только хвостом (wick touch).
        
        Возвращает:
            +1: бычий отскок (касание снизу)
            -1: медвежий отскок (касание сверху)
            0: нет касания
        """
        if pd.isna(ma_value):
            return 0
        
        open_, close_, high_, low_ = df_row['open'], df_row['close'], df_row['high'], df_row['low']
        candle_size = high_ - low_
        
        if candle_size <= 0:
            return 0
        
        body_low = min(open_, close_)
        body_high = max(open_, close_)
        lower_wick = body_low - low_
        upper_wick = high_ - body_high
        
        # Касание снизу: тело выше MA, нижняя тень коснулась MA
        touch_from_below = (body_low > ma_value) and (low_ <= ma_value)
        cond_lower_wick = lower_wick >= (self.config.alpha_wick * candle_size)
        
        # Касание сверху: тело ниже MA, верхняя тень коснулась MA
        touch_from_above = (body_high < ma_value) and (high_ >= ma_value)
        cond_upper_wick = upper_wick >= (self.config.alpha_wick * candle_size)
        
        if touch_from_below and cond_lower_wick:
            return 1  # Бычий отскок
        if touch_from_above and cond_upper_wick:
            return -1  # Медвежий отскок
        
        return 0
    
    def analyze_events(self, df: pd.DataFrame, ma_col: str) -> pd.DataFrame:
        """
        Найти изолированные события (отскоки) и проверить достижение цели.
        
        Параметры:
            df: DataFrame с OHLCV данными и MA колонкой
            ma_col: название колонки MA (например, 'SMA_20')
        
        Возвращает:
            DataFrame с событиями и их результатами
        """
        events = []
        
        for idx in range(len(df)):
            row = df.iloc[idx]
            ma_val = row[ma_col]
            
            if pd.isna(ma_val):
                continue
            
            touch = self.is_wick_touch(row, ma_val)
            if touch == 0:
                continue
            
            # Проверить изолированность (N_pre/N_post без других касаний)
            start_pre = max(0, idx - self.config.n_pre)
            end_post = min(len(df) - 1, idx + self.config.n_post)
            
            isolated = True
            for j in range(start_pre, idx):
                if self.is_wick_touch(df.iloc[j], df.iloc[j][ma_col]) != 0:
                    isolated = False
                    break
            if isolated:
                for j in range(idx + 1, end_post + 1):
                    if self.is_wick_touch(df.iloc[j], df.iloc[j][ma_col]) != 0:
                        isolated = False
                        break
            
            if not isolated:
                continue
            
            # Тест на достижение цели
            close_price = row['close']
            target = close_price * (1 + touch * self.config.target_pct)
            reached = False
            time_to_target = None
            adverse_max = 0.0
            
            lookahead_limit = (
                self.config.max_lookahead 
                if self.config.max_lookahead is not None 
                else (len(df) - idx - 1)
            )
            
            for k in range(1, lookahead_limit + 1):
                if idx + k >= len(df):
                    break
                
                frow = df.iloc[idx + k]
                
                if touch == 1:  # Бычий отскок
                    # Вернулась к цене закрытия или ниже = fail
                    if frow['low'] <= close_price:
                        reached = False
                        break
                    # Достигла цели
                    if frow['high'] >= target:
                        reached = True
                        time_to_target = k
                        break
                    adverse = (close_price - frow['low']) / close_price
                else:  # Медвежий отскок
                    # Вернулась к цене закрытия или выше = fail
                    if frow['high'] >= close_price:
                        reached = False
                        break
                    # Достигла цели
                    if frow['low'] <= target:
                        reached = True
                        time_to_target = k
                        break
                    adverse = (frow['high'] - close_price) / close_price
                
                adverse_max = max(adverse_max, adverse)
            
            events.append({
                'idx': idx,
                'datetime': df.index[idx],
                'type': touch,
                'reached': reached,
                'time_to_target': time_to_target,
                'adverse_max': adverse_max,
            })
        
        return pd.DataFrame(events)
    
    def calculate_metrics(self, events_df: pd.DataFrame) -> Dict:
        """
        Рассчитать метрики качества для найденных событий.
        
        Возвращает:
            Словарь с метриками
        """
        if len(events_df) == 0:
            return {
                'total_events': 0,
                'win_rate': 0.0,
                'wins': 0,
                'losses': 0,
                'avg_time_to_target': None,
                'median_time_to_target': None,
            }
        
        reached = events_df[events_df['reached']].shape[0]
        not_reached = events_df[~events_df['reached']].shape[0]
        total = len(events_df)
        
        win_rate = (reached / total * 100) if total > 0 else 0
        
        times_to_target = events_df[events_df['reached']]['time_to_target'].dropna()
        avg_time = times_to_target.mean() if len(times_to_target) > 0 else None
        median_time = times_to_target.median() if len(times_to_target) > 0 else None
        
        avg_adverse = events_df['adverse_max'].mean() if len(events_df) > 0 else None
        
        return {
            'total_events': total,
            'win_rate': round(win_rate, 2),
            'wins': int(reached),
            'losses': int(not_reached),
            'avg_time_to_target': avg_time,
            'median_time_to_target': median_time,
            'avg_adverse_max': round(avg_adverse, 4) if avg_adverse else None,
        }
    
    def analyze_file(self, filepath: Path, symbol: str, timeframe: str) -> List[Dict]:
        """
        Полный анализ одного CSV файла: перебор всех MA и расчёт метрик.
        
        Параметры:
            filepath: путь к CSV файлу
            symbol: символ торговой пары
            timeframe: таймфрейм
        
        Возвращает:
            Список словарей с результатами по каждой MA
        """
        logger.info(f"Анализирую {filepath.name}...")
        
        # Загрузить данные
        df = pd.read_csv(filepath, index_col=0, parse_dates=True)
        if len(df) == 0:
            logger.warning(f"  CSV пуст: {filepath.name}")
            return []
        
        results = []
        
        # Перебор периодов MA
        for period in range(self.config.ma_period_min, self.config.ma_period_max + 1):
            # Перебор типов MA
            for ma_type in self.config.ma_types:
                # Рассчитать MA
                df_temp = self.compute_mas(df.copy(), period, [ma_type])
                df_temp = df_temp.dropna()
                
                if len(df_temp) == 0:
                    continue
                
                ma_col = f'{ma_type}_{period}'
                
                # Найти события
                events_df = self.analyze_events(df_temp, ma_col)
                
                if len(events_df) < self.config.min_events_for_significance:
                    continue
                
                # Рассчитать метрики
                metrics = self.calculate_metrics(events_df)
                
                # Сохранить результат
                result = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'ma_type': ma_type,
                    'period': period,
                    **metrics,
                }
                results.append(result)
                
                if metrics['total_events'] >= self.config.min_events_for_significance:
                    logger.debug(
                        f"  {ma_col}: {metrics['total_events']} событий, "
                        f"win_rate={metrics['win_rate']}%"
                    )
        
        return results
    
    def analyze_all_data(self) -> pd.DataFrame:
        """
        Проанализировать все CSV файлы в DATA_DIR.
        
        Возвращает:
            DataFrame со всеми результатами
        """
        all_results = []
        
        csv_files = sorted(DATA_DIR.glob('*.csv'))
        if not csv_files:
            logger.warning(f"Нет CSV файлов в {DATA_DIR}")
            return pd.DataFrame()
        
        logger.info(f"Найдено {len(csv_files)} файлов для анализа")
        
        for filepath in csv_files:
            # Парсить имя файла: <exchange>_<symbol>_<timeframe>.csv
            parts = filepath.stem.split('_')
            if len(parts) < 3:
                logger.warning(f"Некорректное имя файла: {filepath.name}")
                continue
            
            timeframe = parts[-1]
            symbol = '_'.join(parts[1:-1]).replace('_', '/')
            
            # Только таймфреймы < 1d
            tf_seconds = self._parse_timeframe(timeframe)
            if tf_seconds >= self._parse_timeframe('1d'):
                logger.debug(f"Пропускаю {timeframe} (>= 1d)")
                continue
            
            try:
                file_results = self.analyze_file(filepath, symbol, timeframe)
                all_results.extend(file_results)
            except Exception as e:
                logger.error(f"Ошибка при анализе {filepath.name}: {e}")
                import traceback
                traceback.print_exc()
        
        if not all_results:
            logger.warning("Нет результатов анализа")
            return pd.DataFrame()
        
        results_df = pd.DataFrame(all_results)
        
        # Сортировать по win_rate убыванию
        results_df = results_df.sort_values('win_rate', ascending=False)
        
        # Сохранить результаты
        summary_path = RESULTS_DIR / 'analysis_results.csv'
        results_df.to_csv(summary_path, index=False)
        logger.info(f"✓ Результаты сохранены: {summary_path}")
        
        return results_df
    
    @staticmethod
    def _parse_timeframe(tf: str) -> int:
        """Парсить таймфрейм строку в секунды."""
        multipliers = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
        for unit, mult in multipliers.items():
            if unit in tf:
                return int(tf.replace(unit, '')) * mult
        return 0
