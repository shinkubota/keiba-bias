#!/usr/bin/env bash
# launchdエージェントを登録するインストーラ
# 使い方: bash app/launchd/install.sh   (登録) / uninstall (解除)
set -e
LA_DIR="$HOME/Library/LaunchAgents"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
PLISTS=(
  com.kubota.bias.predict-sat.plist
  com.kubota.bias.predict-sun.plist
  com.kubota.bias.review-sat.plist
  com.kubota.bias.review-sun.plist
  com.kubota.bias.weekly-recap.plist
  com.kubota.bias.column-tue.plist
  com.kubota.bias.column-wed.plist
  com.kubota.bias.special-entries.plist
  com.kubota.bias.data-refresh.plist
  com.kubota.bias.pundit-mon.plist
  com.kubota.bias.pundit-tue.plist
  com.kubota.bias.pundit-wed.plist
  com.kubota.bias.pundit-thu.plist
)
ACTION="${1:-install}"
mkdir -p "$LA_DIR"

case "$ACTION" in
  install)
    for p in "${PLISTS[@]}"; do
      cp "$SRC_DIR/$p" "$LA_DIR/$p"
      launchctl unload "$LA_DIR/$p" 2>/dev/null || true
      launchctl load -w "$LA_DIR/$p"
      echo "loaded: $p"
    done
    chmod +x /Users/kubota/Desktop/bias/app/scripts/weekly_runner.sh \
              /Users/kubota/Desktop/bias/app/scripts/weekly_pipeline.sh
    echo "=== installed ==="
    launchctl list | grep com.kubota.bias
    ;;
  uninstall)
    for p in "${PLISTS[@]}"; do
      launchctl unload "$LA_DIR/$p" 2>/dev/null && echo "unloaded: $p" || true
      rm -f "$LA_DIR/$p"
    done
    echo "=== uninstalled ==="
    ;;
  status)
    launchctl list | grep com.kubota.bias || echo "(none loaded)"
    ;;
  test-predict)
    /Users/kubota/Desktop/bias/app/scripts/weekly_runner.sh predict_tomorrow
    ;;
  test-review)
    /Users/kubota/Desktop/bias/app/scripts/weekly_runner.sh review_today
    ;;
  *)
    echo "Usage: $0 [install|uninstall|status|test-predict|test-review]"; exit 2 ;;
esac
