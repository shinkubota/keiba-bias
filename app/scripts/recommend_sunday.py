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

    # 警戒馬: 推奨6-12位の中で「警戒すべき馬」を最大1頭抽出
    # v0.11: 回収率検証(6/7)の結果、警戒馬2-3頭追加しても回収率改善せず(E0=E1=E2=36%)
    # → bias>=8 (大穴シグナル強) かつ オッズ>=15倍 の1頭のみに限定
    watch = []
    for idx, r in enumerate(rows[5:12], start=6):
        if r.get("bias", 0) < 8: continue   # 5→8 に厳格化
        um = r["horse"].get("umaban")
        odds_pop = None
        if odds_for_race and um:
            o = odds_for_race.get(str(um)) or odds_for_race.get(int(um) if um.isdigit() else um)
            if o: odds_pop = (o.get("pop"), o.get("win"))
        if odds_pop:
            pop, win = odds_pop
            if win and win < 15: continue   # 10→15倍に厳格化
        watch.append({"rank": idx, "row": r, "odds_pop": odds_pop})
        if len(watch) >= 1: break           # 3→1頭のみ

    return picks[:4], watch, a               # 5→4頭(✕廃止)

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

    L = [f"# 🐎 {d.year}/{d.month}/{d.day}({WD[d.weekday()]}) 推奨（v0.11 絞り版・4頭+α）", ""]
    L.append("> 📝 v0.11: 6/7回収率検証より✕廃止＆警戒馬1頭に絞り (28点ボックス回収率25%→絞り4点で48%)")
    L.append("> ◎総合1位 ○2位 ▲3位 △総合4位またはバイアス特化")
    L.append("> ⚠ **警戒馬** = bias≥8 ＋ 単オッズ≥15倍の推奨6-12位馬を1頭のみ(穴のスパイス)")
    L.append("> 💰 **推奨買い方**: ◎単勝(回収率最高) / ◎○▲△ボックスワイド6点 / 大穴狙いなら◎-警戒馬ワイド1点")
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
        L.append("")
    out = "\n".join(L)
    (ROOT/"data"/f"recommend_wide_{args.date}.md").write_text(out, encoding="utf-8")
    print(out)

if __name__ == "__main__":
    main()
