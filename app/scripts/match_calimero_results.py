#!/usr/bin/env python3
"""calimero_picks.csv に当日の実結果（着順・人気・オッズ）を付加。

入力: notes/calimero_picks.csv
出力: notes/calimero_picks_matched.csv
"""
from __future__ import annotations
import csv, re, time, json, pathlib, sys
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent.parent  # repo root
APP = ROOT/"app"
CACHE = APP/"cache"; CACHE.mkdir(parents=True, exist_ok=True)
SRC = ROOT/"notes"/"calimero_picks.csv"
OUT = ROOT/"notes"/"calimero_picks_matched.csv"
META_OUT = ROOT/"notes"/"calimero_race_meta.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
JO_CODE = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}
JO_CODE_INV = {v:k for k,v in JO_CODE.items()}

def fetch(url, key, ttl=86400*30):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    ct=r.headers.get("Content-Type","").lower()
    if "utf-8" in ct or "utf8" in ct:
        r.encoding="utf-8"
    elif "euc" in ct:
        r.encoding="EUC-JP"
    else:
        g=(r.apparent_encoding or "").lower()
        r.encoding="utf-8" if "utf" in g else "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def race_ids_for_date(date_str):
    html = fetch(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}",
                 f"racelist_{date_str}.html")
    return sorted(set(re.findall(r"race_id=(\d{12})", html)))

def parse_result(race_id):
    html = fetch(f"https://race.netkeiba.com/race/result.html?race_id={race_id}",
                 f"result_{race_id}.html")
    soup = BeautifulSoup(html, "lxml")
    # Race meta
    name_el = soup.select_one(".RaceList_Item02 .RaceName") or soup.select_one(".RaceName")
    race_name = name_el.get_text(strip=True) if name_el else ""
    data01 = soup.select_one(".RaceList_Item02 .RaceData01") or soup.select_one(".RaceData01")
    course_text = data01.get_text(" ", strip=True) if data01 else ""
    m_surface = re.search(r"(芝|ダ|障)\s*(\d+)m", course_text)
    surface, distance = (m_surface.group(1), int(m_surface.group(2))) if m_surface else (None, None)
    page = soup.get_text(" ", strip=True)
    mb = re.search(r"馬場\s*[:：]?\s*(良|稍重|稍|重|不良)", page)
    baba = mb.group(1) if mb else None
    mw = re.search(r"天候\s*[:：]?\s*(晴|曇|小雨|雨|雪)", page)
    weather = mw.group(1) if mw else None

    horses = []
    tbl = soup.select_one("table.RaceTable01") or soup.select_one("table.ResultsTable")
    if tbl:
        for tr in tbl.select("tr"):
            tds = tr.find_all("td")
            if len(tds) < 8: continue
            try:
                finish = tds[0].get_text(strip=True)
                umaban = tds[2].get_text(strip=True)
                name_a = tds[3].find("a")
                name = name_a.get_text(strip=True) if name_a else tds[3].get_text(strip=True)
                popular = None; odds = None
                for td in tds:
                    t = td.get_text(strip=True)
                    if re.fullmatch(r"\d+", t) and len(t) <= 2 and popular is None and t != umaban and t != finish:
                        popular = t
                    if re.fullmatch(r"\d+\.\d", t) and odds is None:
                        odds = t
                if not (finish.isdigit() and umaban.isdigit()): continue
                horses.append({"finish": int(finish), "umaban": int(umaban), "name": name,
                               "popularity": int(popular) if popular else None,
                               "odds": float(odds) if odds else None})
            except Exception:
                continue
    horses.sort(key=lambda r: r["finish"])
    return {"race_id": race_id, "race_name": race_name, "surface": surface, "distance": distance,
            "baba": baba, "weather": weather, "horses": horses}

def build_race_index(date_str):
    """Return dict (track, race_no) -> race_id, plus race meta per id."""
    ids = race_ids_for_date(date_str)
    idx = {}
    metas = {}
    for rid in ids:
        track = JO_CODE.get(rid[4:6], "")
        try:
            rn = int(rid[10:12])
        except ValueError:
            continue
        idx[(track, rn)] = rid
    return idx, metas

def main():
    rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
    # Group dates
    dates = sorted({r["race_date"] for r in rows})
    print(f"Picks: {len(rows)}, Dates: {len(dates)}", file=sys.stderr)
    # Build per-date race index lazily
    race_idx_by_date = {}
    result_cache = {}
    meta_out = {}
    out_rows = []
    for i, r in enumerate(rows):
        d = r["race_date"]
        track = r["course"]; rn = int(r["race"])
        if d not in race_idx_by_date:
            try:
                race_idx_by_date[d], _ = build_race_index(d)
            except Exception as e:
                print(f"  ! race_list fetch failed {d}: {e}", file=sys.stderr)
                race_idx_by_date[d] = {}
        rid = race_idx_by_date[d].get((track, rn))
        finish = pop = odds = res_name = surface = distance = baba = None
        if rid:
            if rid not in result_cache:
                try:
                    result_cache[rid] = parse_result(rid)
                except Exception as e:
                    print(f"  ! result fetch failed {rid}: {e}", file=sys.stderr)
                    result_cache[rid] = None
            res = result_cache[rid]
            if res:
                surface = res["surface"]; distance = res["distance"]; baba = res["baba"]
                meta_out[rid] = {k: res[k] for k in ("race_name","surface","distance","baba","weather")}
                target = next((h for h in res["horses"] if h["umaban"] == int(r["umaban"])), None)
                if target:
                    finish = target["finish"]; pop = target["popularity"]; odds = target["odds"]
                    res_name = target["name"]
        new = dict(r)
        new.update({
            "race_id": rid or "",
            "surface": surface or "",
            "distance": distance or "",
            "baba": baba or "",
            "actual_finish": finish if finish is not None else "",
            "actual_pop": pop if pop is not None else "",
            "actual_odds": odds if odds is not None else "",
            "actual_name": res_name or "",
        })
        out_rows.append(new)
        if (i+1) % 200 == 0:
            print(f"  ..{i+1}/{len(rows)}", file=sys.stderr)
    fields = list(rows[0].keys()) + ["race_id","surface","distance","baba","actual_finish","actual_pop","actual_odds","actual_name"]
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in out_rows: w.writerow(r)
    META_OUT.write_text(json.dumps(meta_out, ensure_ascii=False, indent=1), encoding="utf-8")
    matched = sum(1 for r in out_rows if r["actual_finish"] != "")
    print(f"Output: {OUT}  matched={matched}/{len(out_rows)}", file=sys.stderr)

if __name__ == "__main__":
    main()
