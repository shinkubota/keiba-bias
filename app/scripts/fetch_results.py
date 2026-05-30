#!/usr/bin/env python3
"""指定日の全レース結果（着順）をnetkeibaから取得し results_YYYYMMDD.json に保存。"""
import sys, json, re, time, pathlib, argparse
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"; DATA = ROOT/"data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch(url, key, ttl=86400):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def parse_result(race_id):
    html = fetch(f"https://race.netkeiba.com/race/result.html?race_id={race_id}",
                 f"result_{race_id}.html")
    soup = BeautifulSoup(html, "lxml")
    tbl = soup.select_one("table.RaceTable01") or soup.select_one("table.ResultsTable")
    if not tbl: return {"race_id": race_id, "horses": []}
    rows = []
    for tr in tbl.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 8: continue
        try:
            finish = tds[0].get_text(strip=True)  # 着順
            waku   = tds[1].get_text(strip=True)
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
            rows.append({"finish": int(finish), "umaban": int(umaban),
                         "name": name, "popularity": popular, "odds": odds})
        except Exception:
            continue
    rows.sort(key=lambda r: r["finish"])
    return {"race_id": race_id, "horses": rows}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date"); args = ap.parse_args()
    shutuba = json.loads((DATA/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    out = []
    for r in shutuba:
        res = parse_result(r["race_id"])
        res["track"] = r["track"]; res["race_no"] = r["race_no"]; res["race_name"] = r["race_name"]
        out.append(res)
        print(f"  {r['track']}{r['race_no']:>2}R 着順入手: {len(res['horses'])}頭", file=sys.stderr)
    (DATA/f"results_{args.date}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: results_{args.date}.json", file=sys.stderr)

if __name__ == "__main__":
    main()
