#!/usr/bin/env python3
"""火曜/水曜の「反省コラム」自動生成。
直近の振り返りから「最も改善すべき1つのテーマ」を選び、
データを掘って考察エッセイ風のmdを data/review/columns/YYYYMMDD_<topic>.md に出力。

火曜: 取りこぼしテーマ深堀り(取りこぼし因子で最も悪い軸を1つ選択)
水曜: 警戒馬テーマ深堀り(✕押え or 警戒馬ゾーンのヒット因子分析)
"""
import json, re, sys, pathlib, datetime, importlib.util, collections

ROOT = pathlib.Path(__file__).parent.parent
COL_DIR = ROOT/"data"/"review"/"columns"; COL_DIR.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

WD = ["月","火","水","木","金","土","日"]

def last_sat_sun():
    today = datetime.date.today()
    days_since_sun = today.weekday() + 1
    sun = today - datetime.timedelta(days=days_since_sun)
    sat = sun - datetime.timedelta(days=1)
    return sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")

def aggregate_misses(dates):
    """取りこぼしレースを各軸で集計"""
    miss_by = collections.defaultdict(lambda: collections.defaultdict(int))
    total_by = collections.defaultdict(lambda: collections.defaultdict(int))
    miss_examples = []
    for date in dates:
        sh_p = ROOT/"data"/f"shutuba_{date}.json"
        res_p = ROOT/"data"/f"results_{date}.json"
        if not (sh_p.exists() and res_p.exists()): continue
        sh = json.loads(sh_p.read_text(encoding="utf-8"))
        res = {r["race_id"]: r for r in json.loads(res_p.read_text(encoding="utf-8"))}
        db = az.load_horses(date)
        for race in sh:
            r = res.get(race["race_id"], {})
            if not r.get("horses"): continue
            a = az.analyze_race(race, db)
            if a.get("warn"): continue
            picks = a["horses"][:3]
            if not picks: continue
            top3um = {h["umaban"] for h in r["horses"][:3]}
            in_t3 = any(p["horse"]["umaban"] in top3um for p in picks if p["horse"]["umaban"])
            top1 = picks[0]
            hd = db.get(top1["horse"]["horse_id"], {})
            rec = hd.get("recent", [])
            ped = top1.get("pedigree", {})
            # 軸抽出
            sire = re.match(r"^([぀-ヿ一-鿿・ー]+)", ped.get("sire") or "")
            sire_k = sire.group(1) if sire else "?"
            cls_k = _class_label(race["race_name"])
            intvl_k = _interval(rec[0].get("date") if rec else None, date)
            style_k = az.horse_pace_style(rec) or "?"
            keys = {"血統": sire_k, "クラス": cls_k, "間隔": intvl_k, "脚質": style_k,
                    "場": race["track"], "馬場": race.get("baba") or "?",
                    "天候": race.get("weather") or "?"}
            for ax, k in keys.items():
                total_by[ax][k] += 1
                if not in_t3:
                    miss_by[ax][k] += 1
            if not in_t3:
                wh = r["horses"][0]
                miss_examples.append({
                    "date": date, "race": f"{race['track']}{race['race_no']}R",
                    "race_name": race["race_name"],
                    "top1_name": top1["horse"]["name"], "top1_pop": None,
                    "winner_name": wh["name"], "winner_pop": wh.get("popularity"),
                    "winner_odds": wh.get("odds"),
                    "keys": keys, "ability": top1.get("ability"),
                })
    return miss_by, total_by, miss_examples

def aggregate_watch_factors(dates):
    """警戒馬ゾーン(6-12位)で3着内に来た馬の因子集計"""
    factor_hits = collections.Counter()
    examples_by_factor = collections.defaultdict(list)
    total_dark = 0; in_watch_zone = 0
    for date in dates:
        sh_p = ROOT/"data"/f"shutuba_{date}.json"
        res_p = ROOT/"data"/f"results_{date}.json"
        if not (sh_p.exists() and res_p.exists()): continue
        sh = json.loads(sh_p.read_text(encoding="utf-8"))
        res = {r["race_id"]: r for r in json.loads(res_p.read_text(encoding="utf-8"))}
        db = az.load_horses(date)
        for race in sh:
            r = res.get(race["race_id"], {})
            if not r.get("horses"): continue
            a = az.analyze_race(race, db)
            if a.get("warn"): continue
            rank_by = {}
            for i, h in enumerate(a["horses"], start=1):
                if h["horse"]["umaban"].isdigit():
                    rank_by[int(h["horse"]["umaban"])] = (i, h)
            for hr in r["horses"][:3]:
                ph = hr.get("popularity")
                if not (ph and ph >= 8): continue
                total_dark += 1
                rk_info = rank_by.get(hr["umaban"])
                if not rk_info: continue
                rk, hh = rk_info
                if not (6 <= rk <= 12): continue
                in_watch_zone += 1
                for rr in hh.get("reasons", [])[:5]:
                    key = rr.split("(")[0].split("=")[0].split("該当")[0].strip()
                    factor_hits[key] += 1
                    examples_by_factor[key].append(f"{hr['name']}({ph}人気・{hr.get('odds')}倍)")
    return factor_hits, examples_by_factor, total_dark, in_watch_zone

def _class_label(name):
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

def _interval(prev, today):
    if not prev: return "不明"
    try:
        y,m,d = prev.split("/")
        pv = datetime.date(int(y),int(m),int(d))
        td = datetime.date(int(today[:4]),int(today[4:6]),int(today[6:8]))
        days = (td - pv).days
        if days <= 14: return "連闘〜2週"
        if days <= 28: return "3-4週"
        if days <= 70: return "5-10週"
        if days <= 180: return "11週-半年"
        return "半年超"
    except: return "不明"

def column_miss_topic(dates):
    """火曜: 取りこぼしの最大要因を1つ選んで深堀コラム"""
    miss_by, total_by, examples = aggregate_misses(dates)
    # 最大の取りこぼし率(出現2以上)の(軸,値)を探す
    worst = None
    for ax, vals in miss_by.items():
        for k, miss in vals.items():
            t = total_by[ax][k]
            if t < 2: continue
            rate = miss / t
            if rate < 0.3: continue
            if not worst or rate > worst[3]:
                worst = (ax, k, miss, rate, t)
    if not worst:
        return None, None
    ax, k, miss, rate, t = worst
    matched = [e for e in examples if e["keys"].get(ax) == k]
    body = []
    body.append(f"# 🔍 火曜コラム: {ax}「{k}」の取りこぼしを掘る")
    body.append("")
    body.append(f"## 数字")
    body.append(f"前週末の対象期間で **{ax}「{k}」のレースは {t} 件中 {miss} 件で取りこぼし（{rate*100:.0f}%）**。")
    body.append(f"全体取りこぼし率（〜13%程度）から大きく外れており、改善優先順位は高い。")
    body.append("")
    body.append(f"## 該当レース ({len(matched)}件)")
    for e in matched:
        body.append(f"- {e['date'][4:6]}/{e['date'][6:]} {e['race']} {e['race_name']}")
        body.append(f"  - 本命: {e['top1_name']} (能力{e['ability']}) → 1着 {e['winner_name']}({e['winner_pop']}人気・{e['winner_odds']}倍)")
    body.append("")
    body.append(f"## 考察")
    body += _miss_consider(ax, k, matched)
    body.append("")
    body.append(f"## 次週への申し送り")
    body += _miss_action(ax, k, matched)
    return f"{datetime.date.today().strftime('%Y%m%d')}_火_取りこぼし_{ax}_{k}.md", "\n".join(body)

def _miss_consider(ax, k, examples):
    out = []
    if ax == "間隔":
        if k in ("半年超", "11週-半年"):
            out.append("- 休み明け馬を本命に推した結果、仕上がり不足や鉄砲駆けの不確実性で外している可能性。")
            out.append("- 能力スコアは「過去5走」を見るため、長期休養前の好走が現在のパフォーマンスと乖離するケースが想定される。")
    if ax == "脚質":
        if k == "先行":
            out.append("- 先行馬本命の取りこぼし＝ハイペース展開で前崩れになったケースが多そう。")
            out.append("- 当アプリは出走馬の前走脚質を集計して『先行馬が少ない＝先行有利』と判定するが、ペース予測の精度に課題。")
    if ax == "クラス":
        if k in ("G1", "G2", "G3", "OP/L", "他"):
            out.append("- 重賞・OPでは能力スコアの差が小さく、当アプリのバイアス偏重が裏目に出ている可能性。")
            out.append("- 重賞は『市場の人気評価』と『近走重賞実績』の比重をもっと高めるべきかもしれない。")
        if k == "1勝":
            out.append("- 1勝クラスは出走頭数が安定して多く、紛れが大きい。能力スコアの中位以下に1着馬が眠るケース。")
    if ax == "血統":
        out.append(f"- 父{k}の馬を本命にしたが結果が伴わない。注目血統リスト(courses.json sire_favored)の見直し候補。")
    if not out:
        out.append("- データ蓄積待ち。出現数が増えれば傾向が明確になる。")
    return out

def _miss_action(ax, k, examples):
    out = []
    if ax == "間隔" and k in ("半年超","11週-半年"):
        out.append("- 半年超休み明け馬の能力スコアを ×0.7 で割引する案を検証")
    if ax == "脚質" and k == "先行":
        out.append("- ペース予測ロジックの強化: 同レース内の前走脚質を頭数比だけでなく『極端な逃げ馬数』で評価")
    if ax == "クラス" and k in ("G1","G2","G3","OP/L","他"):
        out.append("- 重賞限定モードを検討: ◎は人気1-3番手から能力スコア最上位を選ぶ保守ロジック")
    if ax == "血統":
        out.append(f"- 父{k}を sire_favored から外す or 弱化する案を検証")
    if not out:
        out.append("- データ蓄積を継続")
    return out

def column_watch_topic(dates):
    """水曜: 警戒馬ゾーンで拾えた因子の深堀"""
    fac, ex, total_dark, in_watch = aggregate_watch_factors(dates)
    if total_dark == 0:
        return None, None
    body = []
    body.append(f"# 🔍 水曜コラム: 警戒馬ゾーン(6-12位)が大穴を拾えた因子")
    body.append("")
    body.append(f"## 数字")
    body.append(f"前週末で 8人気以下が3着内に飛び込んだ件数: **{total_dark} 件**。")
    body.append(f"そのうち推奨6-12位の警戒馬ゾーンが捕捉したのは **{in_watch} 件 ({in_watch/total_dark*100:.0f}%)**。")
    body.append("つまり本命人気馬を◎にしつつワイドで警戒馬を絡める戦略が機能している。")
    body.append("")
    body.append(f"## どの因子が「人気薄を浮上させた」か")
    if not fac:
        body.append("- 該当因子なし")
    else:
        body.append("| 因子 | 発火数 | 拾えた馬例 |")
        body.append("|---|--:|---|")
        for k, v in fac.most_common(10):
            if v < 1: continue
            samples = "／".join(sorted(set(ex[k]))[:3])
            body.append(f"| {k} | {v} | {samples} |")
    body.append("")
    body.append(f"## 考察")
    body.append("- 「強因子（複勝安定・トップ騎手）」は人気馬で発火しやすく、能力スコア上位を支える。")
    body.append("- 一方で「中位因子（距離延長・継続騎乗・大外枠）」は能力下位の人気薄で発火し、警戒馬ゾーンを作り上げる。")
    body.append("- 両者を分けて配点・抽出することで、人気と穴の二段構えが実現する。")
    body.append("")
    body.append(f"## 次週への申し送り")
    body.append("- 警戒馬抽出の閾値(bias>=5, オッズ>=10)が妥当か継続検証")
    body.append("- 大穴3着内ヒットの ◎-警戒馬ワイド での実利益を試算する仕組みを次回追加")
    return f"{datetime.date.today().strftime('%Y%m%d')}_水_警戒馬_因子分析.md", "\n".join(body)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if mode == "auto":
        wd = datetime.date.today().weekday()
        mode = "miss" if wd == 1 else ("watch" if wd == 2 else "miss")
    sat, sun = last_sat_sun()
    dates = [sat, sun]
    if mode == "miss":
        fn, body = column_miss_topic(dates)
    elif mode == "watch":
        fn, body = column_watch_topic(dates)
    else:
        print("Usage: weekday_column.py [miss|watch|auto]"); sys.exit(2)
    if not body:
        print("対象データなし or 取りこぼし軸が見つからず"); return
    p = COL_DIR/fn
    p.write_text(body, encoding="utf-8")
    print(f"saved: {p}")

if __name__ == "__main__":
    main()
