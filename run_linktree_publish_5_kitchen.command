#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%H%M%S)
LOG="$LOG_DIR/linktree_publish_5_${TIMESTAMP}.log"
exec > >(tee -a "$LOG") 2>&1

echo "==============================================================="
echo "  Linktree publish 5-product kitchen — $(date)"
echo "==============================================================="

python run_linktree_publish_5_kitchen.py
EXIT=$?

echo ""
echo "Log: $LOG"
echo "Exit: $EXIT"
echo "이 창은 5초 후 닫힙니다..."
sleep 5
exit $EXIT
