# data/ ディレクトリ構成

## 構造

```
data/
├── memory/         # 知識ベース（静的・予想の土台）
│   ├── courses.json          コース別バイアス(書籍由来)
│   ├── lineage.json          種牡馬→大系統/小系統/型（書籍由来・優先）
│   ├── lineage_fallback.json 血統表から自動判定した補完（毎週更新）
│   ├── lineage_tree.json     11大系統ツリー＋祖先名マーカー
│   └── jockey_stats.json     騎手通算複勝率(直近5年累計、netkeibaから取得)
│
├── review/         # 振り返り（継続更新）
│   └── retrospective.md      週次成績と配点調整の履歴
│
├── archive/        # 旧仕様・初期検討 + 週次自動アーカイブ
│   └── YYYY/MM/    ← archive_old_data.py が日付付きファイルを月ごとに格納
│   ├── _new_entries.json
│   ├── analysis_YYYYMMDD.md           （現在は table_YYYYMMDD.md / recommend_wide_*.md に統合）
│   ├── article_YYYYMMDD.*              （note配信機能の試作）
│   ├── recommend_YYYYMMDD.md           （現在は recommend_wide_YYYYMMDD.md）
│   └── shutuba_2025*.json / horses_2025*.json  （テスト時のダミー）
│
└── （週次データ — 直下）
    ├── shutuba_YYYYMMDD.json    出馬表
    ├── horses_YYYYMMDD.json     各馬の血統＋直近5走
    ├── odds_YYYYMMDD.json       朝/想定オッズ
    ├── results_YYYYMMDD.json    結果（着順/人気/単オッズ）
    ├── table_YYYYMMDD.md        表形式の推奨
    ├── recommend_wide_YYYYMMDD.md  3〜5頭幅広版
    └── evaluation_YYYYMMDD.md   答え合わせ
```

## memory が更新されるタイミング

- `courses.json` / `lineage.json` / `lineage_tree.json` : 書籍由来。基本は静的、追加・修正があるときのみ手動更新
- `lineage_fallback.json` : `python3 scripts/build_lineage_fallback.py` で毎週自動更新
- `jockey_stats.json` : `python3 scripts/fetch_jockey_stats.py YYYYMMDD` で月1程度の更新を推奨（騎手成績は短期間で大きく変わらない）

## review の更新

`retrospective.md` は毎週の答え合わせ後に**下に追記**する形式で運用。
過去の配点バージョンと因子寄与の履歴を残す。

## archive の運用

予想で使わなくなったファイルをここに入れる。**削除はしない**（過去経緯の追跡用）。
