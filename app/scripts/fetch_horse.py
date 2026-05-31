#!/usr/bin/env python3
"""shutuba_{date}.json に登場する各馬の血統(父・母父)と直近5走を取得し
horses_{date}.json にマージ保存。
"""
import sys, json, time, re, pathlib, argparse
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT / "cache"
DATA = ROOT / "data"

def fetch(url, key, ttl=86400):
    p = CACHE / key
    if p.exists() and (time.time() - p.stat().st_mtime) < ttl:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.4)
    return r.text

def parse_pedigree(horse_id):
    """父と母父を返す。"""
    try:
        html = fetch(f"https://db.netkeiba.com/horse/ped/{horse_id}/", f"ped_{horse_id}.html")
    except Exception as e:
        return {"sire": None, "broodmare_sire": None, "error": str(e)}
    soup = BeautifulSoup(html, "lxml")
    tbl = soup.select_one("table.blood_table")
    if not tbl:
        return {"sire": None, "broodmare_sire": None}

    # rowspan=16のtdが2つ: 父(最初) と 母(2番目)
    big = [td for td in tbl.find_all("td") if td.get("rowspan") == "16"]
    sire = mother = None
    if len(big) >= 1:
        a = big[0].find("a")
        if a: sire = a.get_text(strip=True).split("\n")[0]
    if len(big) >= 2:
        a = big[1].find("a")
        if a: mother = a.get_text(strip=True).split("\n")[0]

    # 母父: 母tdの直後に来る兄弟tdで rowspan=8
    broodmare_sire = None
    if len(big) >= 2:
        # 母のtdが含まれるrowの次のtd(rowspan=8)を取りに行く
        mother_tr = big[1].parent
        sibling_tds = mother_tr.find_all("td", recursive=False)
        # 母td以降でrowspan=8を探す
        found_mother = False
        for td in sibling_tds:
            if td is big[1]:
                found_mother = True; continue
            if found_mother and td.get("rowspan") == "8":
                a = td.find("a")
                if a: broodmare_sire = a.get_text(strip=True).split("\n")[0]
                break

    return {"sire": sire, "mother": mother, "broodmare_sire": broodmare_sire}

def parse_recent_races(horse_id, n=5):
    """直近n走を返す。"""
    try:
        html = fetch(f"https://db.netkeiba.com/horse/result/{horse_id}/", f"res_{horse_id}.html")
    except Exception as e:
        return [{"error": str(e)}]
    soup = BeautifulSoup(html, "lxml")
    tbl = soup.select_one("table.db_h_race_results")
    if not tbl: return []
    races = []
    for tr in tbl.select("tbody tr")[:n]:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 15: continue
        try:
            date = tds[0].get_text(strip=True)
            kaisai = tds[1].get_text(strip=True)  # 例: 1小倉9 → 1回小倉9日目
            rname = tds[4].get_text(strip=True)
            atama = tds[6].get_text(strip=True)
            uma   = tds[8].get_text(strip=True)
            chaku = tds[11].get_text(strip=True)
            jky   = tds[12].get_text(strip=True) if len(tds) > 12 else ""
            dist  = tds[14].get_text(strip=True)  # 例: 芝1200
            baba  = tds[16].get_text(strip=True) if len(tds) > 16 else ""
        except Exception:
            continue
        # クラス推定: G1/G2/G3/OP/3勝/2勝/1勝/未勝利/新馬
        cls = None
        for tag, key in [("(G1)","G1"),("(G2)","G2"),("(G3)","G3"),
                          ("(L)","L"),("(OP)","OP")]:
            if tag in rname: cls = key; break
        if cls is None:
            for kw, key in [("新馬","新馬"),("未勝利","未勝利"),
                             ("3勝クラス","3勝"),("2勝クラス","2勝"),("1勝クラス","1勝"),
                             ("オープン","OP"),("障害","障害")]:
                if kw in rname: cls = key; break
        # 上がり3F + 通過順: 通過は "1-1" "5-3-3" "10-10-9-8" のような形式
        agari = None
        passing = None
        for td in tds:
            t = td.get_text(strip=True)
            if re.fullmatch(r"\d{2}\.\d-\d{2}\.\d", t):
                agari = t.split("-")[-1]
            elif re.fullmatch(r"\d{1,2}(-\d{1,2}){0,3}", t):
                passing = t
        # 開催から場名を抽出
        m = re.match(r"(\d+)?(札幌|函館|福島|新潟|東京|中山|中京|京都|阪神|小倉)", kaisai)
        venue = m.group(2) if m else ""
        races.append({
            "date": date, "venue": venue, "kaisai": kaisai, "race_name": rname,
            "field_size": atama, "umaban": uma, "finish": chaku,
            "distance_text": dist, "track_cond": baba, "agari3f": agari, "passing": passing,
            "jockey": jky, "race_class": cls,
        })
    return races

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--limit", type=int, default=0, help="0=全頭")
    args = ap.parse_args()

    shutuba = json.loads((DATA/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    horse_ids = []
    for race in shutuba:
        for h in race["horses"]:
            if h["horse_id"] and h["horse_id"] not in horse_ids:
                horse_ids.append(h["horse_id"])
    if args.limit: horse_ids = horse_ids[:args.limit]
    print(f"取得対象: {len(horse_ids)}頭", file=sys.stderr)

    out = {}
    for i, hid in enumerate(horse_ids, 1):
        ped = parse_pedigree(hid)
        races = parse_recent_races(hid)
        out[hid] = {"pedigree": ped, "recent": races}
        if i % 10 == 0 or i == len(horse_ids):
            print(f"  {i}/{len(horse_ids)}: 父={ped.get('sire')} 母父={ped.get('broodmare_sire')} 前走={len(races)}件", file=sys.stderr)

    p = DATA/f"horses_{args.date}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {p}", file=sys.stderr)

if __name__ == "__main__":
    main()
