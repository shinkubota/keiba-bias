#!/usr/bin/env python3
"""出馬表 × courses.json × horses_*.json を照合し有利な馬を出力。
v0.3 では rule decomposer で前走条件(同距離/短縮/2-5着/上がり最速/重賞名…)を扱う。
Usage: python3 analyze.py YYYYMMDD
"""
import sys, json, pathlib, argparse, re

ROOT = pathlib.Path(__file__).parent.parent
COURSES = json.loads((ROOT/"data"/"courses.json").read_text(encoding="utf-8"))

def _load(name):
    p = ROOT/"data"/name
    if not p.exists(): return {}
    return {k:v for k,v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}
LINEAGE = _load("lineage.json")            # 書籍由来(優先)
LINEAGE_FB = _load("lineage_fallback.json")  # 血統表fallback

def lineage_of(sire_name):
    """種牡馬名→{daikei,shokei,type,src}。書籍優先、無ければfallback。"""
    k = clean_sire(sire_name)
    if k in LINEAGE: return LINEAGE[k]
    if k in LINEAGE_FB: return LINEAGE_FB[k]
    return None

# ── ユーティリティ ────────────────────────────────────────────
def load_horses(date_str):
    p = ROOT/"data"/f"horses_{date_str}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def course_key(track, surface, distance, variant):
    cs = []
    if variant: cs.append(f"{track}{surface}{distance}m{variant}")
    cs.append(f"{track}{surface}{distance}m")
    # netkeibaが内/外を明示しない場合に備え、内→外の順でフォールバック
    cs.append(f"{track}{surface}{distance}m内")
    cs.append(f"{track}{surface}{distance}m外")
    for k in cs:
        if k in COURSES: return k
    return None

def gate_section(umaban_str, total):
    try: u = int(umaban_str)
    except: return None
    if total <= 0: return None
    third = total / 3
    if u <= third: return "内"
    if u <= 2*third: return "中"
    return "外"

def clean_sire(name):
    """日本語先頭部を優先。英語名は括弧(国)を除去して返す。"""
    if not name: return ""
    m = re.match(r"^([぀-ヿ一-鿿・ー]+)", name)
    if m: return m.group(1)
    return name.split("(")[0].strip()

def sire_matches(horse_sire, favored_list):
    """系統対応マッチ。
    - favoredが『○○系』: 種牡馬の大系統/小系統と一致判定
    - favoredが個別馬名: 完全一致
    一致したfavoredラベルを返す。
    """
    s = clean_sire(horse_sire)
    if not s: return None
    lin = lineage_of(horse_sire)  # {daikei, shokei,...} or None
    for fav in favored_list:
        fav_core = re.sub(r"\(.*?\)", "", fav).strip()
        if fav_core.endswith("系"):
            if lin and (lin.get("daikei") == fav_core or lin.get("shokei") == fav_core):
                return fav
        else:
            if s == fav_core:           # 個別馬名は完全一致のみ(部分マッチ廃止)
                return fav
    return None

def parse_recent_dist(distance_text):
    """'芝1200' → ('芝', 1200)"""
    m = re.match(r"(芝|ダ|障)(\d+)", distance_text or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)

def first_passing_pos(passing):
    """'5-3-3' → 5"""
    if not passing: return None
    try: return int(passing.split("-")[0])
    except: return None

def is_front_runner(passing):
    """通過1コーナーが3位以内なら先行扱い"""
    p = first_passing_pos(passing)
    return p is not None and p <= 3

# ── 能力バイアス用ヘルパー ──────────────────────────────
def _to_float(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def _to_int(x):
    try: return int(x)
    except (TypeError, ValueError): return None

def best_recent_agari(recent, n=3):
    """直近n走の上がり3F最速値(秒)。馬場や距離は問わず素の脚力代理。"""
    vals = [_to_float(r.get("agari3f")) for r in recent[:n]]
    vals = [v for v in vals if v]
    return min(vals) if vals else None

def avg_recent_finish(recent, n=3):
    """直近n走の平均着順。少ないほど良い。"""
    vals = [_to_int(r.get("finish")) for r in recent[:n]]
    vals = [v for v in vals if v]
    return (sum(vals)/len(vals)) if vals else None

def place_rate(recent, n=5):
    """直近n走の複勝率(3着以内率)。"""
    vals = [_to_int(r.get("finish")) for r in recent[:n]]
    vals = [v for v in vals if v]
    if not vals: return None
    return sum(1 for v in vals if v <= 3) / len(vals)

def class_rank(race_name):
    """レース名からクラス階級を粗く数値化(大きいほど上)。"""
    s = race_name or ""
    if "G1" in s or "GⅠ" in s: return 9
    if "G2" in s or "GⅡ" in s: return 8
    if "G3" in s or "GⅢ" in s: return 7
    if "(L)" in s or "リステッド" in s: return 6
    if "オープン" in s or "OP" in s or "S)" in s or "ステークス" in s: return 5
    if "3勝" in s or "1600万" in s: return 4
    if "2勝" in s or "1000万" in s: return 3
    if "1勝" in s or "500万" in s: return 2
    if "未勝利" in s or "新馬" in s: return 1
    return 2  # 不明は条件戦相当

def horse_pace_style(recent, n=3):
    """直近の脚質: 通過1角平均から 逃げ/先行/差し/追込 を推定。"""
    poss = [first_passing_pos(r.get("passing")) for r in recent[:n]]
    poss = [p for p in poss if p]
    if not poss: return None
    avg = sum(poss)/len(poss)
    if avg <= 2: return "逃げ"
    if avg <= 4: return "先行"
    if avg <= 8: return "差し"
    return "追込"

def is_closer(passing):
    """最終コーナーで後方→1コーナーで6位以下 かつ 最終で前進"""
    if not passing: return False
    parts = [int(x) for x in passing.split("-") if x.isdigit()]
    if len(parts) < 2: return False
    return parts[0] >= 6

# ── ルール分解器 ─────────────────────────────────────────────
VENUE_NAMES = ["札幌","函館","福島","新潟","東京","中山","中京","京都","阪神","小倉"]
VENUE_RE = re.compile("|".join(VENUE_NAMES))

def parse_rule(rule_text):
    """1ルール文字列を 0以上の条件dictに分解。
    各条件: {type, params, label}
    """
    out = []
    txt = rule_text

    # ── 前走 場・芝ダ・距離 ────────────────────────────────
    for chunk in re.findall(r"前走([^、,。/]+?)(?=で|に|の|$)", txt):
        venues = VENUE_RE.findall(chunk)
        surface = "ダ" if "ダ" in chunk else ("芝" if "芝" in chunk else None)
        # 距離: 1700〜1800 or 1700-1800 or 単一
        dist_range = re.search(r"(\d{3,4})\s*[〜~\-]\s*(\d{3,4})", chunk)
        single_dists = re.findall(r"(?<!\d)(\d{3,4})(?!\d)", chunk)
        if dist_range:
            lo, hi = int(dist_range.group(1)), int(dist_range.group(2))
        elif single_dists:
            ds = [int(d) for d in single_dists]
            lo, hi = min(ds)-50, max(ds)+50
        else:
            lo = hi = None
        if venues or surface or lo:
            out.append({
                "type": "prev_course",
                "venues": venues, "surface": surface, "dist_lo": lo, "dist_hi": hi,
                "label": f"前走{','.join(venues) or '*'}{surface or ''}{f'{lo}-{hi}' if lo else ''}m"
            })

    # ── 距離ローテ ──────────────────────────────────────────
    if "同距離" in txt:
        out.append({"type":"rot_same", "label":"同距離ローテ"})
    if "距離短縮" in txt or "短縮ローテ" in txt:
        out.append({"type":"rot_shorter", "label":"距離短縮ローテ"})
    if "距離延長" in txt or "延長ローテ" in txt:
        out.append({"type":"rot_longer", "label":"距離延長ローテ"})

    # ── 着順条件 ────────────────────────────────────────────
    m = re.search(r"(\d+)[〜~\-](\d+)\s*着", txt)
    if m:
        out.append({"type":"prev_finish_range", "lo": int(m.group(1)), "hi": int(m.group(2)),
                    "label": f"前走{m.group(1)}〜{m.group(2)}着"})
    if "馬券内" in txt:
        out.append({"type":"prev_finish_range", "lo":1, "hi":3, "label":"前走馬券内"})
    if "勝ち" in txt and "実績" in txt:
        out.append({"type":"prev_finish_range", "lo":1, "hi":1, "label":"勝ち鞍実績"})

    # ── 上がり最速(近似:33秒台) ────────────────────────────
    if "上がり最速" in txt:
        out.append({"type":"prev_agari_fast", "threshold": 34.0, "label":"前走上がり高速(<34.0)"})

    # ── 先行/差し実績 ──────────────────────────────────────
    if ("逃げ" in txt or "先行" in txt) and ("有利" in txt or "実績" in txt or "馬" in txt):
        out.append({"type":"prev_front_runner", "label":"前走先行(通過1角≤3)"})
    if ("差し" in txt or "追込" in txt) and ("有利" in txt or "馬" in txt):
        out.append({"type":"prev_closer", "label":"前走後方→差し(通過1角≥6)"})

    # ── 重賞名条件 (ダービー or オークス馬券内 等) ─────────
    races_in_text = re.findall(r"(ダービー|オークス|秋華賞|天皇賞[春秋]|有馬|宝塚|ジャパンカップ|阪神大賞典|目黒記念|アルゼンチン共和国杯|ダイヤモンドS|フェブラリーS|安田記念|エリザベス女王杯)", txt)
    if races_in_text and ("馬券内" in txt or "好走" in txt or "3歳" in txt):
        out.append({"type":"prev_race_name", "names": races_in_text,
                    "label": f"前走{'/'.join(races_in_text)}馬券内"})

    return out

# ── 評価 ─────────────────────────────────────────────────
def eval_condition(cond, horse, recent):
    """条件1つを馬で評価。マッチなら理由文字列、なければNone"""
    r0 = recent[0] if recent else None
    ct = cond["type"]

    if ct == "prev_course":
        if not r0: return None
        rs, rd = parse_recent_dist(r0.get("distance_text"))
        if cond["venues"] and r0.get("venue") not in cond["venues"]: return None
        if cond["surface"] and rs != cond["surface"]: return None
        if cond["dist_lo"] and not (cond["dist_lo"] <= (rd or 0) <= cond["dist_hi"]): return None
        return f"{cond['label']}該当(前走{r0['venue']}{r0['distance_text']}・{r0['finish']}着)"

    if ct == "rot_same":
        if not r0: return None
        _, rd = parse_recent_dist(r0.get("distance_text"))
        if rd and abs(rd - cond.get("_this_dist",0)) <= 50:
            return f"同距離ローテ({r0['distance_text']}→同)"
        return None
    if ct == "rot_shorter":
        if not r0: return None
        _, rd = parse_recent_dist(r0.get("distance_text"))
        if rd and rd > cond.get("_this_dist",0) + 100:
            return f"距離短縮({rd}→{cond.get('_this_dist')})"
        return None
    if ct == "rot_longer":
        if not r0: return None
        _, rd = parse_recent_dist(r0.get("distance_text"))
        if rd and rd < cond.get("_this_dist",0) - 100:
            return f"距離延長({rd}→{cond.get('_this_dist')})"
        return None

    if ct == "prev_finish_range":
        if not r0: return None
        try: f = int(r0.get("finish") or "")
        except: return None
        if cond["lo"] <= f <= cond["hi"]:
            return f"{cond['label']}該当({f}着)"
        return None

    if ct == "prev_agari_fast":
        if not r0: return None
        try: a = float(r0.get("agari3f") or "")
        except: return None
        if a < cond["threshold"]:
            return f"前走上がり{a}(<{cond['threshold']})"
        return None

    if ct == "prev_front_runner":
        if not r0: return None
        if is_front_runner(r0.get("passing")):
            return f"前走先行(通過{r0.get('passing')})"
        return None

    if ct == "prev_closer":
        if not r0: return None
        if is_closer(r0.get("passing")):
            return f"前走後方差し(通過{r0.get('passing')})"
        return None

    if ct == "prev_race_name":
        if not r0: return None
        rn = r0.get("race_name","")
        if any(n in rn for n in cond["names"]):
            try: f = int(r0.get("finish") or "")
            except: return None
            if f <= 3:
                return f"前走{rn} {f}着"
        return None

    return None

def ability_score(recent):
    """過去実績ベースの能力スコア(0-100)。市場非依存・前日算出可。
    各前走の『着順位置率 × クラス係数』を直近重みで加重平均し、複勝安定で微補正。
    - 着順位置率: (頭数-着順+1)/頭数 … 1着=1.0、最下位≈0
    - クラス係数: 上位クラスでの好走を高く評価
    """
    if not recent:
        return None
    rweights = [1.0, 0.7, 0.5, 0.35, 0.25]
    num = den = 0.0
    for r, w in zip(recent[:5], rweights):
        fin = _to_int(r.get("finish")); fs = _to_int(r.get("field_size"))
        if not fin or not fs or fs < 2:
            continue
        pos = (fs - fin + 1) / fs                 # 0..1
        c = class_rank(r.get("race_name")) / 9.0  # 0.11..1.0
        run = pos * (0.55 + 0.45 * c)             # クラス上位の好走を加点
        num += w * run; den += w
    if den == 0:
        return None
    base = num / den                              # 0..1
    pr = place_rate(recent) or 0
    score = base * 100 * (0.9 + 0.2 * pr)         # 複勝安定で±10%
    return round(min(score, 100.0), 1)

def baba_style_pref(surface, baba):
    """馬場状態に応じた有利脚質を返す。(脚質set, 説明) or (None, None)。
    baba: 良/稍/重/不良。ダートと芝で傾向が逆になる点が重要。
    """
    wet = baba in ("稍", "稍重", "重", "不良")
    if surface == "ダ":
        if not wet:
            # 良ダートは時計がかかり前残り（先行有利）
            return ({"逃げ", "先行"}, "良ダートは前残り")
        else:
            # 締まった湿ダートは差しが届きやすい
            return ({"差し", "追込"}, f"{baba}ダートは差し届く")
    else:  # 芝
        if wet:
            # 芝の道悪は内・前有利になりやすい
            return ({"逃げ", "先行"}, f"{baba}芝は前/内有利")
        else:
            return (None, None)  # 良芝はニュートラル（コース固有バイアスに委ねる）

def build_race_context(race, horses_db):
    """レース内の相対指標を事前計算（能力バイアス用）。"""
    field = []
    for h in race["horses"]:
        hd = horses_db.get(h["horse_id"], {})
        recent = hd.get("recent", [])
        field.append({
            "umaban": h["umaban"],
            "agari": best_recent_agari(recent),
            "avg_fin": avg_recent_finish(recent),
            "place": place_rate(recent),
            "max_class": max([class_rank(r.get("race_name")) for r in recent[:5]], default=None),
            "style": horse_pace_style(recent),
        })
    agaris = [f["agari"] for f in field if f["agari"]]
    # 展開: 前走「逃げ/先行」の頭数を数える
    front_count = sum(1 for f in field if f["style"] in ("逃げ", "先行"))
    n = len(field)
    return {
        "best_agari": min(agaris) if agaris else None,
        "front_count": front_count,
        "field_size": n,
        # 先行馬が全体の1/4未満なら「先行有利展開」、半数超なら「差し有利展開」
        "pace_lean": ("先行有利" if n and front_count <= n*0.25
                      else ("差し有利" if n and front_count >= n*0.5 else "中庸")),
        "this_class": class_rank(race.get("race_name")),
    }

def attach_baba(rc, surface, baba):
    pref, why = baba_style_pref(surface, baba)
    rc["baba_pref"] = pref; rc["baba_why"] = why; rc["baba"] = baba
    return rc

def evaluate_horse(horse, course, total_horses, horse_data, this_distance,
                   light_weight_threshold=None, rc=None):
    reasons = []
    score = 0
    # 配点 v0.7: 5/30 全24R(23有効)の実績で再較正
    # 強因子: 複勝安定×1.88, 馬場適性×1.55, 同距離×1.45, 父モーリス×2.88(小サンプル)
    # 中因子: 内枠×1.26, 外枠×1.24, 前走先行×1.23, 上がり最速×1.23, 上位クラス×1.09
    # 弱因子(削除): 軽斤量×0.69, 展開向き×0.88
    weights = {"gate":3, "sire":3, "broodmare":2, "prev":3, "weight":0,
               "agari":2, "stable":5, "class":1, "pace_fit":0, "baba":4}

    # 斤量: レース内で軽量級(下位25%相当の閾値以下)なら恵まれ評価+1
    if light_weight_threshold is not None:
        try:
            kg = float(horse.get("jockey_weight") or 0)
            if kg and kg <= light_weight_threshold:
                reasons.append(f"軽斤量({kg}kg)"); score += weights["weight"]
        except ValueError:
            pass

    # 枠順
    gb = course.get("gate_bias", {})
    sec = gate_section(horse["umaban"], total_horses)
    gen = gb.get("general", "")
    if sec:
        if "内枠有利" in gen and sec == "内":
            reasons.append(f"内枠({horse['umaban']})有利"); score += weights["gate"]
        elif "外枠有利" in gen and sec == "外":
            reasons.append(f"外枠({horse['umaban']})有利"); score += weights["gate"]
        elif "1枠" in gen and horse["umaban"] in ("1","2"):
            reasons.append("1枠有利"); score += weights["gate"]

    # 血統
    favored = course.get("sire_favored", [])
    ped = horse_data.get("pedigree", {}) if horse_data else {}
    if ped.get("sire"):
        m = sire_matches(ped["sire"], favored)
        if m: reasons.append(f"父{clean_sire(ped['sire'])}=注目血統({m})"); score += weights["sire"]
    if ped.get("broodmare_sire"):
        m = sire_matches(ped["broodmare_sire"], favored)
        if m: reasons.append(f"母父{clean_sire(ped['broodmare_sire'])}=注目血統({m})"); score += weights["broodmare"]

    # 前走系ルール（全ルールから条件を集約し、同一条件の重複発火を排除）
    recent = horse_data.get("recent", []) if horse_data else []
    seen_sig = set()
    uniq_conds = []
    for rule_text in course.get("rules", []):
        for c in parse_rule(rule_text):
            sig = (c["type"],) + tuple(
                sorted((k, str(v)) for k, v in c.items() if k != "label")
            )
            if sig in seen_sig:
                continue
            seen_sig.add(sig)
            uniq_conds.append(c)
    for c in uniq_conds:
        if c["type"].startswith("rot_"):
            c["_this_dist"] = this_distance
        msg = eval_condition(c, horse, recent)
        if msg and msg not in reasons:        # 念のため理由の重複も排除
            reasons.append(msg); score += weights["prev"]

    # ── 能力バイアス（レース内相対） ──────────────────────
    if rc:
        # ① 上がり最速偏差: レース内で最速上がりを持つ馬を加点
        my_agari = best_recent_agari(recent)
        if my_agari and rc["best_agari"] and my_agari <= rc["best_agari"] + 0.1:
            reasons.append(f"上がり最速級({my_agari}s)"); score += weights["agari"]

        # ② 着順安定度: 直近複勝率が高い馬を加点
        pr = place_rate(recent)
        if pr is not None and pr >= 0.6:
            reasons.append(f"複勝安定({pr*100:.0f}%)"); score += weights["stable"]

        # ③ 相手強度: 今走より上のクラスを経験している格上挑戦馬を加点
        my_max_class = max([class_rank(r.get("race_name")) for r in recent[:5]], default=None)
        this_class = rc.get("this_class")
        if my_max_class and this_class and my_max_class > this_class:
            reasons.append("上位クラス経験(通用実績)"); score += weights["class"]

        # ④ 展開脚質適性: そのレースの想定ペースに合う脚質を加点
        my_style = horse_pace_style(recent)
        if my_style:
            if rc["pace_lean"] == "先行有利" and my_style in ("逃げ", "先行"):
                reasons.append(f"展開向き(先行少→{my_style})"); score += weights["pace_fit"]
            elif rc["pace_lean"] == "差し有利" and my_style in ("差し", "追込"):
                reasons.append(f"展開向き(先行多→{my_style})"); score += weights["pace_fit"]

        # ⑤ 馬場状態適性: 天候・馬場で有利な脚質に合致するか
        pref, why = rc.get("baba_pref"), rc.get("baba_why")
        if pref and my_style and my_style in pref:
            reasons.append(f"馬場適性({why}→{my_style})"); score += weights["baba"]

    return score, reasons

def analyze_race(race, horses_db, baba=None):
    # baba優先順位: 明示引数 > 出馬表の実データ(race['baba']) > 良
    if baba is None:
        baba = race.get("baba") or "良"
    key = course_key(race["track"], race["surface"], race["distance"], race.get("variant"))
    if not key:
        return {"warn": f"未登録コース: {race['track']}{race['surface']}{race['distance']}m"}
    course = COURSES[key]
    total = len(race["horses"])
    gates = any(h["umaban"] for h in race["horses"])
    # 斤量の軽量閾値: レース内の最小斤量+0.5kg以内を「軽量級」とする
    kgs = []
    for h in race["horses"]:
        try:
            v = float(h.get("jockey_weight") or 0)
            if v: kgs.append(v)
        except ValueError:
            pass
    lw_thr = (min(kgs) + 0.5) if kgs else None

    rc = build_race_context(race, horses_db)
    rc = attach_baba(rc, race["surface"], baba)

    DEFAULT_ABILITY = 28.0   # 新馬・実績僅少馬のデフォ(低め)
    # v0.7: 5/30全24R結果より「能力単独22% = 現行22%」と同等→バイアスはチューニング次第
    # 複勝率は能力78% < バイアス83%、つまりバイアスは複勝寄与が大。係数を維持
    BIAS_K = 0.025

    ranked = []
    for h in race["horses"]:
        hd = horses_db.get(h["horse_id"], {})
        recent = hd.get("recent", [])
        bias, rs = evaluate_horse(h, course, total, hd, race["distance"], lw_thr, rc)
        abil = ability_score(recent)
        abil_eff = abil if abil is not None else DEFAULT_ABILITY
        final = round(abil_eff * (1 + BIAS_K * bias), 1)
        ranked.append({
            "score": final,            # 最終評価(=能力×バイアス補正)。表示・ソートの主指標
            "ability": abil,           # 能力スコア(None=実績なし)
            "ability_eff": round(abil_eff, 1),
            "bias": bias,              # バイアス適合点
            "horse": h, "reasons": rs, "pedigree": hd.get("pedigree", {}),
        })
    ranked.sort(key=lambda x: -x["score"])

    # 穴候補: 能力中位以下だがバイアス補正で上位に食い込んだ馬
    if ranked:
        abil_sorted = sorted((r["ability_eff"] for r in ranked), reverse=True)
        median = abil_sorted[len(abil_sorted)//2]
        for i, r in enumerate(ranked):
            r["value_pick"] = (i < 3 and r["bias"] >= 6 and r["ability_eff"] <= median)

    # 道悪前提のheadlineに馬場状態の注記を付ける
    headline = course.get("headline","")
    wet_words = ("湿", "道悪", "荒れ", "雨")
    is_wet = baba in ("稍","稍重","重","不良")
    note = ""
    if any(w in headline for w in wet_words) and not is_wet:
        note = f"（※本日は{baba}馬場想定。『湿ると〜』は不適用、{race['surface']}{baba}の傾向で補正済み）"

    return {
        "course_key": key,
        "headline": headline + note,
        "baba": baba,
        "baba_pref": rc.get("baba_pref"),
        "baba_why": rc.get("baba_why"),
        "rules": course.get("rules", []),
        "sire_favored": course.get("sire_favored", []),
        "horses": ranked, "gates_assigned": gates,
    }

def fmt(date_str):
    data = json.loads((ROOT/"data"/f"shutuba_{date_str}.json").read_text(encoding="utf-8"))
    horses_db = load_horses(date_str)
    lines = [f"# トラックバイアス分析 {date_str}", ""]
    for race in data:
        if len(race["horses"]) < 2: continue
        a = analyze_race(race, horses_db)
        lines.append(f"## {race['track']}{race['race_no']:>2}R {race['surface']}{race['distance']}m  {race['race_name']}  ({len(race['horses'])}頭)")
        if a.get("warn"):
            lines.append(f"⚠ {a['warn']}"); lines.append(""); continue
        lines.append(f"**{a['headline']}**")
        for r in a["rules"]: lines.append(f"  - {r}")
        lines.append(f"注目血統: {', '.join(a['sire_favored'][:8])}")
        if not a["gates_assigned"]:
            lines.append("> ⚠ 枠順未発表")
        lines.append("")
        lines.append("| 順 | 馬番 | 馬名 | 性齢 | 父 | 母父 | スコア | 該当理由 |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, row in enumerate(a["horses"][:10], 1):
            h = row["horse"]; ped = row["pedigree"]
            sire = clean_sire(ped.get("sire") or "")
            bms  = clean_sire(ped.get("broodmare_sire") or "")
            lines.append(f"| {i} | {h['umaban'] or '?'} | {h['name']} | {h['sex_age']} | {sire} | {bms} | {row['score']} | {'; '.join(row['reasons']) or '—'} |")
        lines.append("")
    return "\n".join(lines)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    args = ap.parse_args()
    out = fmt(args.date)
    outpath = ROOT/"data"/f"analysis_{args.date}.md"
    outpath.write_text(out, encoding="utf-8")
    print(out)
    print(f"\n# saved: {outpath}", file=sys.stderr)
