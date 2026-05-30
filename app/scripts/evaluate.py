#!/usr/bin/env python3
"""推奨と実結果を突き合わせて的中率を集計。
3パターン比較:
  - ability_only : 能力スコアのみで本命
  - bias_only    : バイアス点のみで本命
  - combined     : 既存(能力×バイアス補正) ＝ 現行analyze.py
出力: 単勝(1着的中率) / 複勝(3着以内率) / 平均人気乖離 / レース別内訳
"""
import json, sys, pathlib, importlib.util, argparse

ROOT = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date"); args=ap.parse_args()
    shutuba = json.loads((ROOT/"data"/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    results = {r["race_id"]: r for r in json.loads((ROOT/"data"/f"results_{args.date}.json").read_text(encoding="utf-8"))}
    db = az.load_horses(args.date)

    methods = ["ability_only", "bias_only", "combined"]
    stats = {m: {"win":0,"place":0,"n":0,"top3_in":0,"top3_n":0} for m in methods}
    per_race = []

    for race in shutuba:
        res = results.get(race["race_id"], {})
        if not res.get("horses"): continue
        analyzed = az.analyze_race(race, db)
        if analyzed.get("warn"): continue
        rows = analyzed["horses"]
        ranks = {
            "ability_only": sorted(rows, key=lambda r: -(r.get("ability_eff") or 0)),
            "bias_only":    sorted(rows, key=lambda r: -r.get("bias",0)),
            "combined":     rows,  # 既にscoreでソート済
        }
        # 実1着・3着以内馬番
        winner_um = res["horses"][0]["umaban"] if res["horses"] else None
        top3_um = {h["umaban"] for h in res["horses"][:3]}
        row = {"race": f"{race['track']}{race['race_no']}R", "name": race["race_name"],
               "winner": f"{winner_um}番 {res['horses'][0]['name']}" if res["horses"] else "—"}
        for m in methods:
            stats[m]["n"] += 1
            stats[m]["top3_n"] += 3
            picks = ranks[m][:3]
            top_um = picks[0]["horse"]["umaban"] if picks else None
            try:
                hit_win = (int(top_um) == winner_um)
            except: hit_win = False
            stats[m]["win"] += int(hit_win)
            place_hit = False
            for p in picks[:3]:
                try:
                    if int(p["horse"]["umaban"]) in top3_um:
                        stats[m]["top3_in"] += 1
                        place_hit = True
                except: pass
            stats[m]["place"] += int(place_hit)
            row[m] = f"◎{top_um}" + ("✓" if hit_win else "")
        per_race.append(row)

    # 出力
    out=[]
    out.append(f"# 答え合わせ {args.date}（対象 {stats['combined']['n']}レース）")
    out.append("")
    out.append("## 集計（◎単勝率 / トップ3内に複勝該当馬がいた率 / トップ3各馬の的中率）")
    out.append("| 手法 | 単勝率(◎=1着) | 複勝率(◎▲△に3着内) | 上位3頭内的中率 |")
    out.append("|--|--:|--:|--:|")
    for m in methods:
        s = stats[m]
        win = s["win"]/s["n"]*100 if s["n"] else 0
        plc = s["place"]/s["n"]*100 if s["n"] else 0
        ind = s["top3_in"]/s["top3_n"]*100 if s["top3_n"] else 0
        label = {"ability_only":"能力スコアのみ","bias_only":"バイアスのみ","combined":"能力×バイアス(現行)"}[m]
        out.append(f"| {label} | {win:.0f}% ({s['win']}/{s['n']}) | {plc:.0f}% ({s['place']}/{s['n']}) | {ind:.0f}% ({s['top3_in']}/{s['top3_n']}) |")
    out.append("")
    out.append("## レース別本命比較")
    out.append("| レース | 1着実馬 | 能力◎ | バイアス◎ | 現行◎ |")
    out.append("|--|--|--|--|--|")
    for r in per_race:
        out.append(f"| {r['race']} {r['name']} | {r['winner']} | {r['ability_only']} | {r['bias_only']} | {r['combined']} |")
    text="\n".join(out)
    (ROOT/"data"/f"evaluation_{args.date}.md").write_text(text, encoding="utf-8")
    print(text)

if __name__ == "__main__":
    main()
