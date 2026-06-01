#!/usr/bin/env python3
"""種牡馬の詳細プロフィール(累計成績/年度別/血統)をnetkeibaから取得し
data/memory/sire_profiles/<sire_id>.json にキャッシュ保存。
"""
import sys, json, re, time, pathlib, argparse
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"
PROFILE_DIR = ROOT/"data"/"memory"/"sire_profiles"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch(url, key, ttl=86400*7):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def _to_int(s):
    if not s: return None
    s = s.replace(",","").replace("‐","").strip()
    try: return int(s)
    except: return None

def parse_sire_results(sire_id):
    """sire成績ページ: 累計・年度別の出走/勝利/重賞/特別/平場/芝/ダ + EI"""
    html = fetch(f"https://db.netkeiba.com/horse/sire/{sire_id}/", f"sire_{sire_id}.html")
    soup = BeautifulSoup(html, "lxml")
    out = {"sire_id": sire_id, "years": [], "summary": {}}
    name_el = soup.select_one("h1") or soup.title
    if name_el: out["name"] = name_el.get_text(strip=True).split("の")[0].split("|")[0].strip()
    tbl = soup.select_one("table.race_table_01")
    if not tbl: return out
    rows = tbl.select("tr")
    if len(rows) < 3: return out
    # tdsを横配列で取得 — 列構造:
    # 年度, 順位, 出走頭数, 勝馬頭数, 出走回数, 勝利回数, 重賞出走, 重賞勝利, 特別出走, 特別勝利,
    # 平場出走, 平場勝利, 芝出走, 芝勝利, ダート出走, ダート勝利, 勝馬率, EI, 入着賞金, 平均距離芝, 平均距離ダ, 代表馬
    for tr in rows[2:8]:                # 1行目=サブヘッダ, 2行目=累計, 以降年度
        tds = [t.get_text(" ", strip=True) for t in tr.find_all(["td","th"])]
        if len(tds) < 18: continue
        rec = {
            "year": tds[0],
            "rank": tds[1],
            "starters": _to_int(tds[2]),
            "winners": _to_int(tds[3]),
            "races": _to_int(tds[4]),
            "wins": _to_int(tds[5]),
            "g_races": _to_int(tds[6]), "g_wins": _to_int(tds[7]),
            "sp_races": _to_int(tds[8]), "sp_wins": _to_int(tds[9]),
            "flat_races": _to_int(tds[10]), "flat_wins": _to_int(tds[11]),
            "turf_races": _to_int(tds[12]), "turf_wins": _to_int(tds[13]),
            "dirt_races": _to_int(tds[14]), "dirt_wins": _to_int(tds[15]),
            "win_rate_horse": tds[16],     # %
            "EI": tds[17],
            "prize": tds[18] if len(tds)>18 else None,
            "avg_dist_turf": tds[19] if len(tds)>19 else None,
            "avg_dist_dirt": tds[20] if len(tds)>20 else None,
            "rep_horse": tds[21] if len(tds)>21 else None,
        }
        if rec["year"] == "累計": out["summary"] = rec
        else: out["years"].append(rec)
    return out

def parse_pedigree(sire_id):
    """血統表から父/母父/系統を取得。netkeiba blood_tableベース。"""
    html = fetch(f"https://db.netkeiba.com/horse/ped/{sire_id}/", f"siredetail_{sire_id}.html")
    soup = BeautifulSoup(html, "lxml")
    out = {"father": None, "mother_father": None, "lineage_marker": None}
    tbl = soup.select_one("table.blood_table")
    if not tbl: return out
    big = [td for td in tbl.find_all("td") if td.get("rowspan") == "16"]
    if len(big) >= 1:
        a = big[0].find("a")
        if a: out["father"] = a.get_text(strip=True).split("\n")[0]
    if len(big) >= 2:
        mtr = big[1].find_parent("tr")
        sib = mtr.find_all("td", recursive=False)
        passed = False
        for td in sib:
            if td is big[1]: passed = True; continue
            if passed and td.get("rowspan") == "8":
                a = td.find("a")
                if a: out["mother_father"] = a.get_text(strip=True).split("\n")[0]
                break
    # 系統名（血統表の脚注に「ストームバード系」など）
    txt = tbl.get_text(" ", strip=True)
    m = re.search(r"([ぁ-ヿ一-龥・ー]+系)", txt)
    if m: out["lineage_marker"] = m.group(1)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sire_id", help="netkeiba horse_id (10桁)")
    ap.add_argument("--name", default="", help="表示名(キャッシュ用)")
    args = ap.parse_args()
    sid = args.sire_id
    results = parse_sire_results(sid)
    ped = parse_pedigree(sid)
    out = {"results": results, "pedigree": ped, "fetched_at": time.strftime("%Y-%m-%d")}
    if args.name and not results.get("name"): out["results"]["name"] = args.name
    p = PROFILE_DIR/f"{sid}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {p}", file=sys.stderr)
    print(json.dumps({k:v for k,v in out["results"].items() if k!="years"}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
