#!/usr/bin/env python3
"""カリメロの過去予想の傾向分析。

入力: notes/calimero_picks_matched.csv
出力: notes/calimero_analysis.md
"""
from __future__ import annotations
import csv, re, pathlib, statistics
from collections import defaultdict

ROOT = pathlib.Path(__file__).parent.parent.parent
SRC = ROOT/"notes"/"calimero_picks_matched.csv"
OUT = ROOT/"notes"/"calimero_analysis.md"

KEYWORDS = [
    "距離短縮","距離延長","初ダート","ダート替わり","芝替わり","芝に戻","ダートに戻",
    "逃げ","先行","好位","差し","追い込み",
    "外伸び","内伸び","外有利","内有利","内枠","外枠","大外","最内","最外",
    "前走不利","スムーズ","折り合い","ハイペース","スローペース","展開不利",
    "上がり最速","上がり3F","重賞","少頭数","多頭数","継続騎乗","乗り替わ",
    "斤量増","斤量減","軽ハンデ","減量","休み明け","休養明け","連闘","間隔",
    "1枠","8枠","大外枠","好枠","枠悪","枠不利","枠順",
    "復調","格下","格上","クラス上","クラス下","昇級","降級",
    "重馬場","稍重","道悪","良馬場","直線","コーナー",
    "鞍上","ルメール","川田","モレイラ","レーン","北村",
    "前走着順","前走3着","前走4着","前走5着","勝ち馬","タイム差",
]

def to_int(s, default=None):
    try: return int(s)
    except Exception: return default

def to_float(s, default=None):
    try: return float(s)
    except Exception: return default

def bucket_pop_est(p):
    if p is None: return "不明"
    if p <= 3: return "1-3"
    if p <= 6: return "4-6"
    if p <= 9: return "7-9"
    if p <= 12: return "10-12"
    return "13+"

def bucket_pop_actual(p):
    if p is None: return "不明"
    if p <= 3: return "1-3"
    if p <= 6: return "4-6"
    if p <= 9: return "7-9"
    if p <= 12: return "10-12"
    return "13+"

def bucket_dist(d):
    if not d: return "不明"
    if d <= 1300: return "短距離(~1300)"
    if d <= 1600: return "マイル(1400-1600)"
    if d <= 1900: return "中距離(1700-1900)"
    if d <= 2200: return "中長(2000-2200)"
    return "長距離(2300+)"

def compute_stats(rows):
    n = len(rows)
    matched = [r for r in rows if r["actual_finish"] != ""]
    win = sum(1 for r in matched if to_int(r["actual_finish"]) == 1)
    plc = sum(1 for r in matched if (f := to_int(r["actual_finish"])) is not None and f <= 3)
    ren = sum(1 for r in matched if (f := to_int(r["actual_finish"])) is not None and f <= 2)
    # 単勝ROI = sum(odds for hits) / n picks * 100  (per 100yen bet)
    odds_sum = sum((to_float(r["actual_odds"]) or 0) for r in matched if to_int(r["actual_finish"]) == 1)
    roi_tan = (odds_sum / n * 100) if n else 0
    return {
        "n": n, "matched": len(matched),
        "win": win, "win_pct": (win/len(matched)*100) if matched else 0,
        "plc": plc, "plc_pct": (plc/len(matched)*100) if matched else 0,
        "ren": ren, "ren_pct": (ren/len(matched)*100) if matched else 0,
        "roi_tan": roi_tan,
    }

def fmt_row(label, s, min_n=0):
    if s["n"] < min_n: return None
    return f"| {label} | {s['n']} | {s['win']} ({s['win_pct']:.1f}%) | {s['ren']} ({s['ren_pct']:.1f}%) | {s['plc']} ({s['plc_pct']:.1f}%) | {s['roi_tan']:.0f}% |"

def group_table(rows, key_fn, label_col, min_n=10):
    groups = defaultdict(list)
    for r in rows: groups[key_fn(r)].append(r)
    lines = [f"| {label_col} | 件数 | 単勝 | 連対 | 複勝 | 単回収 |", "|---|---:|---|---|---|---:|"]
    items = []
    for k, v in groups.items():
        s = compute_stats(v)
        if s["n"] < min_n: continue
        items.append((k, s))
    # sort by count desc
    items.sort(key=lambda x: -x[1]["n"])
    for k, s in items:
        line = fmt_row(str(k), s)
        if line: lines.append(line)
    return "\n".join(lines)

def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    # Filter matched only for clean stats; keep unmatched count separately
    matched_rows = [r for r in rows if r["actual_finish"] != ""]
    unmatched = len(rows) - len(matched_rows)

    md = []
    md.append("# カリメロ@穴馬オタク 予想傾向分析")
    md.append("")
    md.append(f"対象: 過去1年（{min(r['race_date'] for r in rows)}〜{max(r['race_date'] for r in rows)}）/ pick総数 {len(rows)} / 結果照合済 {len(matched_rows)} / 未照合 {unmatched}")
    md.append("")
    md.append("- 単勝＝1着 / 連対＝2着以内 / 複勝＝3着以内")
    md.append("- 単回収 = 全pickを単勝100円均等買いした時の回収率 (%)")
    md.append("")

    md.append("## 1. type別（本命◎ / 単穴 / 紐）全体")
    md.append("")
    md.append(group_table(matched_rows, lambda r: r["type"], "type", min_n=5))
    md.append("")

    # 各typeで詳細
    for t in ["◎","単穴","紐"]:
        subset = [r for r in matched_rows if r["type"] == t]
        if not subset: continue
        md.append(f"## 2-{t}  {t}の内訳")
        md.append("")

        md.append(f"### 場別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: r["course"], "場", min_n=20))
        md.append("")

        md.append(f"### 想定人気帯別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: bucket_pop_est(to_int(r["popularity_est"])), "想定人気", min_n=15))
        md.append("")

        md.append(f"### 実際の人気帯別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: bucket_pop_actual(to_int(r["actual_pop"])), "実人気", min_n=15))
        md.append("")

        md.append(f"### 距離帯別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: bucket_dist(to_int(r["distance"])), "距離", min_n=20))
        md.append("")

        md.append(f"### 馬場別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: r.get("surface") or "?", "芝/ダ", min_n=20))
        md.append("")
        md.append(group_table(subset, lambda r: r.get("baba") or "?", "馬場状態", min_n=20))
        md.append("")

        md.append(f"### R番号別 ({t})")
        md.append("")
        md.append(group_table(subset, lambda r: f"{r['race']}R", "R", min_n=20))
        md.append("")

    # 想定人気と実人気の差: 想定より人気しすぎ or 過小評価
    md.append("## 3. 想定人気 vs 実人気のズレ（◎のみ）")
    md.append("")
    diffs = []
    for r in matched_rows:
        if r["type"] != "◎": continue
        pe = to_int(r["popularity_est"]); pa = to_int(r["actual_pop"])
        if pe is None or pa is None: continue
        diffs.append({"diff": pa - pe, **r})
    # bucket
    def diff_bucket(d):
        if d <= -3: return "想定より人気(-3以下)"
        if d <= -1: return "想定より人気(-1〜-2)"
        if d == 0:  return "想定通り(0)"
        if d <= 2:  return "想定より不人気(+1〜+2)"
        return "想定より不人気(+3以上)"
    md.append(group_table(diffs, lambda r: diff_bucket(r["diff"]), "想定との差", min_n=10))
    md.append("")

    # キーワード分析（◎のみ。コメントに登場する語彙別）
    md.append("## 4. ◎コメントのキーワード別（n≥20）")
    md.append("")
    md.append("各キーワードを含むpickをサブセットして集計（重複あり）")
    md.append("")
    honmei = [r for r in matched_rows if r["type"] == "◎"]
    kw_rows = []
    for kw in KEYWORDS:
        sub = [r for r in honmei if kw in (r.get("comment") or "")]
        if len(sub) < 20: continue
        s = compute_stats(sub)
        kw_rows.append((kw, s))
    kw_rows.sort(key=lambda x: -x[1]["plc_pct"])
    md.append("| キーワード | 件数 | 単勝 | 連対 | 複勝 | 単回収 |")
    md.append("|---|---:|---|---|---|---:|")
    for kw, s in kw_rows:
        md.append(f"| {kw} | {s['n']} | {s['win']} ({s['win_pct']:.1f}%) | {s['ren']} ({s['ren_pct']:.1f}%) | {s['plc']} ({s['plc_pct']:.1f}%) | {s['roi_tan']:.0f}% |")
    md.append("")

    # トップ・ワーストキーワード
    md.append("### 複勝率の高いキーワードTOP10 / ワースト10")
    md.append("")
    if kw_rows:
        top10 = kw_rows[:10]; worst10 = kw_rows[-10:]
        md.append("**TOP10（複勝率順）**")
        md.append("")
        for kw, s in top10:
            md.append(f"- `{kw}` n={s['n']}  複勝 {s['plc_pct']:.1f}%  単勝 {s['win_pct']:.1f}%  単回収 {s['roi_tan']:.0f}%")
        md.append("")
        md.append("**ワースト10**")
        md.append("")
        for kw, s in worst10:
            md.append(f"- `{kw}` n={s['n']}  複勝 {s['plc_pct']:.1f}%  単勝 {s['win_pct']:.1f}%  単回収 {s['roi_tan']:.0f}%")
        md.append("")

    # 高オッズで的中したケースの抜粋
    md.append("## 5. 高配当的中ハイライト（単勝100倍以上で1着）")
    md.append("")
    big_hits = [r for r in matched_rows if to_int(r["actual_finish"]) == 1 and (to_float(r["actual_odds"]) or 0) >= 100]
    big_hits.sort(key=lambda r: -(to_float(r["actual_odds"]) or 0))
    if big_hits:
        md.append("| 日付 | 場 | R | type | 馬名 | 単勝 | 想定人気 |")
        md.append("|---|---|---|---|---|---:|---:|")
        for r in big_hits[:30]:
            md.append(f"| {r['race_date']} | {r['course']} | {r['race']}R | {r['type']} | {r['actual_name'] or r['name']} | {r['actual_odds']} | {r['popularity_est']} |")
    md.append("")

    md.append("## 6. ◎ 単勝高オッズ的中（30倍以上）")
    md.append("")
    big30 = [r for r in matched_rows if r["type"] == "◎" and to_int(r["actual_finish"]) == 1 and (to_float(r["actual_odds"]) or 0) >= 30]
    big30.sort(key=lambda r: -(to_float(r["actual_odds"]) or 0))
    if big30:
        md.append("| 日付 | 場 | R | 馬名 | 単勝 | 想定人気→実人気 |")
        md.append("|---|---|---|---|---:|---|")
        for r in big30[:50]:
            md.append(f"| {r['race_date']} | {r['course']} | {r['race']}R | {r['actual_name'] or r['name']} | {r['actual_odds']} | {r['popularity_est']}→{r['actual_pop']} |")
    md.append("")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"Written: {OUT}  ({len(md)} lines)")

if __name__ == "__main__":
    main()
