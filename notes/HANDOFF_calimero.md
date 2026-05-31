# Calimero穴予想知見の統合 — 引き継ぎドキュメント

**最終更新:** 2026-05-31
**対象プロジェクト:** `bias` (Horse racing track bias analyzer)
**統合した外部知見:** noteユーザー「カリメロ@穴馬オタク/競馬」(`kooootalll`) の購入記事 過去1年85本

---

## 1. 何をやったか (TL;DR)

1. noteから購入済みのカリメロ記事85本(2025-05-30〜2026-05-30)を全文取得しMarkdown化
2. 各記事の◎/単穴/紐ピック(計1,978件)を構造化CSVに展開
3. 各pickをnetkeibaの当日結果と照合(着順/オッズ/人気を付与, 99.2%マッチ)
4. 過去実績の的中傾向を多軸集計(タイプ/場/距離/想定人気帯/キーワード等)
5. 集計から複勝率・単回収率の強いシグナル(S3〜S10)を抽出し、`analyze.py` の `evaluate_horse()` に**11番目の評価要素**として正式統合
6. `recommend.py` に Cal由来の★穴候補マーク機能を追加
7. `weights["cal"]` で全体係数を制御可能(0で完全無効化、1で標準、>1で強化)

---

## 2. 生成ファイル一覧

### データ
| ファイル | 説明 | サイズ |
|---|---|---|
| `notes/calimero_articles.md` | 85記事の本文全文(noteAPI→HTML→テキスト化) | 約495KB / 8,252行 |
| `notes/calimero_picks.csv` | 全1,978pickの構造化(date/course/race/type/umaban/name/popularity_est/comment) | 約500KB |
| `notes/calimero_picks_matched.csv` | picks に actual_finish/actual_pop/actual_odds/surface/distance/baba を付加 | 約600KB |
| `notes/calimero_race_meta.json` | 該当レースの surface/distance/baba/race_name メタ | 〜 |

### ドキュメント
| ファイル | 説明 |
|---|---|
| `notes/calimero_analysis.md` | 多軸集計レポート(タイプ別/場別/想定人気帯別/距離別/馬場別/R別/キーワード別+高配当事例) |
| `notes/calimero_integration_plan.md` | 採用シグナル(S1〜S10)/データ依存/スコアリング設計の意思決定記録 |
| `notes/backtest_calimero.md` | 2日138件のCal補正あり/なし比較 |
| `notes/HANDOFF_calimero.md` | このファイル |

### スクリプト (`app/scripts/`)
| ファイル | 役割 | 使い方 |
|---|---|---|
| `parse_calimero.py` | 記事Markdown → picks CSV | `python3 parse_calimero.py` |
| `match_calimero_results.py` | picks CSV に netkeiba結果を join | `python3 match_calimero_results.py` |
| `analyze_calimero.py` | 傾向集計レポート出力 | `python3 analyze_calimero.py` |
| `backtest_calimero.py` | Cal有無の上位3頭的中率比較 | `python3 backtest_calimero.py 20260530 20260425` |
| `fetch_odds.py` | netkeiba想定/朝オッズ取得(現状は予備。analyzeは未使用) | `python3 fetch_odds.py 20260530` |

---

## 3. analyze.py への組み込み詳細

### スコアリング配点表 (`evaluate_horse()` 内 `weights` dict)

```python
weights = {"gate":3, "sire":3, "broodmare":2, "prev":3, "weight":0,
           "agari":2, "stable":5, "class":1, "pace_fit":0, "baba":4,
           "cal":1}   # ★Calimero知見の全体係数
```

`weights["cal"]` を変更するだけでCal要素を強弱できる:
- `0` → 完全無効
- `1` → 標準(現在のデフォルト)
- `2` → Calシグナルを倍掛け
- マイナス値は想定外

### Calシグナル内訳(`calimero_bonus()`)

| Sig | 条件 | 加点(weight前) | 根拠ROI |
|---|---|---:|---|
| S3 | 芝/ダの "ダ" | +1 | ◎ダ単回収396% vs 芝260% |
| S4 | 前走距離との差: -400〜-100m(短縮)/+100〜+400m(延長) | +2 | 短縮529%/延長442% |
| S5 | 騎手名先頭が `☆▲△◇★`(減量印) | +2 | 減量含む◎ 単回収458% |
| S6 | 出走頭数 ≤ 10 | +1 | 少頭数◎ 複勝26.9% |
| S8a | race_no ∈ {6,9,12} | +1 | 6:376%/9:444%/12:397% |
| S8b | race_no = 11 | -1 | 11R◎ 単回収230% |
| S9 | track ∈ {小倉, 福島} | +1 | 小倉679%/福島487%(◎) |
| S9 | track = 札幌 | -1 | 札幌◎ 単回収134% |
| S10 | 1枠 or 大外枠 | +1 | 1枠20.9%/大外23.2% 複勝 |

**除外したシグナル:**
- **S1/S2(想定人気帯)**: 過去分析では◎@4-6人気帯=複勝29.2%/単回収485%、想定より人気が無い+3以上=単回収892% と最強だったが、ユーザー判断により採用見送り(想定オッズへの依存が強く前日運用ロジックと相性が悪いため)。
- 関連コードの `fetch_odds.py` と `app/data/odds_*.json` は残置(将来採用復活時のため)。

### 評価フロー
1. `evaluate_horse()` 内で他10要素のスコアを計算
2. 続けて `calimero_bonus(horse, race, horse_data, total_horses)` を呼ぶ
3. 返り値 `cb_raw` に `weights["cal"]` を掛けた値を `score` に加算
4. 各シグナル発火時のラベルを `[Cal]距離短縮(1800→1400)` のように `reasons` に追加
5. `(score, reasons, cal_pts)` を返却

### recommend.py の★穴候補
- `analyze_race()` で各馬の `cal_pick` フラグを計算
  - 条件: TOP8以内 AND Cal補正≥4 AND ability_eff ≤ race median
- recommend.py 出力時:
  - TOP3に含まれる馬は行頭に `★` 付与
  - TOP3外でも `cal_pick=True` の馬は最大3頭まで「★穴」行として追加表示

---

## 4. 出力サンプル

```
## 東京 6R ダ1600m 3歳1勝クラス (12頭)
  狙い: 外枠の馬がスピードに乗りやすく内枠は不利
   1. [ 1] エスシービクトリア（牡3 横山和 57.0kg）  97.0%  (score 93.2, cal +5)  — 距離短縮(ダ1800→1600); 複勝安定(100%); 馬場適性; [Cal]ダート
   2. [ 5] バトルアックス（牡3 戸崎圭 57.0kg）   3.0%  (score 84.5, cal +4)  — 複勝安定(100%); [Cal]ダート; [Cal]距離延長(1400→1600)
   3. [ 9] カシノスパーク（牡3 ▲石神道 54.0kg）   0.0%  (score 61.9, cal +6)  — 軽斤量; 外枠有利; 距離短縮; [Cal]ダート
  ★穴 [ 3] ナックホワイト  (score 38.3, cal +4)  — [Cal]ダート; [Cal]距離短縮(1800→1600); [Cal]6R(好成績帯)
  ★穴 [11] ラフレードピエル  (score 38.1, cal +4)  — [Cal]ダート; [Cal]減量騎手(☆)
```

各馬の `cal +N` 値で「なぜCal補正がついたか/つかなかったか」が追跡可能。

---

## 5. 知っておくべき制約・前提

### サンプル小さい問題
- 場別ブースト(S9)は ◎n=42(小倉) と小サンプル。ブレが大きく、半年毎の再較正が必要。
- バックテストは2日138件しか取れていない(過去日のnetkeiba shutubaが取得しにくいため)。**Cal補正の純粋な貢献度はまだ統計的に有意ではない**。

### 過去日のshutuba取得問題
- `fetch_shutuba.py` は過去日(数ヶ月前以上)に対しては空のJSONを返す
- netkeibaの shutuba.html は発走直前〜直後のみ生きていて、それ以降は result.html に切り替わる模様
- 大規模バックテストには result.html 経由で entries を逆生成する別実装が必要
- 当面は「直近の翌日予想」運用のみ実用

### 想定オッズの不採用(再掲)
- S1/S2は最強シグナルだが現状不採用
- 復活させたい場合: `fetch_odds.py` で `odds_YYYYMMDD.json` を取得 → `calimero_bonus()` に odds_for_race を渡す → S1/S2 ブロックを復活
- コミットログには残しているので戻すのは容易

### キャッシュ
- `app/cache/` 配下に netkeibaレスポンスが残る
- TTL: shutuba 1h / horse 24h / result 30日
- 大規模バックテストでキャッシュが膨らむ可能性あり

---

## 6. 次にやると効きそうなこと(優先度順)

1. **より長期バックテスト** — 過去85日全部をrerunするための result.html → entries 逆生成スクリプト
2. ~~**継続騎乗ボーナス**~~ → **実装済 (2026-05-31)**: S11として `calimero_bonus()` に追加。出馬表↔結果で略称↔フル名の表記揺れがあるため前方一致でマッチ。日曜348頭で13件発火。
3. ~~**昇級ボーナス**~~ → **実装済 (2026-05-31)**: S12として追加。ただし `fetch_horse.py` の `race_class` 抽出が大半 None となるバグがあり、現状ほぼ発火しない。`fetch_horse.py` 内のクラス推定ロジック(タグ「(1勝クラス)」「(OP)」等の検出)に要修正。
4. **Cal重みのチューニング** — `weights["cal"]` を 0.5, 1.0, 1.5, 2.0 で振り、過去結果に対するROI最大化点を探す → **20260530の単発スイープでは重み0が単勝率最良(6/23=26%)、1.0で5/23=22% に低下。サンプル小**(n=23)で断定不可だが、能力×バイアスの主軸が既に強いため Cal の追加効果は限定的の可能性。`notes/backtest_calimero.md` 参照。
5. **想定オッズ復活検討** — 朝9時頃のスナップショットで odds_*.json を毎日取得し、S1/S2を試験的に有効化(`weights["cal_odds"]` を分離)
6. **(新)race_class抽出バグ修正** — S12を機能させるために必須。`fetch_horse.py` の race_class推定ロジックが「(1勝クラス)」等のレース名パターンを取りこぼしている。要修正。

---

## 7. 関連する既存ドキュメント

- `app/PROJECT.md` — プロジェクト全体まとめ。Cal要素は「11番目の評価要素」として配点表に追加済み(Sec.4)
- `app/RUNBOOK.md` — 毎週の運用手順(`parse_calimero` / `match` / `analyze_calimero` / `backtest_calimero` は今のところ運用ルーチンには含めず、必要時に手動実行する想定)
- `notes/calimero_integration_plan.md` — シグナル選定理由と除外理由のロギング

---

## 8. 連絡事項

- noteの購入記事はユーザー(`shinkbt0427i@gmail.com`)アカウント由来。ブラウザ経由のChrome MCP拡張で取得した。
- 取得元: `https://note.com/library/purchased` → リダイレクト先 `/notes/purchased`
- 取得API: `/api/v3/payments/purchase_notes?note_intro_only=true&page=N` / `/api/v3/notes/{key}`
- 1年より前の記事もさらに74本(2024-01〜2025-05)購入されているが、初回スコープでは取得していない。必要なら同じ手順で追加可能。
