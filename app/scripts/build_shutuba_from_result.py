#!/usr/bin/env python3
"""過去日のshutubaが取得できない問題に対し、db.netkeiba.com/race/{race_id}/ の結果ページから
逆向きにshutuba_*.jsonを生成する。馬IDが結果ページに含まれるのでhorse取得にも繋げられる。

Usage:
  python3 build_shutuba_from_result.py YYYYMMDD
"""
import sys, json, re, time, pathlib, argparse
import requests
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"; DATA = ROOT/"data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
JO_CODE = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}

def fetch(url, key, ttl=86400*30):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def race_ids_for_date(date_str):
    """その日に開催された race_id 一覧をrace_list_sub から（過去日も生きていることが多い）"""
    html = fetch(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}",
                 f"racelist_{date_str}.html", ttl=86400*30)
    return sorted(set(re.findall(r"race_id=(\d{12})", html)))

def parse_db_race(race_id):
    """db.netkeiba.com/race/{rid}/ の結果テーブルから出走馬を逆生成。"""
    html = fetch(f"https://db.netkeiba.com/race/{race_id}/", f"dbrace_{race_id}.html")
    soup = BeautifulSoup(html, "lxml")
    # レース情報: dl.racedataに「3歳未勝利 / ダ右1700m / 天候 : 晴 / ダート : 良 / 発走 : 09:45」
    rdata = soup.select_one("dl.racedata")
    info = rdata.get_text(" ", strip=True) if rdata else ""
    h1 = (rdata.find("h1") if rdata else None) or soup.find("h1")
    race_name_raw = h1.get_text(" ", strip=True) if h1 else ""
    # h1には番号も入る "1 R 3歳未勝利" → "3歳未勝利"だけ
    race_name = re.sub(r"^\d+\s*R\s*", "", race_name_raw)
    surface = distance = None
    m = re.search(r"(芝|ダ|障)[^\d]{0,3}(\d{3,4})m", info)
    if m: surface, distance = m.group(1), int(m.group(2))
    is_outer = "外" in info
    is_inner = "内" in info and not is_outer
    # 馬場: 「芝 : 良」「ダート : 良」両対応
    mb = re.search(r"(?:芝|ダート|障)\s*[:：]\s*(良|稍重|稍|重|不良)", info)
    baba = mb.group(1) if mb else None
    mw = re.search(r"天候\s*[:：]\s*(晴|曇|小雨|雨|雪)", info)
    weather = mw.group(1) if mw else None

    horses = []
    tbl = soup.select_one("table.race_table_01")
    if tbl:
        for tr in tbl.select("tr")[1:]:
            tds = tr.find_all("td")
            if len(tds) < 6: continue
            try:
                waku = tds[1].get_text(strip=True)
                umaban = tds[2].get_text(strip=True)
                a = tds[3].find("a")
                name = a.get_text(strip=True) if a else ""
                href = a.get("href","") if a else ""
                m_hid = re.search(r"/horse/(\d+)", href)
                hid = m_hid.group(1) if m_hid else ""
                # 性齢・斤量
                sex_age = tds[4].get_text(strip=True) if len(tds)>4 else ""
                kg = tds[5].get_text(strip=True) if len(tds)>5 else ""
                # 騎手
                jky_a = tds[6].find("a") if len(tds)>6 else None
                jky = jky_a.get_text(strip=True) if jky_a else ""
                if not umaban.isdigit(): continue
                horses.append({
                    "waku": waku, "umaban": umaban, "name": name,
                    "horse_id": hid, "sex_age": sex_age,
                    "jockey": jky, "jockey_weight": kg.replace("(","").split(")")[0],
                    "odds":"", "popularity":"",
                })
            except Exception:
                continue
    jo = JO_CODE.get(race_id[4:6], "")
    rn = int(race_id[10:12])
    return {
        "race_id": race_id, "track": jo, "race_no": rn, "race_name": race_name,
        "surface": surface, "distance": distance,
        "variant": "外" if is_outer else ("内" if is_inner else None),
        "course_text": info, "weather": weather, "baba": baba, "cushion": None,
        "horses": horses,
    }

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("date"); args = ap.parse_args()
    ids = race_ids_for_date(args.date)
    print(f"[{args.date}] {len(ids)} races", file=sys.stderr)
    out = []
    for rid in ids:
        r = parse_db_race(rid)
        out.append(r)
        print(f"  {r['track']}{r['race_no']:>2}R {r['surface']}{r['distance']}m  {len(r['horses'])}頭", file=sys.stderr)
    p = DATA/f"shutuba_{args.date}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
