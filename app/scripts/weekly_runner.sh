#!/usr/bin/env bash
# launchdから呼ばれるラッパ。引数: predict_tomorrow | review_today
#   predict_tomorrow : 翌日(土or日)分の予想を生成
#   review_today     : 今日(土or日)分の答え合わせ
set -u
MODE="${1:-}"
APP_DIR="/Users/kubota/Desktop/bias/app"

case "$MODE" in
  predict_tomorrow)
    D=$(date -v+1d +%Y%m%d)
    exec "$APP_DIR/scripts/weekly_pipeline.sh" predict "$D"
    ;;
  review_today)
    D=$(date +%Y%m%d)
    exec "$APP_DIR/scripts/weekly_pipeline.sh" review "$D"
    ;;
  *)
    echo "Usage: $0 predict_tomorrow|review_today"; exit 2;;
esac
