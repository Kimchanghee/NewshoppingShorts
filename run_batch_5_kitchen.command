#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

LOG_DIR="$HOME/.ssmaker/logs"
OUT_DIR="$HOME/.ssmaker/sourcing_output"
# Mirror the run log into the project's logs/ folder so Claude (Cowork) can
# monitor progress from outside the user's home directory.
PROJECT_LOG_DIR="$(pwd)/logs"
mkdir -p "$LOG_DIR" "$OUT_DIR" "$PROJECT_LOG_DIR"

# 5 kitchen-product Coupang URLs spanning sponge holder / spice / dish rack /
# cutting board categories so we hit different keyword paths.
URLs=(
"https://www.coupang.com/vp/products/8412480162"
"https://www.coupang.com/vp/products/7116552997"
"https://www.coupang.com/vp/products/7825609530"
"https://www.coupang.com/vp/products/8096845020"
"https://www.coupang.com/vp/products/7726596110"
)

# Move the previous run aside so we don't pick up stale videos.
TIMESTAMP=$(date +%H%M%S)
mkdir -p "$OUT_DIR/_archive_$TIMESTAMP"
mv "$OUT_DIR/sourcing_aliexpress_"*.mp4 "$OUT_DIR/_archive_$TIMESTAMP/" 2>/dev/null
mv "$OUT_DIR/sourcing_1688_"*.mp4 "$OUT_DIR/_archive_$TIMESTAMP/" 2>/dev/null
mv "$OUT_DIR/sourcing_youtube_"*.mp4 "$OUT_DIR/_archive_$TIMESTAMP/" 2>/dev/null

# Reset Linktree publish counter so we start at [1].
echo '{"count": 0}' > "$HOME/.ssmaker/linktree_counter.json"

BATCH_LOG="$LOG_DIR/batch_5_kitchen_${TIMESTAMP}.log"
PROJECT_BATCH_LOG="$PROJECT_LOG_DIR/batch_5_kitchen_${TIMESTAMP}.log"
exec > >(tee -a "$BATCH_LOG" "$PROJECT_BATCH_LOG") 2>&1

echo "==============================================================="
echo "  5-product kitchen batch — $(date)"
echo "==============================================================="

idx=1
for URL in "${URLs[@]}"; do
  echo ""
  echo "==============================================================="
  echo "  [$idx/5] Sourcing: $URL"
  echo "==============================================================="

  python run_full_test.py "$URL" 2>&1
  EXIT=$?
  echo "[Sourcing exit: $EXIT]"

  if [ "$EXIT" -eq 0 ]; then
    # Pick up the newest video from any source (aliexpress, 1688, youtube)
    LATEST=$(ls -t "$OUT_DIR/sourcing_aliexpress_"*.mp4 "$OUT_DIR/sourcing_1688_"*.mp4 "$OUT_DIR/sourcing_youtube_"*.mp4 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
      echo ""
      echo "===== [$idx/5] YouTube upload: $(basename "$LATEST") ====="
      python run_youtube_upload.py "$LATEST" 2>&1

      # Rename so the next run doesn't overwrite (sourcing_output/_kept_N_<basename>)
      KEPT="$OUT_DIR/_kept_${idx}_$(basename "$LATEST")"
      mv "$LATEST" "$KEPT"
      echo "[Kept as: $(basename "$KEPT")]"
    else
      echo "[!] No video produced for $URL"
    fi
  else
    echo "[!] Sourcing failed for $URL — skipping upload"
  fi

  idx=$((idx + 1))
  echo ""
  sleep 3
done

echo ""
echo "==============================================================="
echo "  Batch complete — $(date)"
echo "==============================================================="
echo "Logs: $BATCH_LOG"
echo "Project log: $PROJECT_BATCH_LOG"
echo "Reports: $OUT_DIR/report_*.json"

# Also copy reports into the project so they're analyzable from outside ~/.ssmaker
mkdir -p "$PROJECT_LOG_DIR/reports_${TIMESTAMP}"
cp "$OUT_DIR"/report_*.json "$PROJECT_LOG_DIR/reports_${TIMESTAMP}/" 2>/dev/null || true
echo "Project reports: $PROJECT_LOG_DIR/reports_${TIMESTAMP}/"
echo ""
echo "Linktree publish은 별도 단계입니다 (사용자 chrome MCP 자동화)."
echo "이 창은 10초 후 닫힙니다..."
sleep 10
