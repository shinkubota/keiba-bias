# トラックバイアス分析 運用手順（効率版 v0.3）

## 毎週のルーチン（前日・枠順確定後に実行）

```bash
cd /Users/kubota/Desktop/bias/app

# 0) 枠順確定後はshutubaキャッシュを無効化（出馬表だけ最新化）
rm -f cache/racelist_* cache/shutuba_*

# 1) 出馬表取得（YYYYMMDD。土日それぞれ）
python3 scripts/fetch_shutuba.py 20260530
python3 scripts/fetch_shutuba.py 20260531

# 2) 各馬の血統・前走取得（馬ページは24hキャッシュ。新規馬のみ取得）
python3 scripts/fetch_horse.py 20260530
python3 scripts/fetch_horse.py 20260531

# 3) 血統fallback更新（新しい種牡馬を血統表から自動分類）
python3 scripts/build_lineage_fallback.py

# 4) 分析（標準出力＋ data/analysis_YYYYMMDD.md に保存）
python3 scripts/analyze.py 20260530
python3 scripts/analyze.py 20260531
```

対象場の変更: `fetch_shutuba.py YYYYMMDD --tracks 東京,京都,阪神` のように指定。

## データファイル
| ファイル | 内容 | 更新 |
|---|---|---|
| `data/courses.json` | コース別バイアス（書籍コース事典） | 静的 |
| `data/lineage.json` | 種牡馬→大系統/小系統/型（**書籍・権威源**） | 完全版で拡充中 |
| `data/lineage_fallback.json` | 血統表から自動判定（書籍に無い分） | 毎週自動更新 |
| `data/lineage_tree.json` | 11大系統ツリー＋祖先名マーカー | 静的 |
| `data/shutuba_YYYYMMDD.json` | 出馬表 | 毎週 |
| `data/horses_YYYYMMDD.json` | 各馬の父・母父・直近5走 | 毎週 |
| `data/analysis_YYYYMMDD.md` | 分析レポート | 毎週 |

## スコアリング（v0.3）
- 枠順バイアス一致: +2
- 父が注目血統（系統 or 個別名）: +3
- 母父が注目血統: +2
- 前走条件（同距離/短縮/着順/上がり/先行差し/重賞名/前走場距離）: +3

## 既知の限界
- 血統カバレッジ: ユニーク77% / 出走数加重88%（残りは外国産母父。完全版で対応）
- 枠順発表前は枠スコアが入らない
- 上がり最速は絶対値<34.0で近似（同レース内1位判定は未実装）
- クッション値・含水率は未取得（道悪ルールは前走馬場でのみ近似）

## 精度向上バックログ
1. 完全版 lineage.json（個別プロフィール全読・型/適性付与）← バックグラウンド進行中
2. JRA馬場発表（クッション値・含水率）取得
3. 上がり最速の正確判定（レース結果ページ取得）
4. 的中ログ feedback.jsonl による重み調整
