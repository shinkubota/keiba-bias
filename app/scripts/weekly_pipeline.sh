#!/usr/bin/env bash
# 毎週運用パイプライン
#   predict YYYYMMDD  : 出馬表→血統→fallback→web→md  (枠順確定後の前夜に走らせる)
#   review  YYYYMMDD  : 結果取得→評価→retrospective.md追記  (当日夕方)
#
# 失敗時もログを残し、最後に push まで実行。

set -u
MODE="${1:-}"
DATE="${2:-}"
APP_DIR="/Users/kubota/Desktop/bias/app"
REPO_DIR="/Users/kubota/Desktop/bias"
LOG_DIR="$APP_DIR/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$(date +%Y%m%d_%H%M%S)_${MODE}_${DATE}.log"
exec >>"$LOG" 2>&1

cd "$APP_DIR"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export LANG=ja_JP.UTF-8

log() { echo "[$(date '+%F %T')] $*"; }

run() {
  log "RUN: $*"
  if "$@"; then log "  OK"; else log "  NG (rc=$?)"; return 1; fi
}

git_push() {
  cd "$REPO_DIR"
  git add -A
  if git diff --cached --quiet; then
    log "git: no changes"
  else
    git commit -q -m "$1" && log "git commit: $1" || log "git commit failed"
    git push origin main 2>&1 | tail -3 || log "git push failed"
  fi
  cd "$APP_DIR"
}

predict() {
  local d="$1"
  local phase="${2:-early}"  # early=想定オッズ / late=直前オッズ
  log "=== PREDICT $d ($phase) ==="
  # 出馬表系のキャッシュをクリア(枠順確定/直前更新対応)
  find cache -name "racelist_${d}.html" -delete 2>/dev/null
  if [ "$phase" = "late" ]; then
    # 直前は全キャッシュ刷新(オッズが頻繁に動くため)
    find cache -name "shutuba_*.html" -delete 2>/dev/null
    find cache -name "odds_*.html" -delete 2>/dev/null
  else
    find cache -name "shutuba_*.html" -mtime +0 -delete 2>/dev/null   # >24h
  fi
  run python3 scripts/fetch_shutuba.py "$d"
  run python3 scripts/fetch_horse.py "$d"
  run python3 scripts/build_lineage_fallback.py
  run python3 scripts/fetch_odds.py "$d" || true
  # phaseで出力ファイル名を分ける: early(想定)→_early / late(直前)→_late
  # 互換のためデフォルト名(recommend_wide_${d}.md)はlateで上書き、なければearlyで作る
  local sfx="_${phase}"
  run python3 scripts/recommend_sunday.py "$d" > "data/recommend_wide_${d}${sfx}_A.md"
  run python3 scripts/recommend_sunday.py "$d" --bias-boost-maiden > "data/recommend_wide_${d}${sfx}_B.md"
  # 最新版を canonical 名にも反映 (lateが優先、なければearly)
  cp "data/recommend_wide_${d}${sfx}_A.md" "data/recommend_wide_${d}_A.md"
  cp "data/recommend_wide_${d}${sfx}_B.md" "data/recommend_wide_${d}_B.md"
  cp "data/recommend_wide_${d}${sfx}_A.md" "data/recommend_wide_${d}.md"
  run python3 scripts/build_web.py "$d" --top 4
  git_push "weekly: ${d} 予想生成(${phase}/A・B 2案)"
}

review() {
  local d="$1"
  log "=== REVIEW $d ==="
  # 結果ページのキャッシュ削除(当日反映遅れ対応)
  find cache -name "result_*.html" -mtime -1 -delete 2>/dev/null
  run python3 scripts/fetch_results.py "$d"
  run python3 scripts/evaluate.py "$d"
  # retrospective.md 追記
  python3 scripts/append_retrospective.py "$d" >> "$LOG" 2>&1 || true
  git_push "weekly: ${d} 振り返り"
}

case "$MODE" in
  predict)       predict "$DATE" early ;;
  predict_early) predict "$DATE" early ;;
  predict_late)  predict "$DATE" late ;;
  review)        review  "$DATE" ;;
  *) echo "Usage: $0 predict|predict_early|predict_late|review YYYYMMDD"; exit 2 ;;
esac
log "DONE"
