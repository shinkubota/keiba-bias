#!/usr/bin/env bash
# launchdから呼ばれるラッパ。引数: predict_tomorrow | review_today
#   predict_tomorrow : 翌日(土or日)分の予想を生成
#   review_today     : 今日(土or日)分の答え合わせ
set -u
MODE="${1:-}"
APP_DIR="/Users/kubota/Desktop/bias/app"

cd "$APP_DIR"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
LOG_DIR="$APP_DIR/logs"; mkdir -p "$LOG_DIR"
TS=$(date +%Y%m%d_%H%M%S)

case "$MODE" in
  predict_tomorrow)
    D=$(date -v+1d +%Y%m%d)
    exec "$APP_DIR/scripts/weekly_pipeline.sh" predict "$D"
    ;;
  review_today)
    D=$(date +%Y%m%d)
    exec "$APP_DIR/scripts/weekly_pipeline.sh" review "$D"
    ;;
  weekly_recap)
    LOG="$LOG_DIR/${TS}_weekly_recap.log"
    python3 scripts/weekly_recap.py >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      git diff --cached --quiet || (git commit -q -m "weekly_recap: 月曜朝の週次まとめ自動追記" && git push origin main) >>"$LOG" 2>&1
    ;;
  special_entries)
    LOG="$LOG_DIR/${TS}_special_entries.log"
    python3 scripts/check_special_entries.py >"$LOG" 2>&1
    ;;
  data_refresh)
    LOG="$LOG_DIR/${TS}_data_refresh.log"
    python3 scripts/data_refresh.py >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      git diff --cached --quiet || (git commit -q -m "data_refresh: 金曜夜のメンテ自動更新" && git push origin main) >>"$LOG" 2>&1
    ;;
  *)
    echo "Usage: $0 predict_tomorrow|review_today|weekly_recap|special_entries|data_refresh"; exit 2;;
esac
