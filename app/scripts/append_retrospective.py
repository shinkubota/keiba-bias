#!/usr/bin/env python3
"""指定日の評価結果を data/review/retrospective.md に追記する。
重複追記を防ぐため、見出し `## YYYY-MM-DD` の存在チェックを行う。
"""
import sys, json, pathlib, datetime, importlib.util

ROOT = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

def main():
    date_str = sys.argv[1]
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    wd = "月火水木金土日"[d.weekday()]
    header = f"## {d.year}-{d.month:02d}-{d.day:02d}({wd})  v0.9 weekly run"

    rp = ROOT/"data"/"review"/"retrospective.md"
    text = rp.read_text(encoding="utf-8") if rp.exists() else "# 競馬予想 振り返り\n\n"
    if header in text:
        print(f"already appended: {header}"); return

    sh_p = ROOT/"data"/f"shutuba_{date_str}.json"
    res_p = ROOT/"data"/f"results_{date_str}.json"
    if not (sh_p.exists() and res_p.exists()):
        print(f"missing data: {sh_p.exists()=} {res_p.exists()=}"); return
    shutuba = json.loads(sh_p.read_text(encoding="utf-8"))
    results = {r["race_id"]: r for r in json.loads(res_p.read_text(encoding="utf-8"))}
    db = az.load_horses(date_str)

    n = win = plc = top3in = 0
    big_hits = []          # 7人気以下の本命的中
    hits = []              # 本命1着レース
    place_hits = []        # 推奨上位5頭のうち2-3着に絡んだ馬
    pop_dist = [0]*20
    MARKS = ["◎","○","▲","△","✕"]
    for race in shutuba:
        r = results.get(race["race_id"], {})
        if not r.get("horses"): continue
        a = az.analyze_race(race, db)
        if a.get("warn"): continue
        top3um = {h["umaban"] for h in r["horses"][:3]}
        # 順位→馬データ参照
        finish_by_um = {h["umaban"]: h["finish"] for h in r["horses"]}
        res_by_um = {h["umaban"]: h for h in r["horses"]}
        winner = r["horses"][0]["umaban"]
        picks = a["horses"][:5]   # 5頭まで参照
        if not picks: continue
        n += 1
        try: top1_um = int(picks[0]["horse"]["umaban"])
        except: continue
        top1_res = res_by_um.get(top1_um, {})
        pop = top1_res.get("popularity")
        odds = top1_res.get("odds")
        if pop and 1 <= pop <= 15: pop_dist[pop] += 1
        if top1_um == winner:
            win += 1
            hits.append((race["track"], race["race_no"], race["race_name"],
                         picks[0]["horse"]["name"], pop, odds))
            if pop and pop >= 7:
                big_hits.append((race["track"], race["race_no"], race["race_name"],
                                 picks[0]["horse"]["name"], pop, odds))
        # 複勝圏絡み(2-3着)で推奨に入っていた馬を収集
        in_t3 = False
        for idx, p in enumerate(picks[:3]):
            try:
                u = int(p["horse"]["umaban"])
            except: continue
            if u in top3um:
                top3in += 1; in_t3 = True
                fin = finish_by_um.get(u)
                # 1着は hits に既出。2-3着のみ別途記録
                if fin in (2, 3):
                    pr = res_by_um.get(u, {})
                    place_hits.append((race["track"], race["race_no"], race["race_name"],
                                       MARKS[idx], p["horse"]["name"], fin,
                                       pr.get("popularity"), pr.get("odds")))
        if in_t3: plc += 1

    if n == 0:
        print("no valid races"); return

    block = [f"\n---\n\n{header}\n",
             f"### 成績（{n}R）",
             f"- 単勝率: {win/n*100:.0f}% ({win}/{n})",
             f"- 複勝率(◎○▲): {plc/n*100:.0f}% ({plc}/{n})",
             f"- 上位3頭内的中率: {top3in/(n*3)*100:.0f}% ({top3in}/{n*3})",
             "",
             "### 本命人気分布",
             "| 人気 | 本数 |", "|---:|---:|"]
    for i in range(1, 16):
        if pop_dist[i]: block.append(f"| {i} | {pop_dist[i]} |")
    block += ["", f"### 本命的中 ◎=1着 {len(hits)}本",
              "| レース | 馬 | 人気 | 単 |", "|---|---|---:|---:|"]
    for x in hits:
        block.append(f"| {x[0]}{x[1]}R {x[2]} | {x[3]} | {x[4]} | {x[5]} |")
    if place_hits:
        block += ["", f"### 複勝圏絡み(2-3着) {len(place_hits)}件 ※印付き馬のみ",
                  "| レース | 印 | 馬 | 着 | 人気 | 単 |", "|---|:--:|---|--:|--:|--:|"]
        for x in place_hits:
            block.append(f"| {x[0]}{x[1]}R {x[2]} | {x[3]} | {x[4]} | {x[5]} | {x[6]} | {x[7]} |")
    if big_hits:
        block += ["", "### 大穴本命的中(7人気以下)"]
        for x in big_hits:
            block.append(f"- {x[0]}{x[1]}R {x[2]}: {x[3]} ({x[4]}人気・単{x[5]}倍)")
    # マーカーは既存テキスト側に必ず1つ残す
    marker = "<!-- 次週はここに追記 -->"
    block_str = "\n".join(block).strip() + "\n"
    if marker in text:
        text = text.replace(marker, block_str + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + block_str + "\n" + marker + "\n"
    rp.write_text(text, encoding="utf-8")
    print(f"appended: {header}")

if __name__ == "__main__":
    main()
