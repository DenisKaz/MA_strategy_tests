# MA Strategy Tests — Полное руководство по архитектуре

**Дата:** 16 ноября 2025  
**Язык:** Python 3.9+  
**Архитектура:** Модульная, CLI-ориентированная  

---

## Краткая сводка проекта

**MA Strategy Tests** — это аналитический инструмент для поиска и оценки качества *«ровных отскоков»* от скользящих средних (SMA/EMA) на исторических OHLCV данных криптовалют.

**Входы:**
- OHLCV данные с бирж (CCXT API) за последние 4 года
- Параметры: диапазон периодов SMA/EMA (5–233), типы средних, таймфреймы (1m–1d)

**Выходы:**
- CSV таблицы с метриками по каждой паре MA (период + тип) и таймфрейму
- Метрики качества: win_rate (%), count, avg_time_to_target, adverse_max и др.

**Решаемые задачи:**
1. Загрузка и кэширование исторических данных в локальном `data/` (независимо от сети)
2. Вычисление SMA и EMA для всех периодов (5–233) векторизованно
3. Детектирование *«касаний MA хвостом свечи»* (жёсткие критерии: alpha_wick, N_pre/N_post)
4. Проверка достижения цели (target_pct %) и расчёт метрик успеха
5. Сравнение эффективности MA периодов между таймфреймами и инструментами

---

## Полный список зависимостей

```
ccxt>=2.0.0          # Единая API для 100+ криптобирж (fetch OHLCV с правильными rate limits)
pandas>=1.3.0        # DataFrame для удобной работы с временными рядами и логики касаний
numpy>=1.20.0        # Векторизованные операции над массивами (SMA, условия, агрегация)
```

| Пакет | Роль |
|-------|------|
| **ccxt** | Загрузка OHLCV с бирж (Bybit, Binance, Kraken и т.д.) с соблюдением rate limits и обработкой сетевых ошибок |
| **pandas** | Манипуляция табличными данными: индексирование по времени, rolling/ewm MA, фильтрация хвостов, сохранение в CSV |
| **numpy** | Быстрые численные операции: поиск касаний, вычисление условий (тело vs хвост), агрегация метрик |

---

## Структура репозитория

```
MA_strategy_tests/
├── src/                      # Основная логика приложения
│   ├── __init__.py          # Пакет-маркер
│   ├── config.py            # Конфигурация (dataclasses для параметров)
│   ├── data_fetcher.py      # Класс DataFetcher (загрузка с CCXT)
│   └── analyzer.py          # Класс Analyzer (вычисление MA, детектирование отскоков)
│
├── bin/                      # Точки входа (CLI скрипты)
│   ├── fetch.py             # Загрузка данных с командной строки
│   └── analyze.py           # Анализ отскоков с командной строки
│
├── data/                     # Директория для OHLCV CSV файлов (создаётся автоматически)
├── results/                  # Директория для результатов анализа (создаётся автоматически)
├── requirements.txt          # Зависимости pip
├── README.md                 # Общее описание
└── ARCHITECTURE.md           # Этот файл
```

### Назначение каждого модуля

#### `src/config.py`
**Что:** Единая конфигурация всего проекта (dataclasses)  
**Почему отдельно:** Разделение данных (параметры) от логики; лёгкое переопределение при запуске  
**Ответственность:** Хранение и валидация параметров (биржа, символы, тайм-фреймы, пороги анализа)  
**Границы:** Нет никакой логики, только structure + defaults  

**Ключевые классы:**
```python
ExchangeConfig:
  - exchange_id: str = 'bybit'           # ID биржи в CCXT
  - enable_rate_limit: bool = True       # Соблюдать rate limits CCXT
  - api_key, api_secret: Optional[str]   # Опциональные ключи (для приватных методов)

FetchConfig:
  - symbols: ['BTC/USDT', 'ETH/USDT']   # Какие пары загружать
  - timeframes: ['1m', '5m', ..., '1d'] # Таймфреймы (минуты до дней)
  - limit_per_request: 1000              # Свечей за один fetch_ohlcv()
  - max_history_years: 4                 # Глубина в годах (одинаково для всех TF)
  - max_candles_per_request: 500000      # Лимит свечей за одну загрузку (ограничение памяти)

AnalysisConfig:
  - ma_period_min: 5, ma_period_max: 233  # Диапазон периодов для перебора
  - ma_types: ['SMA', 'EMA']               # Типы средних
  - alpha_wick: 0.30                       # Минимальная доля хвоста: 30% от размера свечи
  - n_pre: 5, n_post: 5                    # До/после касания: не менее 5 свечей без MA касания
  - target_pct: 0.03                       # Целевое движение 3% от цены закрытия
  - max_lookahead: 200                     # Макс. свечей вперёд для проверки цели
```

---

#### `src/data_fetcher.py`
**Что:** Загрузка OHLCV данных с криптобирж и кэширование в CSV  
**Почему отдельно:** Сложная логика: retry, rate limits, валидация символов, формирование историй  
**Ответственность:** Все аспекты общения с CCXT; гарантия целостности данных  
**Границы:** Только fetch → save; не анализирует и не трансформирует данные  

**Ключевые методы:**

```python
class DataFetcher:
  def __init__(self, exchange_config: ExchangeConfig, fetch_config: FetchConfig)
    → инициализирует CCXT биржу с rate limiting
  
  def validate_symbols(self) -> List[str]
    → проверяет, есть ли символы на бирже; вернёт только валидные
    → вход: ничего; выход: список найденных пар
  
  def _fetch_ohlcv_all(self, symbol: str, timeframe: str, since: int) -> pd.DataFrame
    → загружает ВСЕ свечи для пары за период [since, сейчас]
    → вход: 'BTC/USDT', '1m', timestamp_ms
    → выход: DataFrame с индексом datetime, колонки: open, high, low, close, volume
    → особенность: обработка прерываний, retry на сетевых ошибках, соблюдение rate_limit
  
  def fetch_and_save(self, symbols: Optional[List[str]]) -> None
    → главный метод: загружает все пары x таймфреймы и сохраняет в CSV
    → вход: список пар (или None для использования из конфига)
    → выход: CSV файлы в ./data/ вида: bybit_BTC_USDT_1m.csv, и т.д.
```

**Логика глубины загрузки (обновлено):**
- Все таймфреймы загружаются с одинаковой глубиной: `max_history_years` (по дефолту 4 года)
- Since-метка вычисляется один раз для всех: `now_ms - 4*365*24*60*60*1000`
- Для каждого TF вычисляется разное количество свечей:
  - 1m за 4 года ≈ 2.1 млн свечей
  - 1h за 4 года ≈ 35 тыс. свечей
  - 1d за 4 года ≈ 1460 свечей

---

#### `src/analyzer.py`
**Что:** Анализ OHLCV данных: расчёт MA, поиск отскоков, расчёт метрик  
**Почему отдельно:** Сложная бизнес-логика с множеством вспомогательных функций  
**Ответственность:** Все аспекты обработки и анализа; гарантия корректности метрик  
**Границы:** Входит CSV или DataFrame; выходит результаты (CSV или DataFrame)  

**Ключевые методы:**

```python
class Analyzer:
  def __init__(self, analysis_config: AnalysisConfig)
  
  def compute_mas(self, df: DataFrame, period: int, ma_types: List[str]) -> DataFrame
    → вычисляет SMA и/или EMA за один период
    → вход: DataFrame (индекс datetime, колонка 'close'), period=20, ma_types=['SMA', 'EMA']
    → выход: DataFrame + две новые колонки 'SMA_20' и 'EMA_20'
    → особенность: использует rolling().mean() и ewm().mean() (векторизовано, O(n))
  
  def is_wick_touch(self, row: Series, ma_value: float) -> bool
    → проверяет, касается ли строка (свеча) MA только хвостом (не телом)
    → вход: строка DataFrame (o, h, l, c, v), значение MA
    → выход: True/False
    → логика: 
       - Тело свечи = [min(open,close), max(open,close)]
       - Если (low <= ma <= high) И (ma вне тела), то — касание хвостом
       - Плюс проверка: длина хвоста >= alpha_wick * размер свечи
  
  def check_isolation(self, df: DataFrame, idx: int, n_pre: int, n_post: int) -> bool
    → проверяет, что до idx не было касаний за n_pre, и после не будет за n_post
    → вход: DataFrame, индекс строки, параметры
    → выход: True если изолировано
    → используется как фильтр качества события
  
  def lookahead_target(self, df: DataFrame, idx: int, target_pct: float, max_lookahead: int) -> Dict
    → проверяет, ушла ли цена на target_pct% от close[idx] и не вернулась
    → вход: DataFrame, idx, target_pct=0.03, max_lookahead=200
    → выход: {'success': bool, 'time_to_target': int, 'adverse_max': float, ...}
    → особенность: поиск максимального отклонения в худшую сторону (drawdown)
  
  def analyze_all_data(self) -> pd.DataFrame
    → главный метод: анализирует все CSV в ./data/, перебирает всех MA, считает метрики
    → вход: ничего (читает из ./data/)
    → выход: DataFrame с результатами, сохранённая в ./results/analysis_summary.csv
    → структура результата:
       file | ma_period | ma_type | timeframe | total_events | wins | win_rate | ...
```

---

#### `bin/fetch.py`
**Что:** CLI для загрузки данных  
**Почему отдельно:** Интерфейс для пользователя; фиксирует парамметры из командной строки  

**Пример использования:**
```bash
python bin/fetch.py --symbols BTC/USDT ETH/USDT --years 4 --timeframes 1m 5m 1h 1d -v
```

**Аргументы:**
- `--exchange` → ID биржи (default: bybit)
- `--symbols` → пары (default: BTC/USDT ETH/USDT)
- `--timeframes` → таймфреймы (default: 1m 3m 5m 15m 30m 1h 2h 4h 1d)
- `--years` → глубина в годах (default: 4)
- `--limit` → свечей за запрос (default: 1000)
- `--max-candles` → лимит за загрузку (default: 500000)
- `-v, --verbose` → подробный лог

---

#### `bin/analyze.py`
**Что:** CLI для анализа (перебор MA, расчёт метрик)  

**Пример использования:**
```bash
python bin/analyze.py --ma-min 5 --ma-max 233 --ma-types SMA EMA --target 0.03 -v
```

**Аргументы:**
- `--ma-min`, `--ma-max` → диапазон периодов
- `--ma-types` → SMA и/или EMA
- `--alpha-wick` → порог длины хвоста (default: 0.30)
- `--n-pre`, `--n-post` → изолированность (default: 5)
- `--target` → целевое движение в долях (default: 0.03 = 3%)
- `--max-lookahead` → максимум свечей вперёд (default: 200)
- `--min-events` → минимум событий для отчёта (default: 10)
- `-v, --verbose` → подробный лог

---

## Точки входа и команды запуска

### Главные команды

#### 1. Скачивание данных (первый раз)
```bash
# Загрузить BTC и ETH за 4 года, все таймфреймы
python bin/fetch.py --symbols BTC/USDT ETH/USDT --years 4

# Только BTC, мелкие TF, с логом
python bin/fetch.py --symbols BTC/USDT --timeframes 1m 5m 15m 1h -v

# С другой биржей
python bin/fetch.py --exchange binance --symbols BTC/USDT --years 1
```

#### 2. Полный анализ (стандартно)
```bash
# Анализ всех данных в ./data/ со всеми MA периодами 5..233
python bin/analyze.py

# С другими параметрами
python bin/analyze.py --ma-min 20 --ma-max 200 --target 0.05 --alpha-wick 0.25
```

#### 3. Анализ одного MA периода (дебаг)
```bash
python bin/analyze.py --ma-min 50 --ma-max 50  # Только MA=50
```

#### 4. Только SMA (без EMA)
```bash
python bin/analyze.py --ma-types SMA
```

---

### Ожидаемый формат вывода

#### Данные (CSV в `./data/`)

Файл: `bybit_BTC_USDT_1m.csv`
```
datetime,open,high,low,close,volume
2021-11-16 00:00:00+00:00,61512.0,61600.0,61450.0,61590.0,45.2
2021-11-16 00:01:00+00:00,61590.0,61650.0,61550.0,61600.0,38.1
...
```

#### Результаты анализа (CSV в `./results/`)

Файл: `analysis_summary.csv`
```
file,ma_period,ma_type,timeframe,total_events,wins,losses,win_rate_%,avg_time_to_target,median_time_to_target,avg_adverse_max_%
bybit_BTC_USDT_1m.csv,20,SMA,1m,127,71,56,55.91,14.3,12,0.85
bybit_BTC_USDT_1m.csv,50,SMA,1m,95,48,47,50.53,15.2,14,0.92
bybit_BTC_USDT_1m.csv,20,EMA,1m,132,73,59,55.30,13.8,11,0.78
...
```

---

## Детальный разбор логики

### Загрузка данных (`_fetch_ohlcv_all`)

**Псевдокод:**
```
since = миллисекунды_4_года_назад()
fetch_since = since
all_candles = []

while True:
    candles = exchange.fetch_ohlcv(symbol, timeframe, since=fetch_since, limit=1000)
    if not candles:
        break
    all_candles.extend(candles)
    
    if len(all_candles) > 500000:
        break
    
    last_candle_time = candles[-1][0]
    if last_candle_time >= now() - timeframe_in_ms:
        break  # Достигли текущего времени
    
    fetch_since = last_candle_time + 1
    sleep(0.1)  # Соблюдение rate limit
```

**Сложность:** O(n) где n = всё количество свечей  
**Обработка ошибок:** retry при NetworkError, ExchangeError  
**Проблема:** Некоторые биржи не поддерживают `since` → нужен fallback  

---

### Вычисление MA (SMA и EMA)

**SMA (Simple Moving Average):**
```python
df['SMA_20'] = df['close'].rolling(window=20).mean()
```
Сложность: O(n), т.к. rolling() векторизовано в pandas  
Вывод: NaN для первых 19 строк  

**EMA (Exponential Moving Average):**
```python
df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
```
Сложность: O(n)  
Вывод: работает даже для первой строки (экспоненциальная оценка)  

**Разница:** SMA более чувствительна к недавним данным за счёт окна; EMA плавнее, хотя и учитывает всю историю  

---

### Детектор «касания хвостом» (`is_wick_touch`)

**Логика:**
```
1. Определить тело свечи:
   body_low = min(open, close)
   body_high = max(open, close)

2. Проверить, что MA внутри свечи но снаружи тела:
   if not (low <= ma <= high):
       return False  # MA не касалась вообще
   
   if body_low <= ma <= body_high:
       return False  # MA касалась тело, не хвост

3. Проверить, что хвост длинный:
   candle_size = high - low
   if candle_size == 0:
       return False  # Точечная свеча (doji без хвоста)
   
   wick_length = abs(ma - body_high) if ma > body_high else abs(body_low - ma)
   if wick_length < alpha_wick * candle_size:
       return False  # Хвост слишком короткий
   
   return True
```

**Пример на реальной свече:**
```
high = 100, open = 98, close = 99, low = 97
ma = 97.5 (касается нижнего хвоста)

body: [min(98,99), max(98,99)] = [98, 99]
wick (lower): 97 до 97.5 = 0.5
candle_size = 100 - 97 = 3
alpha_wick * candle_size = 0.30 * 3 = 0.9

0.5 < 0.9 → No touch (хвост слишком короткий)
```

---

### Проверка изолированности (`check_isolation`)

**Логика:**
```
for i in range(max(0, idx - n_pre), idx):
    if is_wick_touch(df[i], ma_values[i]):
        return False  # Найден контакт перед событием

for i in range(idx + 1, min(len(df), idx + n_post + 1)):
    if is_wick_touch(df[i], ma_values[i]):
        return False  # Найден контакт после события

return True  # Событие изолировано
```

**Смысл:** n_post обычно используется как тестовая метрика (на пост-анализ)  

---

### Проверка достижения цели (`lookahead_target`)

**Логика:**
```
close_at_touch = df.loc[idx, 'close']
target_level_up = close_at_touch * (1 + target_pct)
target_level_down = close_at_touch * (1 - target_pct)

adverse_max = 0

for i in range(idx + 1, min(len(df), idx + max_lookahead + 1)):
    high = df.loc[i, 'high']
    low = df.loc[i, 'low']
    
    # Если бычий отскок, смотрим вверх
    if side == 'bull':
        if high >= target_level_up:
            # Достигли цели, проверим, не было ли возврата вниз
            for j in range(i, min(len(df), idx + max_lookahead + 1)):
                if df.loc[j, 'low'] <= close_at_touch:
                    return {'success': False, 'reason': 'returned'}
            return {'success': True, 'time_to_target': i - idx, 'adverse_max': adverse_max}
        
        adverse_max = max(adverse_max, (close_at_touch - low) / close_at_touch)

return {'success': False, 'reason': 'timeout'}
```

**Результат:**
```python
{
    'success': True,
    'time_to_target': 14,  # Свечей до цели
    'adverse_max': 0.012,  # Макс. отклонение в худшую сторону (1.2%)
}
```

---

### Расчёт метрик (для одного MA периода)

После нахождения всех событий подсчитываются метрики:

| Метрика | Формула |
|---------|---------|
| **total_events** | Количество найденных и изолированных отскоков |
| **wins** | Количество успешных (достигших цели) |
| **losses** | total_events - wins |
| **win_rate_%** | (wins / total_events) * 100 |
| **avg_time_to_target** | Средняя: сколько свечей до цели |
| **median_time_to_target** | Медиана |
| **avg_adverse_max_%** | Среднее макс. отклонение в % |

---

## Архитектурные решения

### Почему такие модули?

1. **config.py** — Отделение данных (параметры) от логики
   - Упрощает тестирование (mock конфиг)
   - Централизованные значения по умолчанию
   - Легко добавлять новые параметры

2. **data_fetcher.py** — Изоляция работы с API
   - Кэширование в CSV (не нужно переза качивать)
   - Независимая разработка (не зависит от analyzer)
   - Легко менять биржу или источник данных

3. **analyzer.py** — Чистая бизнес-логика
   - Не зависит от источника данных (работает с DataFrame)
   - Легко тестировать (передав финишированные CSV)
   - Переиспользуемо для других источников

4. **bin/fetch.py, bin/analyze.py** — CLI слой
   - Отделение интерфейса пользователя
   - Возможность добавить веб-интерфейс позже

### Структуры данных

| Выбор | Альтернатива | Почему выбрали |
|-------|--------------|----------------|
| **pandas.DataFrame** | numpy arrays | Индексирование по datetime, удобство, rolling/ewm встроены |
| **CSV файлы** | Parquet, SQLite | Простота, просмотр в Excel, совместимость |
| **Глобальные config** | Singleton, DI | Простота, достаточно для small проекта |
| **Sequential fetch** | Async/parallel | Rate limits CCXT, проще отлаживать |

### Компромиссы

- **Читаемость vs Скорость:** Выбрали читаемость (Pandas вместо NumPy)
  - Оптимизация возможна позже (numba для хот-путей)
- **Гибкость vs Простота:** Выбрали простоту (фиксированные параметры)
  - Все параметры в CLI, легко добавить новые
- **Один процесс vs Параллелизм:** Один процесс
  - Rate limits и сложность синхронизации дороги

### Параметры по умолчанию и обоснование

| Параметр | Default | Обоснование |
|----------|---------|------------|
| **max_history_years** | 4 | Достаточно для статистики (~2M свечей на 1m), не слишком давних (BTC существует ~12 лет) |
| **ma_period_min** | 5 | Самая быстрая MA (почти как close), пороговое значение |
| **ma_period_max** | 233 | Число Фибоначчи, популярное в трейдинге, ~день на 1m TF |
| **alpha_wick** | 0.30 | 30% — баланс между редкостью и надёжностью события |
| **n_pre, n_post** | 5 | ~5 минут на 1m, ~день на 1h — разумный буфер |
| **target_pct** | 0.03 | 3% — типичное движение; меньше → слишком часто, больше → редко |
| **max_lookahead** | 200 | ~3 часа на 1m, ~8 дней на 1d — хороший горизонт |
| **limit_per_request** | 1000 | Максимум, поддерживаемый большинством бирж |

---

## Ключевые переменные и конфигурации

### Global Variables (в config.py)

```python
# ExchangeConfig
exchange_id: str                    # ID биржи (bybit, binance, kraken, ...)
enable_rate_limit: bool             # Соблюдать rate limits CCXT
api_key, api_secret: Optional[str]  # Опциональные ключи для приватных запросов

# FetchConfig
symbols: List[str]                  # Пары для загрузки
timeframes: List[str]               # Таймфреймы (1m, 5m, 1h, 1d, ...)
limit_per_request: int              # Свечей за один fetch (1-1000 в зависимости от биржи)
max_history_years: int              # Глубина в годах (одинаково для всех TF)
max_candles_per_request: int        # Лимит памяти: максимум свечей за загрузку

# AnalysisConfig
ma_period_min, ma_period_max: int   # Диапазон периодов SMA/EMA
ma_types: List[str]                 # ['SMA', 'EMA'] или подмножество
alpha_wick: float                   # Доля от размера свечи (0.0-1.0)
n_pre, n_post: int                  # Количество свечей до/после
target_pct: float                   # Целевое движение (0.01 = 1%)
max_lookahead: int                  # Максимум свечей вперёд для проверки
```

### Допустимые диапазоны

| Параметр | Мин | Макс | Рекомендация |
|----------|-----|------|-------------|
| **alpha_wick** | 0.0 | 1.0 | 0.20–0.50 (чем больше → реже) |
| **n_pre, n_post** | 1 | 50 | 3–10 (чем больше → реже) |
| **target_pct** | 0.001 | 0.20 | 0.01–0.10 (3–10% типично) |
| **ma_period_min** | 1 | 232 | >= 5 (слишком маленькие = шум) |
| **ma_period_max** | 6 | 500 | <= 233 (слишком большие = редко) |
| **max_lookahead** | 1 | 1000 | 50–500 в зависимости от TF |

---

## Тестирование и валидация

### Unit-тесты (pytest)

#### Тест 1: `test_is_wick_touch_basic`
```python
import pytest
from src.analyzer import Analyzer
from src.config import AnalysisConfig
import pandas as pd
import numpy as np

def test_is_wick_touch_basic():
    config = AnalysisConfig(alpha_wick=0.30)
    analyzer = Analyzer(config)
    
    # Синтетическая свеча: open=100, close=101, high=105, low=99
    # MA=99 (касается нижнего хвоста)
    row = pd.Series({
        'open': 100.0,
        'close': 101.0,
        'high': 105.0,
        'low': 99.0,
    })
    
    ma_value = 99.0
    
    # Тело: [100, 101], хвост вниз: 99-100=1, размер=105-99=6
    # 1 >= 0.30*6=1.8 ? NO → False
    result = analyzer.is_wick_touch(row, ma_value)
    assert result == False
    
    # Теперь MA=99.5 (0.5 от body_low=100)
    ma_value = 99.5
    # wick_length = 100 - 99.5 = 0.5
    # 0.5 >= 1.8 ? NO → False
    result = analyzer.is_wick_touch(row, ma_value)
    assert result == False
    
    # Теперь MA=98 (более длинный хвост)
    ma_value = 98.0
    # wick_length = 100 - 98 = 2
    # 2 >= 1.8 ? YES → True
    result = analyzer.is_wick_touch(row, ma_value)
    assert result == True
```

#### Тест 2: `test_lookahead_target_success`
```python
def test_lookahead_target_success():
    config = AnalysisConfig(target_pct=0.03, max_lookahead=200)
    analyzer = Analyzer(config)
    
    # Синтетический DataFrame с достижением цели
    df = pd.DataFrame({
        'close': [100, 101, 102, 103, 104, 105],  # Растёт вверх
    })
    
    # Событие на индекс 0, close=100, target=100*1.03=103
    result = analyzer.lookahead_target(df, idx=0, target_pct=0.03, 
                                       max_lookahead=200, side='bull')
    
    assert result['success'] == True
    assert result['time_to_target'] == 3  # На индексе 3 достигли 103
    assert result['adverse_max'] <= 0  # Нет отката
```

#### Тест 3: `test_fetch_validation`
```python
def test_validate_symbols():
    from src.data_fetcher import DataFetcher
    from src.config import ExchangeConfig, FetchConfig
    
    exchange_config = ExchangeConfig(exchange_id='bybit')
    fetch_config = FetchConfig(symbols=['BTC/USDT', 'FAKE/USDT'])
    
    fetcher = DataFetcher(exchange_config, fetch_config)
    valid = fetcher.validate_symbols()
    
    assert 'BTC/USDT' in valid
    assert 'FAKE/USDT' not in valid  # Не существует
```

### Интеграционные тесты

#### Сценарий 1: Полная загрузка и анализ (малая история)
```python
def test_full_pipeline_small():
    """Загрузить 1 день BTC/USDT 1h и проанализировать"""
    # ... (конкретная реализация)
    pass
```

#### Сценарий 2: Edge cases
```python
def test_edge_case_no_wicks():
    """Данные без хвостов (дожи и прямые свечи)"""
    df = pd.DataFrame({
        'open': [100, 100, 100],
        'close': [100, 100, 100],
        'high': [100, 100, 100],
        'low': [100, 100, 100],
    })
    # Должны не найти ни один контакт
    pass
```

### Структура тестов (pytest + fixtures)

```bash
tests/
├── fixtures/
│   ├── conftest.py          # Общие fixtures
│   └── sample_data.csv      # Тестовые данные
├── test_analyzer.py         # Unit-тесты analyzer
├── test_data_fetcher.py     # Unit-тесты fetcher
├── test_integration.py      # Интеграционные тесты
└── test_edge_cases.py       # Edge cases
```

---

## Производительность и масштабируемость

### Анализ сложности

| Операция | Сложность | Примечание |
|----------|-----------|-----------|
| **Fetch OHLCV** | O(n / limit) запросов × O(limit) | n = всё число свечей, limit = 1000 |
| **Compute MA** | O(n × m) | n = свечи, m = периоды (вычисляется для каждого) |
| **Detect touch** | O(n) | Простой loop |
| **Check isolation** | O(n × (n_pre + n_post)) | Может быть O(n²) в худшем случае |
| **Lookahead check** | O(n × max_lookahead) | Может быть O(n²) если max_lookahead большой |
| **Total** | **O(n × m × max_lookahead)** | m = периоды (229), max_lookahead = 200 → потенциально медленно |

### Узкие места и оптимизации

1. **Lookahead проверка** — самая медленная часть
   - **Оптимизация:** Кэширование high/low за окно `max_lookahead`
   - **Parallel:** NumPy broadcasting вместо loop

2. **Compute MA для каждого периода** — O(n × m)
   - **Оптимизация:** Вычислить по одному разу, хранить в памяти
   - **Parallel:** Запустить несколькоperiods одновременно (многопроцессность)

3. **Check isolation** — O(n²)
   - **Оптимизация:** Предсчитать is_wick_touch для всех строк один раз

**Рекомендации для 1M+ свечей:**
```python
# Используйте numba для hот-путей
from numba import jit

@jit(nopython=True)
def is_wick_touch_fast(open_, close_, high_, low_, ma, alpha_wick):
    # Быстрая версия без pandas overhead
    ...

# Параллелизм по периодам
from multiprocessing import Pool
with Pool(n_cpus) as p:
    results = p.map(lambda period: analyze_period(df, period), periods)
```

### Формат хранения

| Формат | Размер | Скорость чтения | Совместимость |
|--------|--------|-----------------|--------------|
| **CSV** | ~1 GB (1M свечей) | Медленно | Отлично (Excel, R, etc) |
| **Parquet** | ~100 MB | Быстро | Хорошо (современные инструменты) |
| **HDF5** | ~200 MB | Очень быстро | Нужна специальная библиотека |

**Рекомендация:** Оставить CSV для простоты, но добавить опцию Parquet для больших проектов.

---

## Надёжность и репродукция

### Фиксирование окружения

```bash
# requirements.txt с точными версиями
pip freeze > requirements.txt

# Использование pyenv для Python версии
pyenv local 3.9.10

# Docker для полной репродукции
```

**Dockerfile:**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bin/fetch.py", "--symbols", "BTC/USDT"]
```

### Логирование и метрики

```python
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

for symbol in tqdm(symbols, desc='Загружаю'):
    # Показывает прогресс-бар
    df = fetcher.fetch(symbol)
```

### Контроль случайности

Проект детерминирован (нет рандомизации) → seed не требуется.

---

## Формат отчётов и визуализации

### CSV Формат результатов

**Файл:** `results/analysis_summary.csv`

```csv
file,ma_period,ma_type,timeframe,total_events,wins,losses,win_rate_%,avg_time_to_target,median_time_to_target,avg_adverse_max_%,avg_return_%
bybit_BTC_USDT_1m.csv,20,SMA,1m,127,71,56,55.91,14.3,12,0.85,2.87
bybit_BTC_USDT_1m.csv,50,SMA,1m,95,48,47,50.53,15.2,14,0.92,2.91
```

### Примеры графиков

#### График 1: Heatmap Win Rate по (Period, Timeframe)
```python
import matplotlib.pyplot as plt
import seaborn as sns

# Pivot table: строки = periods, столбцы = timeframes
heatmap_data = results.pivot_table(
    values='win_rate_%',
    index='ma_period',
    columns='timeframe',
    aggfunc='mean'
)

plt.figure(figsize=(12, 8))
sns.heatmap(heatmap_data, cmap='RdYlGn', center=50, cbar_kws={'label': 'Win Rate %'})
plt.title('Win Rate по MA Периодам и Таймфреймам')
plt.xlabel('Таймфрейм')
plt.ylabel('MA Period')
plt.tight_layout()
plt.savefig('results/heatmap_winrate.png')
```

#### График 2: Scatter Plot (Adverse Max vs Time to Target)
```python
plt.figure(figsize=(10, 6))
for ma_type in ['SMA', 'EMA']:
    subset = results[results['ma_type'] == ma_type]
    plt.scatter(subset['avg_adverse_max_%'], subset['avg_time_to_target'],
                label=ma_type, alpha=0.6, s=100)

plt.xlabel('Avg Adverse Max (%)')
plt.ylabel('Avg Time to Target (candles)')
plt.title('Качество Отскоков: Глубина Отката vs Скорость Достижения')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('results/scatter_quality.png')
```

---

## Практические замечания и подводные камни

### На что обращать внимание при интерпретации

1. **Overfitting:** MA периоды 5–233 перебирали на ОДНИХ И ТЕХ ЖЕ данных
   - Решение: Разделить на Train/Test, кросс-валидация по временным окнам

2. **Look-ahead bias:** Проверка max_lookahead 200 свечей вперёд
   - На реальной торговле вы НЕ знаете будущего!
   - Решение: Использовать только как backtesting метрику, не прямой сигнал

3. **Data snooping:** Найденные лучшие MA периоды специфичны для BTC/USDT 1m
   - На других инструментах могут не работать
   - Решение: Проверить на out-of-sample, других инструментах, другой глубине

### Подводные камни fetch_ohlcv

1. **Три типа таймстемпов:**
   - Opening (CCXT возвращает время открытия свечи)
   - Closing (не то же самое)
   - Execution time
   - Решение: Уточнить у документации биржи

2. **Timezones:** CCXT возвращает UTC, но некоторые графики отображают по локальному времени
   - Решение: Всегда работайте с UTC, конвертируйте в конце

3. **Неполные свечи:** Текущая свеча может быть неполной (ещё не закрытась)
   - Решение: Исключить последние N свечей (например, 5)

4. **Пропуски в выходные:** Крипто торгуется 24/7, но данные могут быть неполными
   - Решение: Проверить, нет ли больших разрывов в индексе

---

## План улучшений (Roadmap)

### Короткосрочные (1–2 недели)
1. Учёт комиссий биржи (-0.1% за каждую сделку)
2. Параметр для исключения последних N свечей (текущая свеча)
3. Экспорт результатов в JSON
4. Простой веб-интерфейс (Streamlit)

### Среднесрочные (1 месяц)
5. Стоп-логика: максимум убытка перед целью
6. Профильные тесты на разных таймфреймах и инструментах
7. Cross-instrument validation (найти MA на BTC, протестировать на ETH)
8. Robust statistics (медиана вместо среднего, percentiles)

### Долгосрочные (2–3 месяца)
9. ML-классификатор событий (предсказать успех по признакам свечи)
10. Интеграция с Pine Script / TradingView (webhook для live сигналов)
11. Базовая симуляция портфеля (несколько инструментов одновременно)
12. Параллелизм: multiprocessing по периодам/инструментам
13. Оптимизация памяти: Parquet вместо CSV
14. Интеграция с InfluxDB/Grafana для реал-тайма
15. Backtesting на несных больших объёмах (pyarrow, Dask)

---

## Mapping to Pine Script

### Что можно реализовать в Pine напрямую

- **Вычисление MA:** ✅ Pine встроенные ta.sma() и ta.ema()
- **Wick detection:** ✅ Простая логика на low/high/open/close
- **Event marking:** ✅ plotshape() для отметки точек

### Что нельзя / сложно в Pine

- **Статистика (win_rate):** ❌ Нужна история 1000+ событий (Pine хранит ~5000 свечей)
- **Lookahead:** ❌ Запрос будущих данных запрещён
- **Multi-timeframe анализ:** ⚠️ Возможно, но медленно

### Примерный план порта в Pine

**Часть 1 (Python):** Найти лучшие MA периоды
```python
# Результат: best_periods = [(20, SMA), (50, EMA), ...]
```

**Часть 2 (Pine Script):** Отметить эти точки на графике
```pine
indicator("MA Bounce Detector", overlay=true)

ma_period = input.int(20, title="MA Period")
ma_type = input.string("SMA", options=["SMA", "EMA"])

ma = ma_type == "SMA" ? ta.sma(close, ma_period) : ta.ema(close, ma_period)

is_touch = (low <= ma and ma < open) or (low <= ma and ma < close)
is_quality = math.abs(high - low) > 0.30 * (high - low)

plotshape(is_touch and is_quality, style=shape.circle, color=color.green)
```

---

## Как читать код

### Пошаговая стратегия отладки

1. **Понимание потока:**
   ```
   bin/fetch.py → src/data_fetcher.py → data/*.csv
   bin/analyze.py → src/analyzer.py → results/*.csv
   ```

2. **Точка старта отладки:**
   - Проблема с загрузкой? → Debug в `data_fetcher._fetch_ohlcv_all()`
   - Проблема с MA? → Debug в `analyzer.compute_mas()`
   - Проблема с касаниями? → Debug в `analyzer.is_wick_touch()`

3. **Добавить логирование:**
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.debug(f"Проверяю row: {row}, ma={ma}")
   ```

4. **Запустить с `-v` флагом:**
   ```bash
   python bin/analyze.py --ma-min 20 --ma-max 20 -v  # Только один период
   ```

5. **Проверить CSV входных данных:**
   ```bash
   head -10 data/bybit_BTC_USDT_1m.csv
   ```

---

## Содержимое README.md

[Файл будет создан отдельно]

---

## Быстрые правки (actionable tasks)

### За 1 час:
- [ ] Добавить параметр `--exclude-last-n-candles` в fetch.py
- [ ] Реализовать экспорт результатов в JSON
- [ ] Добавить валидацию параметров (alpha_wick <= 1.0, ma_period_min < ma_period_max)
- [ ] Написать первый unit-тест в tests/test_analyzer.py

### За 4 часа:
- [ ] Интегрировать Streamlit для веб-интерфейса
- [ ] Добавить параметр комиссий (-0.1% за сделку)
- [ ] Написать интеграционный тест (fetch + analyze на малом наборе)
- [ ] Оптимизировать lookahead_check() с NumPy
- [ ] Добавить Dockerfile

### За 1 день:
- [ ] Cross-instrument validation (найти на BTC, протестировать на ETH, SOL)
- [ ] Параллелизм: multiprocessing по периодам
- [ ] Создать Pine Script индикатор для лучших периодов
- [ ] Написать guide по интерпретации результатов
- [ ] Парк-тестирование на 10+ инструментах и таймфреймах

---

**Конец документа**
