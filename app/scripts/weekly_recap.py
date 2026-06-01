#!/usr/bin/env python3
"""月曜朝の週次まとめ。前週末(土+日)の通算成績をretrospective.mdに追記。
"""
import json, pathlib, datetime, importlib.util, sys

ROOT = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

def last_sat_sun():
    """実行日の直近過去土日YYYYMMDDのタプルを返す"""
    today = datetime.date.today()
    # 月曜なら2,1日前=土日 / 火なら3,2日前など
    days_since_sun = today.weekday() + 1  # 月=0なので+1で日(=昨日)
    sun = today - datetime.timedelta(days=days_since_sun)
    sat = sun - datetime.timedelta(days=1)
    return sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")

def aggregate(dates):
    agg = {"n":0, "win":0, "plc":0, "top3":0, "n3":0}
    hits = []; dark_top12 = 0; dark_total = 0
    for d in dates:
        sh_p = ROOT/"data"/f"shutuba_{d}.json"
        res_p = ROOT/"data"/f"results_{d}.json"
        if not (sh_p.exists() and res_p.exists()): continue
        sh = json.loads(sh_p.read_text(encoding="utf-8"))
        res = {r["race_id"]: r for r in json.loads(res_p.read_text(encoding="utf-8"))}
        db = az.load_horses(d)
        for race in sh:
            r = res.get(race["race_id"], {})
            if not r.get("horses"): continue
            a = az.analyze_race(race, db)
            if a.get("warn"): continue
            picks = a["horses"][:3]
            if not picks: continue
            agg["n"] += 1; agg["n3"] += 3
            top3um = {h["umaban"] for h in r["horses"][:3]}
            winner = r["horses"][0]["umaban"]
            try: top1 = int(picks[0]["horse"]["umaban"])
            except: continue
            if top1 == winner:
                agg["win"] += 1
                wh = r["horses"][0]
                hits.append((d, race["track"], race["race_no"], race["race_name"],
                             wh["name"], wh.get("popularity"), wh.get("odds")))
            in_t3 = False
            for p in picks:
                try:
                    if int(p["horse"]["umaban"]) in top3um:
                        agg["top3"] += 1; in_t3 = True
                except: pass
            if in_t3: agg["plc"] += 1
            # 大穴3着内の警戒馬ゾーン捕捉
            rank_by = {int(h["horse"]["umaban"]): i+1 for i, h in enumerate(a["horses"])
                       if h["horse"]["umaban"].isdigit()}
            for hr in r["horses"][:3]:
                ph = hr.get("popularity")
                if ph and ph >= 8:
                    dark_total += 1
                    rk = rank_by.get(hr["umaban"])
                    if rk and 6 <= rk <= 12: dark_top12 += 1
    return agg, hits, dark_top12, dark_total

def main():
    if len(sys.argv) >= 3:
        sat, sun = sys.argv[1], sys.argv[2]
    else:
        sat, sun = last_sat_sun()
    print(f"対象: {sat} + {sun}", file=sys.stderr)
    agg, hits, dt12, dtot = aggregate([sat, sun])
    if agg["n"] == 0:
        print("対象期間に有効レースなし", file=sys.stderr); return

    today = datetime.date.today()
    header = f"## 📅 週次まとめ {sat[4:6]}/{sat[6:]}-{sun[4:6]}/{sun[6:]} ({agg['n']}R, 集計日{today.isoformat()})"

    block = ["", "---", "", header, "",
             f"- 単勝率: **{agg['win']/agg['n']*100:.0f}%** ({agg['win']}/{agg['n']})",
             f"- 複勝率(◎○▲のいずれか3着内): **{agg['plc']/agg['n']*100:.0f}%** ({agg['plc']}/{agg['n']})",
             f"- 上位3頭内的中率: **{agg['top3']/agg['n3']*100:.0f}%** ({agg['top3']}/{agg['n3']})",
             ""]
    if dtot:
        block.append(f"- 大穴(8人気以下)3着内: {dtot}件 のうち警戒馬ゾーン(6-12位)で **{dt12}件捕捉** ({dt12/dtot*100:.0f}%)")
        block.append("")
    # 中穴・大穴本命的中
    middle = [x for x in hits if x[5] and 4 <= x[5] <= 7]
    big = [x for x in hits if x[5] and x[5] >= 8]
    if middle or big:
        block.append("### 配当を稼いだ本命1着")
        for x in middle + big:
            block.append(f"- {x[0][4:]} {x[1]}{x[2]}R {x[3]}: {x[4]} ({x[5]}人気・{x[6]}倍)")
        block.append("")
    block.append("<!-- ↑ launchd weekly-recap が月曜朝に自動追記 -->")
    block.append("")

    rp = ROOT/"data"/"review"/"retrospective.md"
    text = rp.read_text(encoding="utf-8") if rp.exists() else "# 振り返り\n\n"
    if header in text:
        print(f"already appended: {header}", file=sys.stderr); return
    marker = "<!-- 次週はここに追記 -->"
    new_block = "\n".join(block).rstrip() + "\n"
    if marker in text:
        text = text.replace(marker, new_block + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + new_block
    rp.write_text(text, encoding="utf-8")
    print(f"appended: {header}", file=sys.stderr)

if __name__ == "__main__":
    main()
