#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

LOG="$(pwd)/logs/debug_video_extraction_$(date +%H%M%S).log"
mkdir -p "$(pwd)/logs"
exec > >(tee -a "$LOG") 2>&1

echo "==============================================================="
echo "  Video extraction debug — $(date)"
echo "==============================================================="

python debug_video_extraction.py
EXIT=$?

echo ""
echo "Log: $LOG"
echo "Exit: $EXIT"
echo "이 창은 5초 후 닫힙니다..."
sleep 5
exit $EXIT
