#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
LOG="$(pwd)/logs/debug_video_v2_$(date +%H%M%S).log"
mkdir -p "$(pwd)/logs"
exec > >(tee -a "$LOG") 2>&1
echo "=== debug_video_v2 — $(date) ==="
python debug_video_v2.py
echo "Exit: $?"
echo "Log: $LOG"
sleep 5
