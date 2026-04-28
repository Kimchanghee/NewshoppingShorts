#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
LOG="$(pwd)/logs/debug_1688_$(date +%H%M%S).log"
mkdir -p "$(pwd)/logs"
exec > >(tee -a "$LOG") 2>&1
echo "=== debug_1688_detail — $(date) ==="
python debug_1688_detail.py
echo "Exit: $?"
sleep 5
