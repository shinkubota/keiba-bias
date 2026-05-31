#!/usr/bin/env python3
"""analyze.py の Cal補正有/無 で上位3頭の的中率を比較するバックテスト。

入力: 指定日(複数) の shutuba_*.json / horses_*.json
出力: 標準出力サマリ + notes/backtest_calimero.md

結果(着順)は netkeiba から都度パース(同一実装を match_calimero_results.py から流用)。
"""
from __future__ import annotations
import sys, json, csv, pathlib, importlib
import argparse
import importlib.util

ROOT = pathlib.Path(__file__).parent.parent.parent
APP = ROOT/"app"
sys.path.insert(0, str(APP/"scripts"))
import analyze as A
import match_calimero_results as M  # for parse_result

def to_int(s):
    try: return int(s)
    except: return None

def run_for_date(date_str, use_cal):
    shutuba = json.loads((APP/"data"/f"shutuba_{date_str}.json").read_text(encoding="utf-8"))
    horses_db = A.load_horses(date_str)
    # monkeypatch
    orig = A.calimero_bonus
    if not use_cal:
        A.calimero_bonus = lambda *a, **kw: (0, [])
    picks_top3 = []
    try:
        for race in shutuba:
            if len(race["horses"]) < 2: continue
            a = A.analyze_race(race, horses_db)
            if a.get("warn"): continue
            top3 = a["horses"][:3]
            for rank, row in enumerate(top3, 1):
                h = row["horse"]
                picks_top3.append({
                    "date": date_str, "race_id": race["race_id"],
                    "track": race["track"], "race_no": race["race_no"],
                    "rank": rank, "umaban": to_int(h.get("umaban")),
                    "name": h["name"], "score": row["score"],
                })
    finally:
        A.calimero_bonus = orig
    return picks_top3

def get_results(race_id, cache={}):
    if race_id not in cache:
        try:
            cache[race_id] = M.parse_result(race_id)
        except Exception:
            cache[race_id] = {"horses": []}
    return cache[race_id]

def attach_results(picks):
    rcache = {}
    for p in picks:
        res = get_results(p["race_id"], rcache)
        target = next((h for h in res["horses"] if h["umaban"] == p["umaban"]), None)
        p["finish"] = target["finish"] if target else None
        p["odds"] = target["odds"] if target else None
        p["pop"] = target["popularity"] if target else None
    return picks

def summarize(picks, label):
    n = len(picks)
    matched = [p for p in picks if p["finish"] is not None]
    win = sum(1 for p in matched if p["finish"] == 1)
    ren = sum(1 for p in matched if p["finish"] <= 2)
    plc = sum(1 for p in matched if p["finish"] <= 3)
    odds_sum = sum((p["odds"] or 0) for p in matched if p["finish"] == 1)
    roi = (odds_sum / n * 100) if n else 0
    # per-rank
    by_rank = {1: [], 2: [], 3: []}
    for p in matched: by_rank[p["rank"]].append(p)
    rank_stats = {}
    for r, sub in by_rank.items():
        w = sum(1 for x in sub if x["finish"] == 1)
        pl = sum(1 for x in sub if x["finish"] <= 3)
        rank_stats[r] = {"n": len(sub), "win": w, "plc": pl}
    return {
        "label": label, "n": n, "matched": len(matched),
        "win": win, "win_pct": (win/len(matched)*100) if matched else 0,
        "ren": ren, "ren_pct": (ren/len(matched)*100) if matched else 0,
        "plc": plc, "plc_pct": (plc/len(matched)*100) if matched else 0,
        "roi_tan": roi, "by_rank": rank_stats,
    }

def fmt_block(s):
    out = [f"### {s['label']}", "",
           f"- n={s['n']}  matched={s['matched']}",
           f"- 単勝 {s['win']} ({s['win_pct']:.1f}%) / 連対 {s['ren']} ({s['ren_pct']:.1f}%) / 複勝 {s['plc']} ({s['plc_pct']:.1f}%)",
           f"- 単回収率 {s['roi_tan']:.0f}% (全候補に均等100円)",
           "",
           "| Rank | n | 単勝 | 複勝 |",
           "|---|---:|---|---|",
    ]
    for r in (1,2,3):
        st = s["by_rank"][r]
        nn = st["n"]
        w = st["win"]; p = st["plc"]
        wp = (w/nn*100) if nn else 0
        pp = (p/nn*100) if nn else 0
        out.append(f"| {r}位 | {nn} | {w} ({wp:.1f}%) | {p} ({pp:.1f}%) |")
    return "\n".join(out) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dates", nargs="+")
    args = ap.parse_args()
    md = ["# Cal補正バックテスト", "", "対象日: " + ", ".join(args.dates), ""]
    all_with = []; all_without = []
    for d in args.dates:
        print(f"=== {d} (Calあり) ===", file=sys.stderr)
        p_with = attach_results(run_for_date(d, use_cal=True))
        print(f"=== {d} (Calなし) ===", file=sys.stderr)
        p_no = attach_results(run_for_date(d, use_cal=False))
        all_with.extend(p_with)
        all_without.extend(p_no)
        s_with = summarize(p_with, f"{d} Calあり")
        s_no = summarize(p_no, f"{d} Calなし")
        md.append(f"## {d}")
        md.append("")
        md.append(fmt_block(s_with))
        md.append(fmt_block(s_no))
    md.append("## 合計（全日合算）")
    md.append("")
    md.append(fmt_block(summarize(all_with, "Calあり TOTAL")))
    md.append(fmt_block(summarize(all_without, "Calなし TOTAL")))
    out = ROOT/"notes"/"backtest_calimero.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print(f"\nSaved: {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
