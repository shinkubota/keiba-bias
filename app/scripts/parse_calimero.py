#!/usr/bin/env python3
"""カリメロ@穴馬オタクの購入記事をパースして pick リストCSVを生成。

入力: notes/calimero_articles.md  (build_calimero側で取得済み)
出力: notes/calimero_picks.csv

抽出ルール:
- ## 見出し行で記事区切り。タイトル先頭の MMDD と本文中の場名候補からレース日 YYYYMMDD を決定。
- 【場名】セクション → 場
- 「<数字>R」行 → R番号
- 「◎<馬番><馬名>(<pop>番人気想定)」 → type=◎ pick
- 「単穴は…<馬番><馬名>(<pop>番人気想定)」 → type=単穴 pick (簡易)
- 「紐穴は…1.2.13」のような数字列 → type=紐 pick (馬番のみ。馬名なし)
- pickの直後のコメント数行を comment として保持
"""
from __future__ import annotations
import re, csv, pathlib, sys, json
from typing import List, Dict, Optional

ROOT = pathlib.Path(__file__).parent.parent.parent
SRC = ROOT/"notes"/"calimero_articles.md"
OUT_CSV = ROOT/"notes"/"calimero_picks.csv"

COURSE_ORDER = ["東京","京都","中山","阪神","中京","新潟","福島","札幌","函館","小倉"]
COURSE_RE = re.compile(r"^【(" + "|".join(COURSE_ORDER) + r")】")
RACE_RE = re.compile(r"^(\d{1,2})R\b")
# ◎マークの後に馬番、馬名、(人気想定)
HONMEI_RE = re.compile(r"◎\s*(\d{1,2})\s*([^\s()\[\]【】]+?)\s*[\(（]\s*(\d{1,2})\s*番人気想定")
# 単穴: 行頭近くから単穴/穴・大穴
TANANA_RE = re.compile(r"(?:単穴|大穴)[^◎]{0,40}?(\d{1,2})\s*([^\s()\[\]【】]+?)\s*[\(（]\s*(\d{1,2})\s*番人気想定")
# 紐: 「紐(穴)?は 1.2.13」  「ヒモ評価まで」など 数字列
HIMO_LIST_RE = re.compile(r"(?:紐穴?|ヒモ)(?:なら|は|評価)?[^\n]{0,15}?((?:\d{1,2}[\.\・\,、\s]?){1,}\d{1,2}|\d{1,2})")
# 他候補/穴候補: のリストは厳密には pick ではないので拾わない（紐ではないため）

DATE_TITLE_RE = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s+(\d{4})穴馬リスト")

def split_articles(text: str) -> List[Dict]:
    arts: List[Dict] = []
    cur: Optional[Dict] = None
    for line in text.splitlines():
        m = DATE_TITLE_RE.match(line)
        if m:
            if cur: arts.append(cur)
            publish_date, mmdd = m.group(1), m.group(2)
            # race date = MMDD with year inferred from publish_date
            py, pm, pd = int(publish_date[:4]), int(publish_date[5:7]), int(publish_date[8:10])
            mm, dd = int(mmdd[:2]), int(mmdd[2:])
            ry = py
            # if publish month is Dec (12) and mmdd is Jan (01) → next year
            if pm == 12 and mm == 1: ry = py + 1
            # if publish month is Jan and mmdd is Dec (rare wrap) → prev year
            if pm == 1 and mm == 12: ry = py - 1
            race_date = f"{ry:04d}{mm:02d}{dd:02d}"
            cur = {"publish_date": publish_date, "race_date": race_date, "lines": []}
            continue
        if cur is not None:
            cur["lines"].append(line)
    if cur: arts.append(cur)
    return arts

def parse_article(art: Dict) -> List[Dict]:
    picks: List[Dict] = []
    course: Optional[str] = None
    race: Optional[int] = None
    # We'll accumulate comment lines per pick.
    last_pick_idx: Optional[int] = None
    for line in art["lines"]:
        s = line.strip()
        if not s:
            last_pick_idx = None
            continue
        m = COURSE_RE.match(s)
        if m:
            course = m.group(1); race = None; last_pick_idx = None; continue
        m = RACE_RE.match(s)
        if m:
            race = int(m.group(1)); last_pick_idx = None; continue
        if course is None or race is None:
            continue
        # ◎ 本命
        m = HONMEI_RE.search(s)
        if m:
            picks.append({
                "race_date": art["race_date"], "publish_date": art["publish_date"],
                "course": course, "race": race, "type": "◎",
                "umaban": int(m.group(1)), "name": m.group(2),
                "popularity_est": int(m.group(3)), "comment": "",
            })
            last_pick_idx = len(picks) - 1
            continue
        # 単穴/大穴 with horse num + name + pop
        m = TANANA_RE.search(s)
        if m:
            picks.append({
                "race_date": art["race_date"], "publish_date": art["publish_date"],
                "course": course, "race": race, "type": "単穴",
                "umaban": int(m.group(1)), "name": m.group(2),
                "popularity_est": int(m.group(3)), "comment": "",
            })
            last_pick_idx = len(picks) - 1
            continue
        # 紐 with horse num list
        m = HIMO_LIST_RE.search(s)
        if m:
            nums_str = m.group(1)
            nums = [int(x) for x in re.findall(r"\d{1,2}", nums_str)]
            for n in nums:
                picks.append({
                    "race_date": art["race_date"], "publish_date": art["publish_date"],
                    "course": course, "race": race, "type": "紐",
                    "umaban": n, "name": "", "popularity_est": None, "comment": s,
                })
            last_pick_idx = None
            continue
        # accumulate comment for last pick (max 3 lines)
        if last_pick_idx is not None:
            cur = picks[last_pick_idx]
            if cur["comment"].count("\n") < 3:
                cur["comment"] = (cur["comment"] + "\n" + s).strip()
    return picks

def main():
    text = SRC.read_text(encoding="utf-8")
    arts = split_articles(text)
    all_picks: List[Dict] = []
    for art in arts:
        all_picks.extend(parse_article(art))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["race_date","publish_date","course","race","type","umaban","name","popularity_est","comment"])
        w.writeheader()
        for p in all_picks:
            w.writerow(p)
    # summary
    by_type = {}
    for p in all_picks:
        by_type[p["type"]] = by_type.get(p["type"],0)+1
    print(f"Articles: {len(arts)}  Picks: {len(all_picks)}  by_type: {by_type}")
    print(f"Output: {OUT_CSV}")

if __name__ == "__main__":
    main()
