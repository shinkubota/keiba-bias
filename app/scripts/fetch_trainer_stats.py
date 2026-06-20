#!/usr/bin/env python3
"""調教師通算複勝率(直近5年累計)取得 → data/memory/trainer_stats.json
"""
import sys, json, re, time, pathlib, argparse
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"; DATA = ROOT/"data"; MEM = DATA/"memory"; MEM.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch(url, key, ttl=86400*30):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
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

def _to_int(s):
    if not s: return None
    s = s.replace(",","").strip()
    try: return int(s)
    except: return None

def pct(s):
    s = (s or "").replace("％","").replace("%","").strip()
    try: return float(s)/100
    except: return None

def parse_trainer(tid):
    try:
        html = fetch(f"https://db.netkeiba.com/trainer/{tid}/", f"trainer_{tid}.html")
    except Exception as e:
        return {"error": str(e)}
    soup = BeautifulSoup(html, "lxml")
    out = {"trainer_id": tid, "career": None, "recent_year": None}
    for tbl in soup.select("table.race_table_01"):
        ths = [t.get_text(strip=True) for t in tbl.select("tr")[0].find_all("th")]
        if "勝率" not in ths or "複勝率" not in ths: continue
        for tr in tbl.select("tr")[1:]:
            tds = [t.get_text(strip=True) for t in tr.find_all(["td","th"])]
            if not tds: continue
            yr = tds[0]
            stats = {"year": yr,
                     "win": _to_int(tds[2] if len(tds)>2 else None),
                     "win2": _to_int(tds[3] if len(tds)>3 else None),
                     "win3": _to_int(tds[4] if len(tds)>4 else None),
                     "runs": _to_int(tds[6] if len(tds)>6 else None),
                     "win_rate": pct(tds[9] if len(tds)>9 else None),
                     "place_rate": pct(tds[11] if len(tds)>11 else None)}
            if yr == "累計": out["career"] = stats
            elif yr.isdigit() and not out["recent_year"]: out["recent_year"] = stats
        break
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    shutuba = json.loads((DATA/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    # 厩舎id収集: shutubaキャッシュHTMLから /trainer/result/recent/{id}/ を逆引き
    tids = set(); name_to_id = {}
    for race in shutuba:
        html_p = CACHE/f"shutuba_{race['race_id']}.html"
        if not html_p.exists(): continue
        h = html_p.read_text(encoding="utf-8")
        for m in re.finditer(r'/trainer/result/recent/(\d+)/"\s+target="_blank"\s+title="([^"]+)"', h):
            tids.add(m.group(1)); name_to_id[m.group(2)] = m.group(1)
    tids = sorted(tids)
    if args.limit: tids = tids[:args.limit]
    print(f"厩舎数: {len(tids)}", file=sys.stderr)
    out = {"_meta":{"date":args.date,"source":"netkeiba直近5年累計"},
           "name_to_id": name_to_id, "stats": {}}
    for i, tid in enumerate(tids, 1):
        out["stats"][tid] = parse_trainer(tid)
        if i % 20 == 0 or i == len(tids):
            c = (out["stats"][tid].get("career") or {})
            print(f"  {i}/{len(tids)}: id={tid} 累計騎乗={c.get('runs')} 複勝率={c.get('place_rate')}", file=sys.stderr)
    p = MEM/"trainer_stats.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
