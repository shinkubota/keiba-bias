#!/usr/bin/env python3
"""trueblood/ のOCR結果(raw_*.json)を集約し、
1) trueblood_long.csv  : 種牡馬×カテゴリ×条件の成績ロングテーブル(分析用)
2) sire_aptitude.json  : 予想取込用の正規化(種牡馬→脚質/馬場/コース/枠 適性 + 狙い目テキスト)

OCRのバッチごとにJSONスキーマが異なるため、再帰探索で
カテゴリ(脚質/馬場/コース/距離/枠/人気/クラス)を含むキーを拾う。
"""
import json, glob, csv, re, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).parent.parent
TB = ROOT / "data" / "memory" / "trueblood"

# カテゴリ判定キーワード(キー名に含まれるか)
CAT_KEYS = {
    "pace":   ["pace_style", "脚質", "running", "style", "pace"],
    "baba":   ["baba", "馬場", "going", "track_cond"],
    "course": ["course", "コース", "surface"],
    "distance":["distance", "距離", "dist"],
    "draw":   ["draw", "枠", "waku", "gate"],
    "popularity":["popularity", "人気", "ninki", "pop"],
    "klass":  ["klass", "class", "クラス", "条件"],
    "grade":  ["grade", "グレード", "重賞"],
    "age":    ["age", "年齢", "歳"],
    "sex":    ["sex", "性", "牝"],
    "interval":["interval", "間隔", "ローテ"],
    "season": ["season", "季節", "時期"],
}
# 脚質キーの正規化
PACE_NORM = {"逃げ":"逃げ","先行":"先行","差し":"差し","追込":"追込","追い込み":"追込","まくり":"差し"}
BABA_NORM = {"良":"良","稍":"稍","稍重":"稍","重":"重","不良":"不良"}

def cat_of(keyname):
    k = str(keyname).lower()
    for cat, kws in CAT_KEYS.items():
        for kw in kws:
            if kw.lower() in k:
                return cat
    return None

def num(v):
    """文字列/数値から数値を取り出す。'33.5%','110' -> float。不可ならNone"""
    if v is None: return None
    if isinstance(v,(int,float)): return float(v)
    m = re.search(r"-?\d+\.?\d*", str(v).replace(",",""))
    return float(m.group()) if m else None

def is_row(d):
    """rowらしいdict(key + 数値指標を持つ)か"""
    if not isinstance(d, dict): return False
    has_key = any(k in d for k in ("key","name","cond","label","条件"))
    has_val = any(k in d for k in ("place_pct","win_pct","runs","fuku_return","tan_return","place2_pct","rentai_pct"))
    return has_key and has_val

def row_key(d):
    for k in ("key","name","cond","label","条件"):
        if d.get(k): return str(d[k])
    return ""

def walk(node, surface_hint, out):
    """再帰探索でrow(成績行)を集める。out: list of (category, surface, key, row_dict)"""
    if isinstance(node, dict):
        # surfaceヒントの更新(階層キーが芝/ダ/shiba/dirt)
        for sk, sval in node.items():
            skl = str(sk).lower()
            new_surf = surface_hint
            if skl in ("shiba","芝","turf"): new_surf = "芝"
            elif skl in ("dirt","ダ","ダート"): new_surf = "ダ"
            if is_row(sval):
                cat = cat_of(sk) or "other"
                out.append((cat, new_surf, row_key(sval), sval))
            elif isinstance(sval, list):
                cat = cat_of(sk)
                for item in sval:
                    if is_row(item):
                        # rowにsurfaceフィールドがあれば優先
                        rs = item.get("surface")
                        s = ("芝" if rs in ("芝","shiba","turf") else
                             "ダ" if rs in ("ダ","dirt","ダート") else new_surf)
                        out.append((cat or cat_of(row_key(item)) or "other", s, row_key(item), item))
                    else:
                        walk(item, new_surf, out)
            else:
                walk(sval, new_surf, out)
    elif isinstance(node, list):
        for item in node:
            walk(item, surface_hint, out)

def main():
    raws = sorted(TB.glob("raw_*.json"))
    sires = {}  # name -> aggregated record

    long_rows = []     # for CSV (詳細成績)
    catalog_rows = []  # for CSV (名鑑: af1/2/3の複数頭ページ)

    def default_rec(name):
        return {
            "sire_name": name, "rank": None, "sire_name_en": None,
            "birth_year": None, "catchphrase": None,
            "pedigree": {}, "blood_comment": None, "bet_comment": None,
            "aim": None, "cats": defaultdict(dict),
            "source_images": [],
        }

    for f in raws:
        try:
            data = json.load(open(f))
        except Exception as e:
            print(f"skip {f.name}: {e}"); continue
        for img in data.get("images", []):
            # 名鑑形式(1ページに複数種牡馬: sires リスト)
            if isinstance(img.get("sires"), list):
                for s in img["sires"]:
                    nm = (s.get("sire_name") or "").strip()
                    if not nm: continue
                    ped = s.get("pedigree") or {}
                    apt_slider = s.get("aptitude") or {}
                    catalog_rows.append({
                        "sire": nm,
                        "section": img.get("section") or img.get("page_title") or "",
                        "line": s.get("sire_line") or s.get("line") or "",
                        "country": s.get("country") or s.get("origin") or "",
                        "sire": nm,
                        "f_sire": ped.get("sire",""),
                        "f_dam": ped.get("dam",""),
                        "f_damsire": ped.get("damsire",""),
                        "baba_pos": apt_slider.get("baba_pos",""),
                        "dirt_pos": apt_slider.get("dirt_pos",""),
                        "distance_pos": apt_slider.get("distance_pos",""),
                        "catchphrase": s.get("catchphrase") or "",
                        "aim": s.get("aim") or "",
                        "comment": (s.get("comment") or s.get("memo") or "")[:200],
                    })
                    # sire_aptitudeにテキスト系メタを登録(未登録時のみ)
                    rec = sires.setdefault(nm, default_rec(nm))
                    for k in ("catchphrase","aim","sire_name_en","birth_year"):
                        if s.get(k) and not rec.get(k): rec[k] = s[k]
                    if ped and not rec["pedigree"]: rec["pedigree"] = ped
                    # 重馬場スライダー(1=得意)を道悪ヒントとして保持
                    if apt_slider.get("baba_pos") is not None:
                        rec["baba_slider"] = apt_slider.get("baba_pos")
                continue

            if img.get("type") not in ("profile","data"): continue
            name = img.get("sire_name")
            if not name: continue
            name = name.strip()
            rec = sires.setdefault(name, {
                "sire_name": name, "rank": None, "sire_name_en": None,
                "birth_year": None, "catchphrase": None,
                "pedigree": {}, "blood_comment": None, "bet_comment": None,
                "aim": None, "cats": defaultdict(dict),
                "source_images": [],
            })
            # メタ(profileページ優先で埋める)
            for k in ("rank","sire_name_en","birth_year","catchphrase","aim",
                      "blood_comment","bet_comment"):
                v = img.get(k)
                if v and not rec.get(k): rec[k] = v
            if img.get("pedigree") and not rec["pedigree"]:
                rec["pedigree"] = img["pedigree"]
            if img.get("file"): rec["source_images"].append(img["file"])

            # data部分を再帰探索
            collected = []
            walk(img.get("data", img), None, collected)
            for cat, surf, key, row in collected:
                place = num(row.get("place_pct"))
                win = num(row.get("win_pct"))
                fuku_ret = num(row.get("fuku_return"))
                tan_ret = num(row.get("tan_return"))
                runs = row.get("runs")
                rentai = num(row.get("place2_pct") or row.get("rentai_pct"))
                long_rows.append({
                    "sire": name, "rank": rec.get("rank"),
                    "category": cat, "surface": surf or "", "key": key,
                    "runs": runs or "", "win_pct": win if win is not None else "",
                    "rentai_pct": rentai if rentai is not None else "",
                    "place_pct": place if place is not None else "",
                    "tan_return": tan_ret if tan_ret is not None else "",
                    "fuku_return": fuku_ret if fuku_ret is not None else "",
                })
                # 正規化保存(複勝率 or 複勝回収率があるもの)
                if place is not None or fuku_ret is not None:
                    skey = f"{surf}/{key}" if surf else key
                    rec["cats"][cat][skey] = {
                        "place_pct": place, "fuku_return": fuku_ret,
                        "win_pct": win, "runs": runs,
                    }

    # --- CSV出力 ---
    TB.mkdir(parents=True, exist_ok=True)
    csv_path = TB / "trueblood_long.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=["sire","rank","category","surface","key",
                                            "runs","win_pct","rentai_pct","place_pct",
                                            "tan_return","fuku_return"])
        w.writeheader()
        for r in sorted(long_rows, key=lambda x:(x["rank"] or 999, x["sire"], x["category"])):
            w.writerow(r)
    print(f"saved: {csv_path} ({len(long_rows)} rows)")

    # --- 名鑑CSV(af1/2/3の複数頭ページ) ---
    if catalog_rows:
        cat_path = TB / "trueblood_catalog.csv"
        fields = ["sire","section","line","country","f_sire","f_dam","f_damsire",
                  "baba_pos","dirt_pos","distance_pos","catchphrase","aim","comment"]
        with open(cat_path, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in sorted(catalog_rows, key=lambda x: x["sire"]):
                w.writerow(r)
        print(f"saved: {cat_path} ({len(catalog_rows)} sires in catalog)")

    # --- 予想取込用 正規化JSON ---
    apt = {}
    for name, rec in sires.items():
        cats = rec["cats"]
        entry = {
            "rank": rec.get("rank"),
            "catchphrase": rec.get("catchphrase"),
            "aim": rec.get("aim"),
            "pedigree": rec.get("pedigree"),
        }
        if rec.get("baba_slider") is not None:
            entry["baba_slider"] = rec["baba_slider"]  # 1=道悪得意 (名鑑由来)
        # 脚質: 複勝率が最も高い脚質
        pace = {}
        for skey, v in cats.get("pace", {}).items():
            k2 = skey.split("/")[-1]
            for raw, norm in PACE_NORM.items():
                if raw in k2:
                    if v["place_pct"] is not None:
                        pace[norm] = max(pace.get(norm,0), v["place_pct"])
        if pace: entry["pace_place"] = pace
        # 馬場
        baba = {}
        for skey, v in cats.get("baba", {}).items():
            k2 = skey.split("/")[-1]
            for raw, norm in BABA_NORM.items():
                if raw in k2 and v["place_pct"] is not None:
                    baba[norm] = max(baba.get(norm,0), v["place_pct"])
        if baba: entry["baba_place"] = baba
        # コース(芝ダ)
        course = {}
        for skey, v in cats.get("course", {}).items():
            if v["place_pct"] is None: continue
            if "芝" in skey: course["芝"] = max(course.get("芝",0), v["place_pct"])
            elif "ダ" in skey: course["ダ"] = max(course.get("ダ",0), v["place_pct"])
        if course: entry["course_place"] = course
        apt[name] = entry

    apt_path = TB / "sire_aptitude.json"
    json.dump(apt, open(apt_path,"w"), ensure_ascii=False, indent=2)
    print(f"saved: {apt_path} ({len(apt)} sires)")

    # サマリ
    n_pace = sum(1 for e in apt.values() if e.get("pace_place"))
    n_baba = sum(1 for e in apt.values() if e.get("baba_place"))
    n_catch = sum(1 for e in apt.values() if e.get("catchphrase"))
    print(f"\n種牡馬: {len(apt)} / 脚質データ有: {n_pace} / 馬場データ有: {n_baba} / 狙い目文有: {n_catch}")

if __name__ == "__main__":
    main()
