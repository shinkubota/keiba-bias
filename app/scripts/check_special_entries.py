#!/usr/bin/env python3
"""翌週末の特別登録(出馬表確定前の登録段階)からwatchlist候補を抽出。
※netkeibaの特別登録ページは構造が不安定なため、現状は「翌々週末の重賞名」を表示する最小実装。
将来: race_listから注目度の高いレース(重賞・特別)を抽出してプロンプト出力。
"""
import json, sys, datetime, pathlib, urllib.request, re

ROOT = pathlib.Path(__file__).parent.parent

def next_sat_sun():
    today = datetime.date.today()
    # 次の土曜まで何日か
    days_to_sat = (5 - today.weekday()) % 7
    if days_to_sat == 0 and today.weekday() == 5: days_to_sat = 7
    sat = today + datetime.timedelta(days=days_to_sat)
    sun = sat + datetime.timedelta(days=1)
    return sat.strftime("%Y%m%d"), sun.strftime("%Y%m%d")

def fetch_race_list(date):
    url = f"https://race.netkeiba.com/top/race_list_sub.html?kaisai_date={date}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.read().decode("EUC-JP", errors="ignore")
    except Exception as e:
        return ""

def main():
    sat, sun = next_sat_sun()
    print(f"# 翌週末特別レース確認 ({sat} {sun})\n")
    for d in [sat, sun]:
        html = fetch_race_list(d)
        if not html:
            print(f"## {d}: race_list取得失敗（まだ未公開の可能性）\n")
            continue
        # 重賞・特別レース名を抽出
        names = re.findall(r'<span class="RaceName_main[^>]*>([^<]+)', html) or []
        if not names:
            # フォールバック: タイトル風文字列
            names = re.findall(r'>([一-龥ァ-ンA-Z]+(?:S|杯|賞|記念|特別|ステークス))<', html)
        special = []
        for n in names:
            if any(k in n for k in ("S", "杯", "賞", "記念", "特別", "ステークス")):
                special.append(n)
        special = sorted(set(special))[:20]
        print(f"## {d}")
        if special:
            for s in special:
                print(f"- {s}")
            print("\n💡 注目馬を `python3 scripts/watchlist.py add <馬名> --reason '...'` で登録\n")
        else:
            print("(未公開 or 抽出失敗)\n")

if __name__ == "__main__":
    main()
