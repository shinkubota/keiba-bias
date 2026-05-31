#!/usr/bin/env python3
"""各レースのバイアス推奨上位N頭を、レース内ソフトマックスで%化して出力。
Usage: python3 recommend.py YYYYMMDD [--track 東京|京都] [--top 3]
%は「バイアス推奨度」= レース内でその馬にバイアス支持がどれだけ集中しているかの相対指標。
勝率予測ではない点に注意。
"""
import json, pathlib, argparse, math, sys
import analyze  # 同じscriptsディレクトリ

ROOT = pathlib.Path(__file__).parent.parent

def softmax(scores, T):
    if not scores: return []
    mx = max(scores)
    exps = [math.exp((s-mx)/T) for s in scores]
    z = sum(exps)
    return [e/z for e in exps]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--track", default=None)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--temp", type=float, default=2.5)
    ap.add_argument("--baba", default=None, help="馬場状態 良/稍/重/不良（未指定なら出馬表の実データ→無ければ良）")
    args = ap.parse_args()

    data = json.loads((ROOT/"data"/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    horses_db = analyze.load_horses(args.date)

    out = []
    for race in data:
        if args.track and race["track"] != args.track: continue
        if len(race["horses"]) < 2: continue
        a = analyze.analyze_race(race, horses_db, baba=args.baba)
        if a.get("warn"):
            out.append(f"## {race['track']}{race['race_no']:>2}R {race['surface']}{race['distance']}m {race['race_name']}\n  {a['warn']}\n")
            continue
        ranked = a["horses"]
        scores = [r["score"] for r in ranked]
        probs = softmax(scores, args.temp)
        for r, p in zip(ranked, probs): r["pct"] = p

        head = f"## {race['track']}{race['race_no']:>2}R {race['surface']}{race['distance']}m {race['race_name']} ({len(race['horses'])}頭)"
        lines = [head, f"  狙い: {a['headline']}"]
        shown = 0
        for r in ranked:
            if shown >= args.top: break
            if r["score"] <= 0: break  # バイアス該当なしは出さない
            h = r["horse"]
            reasons = "; ".join(r["reasons"][:4])
            kg = h.get("jockey_weight") or "?"
            mark = "★" if r.get("cal_pick") else " "
            lines.append(f"  {mark}{shown+1}. [{h['umaban']:>2}] {h['name']}（{h.get('sex_age','')} {h.get('jockey','')} {kg}kg）  {r['pct']*100:4.1f}%  (score {r['score']}, cal {r.get('cal_bonus',0):+d})  — {reasons}")
            shown += 1
        # TOP外で★が立っている馬も穴候補として追記
        extras = [r for r in ranked[args.top:8] if r.get("cal_pick")]
        for r in extras[:3]:
            h = r["horse"]
            reasons = "; ".join(r["reasons"][:4])
            kg = h.get("jockey_weight") or "?"
            lines.append(f"  ★穴 [{h['umaban']:>2}] {h['name']}（{h.get('sex_age','')} {h.get('jockey','')} {kg}kg）  (score {r['score']}, cal {r.get('cal_bonus',0):+d})  — {reasons}")
        if shown == 0:
            lines.append("  バイアス該当馬なし")
        out.append("\n".join(lines)+"\n")

    text = "\n".join(out)
    print(text)
    p = ROOT/"data"/f"recommend_{args.date}{'_'+args.track if args.track else ''}.md"
    p.write_text(text, encoding="utf-8")
    print(f"# saved: {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
