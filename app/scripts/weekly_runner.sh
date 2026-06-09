#!/bin/bash
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
  predict_tomorrow|predict_tomorrow_early)
    D=$(date -v+1d +%Y%m%d)
    "$APP_DIR/scripts/weekly_pipeline.sh" predict_early "$D"
    python3 "$APP_DIR/scripts/note_writer.py" predict "$D" 2>/dev/null
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "予想+note記事(早期/想定オッズ): $D" && git push origin main))
    ;;
  predict_today_late)
    D=$(date +%Y%m%d)
    "$APP_DIR/scripts/weekly_pipeline.sh" predict_late "$D"
    python3 "$APP_DIR/scripts/note_writer.py" predict "$D" 2>/dev/null
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "予想+note記事(直前/最新オッズ): $D" && git push origin main))
    ;;
  review_today)
    D=$(date +%Y%m%d)
    "$APP_DIR/scripts/weekly_pipeline.sh" review "$D"
    python3 "$APP_DIR/scripts/note_writer.py" review "$D" 2>/dev/null
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "振り返り+note記事: $D" && git push origin main))
    ;;
  daily_inbox_sync)
    LOG="$LOG_DIR/${TS}_daily_inbox_sync.log"
    cd "$APP_DIR/.." && git pull --rebase --autostash origin main >>"$LOG" 2>&1 || true
    python3 "$APP_DIR/scripts/integrate_mobile_notes.py" >>"$LOG" 2>&1
    git add -A && \
      (git diff --cached --quiet || (git commit -q -m "daily_inbox_sync: モバイルメモ統合" && git push origin main)) >>"$LOG" 2>&1
    ;;
  weekly_recap)
    LOG="$LOG_DIR/${TS}_weekly_recap.log"
    # スマホ(GitHubアプリ)で書き溜めたメモを retrospective.md へ統合
    python3 scripts/integrate_mobile_notes.py >>"$LOG" 2>&1
    python3 scripts/weekly_recap.py >>"$LOG" 2>&1
    # 古い日付ファイルをアーカイブ(4日より古い)
    python3 scripts/archive_old_data.py >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "weekly_recap: 月曜朝の週次まとめ+モバイルメモ統合+古データ整理" && git push origin main)) >>"$LOG" 2>&1
    ;;
  special_entries)
    LOG="$LOG_DIR/${TS}_special_entries.log"
    # 結果は data/review/columns/ ではなくログにのみ出す設計
    # ただし watchlist.json などが手動更新されていた場合に備えて add のみ実行
    python3 scripts/check_special_entries.py >"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "special_entries: 翌週末特別レース確認" && git push origin main)) >>"$LOG" 2>&1
    ;;
  column_miss)
    LOG="$LOG_DIR/${TS}_column_miss.log"
    python3 scripts/weekday_column.py miss >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "火曜コラム: 取りこぼし深堀" && git push origin main)) >>"$LOG" 2>&1
    ;;
  column_watch)
    LOG="$LOG_DIR/${TS}_column_watch.log"
    python3 scripts/weekday_column.py watch >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "水曜コラム: 警戒馬因子分析" && git push origin main)) >>"$LOG" 2>&1
    ;;
  pundit_review)
    LOG="$LOG_DIR/${TS}_pundit_review.log"
    python3 scripts/pundit_review.py >>"$LOG" 2>&1
    cd "$APP_DIR/.." && git add -A && \
      (git diff --cached --quiet || (git commit -q -m "配信者レビュー(平日夕方)" && git push origin main)) >>"$LOG" 2>&1
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
