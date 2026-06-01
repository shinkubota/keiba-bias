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

    # 5マーク使うのでrecommend_sundayと同じロジックを呼ぶ
    import importlib
    rs_spec = importlib.util.spec_from_file_location("rs", ROOT/"scripts"/"recommend_sunday.py")
    rs = importlib.util.module_from_spec(rs_spec); rs_spec.loader.exec_module(rs)

    n = win = plc = top3in = 0
    big_hits = []          # 7人気以下の本命的中
    hits = []              # 本命1着レース
    place_hits = []        # 推奨上位5頭のうち2-3着に絡んだ馬
    miss_races = []        # 推奨3頭全滅レース(取りこぼし詳細)
    miss_by = {"血統":{}, "クラス":{}, "間隔":{}, "脚質":{}, "場":{}, "馬場":{}, "天候":{}}
    total_by = {k:{} for k in miss_by}
    dark_horse_hits = []   # 8人気以下が3着内に飛び込み、推奨で何位だったか
    pop_dist = [0]*20
    cross_picks = []       # ✕押え馬の結果集計
    MARKS = ["◎","○","▲","△","✕"]
    for race in shutuba:
        r = results.get(race["race_id"], {})
        if not r.get("horses"): continue
        a = az.analyze_race(race, db)
        if a.get("warn"): continue
        # 推奨ランク辞書(全頭)
        rank_by_um = {}
        for idx, h in enumerate(a["horses"], start=1):
            try: rank_by_um[int(h["horse"]["umaban"])] = idx
            except: pass
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

        # ✕押え馬の追跡: recommend_sundayの5頭印を呼んで✕馬の結果を記録
        try:
            picks5, _watch, _a2 = rs.pick(race, db)
            cross = next((p for p in picks5 if p["mark"] == "✕"), None) if picks5 else None
        except Exception:
            cross = None
        if cross:
            try: um_c = int(cross["row"]["horse"]["umaban"])
            except: um_c = None
            cres = res_by_um.get(um_c) if um_c else None
            if cres:
                cross_picks.append({
                    "track": race["track"], "race_no": race["race_no"], "race_name": race["race_name"],
                    "umaban": um_c, "name": cross["row"]["horse"]["name"],
                    "pop": cres.get("popularity"), "odds": cres.get("odds"),
                    "finish": cres["finish"], "bias": cross["row"].get("bias", 0),
                    "reasons": cross["row"].get("reasons", [])[:4],
                })

        # 大穴3着内ヒットの集計（推奨ランク＋発火した因子も記録 — 「なぜ拾えたか」分析用）
        for h_res in r["horses"][:3]:
            ph = h_res.get("popularity")
            if ph and ph >= 8:
                try: u_int = int(h_res["umaban"])
                except: u_int = None
                rk = rank_by_um.get(u_int) if u_int else None
                # 該当馬のreasons取得
                reasons = []
                bias_pt = 0
                for hh in a["horses"]:
                    try:
                        if int(hh["horse"]["umaban"]) == u_int:
                            reasons = hh.get("reasons", [])[:5]
                            bias_pt = hh.get("bias", 0)
                            break
                    except: pass
                dark_horse_hits.append({
                    "track": race["track"], "race_no": race["race_no"],
                    "race_name": race["race_name"],
                    "finish": h_res["finish"], "name": h_res["name"],
                    "pop": ph, "odds": h_res.get("odds"), "rank": rk,
                    "reasons": reasons, "bias": bias_pt,
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

    # 大穴3着内ヒットの推奨ランク分布
    if dark_horse_hits:
        block += ["", f"### 🐎 大穴3着内ヒット {len(dark_horse_hits)}件 (8人気以下→3着内)",
                  "推奨ランク別の分布で「警戒馬セクション(6-12位)」の有効性を検証",
                  "", "| レース | 着 | 馬 | 人気・単 | 推奨ランク |",
                  "|---|--:|---|---|--:|"]
        bucket = {"印内(1-5位)":0, "警戒馬(6-12位)":0, "圏外(13位以下)":0, "不明":0}
        for x in dark_horse_hits:
            rk = x["rank"]
            if rk is None: bk = "不明"
            elif rk <= 5: bk = "印内(1-5位)"
            elif rk <= 12: bk = "警戒馬(6-12位)"
            else: bk = "圏外(13位以下)"
            bucket[bk] += 1
            rk_s = f"{rk}位" if rk else "?"
            block.append(f"| {x['track']}{x['race_no']}R {x['race_name']} | {x['finish']} | {x['name']} | {x['pop']}人気・{x['odds']}倍 | {rk_s} |")
        block += ["", "**推奨ランク分布**:"]
        for k, v in bucket.items():
            block.append(f"- {k}: {v}件")
        total = sum(bucket.values())
        if total > 0:
            watch_ratio = bucket["警戒馬(6-12位)"] / total
            if watch_ratio >= 0.5:
                block.append(f"> ✅ 警戒馬ゾーン(6-12位)が大穴ヒットの{watch_ratio*100:.0f}%を占める — 「人気軸◎＋警戒馬ワイド」戦略が有効")
            elif bucket["圏外(13位以下)"] > bucket["警戒馬(6-12位)"]:
                block.append(f"> ⚠ 大穴の{bucket['圏外(13位以下)']/total*100:.0f}%が推奨13位以下＝バイアス検出から漏れている。閾値見直し検討")

        # 「なぜ拾えたか」因子別分析
        block += ["", "#### なぜ拾えたか — 因子別ヒット数", "推奨6位以内に入った大穴馬の発火因子（理由）を集計："]
        factor_count = {}
        sample_horses = {}
        for x in dark_horse_hits:
            if x["rank"] is None or x["rank"] > 12: continue   # 圏外は除外
            for rr in x["reasons"]:
                key = rr.split("(")[0].split("=")[0].split("該当")[0].strip()
                factor_count[key] = factor_count.get(key, 0) + 1
                sample_horses.setdefault(key, []).append(f"{x['name']}({x['pop']}人気)")
        if factor_count:
            block += ["", "| 因子 | 発火数 | 拾えた馬例 |", "|---|--:|---|"]
            for k, v in sorted(factor_count.items(), key=lambda x:-x[1]):
                if v < 2: continue
                samples = "／".join(sample_horses[k][:3])
                block.append(f"| {k} | {v} | {samples} |")
            block.append("")
            block.append("> 💡 この因子群が「人気薄を拾う鍵」になっている。配点強化候補。")

    # ✕押え馬の結果総括
    if cross_picks:
        cross_hit = [c for c in cross_picks if c["finish"] <= 3]
        cross_close = [c for c in cross_picks if 4 <= c["finish"] <= 6]
        block += ["", f"### ✕押え馬の結果 {len(cross_picks)}件中 {len(cross_hit)}件3着内",
                  "「6-12位の警戒馬群から✕として1頭だけ選んだ馬」がどう走ったか／**なぜその1頭を選べたか**を検証",
                  ""]
        if cross_hit:
            block.append("**✓ 3着内ヒット**")
            block.append("| レース | 馬 | 人気・単 | 着 | bias | 選定理由(発火因子) |")
            block.append("|---|---|---|--:|--:|---|")
            for c in cross_hit:
                rs_txt = " ／ ".join(c["reasons"])
                block.append(f"| {c['track']}{c['race_no']}R {c['race_name']} | {c['name']} | {c['pop']}人気・{c['odds']}倍 | {c['finish']} | {c['bias']} | {rs_txt} |")
            block.append("")
        if cross_close:
            block.append(f"**△ 4-6着で惜しかった**: {len(cross_close)}件 ({', '.join(c['name']+'('+str(c['finish'])+'着)' for c in cross_close)})")
            block.append("")
        # ✕選定の根拠分析: bias点とヒット率の相関
        hi_bias = [c for c in cross_picks if c["bias"] >= 10]
        if hi_bias:
            hit_rate_hi = sum(1 for c in hi_bias if c["finish"] <= 3) / len(hi_bias)
            block.append(f"- bias≥10の✕（強推奨）: {len(hi_bias)}件、3着内率{hit_rate_hi*100:.0f}%")
        lo_bias = [c for c in cross_picks if c["bias"] < 10]
        if lo_bias:
            hit_rate_lo = sum(1 for c in lo_bias if c["finish"] <= 3) / len(lo_bias)
            block.append(f"- bias<10の✕（弱推奨）: {len(lo_bias)}件、3着内率{hit_rate_lo*100:.0f}%")
        if hi_bias and lo_bias and hit_rate_hi > hit_rate_lo * 1.5:
            block.append(f"> 💡 **bias≥10の✕は信頼度が高い**（{hit_rate_hi*100:.0f}% vs {hit_rate_lo*100:.0f}%）。馬券厚めに")

        # 圏外で外した馬の特徴
        outside = [x for x in dark_horse_hits if x["rank"] and x["rank"] > 12]
        if outside:
            block += ["", "#### 圏外(13位以下)で逃した大穴 — 改善余地",
                      "推奨13位以下の大穴3着内ヒット。バイアス検出が届かなかった例:",
                      "", "| 馬 | 人気 | 推奨ランク | bias | 主な理由 |", "|---|--:|--:|--:|---|"]
            for x in outside:
                rs = "／".join(x["reasons"][:3]) if x["reasons"] else "—"
                block.append(f"| {x['name']} | {x['pop']} | {x['rank']}位 | {x['bias']} | {rs} |")

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
