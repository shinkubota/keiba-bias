#!/usr/bin/env python3
"""3-5頭幅の推奨を出力。
- 軸◎: 現行(能力×バイアス)1位
- 対抗○: 現行2位
- 単穴▲: 現行3位
- 連下△: 現行4位 OR バイアス単独上位（能力◎と被らない場合に追加）
- 押え✕: バイアス上位で能力中位以下の伏兵（土曜の鳳雛Sタイプを拾う）
"""
import json, argparse, pathlib, importlib.util, datetime, html

ROOT = pathlib.Path(__file__).parent.parent
SITE = ROOT.parent/"docs"
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

WD = ["月","火","水","木","金","土","日"]
MARKS = ["◎","○","▲","△","✕"]

def pick(race, db):
    a = az.analyze_race(race, db)
    if a.get("warn"): return None, a
    rows = a["horses"]                                       # 既にscore順
    by_bias = sorted(rows, key=lambda r: -r.get("bias",0))
    by_ability = sorted(rows, key=lambda r: -(r.get("ability_eff") or 0))

    picks = []
    used = set()
    def add(r, mark, why):
        uid = r["horse"].get("horse_id") or r["horse"]["umaban"]
        if uid in used: return
        used.add(uid); picks.append({"mark":mark,"row":r,"why":why})

    # ◎ ○ ▲: 現行上位3
    for i,r in enumerate(rows[:3]):
        if r["score"]<=0: break
        add(r, MARKS[i], "総合")
    # △: バイアス単独で食い込む馬（能力◎▲と違うバイアス上位を1頭）
    for r in by_bias:
        if r["bias"] < 5: break
        uid = r["horse"].get("horse_id") or r["horse"]["umaban"]
        if uid in used: continue
        add(r, "△", f"バイアス特化(bias{r['bias']})")
        break
    # ✕: バイアス上位 かつ 能力中位以下＝伏兵(土曜鳳雛Sタイプ)
    abil_sorted = sorted([(r.get("ability_eff") or 0) for r in rows], reverse=True)
    med = abil_sorted[len(abil_sorted)//2] if abil_sorted else 0
    for r in by_bias:
        if r["bias"] < 6: break
        uid = r["horse"].get("horse_id") or r["horse"]["umaban"]
        if uid in used: continue
        if (r.get("ability_eff") or 0) > med: continue
        add(r, "✕", f"伏兵(bias{r['bias']}・能力中位以下)")
        break
    # 4頭以下なら現行4位を△で補完
    if len(picks) < 4 and len(rows) >= 4 and rows[3]["score"] > 0:
        add(rows[3], "△", "総合4位")

    return picks[:5], a

def fmt_row(p):
    h = p["row"]["horse"]
    abil = p["row"].get("ability"); abil_s = f"{abil:.0f}" if abil is not None else "—"
    reasons = " ／ ".join(p["row"]["reasons"][:4])
    return (f"| {p['mark']} | **{h['umaban']}** | {h['name']} | {h.get('sex_age','')} | "
            f"{h.get('jockey','')} | {h.get('jockey_weight','')} | {abil_s} | "
            f"{p['row'].get('bias',0)} | **{p['row']['score']}** | {reasons} |")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date")
    ap.add_argument("--track", default="東京,京都"); args = ap.parse_args()
    tracks = set(args.track.split(","))
    d = datetime.date(int(args.date[:4]),int(args.date[4:6]),int(args.date[6:8]))
    data = json.loads((ROOT/"data"/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    db = az.load_horses(args.date)

    L = [f"# 🐎 {d.year}/{d.month}/{d.day}({WD[d.weekday()]}) 推奨（3-5頭・幅広版）", ""]
    L.append("> ◎総合1位 ○2位 ▲3位 △バイアス特化or総合4位 ✕能力中位の伏兵(土曜鳳雛Sタイプ)")
    L.append("")
    for race in data:
        if race["track"] not in tracks: continue
        if len(race["horses"]) < 2: continue
        picks, a = pick(race, db)
        title = f"{race['track']}{race['race_no']}R {race['surface']}{race['distance']}m {race['race_name']}"
        if not picks:
            L.append(f"### {title}")
            L.append(f"_対象外（{a.get('warn','')}）_"); L.append(""); continue
        L.append(f"### {title}（{len(race['horses'])}頭）")
        L.append(f"狙い: {a['headline'].split('（')[0]}")
        L.append("")
        L.append("| 印 | 馬番 | 馬名 | 性齢 | 騎手 | 斤量 | 能力 | bias | 評価 | 根拠 |")
        L.append("|:--:|:--:|--|:--:|--|:--:|--:|--:|--:|--|")
        for p in picks: L.append(fmt_row(p))
        L.append("")
    out = "\n".join(L)
    (ROOT/"data"/f"recommend_wide_{args.date}.md").write_text(out, encoding="utf-8")
    print(out)

if __name__ == "__main__":
    main()
