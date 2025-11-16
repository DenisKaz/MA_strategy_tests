#!/bin/bash
# ============================================================================
# MA Strategy Tests – Quick Start Guide
# ============================================================================
# Этот скрипт быстро устанавливает окружение и запускает первый анализ

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  MA Strategy Tests – Quick Start                          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# 1. Check Python version
echo -e "${YELLOW}[1/4] Проверка Python...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Версия Python: $python_version"

# 2. Install requirements
echo -e "${YELLOW}[2/4] Установка зависимостей...${NC}"
pip install -q -r requirements.txt
echo "✓ Зависимости установлены"

# 3. Create directories
echo -e "${YELLOW}[3/4] Создание директорий...${NC}"
mkdir -p data results tests
echo "✓ Директории готовы"

# 4. Make scripts executable
echo -e "${YELLOW}[4/4] Подготовка скриптов...${NC}"
chmod +x bin/fetch.py bin/analyze.py bin/commands.sh
echo "✓ Скрипты готовы"

echo ""
echo -e "${GREEN}✓ Окружение готово!${NC}"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}Следующие шаги:${NC}"
echo ""
echo "  1. Быстрый тест (2 минуты):"
echo "     bash bin/commands.sh 1"
echo ""
echo "  2. Загрузить данные:"
echo "     python bin/fetch.py --symbols BTC/USDT --years 1"
echo ""
echo "  3. Запустить анализ:"
echo "     python bin/analyze.py"
echo ""
echo "  4. Посмотреть все примеры:"
echo "     bash bin/commands.sh"
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
