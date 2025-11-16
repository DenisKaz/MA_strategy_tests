#!/bin/bash
# ============================================================================
# MA_strategy_tests — Примеры команд
# ============================================================================
# Копируйте отдельные команды или запускайте целые сценарии

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# ============================================================================
# СЦЕНАРИЙ 1: БЫСТРЫЙ ТЕСТ (1 час данных, только 1h таймфрейм)
# ============================================================================
scenario_quick_test() {
    echo -e "${BLUE}=== Сценарий 1: Быстрый тест (1 час, 1h TF) ===${NC}"
    
    echo -e "${YELLOW}[1/2] Загрузить данные...${NC}"
    python bin/fetch.py \
        --symbols BTC/USDT \
        --years 0.0027 \
        --timeframes 1h \
        -v
    
    echo -e "${YELLOW}[2/2] Анализировать (MA 5..100)...${NC}"
    python bin/analyze.py \
        --ma-min 5 \
        --ma-max 100 \
        -v
    
    echo -e "${GREEN}✓ Сценарий 1 завершен${NC}"
    echo "Результаты: results/analysis_summary.csv"
}

# ============================================================================
# СЦЕНАРИЙ 2: СТАНДАРТНЫЙ АНАЛИЗ (4 года, все таймфреймы, BTC+ETH)
# ============================================================================
scenario_standard() {
    echo -e "${BLUE}=== Сценарий 2: Стандартный анализ (4 года, все TF, BTC+ETH) ===${NC}"
    
    echo -e "${YELLOW}[1/2] Загрузить данные (это займет ~10 минут)...${NC}"
    python bin/fetch.py \
        --symbols BTC/USDT ETH/USDT \
        --years 4 \
        --verbose
    
    echo -e "${YELLOW}[2/2] Анализировать (229 × 2 × 9 = 4122 комбинации, ~5 минут)...${NC}"
    python bin/analyze.py --verbose
    
    echo -e "${GREEN}✓ Сценарий 2 завершен${NC}"
    echo "Результаты: results/analysis_summary.csv"
    echo ""
    echo "Топ-10 по win_rate:"
    python -c "
import pandas as pd
df = pd.read_csv('results/analysis_summary.csv')
print(df.nlargest(10, 'win_rate_%')[['file', 'ma_period', 'ma_type', 'timeframe', 'win_rate_%', 'total_events']].to_string(index=False))
"
}

# ============================================================================
# СЦЕНАРИЙ 3: ШИРОКОЕ ИССЛЕДОВАНИЕ (3+ инструмента, все данные)
# ============================================================================
scenario_wide_research() {
    echo -e "${BLUE}=== Сценарий 3: Широкое исследование (3+ инструмента, 4 года) ===${NC}"
    
    echo -e "${YELLOW}[1/2] Загрузить данные (BTC, ETH, SOL, ADA)...${NC}"
    python bin/fetch.py \
        --symbols BTC/USDT ETH/USDT SOL/USDT ADA/USDT \
        --years 4 \
        --verbose
    
    echo -e "${YELLOW}[2/2] Анализировать все комбинации...${NC}"
    python bin/analyze.py --verbose
    
    echo -e "${GREEN}✓ Сценарий 3 завершен${NC}"
    echo ""
    echo "Результаты сохранены в: results/analysis_summary.csv"
    echo "Размер результата: $(wc -l < results/analysis_summary.csv) строк"
}

# ============================================================================
# СЦЕНАРИЙ 4: ФОКУСИРОВАННЫЙ АНАЛИЗ (одна пара, узкий диапазон MA)
# ============================================================================
scenario_focused() {
    echo -e "${BLUE}=== Сценарий 4: Фокусированный анализ (BTC 1h, MA 10-100) ===${NC}"
    
    echo -e "${YELLOW}[1/2] Загрузить 1 год BTC на 1h...${NC}"
    python bin/fetch.py \
        --symbols BTC/USDT \
        --years 1 \
        --timeframes 1h \
        --verbose
    
    echo -e "${YELLOW}[2/2] Анализировать только MA 10-100...${NC}"
    python bin/analyze.py \
        --ma-min 10 \
        --ma-max 100 \
        --verbose
    
    echo -e "${GREEN}✓ Сценарий 4 завершен${NC}"
}

# ============================================================================
# СЦЕНАРИЙ 5: ДЕБАГ ОДНОГО MA ПЕРИОДА
# ============================================================================
scenario_debug() {
    echo -e "${BLUE}=== Сценарий 5: Дебаг одного MA периода (MA=50 SMA) ===${NC}"
    
    # Предполагаем, что данные уже загружены
    if [ ! -d "data" ] || [ -z "$(ls -A data)" ]; then
        echo -e "${YELLOW}Данные не найдены, загружаю BTC 1h...${NC}"
        python bin/fetch.py \
            --symbols BTC/USDT \
            --years 1 \
            --timeframes 1h
    fi
    
    echo -e "${YELLOW}Анализирую только MA=50, SMA...${NC}"
    python bin/analyze.py \
        --ma-min 50 \
        --ma-max 50 \
        --ma-types SMA \
        --verbose
    
    echo -e "${GREEN}✓ Сценарий 5 завершен${NC}"
}

# ============================================================================
# СЦЕНАРИЙ 6: СРАВНЕНИЕ MA ТИПОВ (SMA vs EMA)
# ============================================================================
scenario_sma_vs_ema() {
    echo -e "${BLUE}=== Сценарий 6: SMA vs EMA (какой лучше?) ===${NC}"
    
    if [ ! -d "data" ] || [ -z "$(ls -A data)" ]; then
        echo -e "${YELLOW}Загружаю BTC 1h...${NC}"
        python bin/fetch.py \
            --symbols BTC/USDT \
            --years 2 \
            --timeframes 1h
    fi
    
    echo -e "${YELLOW}Анализирую SMA и EMA отдельно...${NC}"
    python bin/analyze.py \
        --ma-min 5 \
        --ma-max 200 \
        --verbose
    
    echo -e "${YELLOW}Сравнение результатов:${NC}"
    python -c "
import pandas as pd
df = pd.read_csv('results/analysis_summary.csv')
# SMA results
sma = df[df['ma_type'] == 'SMA'].agg({
    'total_events': 'sum',
    'wins': 'sum',
    'win_rate_%': 'mean'
}).round(2)
# EMA results
ema = df[df['ma_type'] == 'EMA'].agg({
    'total_events': 'sum',
    'wins': 'sum',
    'win_rate_%': 'mean'
}).round(2)
print('SMA: win_rate =', sma['win_rate_%'], '%, total_events =', int(sma['total_events']))
print('EMA: win_rate =', ema['win_rate_%'], '%, total_events =', int(ema['total_events']))
"
}

# ============================================================================
# СЦЕНАРИЙ 7: АНАЛИЗ ПО ТАЙМФРЕЙМАМ (1m vs 5m vs 1h vs 1d)
# ============================================================================
scenario_timeframes() {
    echo -e "${BLUE}=== Сценарий 7: Анализ по таймфреймам ===${NC}"
    
    if [ ! -d "data" ] || [ -z "$(ls -A data)" ]; then
        echo -e "${YELLOW}Загружаю BTC все TF...${NC}"
        python bin/fetch.py \
            --symbols BTC/USDT \
            --years 1
    fi
    
    echo -e "${YELLOW}Анализирую...${NC}"
    python bin/analyze.py --verbose
    
    echo -e "${YELLOW}Win rate по таймфреймам:${NC}"
    python -c "
import pandas as pd
df = pd.read_csv('results/analysis_summary.csv')
by_tf = df.groupby('timeframe').agg({
    'total_events': 'sum',
    'wins': 'sum',
    'win_rate_%': 'mean'
}).round(2)
print(by_tf)
"
}

# ============================================================================
# СЦЕНАРИЙ 8: ДРУГАЯ БИРЖА (Binance вместо Bybit)
# ============================================================================
scenario_binance() {
    echo -e "${BLUE}=== Сценарий 8: Загрузка с Binance (вместо Bybit) ===${NC}"
    
    echo -e "${YELLOW}Загружаю BTC/USDT с Binance (1 год)...${NC}"
    python bin/fetch.py \
        --exchange binance \
        --symbols BTC/USDT \
        --years 1 \
        --timeframes 1h 4h \
        --verbose
    
    echo -e "${GREEN}✓ Сценарий 8 завершен${NC}"
    echo "Файлы: data/binance_BTC_USDT_*.csv"
}

# ============================================================================
# УТИЛИТА: ПОКАЗАТЬ ТОП РЕЗУЛЬТАТОВ
# ============================================================================
show_top_results() {
    echo -e "${BLUE}=== Топ-20 результатов по win_rate ===${NC}"
    
    if [ ! -f "results/analysis_summary.csv" ]; then
        echo -e "${RED}✗ results/analysis_summary.csv не найден${NC}"
        echo "Запустите анализ: python bin/analyze.py"
        return 1
    fi
    
    python -c "
import pandas as pd
df = pd.read_csv('results/analysis_summary.csv')
top = df.nlargest(20, 'win_rate_%')[
    ['file', 'ma_period', 'ma_type', 'timeframe', 'total_events', 'wins', 'win_rate_%', 'avg_time_to_target']
]
print(top.to_string(index=False))
"
}

# ============================================================================
# УТИЛИТА: СТАТИСТИКА ДАННЫХ
# ============================================================================
show_data_stats() {
    echo -e "${BLUE}=== Статистика загруженных данных ===${NC}"
    
    if [ ! -d "data" ] || [ -z "$(ls -A data)" ]; then
        echo -e "${RED}✗ Данные не загружены${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Размер файлов:${NC}"
    du -h data/* | sort -h
    
    echo -e "\n${YELLOW}Количество свечей:${NC}"
    for file in data/*.csv; do
        lines=$(($(wc -l < "$file") - 1))  # Минус header
        echo "  $(basename "$file"): $lines свечей"
    done
}

# ============================================================================
# УТИЛИТА: ОЧИСТИТЬ РЕЗУЛЬТАТЫ
# ============================================================================
clear_results() {
    echo -e "${YELLOW}Очистить results/? (это удалит все результаты анализа)${NC}"
    read -p "Введите 'да' для подтверждения: " confirm
    if [ "$confirm" = "да" ]; then
        rm -rf results/*
        echo -e "${GREEN}✓ Результаты удалены${NC}"
    else
        echo "Отменено"
    fi
}

# ============================================================================
# ГЛАВНОЕ МЕНЮ
# ============================================================================
main() {
    if [ $# -eq 0 ]; then
        cat <<EOF
${BLUE}╔════════════════════════════════════════════════════════════╗${NC}
${BLUE}║  MA Strategy Tests – Примеры команд                       ║${NC}
${BLUE}╚════════════════════════════════════════════════════════════╝${NC}

${GREEN}Сценарии:${NC}
  1) Быстрый тест              (1 час, 1h TF, ~2 минуты)
  2) Стандартный анализ         (4 года, BTC+ETH, ~15 минут)
  3) Широкое исследование       (4 года, 4 инструмента, ~25 минут)
  4) Фокусированный анализ      (1 год, MA 10-100, ~3 минуты)
  5) Дебаг одного MA периода    (MA=50 SMA, ~1 минута)
  6) Сравнение SMA vs EMA       (какой лучше?)
  7) Анализ по таймфреймам      (1m vs 5m vs 1h vs 1d)
  8) Загрузка с Binance         (альтернативная биржа)

${GREEN}Утилиты:${NC}
  top)   Показать топ-20 результатов
  stats) Статистика загруженных данных
  clear) Удалить результаты

${GREEN}Примеры использования:${NC}
  # Запустить сценарий 1
  bash bin/commands.sh 1

  # Показать топ результатов
  bash bin/commands.sh top

  # Загрузить только данные (без анализа)
  python bin/fetch.py --symbols BTC/USDT --years 1

  # Анализировать уже загруженные данные
  python bin/analyze.py --ma-min 20 --ma-max 100

${BLUE}════════════════════════════════════════════════════════════${NC}
EOF
        return 0
    fi
    
    case "$1" in
        1) scenario_quick_test ;;
        2) scenario_standard ;;
        3) scenario_wide_research ;;
        4) scenario_focused ;;
        5) scenario_debug ;;
        6) scenario_sma_vs_ema ;;
        7) scenario_timeframes ;;
        8) scenario_binance ;;
        top) show_top_results ;;
        stats) show_data_stats ;;
        clear) clear_results ;;
        *)
            echo -e "${RED}✗ Неизвестная команда: $1${NC}"
            echo "Используйте: bash bin/commands.sh [1-8|top|stats|clear]"
            return 1
            ;;
    esac
}

# Run main
main "$@"
