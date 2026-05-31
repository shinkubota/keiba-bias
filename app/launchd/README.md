# 週次自動運用 (launchd)

毎週末の予想生成と振り返り追記をmacOSのlaunchdでスケジュール実行する。

## スケジュール

| 曜日・時刻 | ジョブ | 内容 |
|---|---|---|
| 金 20:00 | `predict-sat` | 翌日(土)の予想生成→push→Pages反映 |
| 土 19:00 | `review-sat` | 当日(土)結果取得→評価→retrospective.md追記 |
| 土 20:00 | `predict-sun` | 翌日(日)の予想生成→push→Pages反映 |
| 日 19:00 | `review-sun` | 当日(日)結果取得→評価→retrospective.md追記 |

時刻はWWFFの実況スケジュール(発走11:00〜16:00台)に合わせ、最終R終了から30〜60分後を狙う。

## インストール

```bash
bash /Users/kubota/Desktop/bias/app/launchd/install.sh install
```

→ `~/Library/LaunchAgents/` に4つの plist がコピーされ、`launchctl load` で常駐化される。

## ステータス確認

```bash
bash /Users/kubota/Desktop/bias/app/launchd/install.sh status
# 例:
# 12345 0 com.kubota.bias.predict-sat
# 12346 0 com.kubota.bias.predict-sun
# 12347 0 com.kubota.bias.review-sat
# 12348 0 com.kubota.bias.review-sun
```

## 手動テスト

```bash
# 明日の予想を即時生成(発火時刻を待たずに動作確認)
bash /Users/kubota/Desktop/bias/app/launchd/install.sh test-predict

# 今日の結果取得＋振り返り
bash /Users/kubota/Desktop/bias/app/launchd/install.sh test-review
```

## 解除

```bash
bash /Users/kubota/Desktop/bias/app/launchd/install.sh uninstall
```

## ログ

- `app/logs/launchd_*.log` — launchdが受け取る標準出力
- `app/logs/YYYYMMDD_HHMMSS_<mode>_<date>.log` — 各ジョブの実行ログ(stdout/stderr統合)

## 前提条件

1. **PC起動＋ネット接続**: launchdは指定時刻にMacが起動&スリープ解除されている必要あり。スリープ中は次に起き上がった瞬間に実行される(catchup挙動)
2. **gh CLIが認証済み**: pushは `gh auth login` 済み前提
3. **homebrew Python3** が `/opt/homebrew/bin` または `/usr/local/bin` にあること(pipeline.shでPATH追加済)

## 各ジョブの動作

### predict (predict_tomorrow)
1. `racelist_*` `shutuba_*` キャッシュをクリア(枠順確定対応)
2. `fetch_shutuba.py {翌日}` 出馬表取得
3. `fetch_horse.py {翌日}` 各馬血統＋直近5走
4. `build_lineage_fallback.py` 新種牡馬の系統補完
5. `fetch_odds.py {翌日}` 想定オッズ(取れなければスキップ)
6. `recommend_sunday.py {翌日}` 3-5頭幅広版
7. `build_web.py {翌日}` HTML/table生成
8. `git add -A && commit && push` 自動反映

### review (review_today)
1. `result_*` キャッシュをクリア(当日反映遅れ対応)
2. `fetch_results.py {当日}` 着順・人気・オッズ取得
3. `evaluate.py {当日}` 3手法比較
4. `append_retrospective.py {当日}` retrospective.md に新セクション追記(重複防止つき)
5. `git push`

## 動作確認済み

- `append_retrospective.py 20260531` → 「## 2026-05-31(日) v0.9 weekly run」セクション追加成功
- 重複呼び出し時は `already appended:` で何もしない
