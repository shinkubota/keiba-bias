# カリメロ知見の予想ロジック統合プラン

`notes/calimero_analysis.md` の集計から抽出した強シグナルを、`app/scripts/analyze.py` の評価式に組み込むための整理。

## A. 採用するシグナル（ROI/n基準）

| # | シグナル | 根拠 | 加点案 |
|---|---|---|---:|
| S1 | **想定4-6番人気帯** | ◎@(4-6) 単回収485% 複勝29.2% n=267 | +3 |
| S2 | **想定より実人気が無くなった** (+3以上) | 単回収892% 複勝42.1% n=38 | +4 |
| S3 | **ダート** | ◎@ダ単回収396% vs 芝260% | +1(ダ) |
| S4 | **距離短縮 / 距離延長** | 短縮 単回収529%, 延長442% | +2 |
| S5 | **減量騎手** | 減量含む◎ 単回収458% | +2 |
| S6 | **少頭数 (≤10頭)** | 含む◎ 複勝26.9% n=26 | +1 |
| S7 | **逃げ・先行展開合致** | 逃げ◎ 単回収444% / 先行388% | +2 |
| S8 | **特定R番号** (9R/12R/6R) | 9R:444% 12R:397% 6R:376% | +1 |
| S9 | **小倉・福島開催** | 小倉679% 福島487% | +1 |
| S10 | **大外枠/1枠** | 大外23% 1枠20.9%複勝 | +1 |

逆方向（マイナス補正候補）:
- 想定10-12番人気想定: 複勝11.0% n=172
- 札幌: 複勝17.1% 単回収134%
- 11R: 単回収230%（穴は11Rで効きにくい）

## B. 各シグナルに必要な入力 vs 現在のデータ

| シグナル | 必要データ | 現在所在 | ステータス |
|---|---|---|---|
| S1/S2 (人気) | **想定オッズ or 当日朝オッズ** | netkeibaの予想オッズページ (前日19時〜) | **未取得** |
| S3 (芝/ダ) | shutuba.surface | `shutuba_*.json` | ✅有 |
| S4 (距離変化) | 今走distance / 前走distance | shutuba + horses.recent[0].distance_text | ✅有 |
| S5 (減量) | jockey 先頭マーク `☆▲△◇` | shutuba.horses.jockey | ✅有(パース要) |
| S6 (頭数) | レース出走頭数 | len(shutuba.horses) | ✅有 |
| S7 (展開) | 想定脚質 (前走通過順から推定) | horses.recent.passing | ✅有 (現行analyzeで実装済) |
| S8 (R番号) | race_no | shutuba.race_no | ✅有 |
| S9 (場) | shutuba.track | ✅有 |
| S10 (枠位置) | umaban / 頭数 | ✅有 |
| 追加: 継続騎乗 | 前走の騎手 | **horses.recentに騎手列なし** | **未取得** |
| 追加: クラス変化 | 前走クラス / 今走クラス | race_name から推定要 | ✅(パース要) |

## C. データ取得タスク（不足分）

### C-1. 想定オッズ取得 (重要)
- ソース: `https://race.netkeiba.com/api/api_get_jra_odds.html?race_id=...&type=1` (単勝) or shutubaに含まれる予想オッズ列
- タイミング: 朝の最終評価で叩く（前日夜は未確定）
- 保存先: `app/data/odds_YYYYMMDD.json` (race_id → {umaban: {odds, pop}})
- 新規スクリプト: `app/scripts/fetch_odds.py`

### C-2. 前走の騎手名を horses.recent に追加
- 現在の `fetch_horse.py` の HTML パース時に騎手列も取得して `recent[i].jockey` フィールドを追加
- 既存キャッシュは再利用可（騎手列は同じテーブル内）

### C-3. 前走クラス・今走クラスのパース
- 共通ユーティリティ `class_from_race_name(name) -> "未勝利"|"1勝"|"2勝"|"3勝"|"OP"|"G3"|"G2"|"G1"|"新馬"|"障害"|None`
- race_name 文字列を判定

## D. スコアリング統合案

`analyze.py evaluate_horse()` に以下を追加:

```python
# --- Calimero補正 ---
cal_score = 0
notes = []

# S1/S2: 想定人気帯 (odds_data から)
pop = odds_data.get(umaban, {}).get("pop")  # 朝の想定人気
if pop and 4 <= pop <= 6:
    cal_score += 3; notes.append("人気帯4-6(穴の本線)")
if pop and pop >= 13:
    cal_score -= 2; notes.append("人気帯13+(危険穴)")

# S3: ダート
if surface == "ダ":
    cal_score += 1; notes.append("ダート(◎ROI高)")

# S4: 距離変化
if prev_dist and curr_dist:
    diff = curr_dist - prev_dist
    if -400 <= diff <= -100:
        cal_score += 2; notes.append("距離短縮")
    elif 100 <= diff <= 400:
        cal_score += 2; notes.append("距離延長")

# S5: 減量騎手
if jockey.startswith(("☆","▲","△","◇","★")):
    cal_score += 2; notes.append(f"減量({jockey[0]})")

# S6: 少頭数
if field_size <= 10:
    cal_score += 1; notes.append("少頭数")

# S8/S9: 場・R番号
boost_map = {"小倉":1, "福島":1, "札幌":-1}
cal_score += boost_map.get(track, 0)
if race_no in (6, 9, 12):
    cal_score += 1; notes.append(f"{race_no}R(好成績帯)")
elif race_no == 11:
    cal_score -= 1; notes.append("11R(穴薄)")

# S10: 枠
if waku == 1 or umaban == field_size:
    cal_score += 1; notes.append("端枠")
```

## E. 実行順

1. **C-1 fetch_odds.py 実装** — netkeiba 想定オッズ取得
2. **C-2 fetch_horse.py 改修** — 前走騎手名を recent に追加 (キャッシュ無効化または別フィールド)
3. **C-3 class判定ユーティリティ** — `app/scripts/util_class.py`
4. **D analyze.py 統合** — Calimero補正セクションを `evaluate_horse()` に追加
5. **回帰テスト** — 過去85日の予想結果に対して新スコアを計算し、上位N頭の的中率改善を測る
   - 入力: `notes/calimero_picks_matched.csv` の◎ピックを「Calimero予想」とみなし、当日 analyze.py の上位N頭と一致した場合の的中率と単純比較

## F. 注意点

- **人気帯シグナルは取得タイミング依存**: 予想オッズと最終オッズで差が出るため、朝9時台のスナップショットで運用するのが妥当
- **キーワード由来の補正は弱め**: コメントマッチでn≥20までしか絞れず偽相関のリスク。S1〜S6は数値根拠で堅いが、S7以降は実運用しながら検証
- **過学習リスク**: 場別・R別ブーストはサンプル数が小さく（小倉◎n=42）、半年ごとに再評価する想定
- **コスト**: netkeibaへの追加リクエスト ≈ 1日 30レース × 1回(予想オッズ) = 軽い
