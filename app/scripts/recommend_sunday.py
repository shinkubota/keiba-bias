#!/usr/bin/env python3
"""3-5頭幅の推奨を出力。
- 軸◎: 現行(能力×バイアス)1位
- 対抗○: 現行2位
- 単穴▲: 現行3位
- 連下△: 現行4位 OR バイアス単独上位（能力◎と被らない場合に追加）
- 押え✕: 能力中位だがバイアス特化＝穴の一発候補
"""
import json, argparse, pathlib, importlib.util, datetime, html

ROOT = pathlib.Path(__file__).parent.parent
SITE = ROOT.parent/"docs"
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

WD = ["月","火","水","木","金","土","日"]
MARKS = ["◎","○","▲","△","✕"]

def pick(race, db, odds_for_race=None, baba_by_track=None, bias_boost_maiden=False):
    a = az.analyze_race(race, db, baba_by_track=baba_by_track, bias_boost_maiden=bias_boost_maiden)
    if a.get("warn"): return None, [], a
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
    # v0.11: 回収率検証(6/7)の結果、✕を廃止し4頭(◎○▲△)に絞る
    # ✕廃止理由: 警戒馬込み28点ボックスの回収率25% vs ◎○▲△6点48%
    # → 印は絞った方が回収率が上がる
    # 4頭以下なら現行4位を△で補完
    if len(picks) < 4 and len(rows) >= 4 and rows[3]["score"] > 0:
        add(rows[3], "△", "総合4位")

    # 警戒馬: 推奨6-12位の中で「警戒すべき馬」を最大2頭抽出
    # v0.15: 馬場状態で閾値を動的調整
    # - 良: bias≥6 / オッズ≥10倍 (標準)
    # - 稍以上(湿): bias≥5 / オッズ≥8倍 (大穴的中率高い→緩める)
    baba = a.get("baba", "良")
    wet_baba = baba in ("稍","稍重","重","不良")
    bias_thr = 5 if wet_baba else 6
    odds_thr = 8 if wet_baba else 10
    watch = []
    for idx, r in enumerate(rows[5:12], start=6):
        if r.get("bias", 0) < bias_thr: continue
        um = r["horse"].get("umaban")
        odds_pop = None
        if odds_for_race and um:
            o = odds_for_race.get(str(um)) or odds_for_race.get(int(um) if um.isdigit() else um)
            if o: odds_pop = (o.get("pop"), o.get("win"))
        if odds_pop:
            pop, win = odds_pop
            if win and win < odds_thr: continue
        watch.append({"rank": idx, "row": r, "odds_pop": odds_pop})
        if len(watch) >= 2: break

    return picks[:4], watch, a

def fmt_row(p):
    h = p["row"]["horse"]
    abil = p["row"].get("ability"); abil_s = f"{abil:.0f}" if abil is not None else "—"
    reasons = " ／ ".join(p["row"]["reasons"][:4])
    return (f"| {p['mark']} | **{h['umaban']}** | {h['name']} | {h.get('sex_age','')} | "
            f"{h.get('jockey','')} | {h.get('jockey_weight','')} | {abil_s} | "
            f"{p['row'].get('bias',0)} | **{p['row']['score']}** | {reasons} |")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date")
    ap.add_argument("--track", default="札幌,函館,福島,新潟,東京,中山,中京,京都,阪神,小倉")
    ap.add_argument("--baba-track", action="append", default=[],
                    help="場別馬場上書き 例: --baba-track 阪神=稍重")
    ap.add_argument("--bias-boost-maiden", action="store_true",
                    help="B案: 未勝利・新馬戦でbias倍率を2倍(0.025→0.05)")
    ap.add_argument("--out-suffix", default="",
                    help="出力ファイル名サフィックス(_A/_B等)")
    args = ap.parse_args()
    baba_by_track = {}
    for kv in args.baba_track:
        if "=" in kv:
            t, b = kv.split("=", 1)
            baba_by_track[t.strip()] = b.strip()
    tracks = set(args.track.split(","))
    d = datetime.date(int(args.date[:4]),int(args.date[4:6]),int(args.date[6:8]))
    data = json.loads((ROOT/"data"/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    db = az.load_horses(args.date)

    # オッズ辞書
    odds_path = ROOT/"data"/f"odds_{args.date}.json"
    odds_all = json.loads(odds_path.read_text(encoding="utf-8")) if odds_path.exists() else {}

    L = [f"# 🐎 {d.year}/{d.month}/{d.day}({WD[d.weekday()]}) 推奨（v0.16 包括検証ベスト戦略）", ""]
    L.append("> 📝 v0.16: 2日46R包括検証 — **3連複流しの相手は4頭がスイートスポット(ROI 100%)** / **5人気↓◎は見送り(4R全敗)**")
    L.append("> ◎総合1位 ○2位 ▲3位 △総合4位またはバイアス特化")
    L.append("> ⚠ **警戒馬** = bias≥6(湿時5) ＋ 単オッズ≥10倍(湿時8倍)の推奨6-12位馬を最大2頭")
    L.append("")
    L.append("> 💰 **動的配分戦略 v0.16** (券種・点数を最適化):")
    L.append("> ")
    L.append("> | ◎人気 | 単勝EV | **推奨配分** | 1Rコスト |")
    L.append("> |---|---:|---|---:|")
    L.append("> | 1-2人気 | 0.62❌ | **◎軸3連複4頭流し 6点** | 600円 |")
    L.append("> | **3-4人気** | **2.34**🏆 | **🔥単勝500円 + 3連複4頭流し 6点** | **1,100円** |")
    L.append("> | 5人気↓ | 0.00 | ⛔ **見送り**(2日4R全敗) | 0円 |")
    L.append(">")
    L.append("> **検証ROI 125%** (v0.14旧版84%→大幅改善)。3連複の相手は5頭よりも**4頭の方が良い**(ROI 100% vs 69%)。馬連/ワイドは ROI 12-32%で論外。")
    L.append("")
    for race in data:
        if race["track"] not in tracks: continue
        if len(race["horses"]) < 2: continue
        odds_for_race = odds_all.get(race["race_id"])
        picks, watch, a = pick(race, db, odds_for_race, baba_by_track=baba_by_track, bias_boost_maiden=args.bias_boost_maiden)
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
        if watch:
            L.append("")
            L.append("**⚠ 警戒馬(3着候補・ワイド要員)**")
            for w in watch:
                h = w["row"]["horse"]
                op = w.get("odds_pop")
                odds_str = f"・{op[0]}人気{op[1]}倍" if op else ""
                bias = w["row"].get("bias",0)
                abil = w["row"].get("ability"); abil_s = f"{abil:.0f}" if abil is not None else "—"
                top_reasons = " ／ ".join(w["row"]["reasons"][:3])
                L.append(f"- 推奨{w['rank']}位 {h['umaban']}番 {h['name']}（能力{abil_s}・bias{bias}{odds_str}） {top_reasons}")

        # v0.14: 動的配分戦略を提示
        # ◎の人気を推定: (1)shutuba popularity (2)odds_for_race (3)shutuba odds
        main_row = picks[0]["row"]
        main_horse = main_row["horse"]
        main_um = main_horse.get("umaban")
        main_pop = None
        if main_horse.get("popularity") and str(main_horse["popularity"]).isdigit():
            main_pop = int(main_horse["popularity"])
        elif odds_for_race and main_um:
            o = odds_for_race.get(str(main_um)) or odds_for_race.get(main_um)
            if o and o.get("pop"):
                try: main_pop = int(o["pop"])
                except: pass
        if main_pop is None and main_horse.get("odds"):
            try:
                all_odds=[]
                for h in race["horses"]:
                    if h.get("odds"):
                        try: all_odds.append((float(h["odds"]), h["umaban"]))
                        except: pass
                all_odds.sort()
                for i, (o, um) in enumerate(all_odds, 1):
                    if um == main_um: main_pop = i; break
            except: pass

        L.append("")
        L.append("**💰 推奨配分**")
        # 相手プール — 重複排除 (△に選ばれた馬と警戒馬が重なる場合あり)
        other_names = [p["row"]["horse"]["name"] for p in picks[1:4]]
        watch_only = [w["row"]["horse"]["name"] for w in watch
                      if w["row"]["horse"]["name"] not in other_names]
        pool = other_names + watch_only
        main_name = main_horse["name"]
        # v0.16: 包括検証(46R)で得たベスト戦略 ROI 125%
        # - 3連複流しの相手は「4頭」がスイートスポット(ROI 100%, 5頭流しは69%)
        # - 5人気↓◎は4R全敗→見送り
        # - 馬連はROI 12-20%で論外、ワイドは28-32%で3連複に劣る
        weather = race.get("weather") or ""
        baba_now = race.get("baba") or ""
        baba_note = f"(馬場{baba_now}=警戒馬閾値緩和)" if baba_now in ("稍","稍重","重","不良") else ""

        # 3連複流し相手プール: ○▲△ + 警戒馬から計4頭 (4C2=6点)
        pool4 = (other_names + watch_only)[:4]
        n_combo = len(pool4) * (len(pool4)-1) // 2  # =6 if 4頭
        pool_str = " / ".join(pool4) if pool4 else "(相手不足)"

        if main_pop is None:
            L.append(f"- ⏳ (オッズ未確定→朝再生成推奨) **◎軸3連複4頭流し** {main_name} → {pool_str} ({n_combo}点・{n_combo*100}円)")
        elif main_pop >= 5:
            L.append(f"- ⛔ **見送り推奨** {main_name}({main_pop}人気) — 5人気↓◎は2日4R全敗(ROI 0%)")
            L.append(f"  - 観戦のみ。または少額の遊び馬券のみに留める")
        elif main_pop <= 2:
            L.append(f"- **◎軸3連複4頭流し** {main_name}({main_pop}人気) → {pool_str} ({n_combo}点・{n_combo*100}円){baba_note}")
            L.append(f"  - ※1-2人気◎は単勝EV<1(0.62)につき単勝は買わない")
        else:  # 3-4人気
            L.append(f"- 🔥 **◎単勝 500円** {main_name}({main_pop}人気) — **単勝EV最大帯(2.34)** {baba_note}")
            L.append(f"- **◎軸3連複4頭流し** → {pool_str} ({n_combo}点・{n_combo*100}円)")
        L.append("")
    out = "\n".join(L)
    (ROOT/"data"/f"recommend_wide_{args.date}.md").write_text(out, encoding="utf-8")
    print(out)

if __name__ == "__main__":
    main()
