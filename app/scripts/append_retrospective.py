#!/usr/bin/env python3
"""指定日の評価結果を data/review/retrospective.md に追記する。
重複追記を防ぐため、見出し `## YYYY-MM-DD` の存在チェックを行う。
"""
import sys, json, re, pathlib, datetime, importlib.util

ROOT = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

def class_label(name):
    if "G1" in name or "GⅠ" in name: return "G1"
    if "G2" in name or "GⅡ" in name: return "G2"
    if "G3" in name or "GⅢ" in name: return "G3"
    if "(L)" in name or "S)" in name or "ステークス" in name: return "OP/L"
    if "3勝" in name: return "3勝"
    if "2勝" in name: return "2勝"
    if "1勝" in name: return "1勝"
    if "未勝利" in name: return "未勝利"
    if "新馬" in name: return "新馬"
    return "他"

def interval_label(prev_date_str, today_str):
    if not prev_date_str: return "不明"
    try:
        y,m,d = prev_date_str.split("/")
        prev = datetime.date(int(y), int(m), int(d))
        td = datetime.date(int(today_str[:4]), int(today_str[4:6]), int(today_str[6:8]))
        days = (td - prev).days
        if days <= 14: return "連闘〜2週"
        if days <= 28: return "3-4週"
        if days <= 70: return "5-10週"
        if days <= 180: return "11週-半年"
        return "半年超"
    except Exception:
        return "不明"

def jp_sire(sire):
    m = re.match(r"^([぀-ヿ一-鿿・ー]+)", sire or "")
    return m.group(1) if m else (sire or "?")

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
    miss_races = []        # 推奨3頭全滅レース(取りこぼし詳細)
    miss_by = {"血統":{}, "クラス":{}, "間隔":{}, "脚質":{}, "場":{}, "馬場":{}, "天候":{}}
    total_by = {k:{} for k in miss_by}
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

        # 取りこぼし分析: ◎の属性で集計
        ped = picks[0].get("pedigree", {})
        sire_k = jp_sire(ped.get("sire"))
        hd = db.get(picks[0]["horse"]["horse_id"], {})
        rec = hd.get("recent", [])
        intvl_k = interval_label(rec[0].get("date") if rec else None, date_str)
        style_k = az.horse_pace_style(rec) or "?"
        keys = {
            "血統": sire_k, "クラス": class_label(race["race_name"]),
            "間隔": intvl_k, "脚質": style_k, "場": race["track"],
            "馬場": race.get("baba") or "?", "天候": race.get("weather") or "?",
        }
        for axis, k in keys.items():
            total_by[axis][k] = total_by[axis].get(k, 0) + 1
            if not in_t3:
                miss_by[axis][k] = miss_by[axis].get(k, 0) + 1
        if not in_t3:
            winner_h = r["horses"][0]
            miss_races.append({
                "track": race["track"], "race_no": race["race_no"], "race_name": race["race_name"],
                "top1": picks[0]["horse"]["name"], "top1_pop": pop,
                "winner_um": winner, "winner_name": winner_h["name"],
                "winner_pop": winner_h.get("popularity"), "winner_odds": winner_h.get("odds"),
                "sire": sire_k, "cls": keys["クラス"], "intvl": intvl_k, "style": style_k,
                "baba": keys["馬場"], "weather": keys["天候"],
            })

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

    # 取りこぼし分析
    if miss_races:
        block += ["", f"### ❌ 取りこぼし {len(miss_races)}件（推奨上位3頭が全滅）",
                  "| レース | 本命 → 1着馬(人気・単) | 父 | クラス | 間隔 | 脚質 | 馬場/天候 |",
                  "|---|---|---|---|---|---|---|"]
        for m in miss_races:
            wpop = f"{m['winner_pop']}人気" if m['winner_pop'] else "?"
            wod = f"{m['winner_odds']}" if m['winner_odds'] else "?"
            block.append(f"| {m['track']}{m['race_no']}R {m['race_name']} | "
                         f"{m['top1']} → {m['winner_name']}({wpop}・{wod}倍) | "
                         f"{m['sire']} | {m['cls']} | {m['intvl']} | {m['style']} | "
                         f"{m['baba']}/{m['weather']} |")
        # 軸別の取りこぼし率
        block += ["", "#### 取りこぼし率の軸別内訳（取りこぼし数/全レース数, 出現2以上）"]
        for axis in ["血統","クラス","間隔","脚質","場","馬場","天候"]:
            rows = []
            for k, t in sorted(total_by[axis].items(), key=lambda x:-x[1]):
                if t < 2: continue
                miss = miss_by[axis].get(k, 0)
                if miss == 0 and t < 3: continue   # 取りこぼしも出現も少ない値は省略
                rate = miss/t*100 if t else 0
                marker = " ⚠" if rate >= 30 and miss >= 2 else ""
                rows.append(f"  - {k}: {miss}/{t} ({rate:.0f}%){marker}")
            if rows:
                block.append(f"**{axis}**")
                block += rows
                block.append("")
        block.append("> ⚠ = 取りこぼし率30%以上かつ2件以上(改善優先候補)")
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
