#!/usr/bin/env python3
"""出馬表に出る全騎手の通算複勝率(直近5年累計)を取得し jockey_stats.json に保存。
netkeibaは騎手プロフィールに「直近5年成績」テーブルがあり、最初のtableが中央累計成績。
"""
import sys, json, re, time, pathlib, argparse
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"; DATA = ROOT/"data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch(url, key, ttl=86400*30):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def percent_to_float(s):
    s = (s or "").replace("％","").replace("%","").strip()
    try: return float(s)/100
    except: return None

def parse_jockey(jky_id):
    """騎手プロフィールから 通算(中央累計) と直近年(2026)成績を取得。"""
    try:
        html = fetch(f"https://db.netkeiba.com/jockey/{jky_id}/", f"jky_{jky_id}.html")
    except Exception as e:
        return {"error": str(e)}
    soup = BeautifulSoup(html, "lxml")
    out = {"jockey_id": jky_id, "career": None, "recent_year": None}
    # 「直近5年成績」テーブルを探す: 中央累計は最初の race_table_01 のうち
    # ヘッダに「年度 / 順位 / 1着 ...」を含むもの。最初の出現が中央。
    for tbl in soup.select("table.race_table_01"):
        ths = [t.get_text(strip=True) for t in tbl.select("tr")[0].find_all("th")]
        if "勝率" not in ths or "複勝率" not in ths: continue
        rows = tbl.select("tr")
        # 累計行
        for tr in rows[1:]:
            tds = [t.get_text(strip=True) for t in tr.find_all(["td","th"])]
            if not tds: continue
            year_label = tds[0]
            stats = {
                "year": year_label,
                "rides": _to_int(tds[6] if len(tds)>6 else None),
                "win": _to_int(tds[2] if len(tds)>2 else None),
                "win2": _to_int(tds[3] if len(tds)>3 else None),
                "win3": _to_int(tds[4] if len(tds)>4 else None),
                "win_rate": percent_to_float(tds[9] if len(tds)>9 else None),
                "place_rate": percent_to_float(tds[11] if len(tds)>11 else None),
            }
            if year_label == "累計":
                out["career"] = stats
            elif year_label and year_label.isdigit() and out["recent_year"] is None:
                out["recent_year"] = stats   # 一番上の年=最新
        break    # 最初の(=中央累計) tableだけ採用
    return out

def _to_int(s):
    if not s: return None
    s = s.replace(",","").strip()
    try: return int(s)
    except: return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    shutuba = json.loads((DATA/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    # 騎手id収集: shutuba HTMLから jockey/result/recent/{id}/ を逆引きするため、
    # キャッシュHTMLから取り出す
    jky_ids = set()
    name_to_id = {}
    for race in shutuba:
        html_p = CACHE/f"shutuba_{race['race_id']}.html"
        if not html_p.exists(): continue
        html = html_p.read_text(encoding="utf-8")
        for m in re.finditer(r'/jockey/result/recent/(\d+)/"\s+target="_blank"\s+title="([^"]+)"', html):
            jky_ids.add(m.group(1))
            name_to_id[m.group(2)] = m.group(1)
    jky_ids = sorted(jky_ids)
    if args.limit: jky_ids = jky_ids[:args.limit]
    print(f"騎手数: {len(jky_ids)}", file=sys.stderr)

    out = {"_meta":{"date": args.date, "source":"netkeiba直近5年累計"}, "name_to_id": name_to_id, "stats":{}}
    for i, jid in enumerate(jky_ids, 1):
        out["stats"][jid] = parse_jockey(jid)
        if i % 20 == 0 or i == len(jky_ids):
            r = out["stats"][jid]
            c = r.get("career") or {}
            print(f"  {i}/{len(jky_ids)}: id={jid} 累計騎乗={c.get('rides')} 複勝率={c.get('place_rate')}", file=sys.stderr)
    (DATA/"memory").mkdir(exist_ok=True)
    p = DATA/"memory"/"jockey_stats.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
