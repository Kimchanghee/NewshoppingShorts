#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
COUPANG_URL="https://www.coupang.com/vp/products/9423373566?itemId=28009663306"
LOG_DIR="$HOME/.ssmaker/logs"
mkdir -p "$LOG_DIR"

echo "===== [1/2] 쿠팡 풀 sourcing 시작 ====="
echo "URL: $COUPANG_URL"
echo ""

# 기존 영상 백업 (이전 다른 상품 영상과 구분)
mv -f "$HOME/.ssmaker/sourcing_output/sourcing_aliexpress_1_video.mp4" "$HOME/.ssmaker/sourcing_output/_prev_aliexpress_1_$(date +%H%M%S).mp4" 2>/dev/null
mv -f "$HOME/.ssmaker/sourcing_output/sourcing_aliexpress_2_video.mp4" "$HOME/.ssmaker/sourcing_output/_prev_aliexpress_2_$(date +%H%M%S).mp4" 2>/dev/null

python run_full_test.py "$COUPANG_URL" 2>&1 | tee "$LOG_DIR/sourcing_pipeline.log"
SOURCING_EXIT=${PIPESTATUS[0]}
echo "[Sourcing 종료 코드: $SOURCING_EXIT]"

if [ "$SOURCING_EXIT" -ne 0 ]; then
  echo "===== [실패] sourcing 단계에서 멈춤. YouTube 업로드 skip ====="
  sleep 10
  exit 1
fi

echo ""
echo "===== [2/2] 다운로드된 새 영상으로 YouTube 추가 업로드 ====="
LATEST_VIDEO=$(ls -t "$HOME/.ssmaker/sourcing_output/"sourcing_*.mp4 2>/dev/null | head -1)

if [ -z "$LATEST_VIDEO" ]; then
  echo "[!] 새 영상이 다운로드되지 않았습니다."
  sleep 10
  exit 2
fi

echo "업로드 영상: $LATEST_VIDEO"
python run_youtube_upload.py "$LATEST_VIDEO" 2>&1 | tee "$LOG_DIR/youtube_upload2.log"

echo ""
echo "===== 풀 자동화 종료 ====="
echo "5초 후 창이 닫힙니다..."
sleep 5
