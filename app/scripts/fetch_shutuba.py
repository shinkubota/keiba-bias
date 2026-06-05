#!/usr/bin/env python3
"""netkeibaから指定日の全レース出馬表を取得しJSONで保存。
Usage: python3 fetch_shutuba.py YYYYMMDD [--tracks 東京,京都]
"""
import sys, os, re, json, time, argparse, pathlib
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
JO_CODE = {"01":"札幌","02":"函館","03":"福島","04":"新潟","05":"東京","06":"中山","07":"中京","08":"京都","09":"阪神","10":"小倉"}
CACHE = pathlib.Path(__file__).parent.parent / "cache"
DATA  = pathlib.Path(__file__).parent.parent / "data"
CACHE.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)

def fetch(url, cache_key):
    p = CACHE / cache_key
    if p.exists() and (time.time() - p.stat().st_mtime) < 3600:
        return p.read_text(encoding="utf-8")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.encoding = "EUC-JP"
    p.write_text(r.text, encoding="utf-8")
    return r.text

def race_ids_for_date(date_str):
    html = fetch(f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date_str}",
                 f"racelist_{date_str}.html")
    ids = sorted(set(re.findall(r"race_id=(\d{12})", html)))
    return ids

def parse_shutuba(race_id):
    html = fetch(f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}",
                 f"shutuba_{race_id}.html")
    soup = BeautifulSoup(html, "lxml")

    name_el = soup.select_one(".RaceList_Item02 .RaceName")
    race_name = name_el.get_text(strip=True) if name_el else ""

    data01 = soup.select_one(".RaceList_Item02 .RaceData01")
    course_text = data01.get_text(" ", strip=True) if data01 else ""
    m = re.search(r"(芝|ダ|障)\s*(\d+)m", course_text)
    surface, distance = (m.group(1), int(m.group(2))) if m else (None, None)
    is_outer = "外" in course_text  # 京都/新潟など外回り
    is_inner = "内" in course_text and not is_outer

    # 天候・馬場・クッション値（当日のみ表示。発走前はNoneのことが多い）
    page_text = soup.get_text(" ", strip=True)
    mw = re.search(r"天候\s*[:：]?\s*(晴|曇|小雨|雨|雪)", page_text)
    mb = re.search(r"馬場\s*[:：]?\s*(良|稍重|稍|重|不良)", page_text)
    mc = re.search(r"クッション値\s*[:：]?\s*(\d+\.?\d*)", page_text)
    weather = mw.group(1) if mw else None
    baba = mb.group(1) if mb else None
    cushion = mc.group(1) if mc else None

    jo = JO_CODE.get(race_id[4:6], "")
    rn = int(race_id[10:12])

    horses = []
    for tr in soup.select("tr.HorseList"):
        # 枠順確定後はclassが Waku→Waku1, Umaban→Umaban3 のように
        # 枠/馬番がclass名に付く。前方一致で両対応する。
        waku  = tr.select_one('td[class^="Waku"]')
        umaban= tr.select_one('td[class^="Umaban"]')
        # 馬名: 枠順前(.HorseName)と確定後(.Horse_Name)の両レイアウト対応
        name  = (tr.select_one(".HorseName a") or tr.select_one(".Horse_Name a")
                 or tr.select_one("a[href*='/horse/']"))
        barei = tr.select_one(".Barei")
        jky   = tr.select_one(".Jockey a")
        if not name: continue
        href = name.get("href","")
        horse_id = re.search(r"/horse/(\d+)", href)
        # 末尾の空テンプレ行対策: 馬番が空の行はゴースト→除外
        if not (umaban and umaban.get_text(strip=True)):
            continue

        # 斤量: Bareiセルの次のtd(class="Txt_C")に "52.0" のように入る
        jockey_weight = ""
        if barei:
            sib = barei.find_next_sibling("td")
            if sib:
                mjw = re.fullmatch(r"\d{2}\.\d", sib.get_text(strip=True))
                if mjw: jockey_weight = mjw.group(0)

        # 単勝オッズ: id^="odds-" の span。前日は "---.-" で未確定。
        odds = ""
        odds_el = tr.select_one('[id^="odds-"]')
        if odds_el:
            ot = odds_el.get_text(strip=True)
            if re.fullmatch(r"\d+\.\d", ot): odds = ot

        # 人気: id^="ninki-"。前日は "**" で未確定。
        pop = ""
        pop_el = tr.select_one('[id^="ninki-"]')
        if pop_el:
            pt = pop_el.get_text(strip=True)
            if pt.isdigit(): pop = pt

        horses.append({
            "waku":   waku.get_text(strip=True) if waku else "",
            "umaban": umaban.get_text(strip=True) if umaban else "",
            "name":   name.get_text(strip=True),
            "horse_id": horse_id.group(1) if horse_id else "",
            "sex_age": barei.get_text(strip=True) if barei else "",
            "jockey": jky.get_text(strip=True) if jky else "",
            "jockey_weight": jockey_weight,
            "odds": odds,
            "popularity": pop,
        })

    return {
        "race_id": race_id,
        "track": jo,
        "race_no": rn,
        "race_name": race_name,
        "surface": surface,
        "distance": distance,
        "variant": "外" if is_outer else ("内" if is_inner else None),
        "course_text": course_text,
        "weather": weather,
        "baba": baba,
        "cushion": cushion,
        "horses": horses,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="YYYYMMDD")
    ap.add_argument("--tracks", default="札幌,函館,福島,新潟,東京,中山,中京,京都,阪神,小倉",
                    help="対象場(カンマ区切り)。デフォルト中央10場全て＝その日の開催場を自動取得")
    args = ap.parse_args()
    tracks = set(args.tracks.split(","))

    ids = race_ids_for_date(args.date)
    print(f"[{args.date}] {len(ids)} races found", file=sys.stderr)
    out = []
    for rid in ids:
        jo = JO_CODE.get(rid[4:6], "")
        if jo not in tracks: continue
        r = parse_shutuba(rid)
        out.append(r)
        print(f"  {r['track']}{r['race_no']:>2}R {r['surface']}{r['distance']}m  {len(r['horses'])}頭  {r['race_name']}", file=sys.stderr)
        time.sleep(0.3)

    outpath = DATA / f"shutuba_{args.date}.json"

    # --- データ保全: 既存の方が良ければ上書きしない ---
    # netkeibaは未来日付や枠順前に3頭プレースホルダーを返すことがあるため、
    # レース毎に「頭数が多い／枠番が埋まっている」方を採用してマージする。
    def quality(race):
        # 枠番が埋まった有効頭数を主基準に（ゴースト混入の多い側を優先しない）
        valid = sum(1 for h in race["horses"] if h.get("umaban") and h.get("horse_id"))
        return (valid, len(race["horses"]))
    if outpath.exists():
        try:
            prev = json.loads(outpath.read_text(encoding="utf-8"))
            best = {r["race_id"]: r for r in prev}   # 既存を土台に和集合でマージ
            for r in out:
                old = best.get(r["race_id"])
                if old is None or quality(r) >= quality(old):
                    best[r["race_id"]] = r
                else:
                    print(f"  keep existing (better): {r['track']}{r['race_no']}R "
                          f"{quality(old)} > {quality(r)}", file=sys.stderr)
            out = sorted(best.values(), key=lambda r: r["race_id"])
        except Exception as e:
            print(f"  merge skipped: {e!r}", file=sys.stderr)

    outpath.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved: {outpath}", file=sys.stderr)

if __name__ == "__main__":
    main()
