#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo "===== YouTube 자동 업로드 시작 ====="
python run_youtube_upload.py 2>&1 | tee ~/.ssmaker/logs/youtube_upload.log
echo "===== 종료 ====="
echo "5초 후 창이 닫힙니다..."
sleep 5
