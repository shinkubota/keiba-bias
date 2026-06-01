#!/usr/bin/env python3
"""火曜/水曜の「反省コラム」自動生成。
直近の振り返りから「最も改善すべき1つのテーマ」を選び、
データを掘って考察エッセイ風のmdを data/review/columns/YYYYMMDD_<topic>.md に出力。

火曜: 取りこぼしテーマ深堀り(取りこぼし因子で最も悪い軸を1つ選択)
水曜: 警戒馬テーマ深堀り(✕押え or 警戒馬ゾーンのヒット因子分析)
"""
import json, re, sys, pathlib, datetime, importlib.util, collections, subprocess

ROOT = pathlib.Path(__file__).parent.parent
COL_DIR = ROOT/"data"/"review"/"columns"; COL_DIR.mkdir(parents=True, exist_ok=True)
SIRE_DIR = ROOT/"data"/"memory"/"sire_profiles"; SIRE_DIR.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

# 種牡馬プロフィール取得・キャッシュ
def ensure_sire_profile(sire_name, sire_id=None):
    """horses_*.json+ped HTMLから sire/broodmare_sire の horse_idを逆引きしてプロファイル取得。"""
    if not sire_id:
        from bs4 import BeautifulSoup
        for hp in sorted((ROOT/"data").glob("horses_*.json"), reverse=True):
            try: d = json.loads(hp.read_text(encoding="utf-8"))
            except Exception: continue
            for child_hid, v in d.items():
                ped = v.get("pedigree", {})
                # 父名 or 母父名 と一致した子馬を探す
                hit_role = None
                for role in ("sire", "broodmare_sire"):
                    sn = ped.get(role) or ""
                    m = re.match(r"^([぀-ヿ一-鿿・ー]+)", sn)
                    key = m.group(1) if m else sn
                    if key == sire_name:
                        hit_role = role; break
                if not hit_role: continue
                ped_cache = ROOT/"cache"/f"ped_{child_hid}.html"
                if not ped_cache.exists(): continue
                s = BeautifulSoup(ped_cache.read_text(encoding="utf-8"), "lxml")
                tbl = s.select_one("table.blood_table")
                if not tbl: continue
                big = [td for td in tbl.find_all("td") if td.get("rowspan") == "16"]
                target_td = None
                if hit_role == "sire":
                    target_td = big[0] if big else None
                else:
                    # 母父: 母(big[1])を含むtr内の最初の rowspan=8 のtd
                    if len(big) >= 2:
                        mtr = big[1].find_parent("tr")
                        sibs = mtr.find_all("td", recursive=False)
                        passed = False
                        for td in sibs:
                            if td is big[1]:
                                passed = True; continue
                            if passed and td.get("rowspan") == "8":
                                target_td = td; break
                if not target_td: continue
                a = target_td.find("a")
                if not a: continue
                m2 = re.search(r"/horse/([0-9a-z]+)", a.get("href",""))
                if m2:
                    sire_id = m2.group(1); break
            if sire_id: break
    if not sire_id:
        return None
    cache_path = SIRE_DIR/f"{sire_id}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    # 取得実行
    try:
        subprocess.run([sys.executable, str(ROOT/"scripts"/"fetch_sire_profile.py"), sire_id,
                        "--name", sire_name], cwd=ROOT, check=False, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return None

def render_sire_profile(prof):
    """サイア詳細をmd断片に。"""
    if not prof: return ["- 種牡馬データ取得失敗"]
    r = prof.get("results", {}); s = r.get("summary", {}); ped = prof.get("pedigree", {})
    out = []
    rank_trend = ", ".join(f"{y['year']}:{y['rank']}位" for y in r.get('years',[])[:3] if y.get('rank'))
    out.append(f"**{r.get('name','種牡馬')}** 累計プロフィール (年度ランキング推移：{rank_trend})")
    if ped:
        out.append(f"- 系統: 父{ped.get('father','?')} / 母父{ped.get('mother_father','?')}" + (f" ({ped['lineage_marker']})" if ped.get('lineage_marker') else ""))
    if s:
        out.append(f"- 累計出走馬{s.get('starters')}頭 / 勝馬{s.get('winners')}頭 (勝馬率{s.get('win_rate_horse','?')}) / EI {s.get('EI','?')} / 賞金{s.get('prize','?')}万円")
        # 芝/ダ勝率
        tr = s.get("turf_races") or 0; tw = s.get("turf_wins") or 0
        dr = s.get("dirt_races") or 0; dw = s.get("dirt_wins") or 0
        if tr or dr:
            tr_rate = tw/tr*100 if tr else 0; dr_rate = dw/dr*100 if dr else 0
            stronger = "ダート" if dr_rate > tr_rate else ("芝" if tr_rate > dr_rate else "互角")
            out.append(f"- **芝勝率 {tr_rate:.1f}% ({tw}/{tr}) / ダ勝率 {dr_rate:.1f}% ({dw}/{dr})** → 得意は**{stronger}**")
        g_races = s.get("g_races") or 0; g_wins = s.get("g_wins") or 0
        sp_races = s.get("sp_races") or 0; sp_wins = s.get("sp_wins") or 0
        out.append(f"- 重賞 {g_wins}/{g_races} / 特別 {sp_wins}/{sp_races} → 重賞勝率{(g_wins/g_races*100 if g_races else 0):.1f}%")
        if s.get("avg_dist_turf"): out.append(f"- 平均距離: 芝{s['avg_dist_turf']}m / ダ{s.get('avg_dist_dirt','?')}m → 適性距離帯の参考")
        if s.get("rep_horse"): out.append(f"- 代表産駒: {s['rep_horse']}")
    return out

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
    body.append(f"_前週: {dates[0][4:6]}/{dates[0][6:]}-{dates[1][4:6]}/{dates[1][6:]}_")
    body.append("")
    body.append(f"## 1. 数字で見る問題")
    body.append(f"前週末の対象期間で **{ax}「{k}」のレースは {t} 件中 {miss} 件で取りこぼし（{rate*100:.0f}%）**。")
    body.append(f"全体取りこぼし率（〜13%程度）から大きく外れており、改善優先順位は高い。")
    body.append("")
    body.append(f"## 2. 該当レース ({len(matched)}件)")
    for e in matched:
        body.append(f"- {e['date'][4:6]}/{e['date'][6:]} {e['race']} {e['race_name']}")
        body.append(f"  - 本命: {e['top1_name']} (能力{e['ability']}) → 1着 {e['winner_name']}({e['winner_pop']}人気・{e['winner_odds']}倍)")
    body.append("")

    # 血統軸なら種牡馬深堀
    if ax == "血統":
        body.append(f"## 3. {k}産駒の戦績データ")
        prof = ensure_sire_profile(k)
        body += render_sire_profile(prof)
        body.append("")
        body.append(f"## 4. なぜ取りこぼしたか — 配合パターン考察")
        if prof and prof.get("results", {}).get("summary"):
            s = prof["results"]["summary"]
            tr = s.get("turf_races") or 0; tw = s.get("turf_wins") or 0
            dr = s.get("dirt_races") or 0; dw = s.get("dirt_wins") or 0
            if tr and dr:
                t_rate = tw/tr*100; d_rate = dw/dr*100
                if abs(t_rate-d_rate) >= 2:
                    body.append(f"- {k}は **{'芝' if t_rate>d_rate else 'ダート'}向きの種牡馬**（勝率差{abs(t_rate-d_rate):.1f}pt）。条件外で取りこぼした可能性")
            avg_t = s.get("avg_dist_turf","")
            if avg_t: body.append(f"- 平均距離(芝)={avg_t}m → これと大きく外れる距離は適性外と判断する目安")
            ped = prof.get("pedigree", {})
            if ped.get("father"): body.append(f"- 父系: {ped['father']} → 同系統馬の好走条件をcourses.json sire_favoredと照合可能")
        body.append("")
    else:
        body.append(f"## 3. 考察")
        body += _miss_consider(ax, k, matched)
        body.append("")
    body.append(f"## 5. 次週への申し送り")
    body += _miss_action(ax, k, matched)
    body.append("")
    body.append(f"## 6. 確認ポイント")
    body += build_miss_check_list(ax, k)
    return f"{datetime.date.today().strftime('%Y%m%d')}_火_取りこぼし_{ax}_{k}.md", "\n".join(body)

def build_miss_check_list(ax, k):
    out = []
    if ax == "血統":
        out.append(f"- 出走表に{k}産駒がいたら、その馬の芝・ダ別実績を horse_id 経由で確認")
        out.append(f"- courses.json sire_favored から{k}を外す/弱化する判断材料を蓄積")
    if ax == "間隔":
        out.append(f"- 該当間隔の馬は能力スコアを 0.7〜0.8 で割引するシミュレーションを試行")
    if ax == "脚質":
        out.append(f"- 想定ペース予測ロジックの精度確認（先行馬数の判定閾値が妥当か）")
    if ax == "クラス":
        out.append(f"- 該当クラス専用の重みプロファイル(weights分岐)を検討")
    out.append("- 同条件が翌週も発生するか出馬表確認、再現性チェック")
    return out

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
    """水曜: 警戒馬ゾーンで拾えた因子の深堀+種牡馬詳細"""
    fac, ex, total_dark, in_watch = aggregate_watch_factors(dates)
    if total_dark == 0: return None, None
    body = []
    body.append(f"# 🔍 水曜コラム: 警戒馬ゾーンが大穴を拾えた因子を深掘る")
    body.append(f"_前週: {dates[0][4:6]}/{dates[0][6:]}-{dates[1][4:6]}/{dates[1][6:]}_")
    body.append("")
    body.append(f"## 1. 数字で見る警戒馬戦略")
    body.append(f"- 8人気以下が3着内に飛び込んだ件数: **{total_dark} 件**")
    body.append(f"- そのうち推奨6-12位の警戒馬ゾーンが捕捉: **{in_watch} 件 ({in_watch/total_dark*100:.0f}%)**")
    body.append(f"- 本命人気馬を◎にしつつワイドで警戒馬を絡める「人気軸×警戒馬」戦略が機能")
    body.append("")
    body.append(f"## 2. 人気薄を浮上させた因子ランキング")
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

    # 血統因子の深堀: 因子名が「父○○」「母父○○」のものから種牡馬詳細
    sire_factors = [(k, v) for k, v in fac.most_common() if k.startswith(("父","母父"))]
    if sire_factors:
        body.append(f"## 3. 注目血統の深掘り（戦績データ）")
        for fk, fv in sire_factors[:3]:
            # 「母父」を先に削る(でないと「父」だけ削って「母」が残る)
            sire_name = fk.replace("母父","").replace("父","").strip()
            prof = ensure_sire_profile(sire_name)
            body.append(f"\n### {fk} (発火{fv}回)")
            body.append(f"_{ '／'.join(sorted(set(ex[fk]))[:3]) }_")
            body += render_sire_profile(prof)
        body.append("")

    # コース・距離・脚質系の深堀
    course_factors = [(k, v) for k, v in fac.most_common() if any(t in k for t in ("ダート","芝","距離","枠","先行","差し","上がり"))]
    if course_factors:
        body.append(f"## 4. コース・距離・脚質系シグナルの解釈")
        for fk, fv in course_factors[:5]:
            body.append(f"- **{fk}** ({fv}回): {analyze_signal_meaning(fk)}")
        body.append("")

    body.append(f"## 5. 来週の確認ポイント")
    body += build_check_list(fac, course_factors, sire_factors)
    body.append("")
    body.append(f"## 6. 検証データの出典")
    body.append(f"- 推奨ロジック: analyze.py v0.9 (能力×バイアス補正)")
    body.append(f"- 種牡馬累計成績: netkeiba 産駒成績ページ (data/memory/sire_profiles/*.json)")
    body.append(f"- 集計対象: {dates[0]} + {dates[1]} 2日間の中央全レース")
    return f"{datetime.date.today().strftime('%Y%m%d')}_水_警戒馬_因子分析.md", "\n".join(body)

def analyze_signal_meaning(factor_name):
    """因子名から戦略的意味を返す。"""
    if "ダート" in factor_name:
        return "ダート戦は時計の絶対値より砂適性が支配的。芝→ダ替わり初戦の人気薄は粗削りで取りこぼされやすい。馬体重増減・血統と合わせ評価"
    if "距離延長" in factor_name:
        return "ペース緩和で前残りor末脚瞬発を活かすパターン。出走馬の脚質構成(前走通過順)から想定ペースを読み、延長馬の脚質が合致するか確認"
    if "距離短縮" in factor_name:
        return "前走スタミナ温存→ハイラップ対応。スピード持続型(芝マイル↔1400, ダ1700↔1400)の血統馬で機能しやすい"
    if "外枠" in factor_name or "大外枠" in factor_name:
        return "コース別の外枠バイアスはレース毎に強弱あり。馬場発表(芝の傷み具合)と先行馬の枠位置から外枠が活きるかを判断"
    if "内枠" in factor_name:
        return "ロスなく回れる利点だが、出遅れリスクと前詰まりに注意。先行馬の枠分布を見て『内に逃げ馬が居ない』なら好機"
    if "先行" in factor_name:
        return "ペース読みが鍵。逃げ馬複数で潰し合う展開なら不利、先行馬が少なければ単騎で残れる"
    if "差し" in factor_name or "後方" in factor_name:
        return "ハイペース必至 or 直線長コースで活きる。前走通過順が深い馬の上がり3F時計を確認"
    if "上がり" in factor_name:
        return "末脚絶対値より相対値(レース上がりに対する差)が重要。直近の上がり3F最速は能力代理として強い指標"
    return "—"

def build_check_list(fac, course_facs, sire_facs):
    out = []
    if sire_facs:
        names = "／".join(f.replace("父","").replace("母父","") for f, _ in sire_facs[:3])
        out.append(f"- **血統チェック**: {names}産駒の今週末出走を確認、watchlistへ登録検討")
    if course_facs:
        out.append(f"- **コース×脚質マッチング**: {len(course_facs)}つの効いた因子について、対象コースで該当馬が居るか出馬表確認")
    out.append("- **警戒馬抽出閾値**: 現状bias>=5/オッズ>=10で運用、もし大穴ヒットが圏外(13位以下)に偏る週があれば閾値見直し検討")
    out.append("- **馬場発表**: 当日朝のクッション値/含水率で芝の前残り傾向が変わる。馬場適性因子の重み再考")
    out.append("- **ペース予測**: 出走馬の前走脚質を集計し、先行馬3頭以上なら『差し有利』判定で警戒馬ゾーンに差し馬を加える")
    return out

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
