#!/usr/bin/env python3
"""note記事自動生成: 予想型/振り返り型 の2タイプ。

予想型 (predict): 金/土夕方+土/日朝 — 翌日のメインレース紹介+動的配分の解説
振り返り型 (review): 土/日夜 — 当日結果+回収率検証+学び

Usage:
  python3 note_writer.py predict 20260613      # 6/13(土)の予想記事
  python3 note_writer.py review  20260613      # 6/13(土)の振り返り記事
"""
import sys, json, pathlib, argparse, datetime, re

ROOT = pathlib.Path(__file__).parent.parent
ART  = ROOT / "data" / "articles"
ART.mkdir(parents=True, exist_ok=True)

WD = ["月","火","水","木","金","土","日"]
GRADE_RACES = ("記念","賞","ステークス","S","C","ハンデ","オープン","オールカマー","Tro","T","WL")

def fmt_date(d):
    return f"{d.year}/{d.month}/{d.day}({WD[d.weekday()]})"

def get_main_races(date_str, top_n=3):
    """その日のメインっぽいレース(11R,10R,重賞名)を抽出"""
    p = ROOT/"data"/f"shutuba_{date_str}.json"
    if not p.exists(): return []
    data = json.loads(p.read_text(encoding="utf-8"))
    # 11R, 10R を優先、なければG付き
    mains=[]
    for race in data:
        if race["race_no"] in (10, 11):
            mains.append(race)
    return mains[:top_n]

def get_recommendations(date_str, suffix=""):
    """recommend_wide_YYYYMMDD_late_A.md または _early_A.md または canonical名 を読む"""
    for cand in [f"recommend_wide_{date_str}_late_A.md",
                 f"recommend_wide_{date_str}_early_A.md",
                 f"recommend_wide_{date_str}.md"]:
        p = ROOT/"data"/cand
        if p.exists(): return p.read_text(encoding="utf-8")
    return None

def get_results(date_str):
    p = ROOT/"data"/f"results_{date_str}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def extract_race_block(rec_text, race_name_hint):
    """recommend記事から特定レースのブロックを抽出"""
    if not rec_text: return ""
    pat = re.compile(r"(### [^\n]*?" + re.escape(race_name_hint) + r"[^\n]*?\n.*?)(?=\n### |\Z)", re.S)
    m = pat.search(rec_text)
    return m.group(1) if m else ""

def write_predict(date_str):
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    mains = get_main_races(date_str)
    rec = get_recommendations(date_str)
    if not rec:
        print(f"[predict] no recommendation for {date_str}", file=sys.stderr)
        return None

    L = [f"# 【{fmt_date(d)} 注目レース予想】データが弾き出した「◎軸3連複4頭流し」+メインの一押し", ""]
    L.append("## はじめに")
    L.append("")
    L.append(f"明日{fmt_date(d)}のJRA中央開催。本ブログでは「コースバイアス×血統×騎手×厩舎」など13因子を機械的にスコア化した予想を提供しています。")
    L.append("")
    L.append("> **戦略 v0.16**: 2日46Rの包括検証で得たベスト戦略 = **3連複4頭流し(6点)が回収率100%**、**3-4人気◎は単勝500円厚張り(EV 2.34)**、**5人気↓◎は見送り**。これでROI 125%。")
    L.append("")
    L.append("---")
    L.append("")

    # メインレース3つ
    if mains:
        L.append(f"## 本日の注目 {len(mains)}レース")
        L.append("")
        for race in mains:
            title = f"{race['track']}{race['race_no']}R {race.get('race_name','')}"
            L.append(f"### 🏇 {title}")
            L.append(f"- 距離: {race['surface']}{race['distance']}m")
            if race.get("weather"):
                L.append(f"- 天候/馬場: {race.get('weather','-')}/{race.get('baba','-')}")
            block = extract_race_block(rec, race.get("race_name",""))
            if block:
                # 印テーブルと推奨配分だけ抜く
                lines = block.split("\n")
                in_table=False; in_haibun=False
                for ln in lines[1:]:
                    if ln.startswith("| 印"):
                        in_table=True; L.append(ln); continue
                    if in_table:
                        if ln.startswith("|"):
                            L.append(ln); continue
                        else:
                            in_table=False
                    if "推奨配分" in ln:
                        in_haibun=True; L.append("");
                        L.append("**💰 推奨配分**"); continue
                    if in_haibun:
                        if ln.startswith("- ") or ln.startswith("  -"):
                            L.append(ln); continue
                        else:
                            in_haibun=False
            L.append("")

    L.append("---")
    L.append("")
    L.append("## 全レースの推奨")
    L.append("")
    L.append("GitHub Pagesに全レース分の印・警戒馬・推奨配分を公開しています。")
    L.append("👉 https://shinkubota.github.io/keiba-bias/")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## 戦略まとめ (v0.16 動的配分)")
    L.append("")
    L.append("| ◎人気 | 推奨 | 1Rコスト |")
    L.append("|---|---|---:|")
    L.append("| 1-2人気 | 3連複4頭流し(6点) | 600円 |")
    L.append("| **3-4人気** | **🔥単勝500円 + 3連複4頭流し** | **1,100円** |")
    L.append("| 5人気↓ | ⛔見送り | 0円 |")
    L.append("")
    L.append("検証ROI **125%**。馬連はROI 18%・ワイドも28-32%で論外、3連単は分散大きすぎ。**シンプルに「軸固定3連複4頭流し」が最適解**でした。")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*予想は機械的スコアに基づきます。投資は自己責任で。フォロー&スキで応援ください🙏*")

    out = "\n".join(L)
    fp = ART/f"note_predict_{date_str}.md"
    fp.write_text(out, encoding="utf-8")
    print(f"saved: {fp}")
    return fp

def write_review(date_str):
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    results = get_results(date_str)
    if not results:
        print(f"[review] no results for {date_str}", file=sys.stderr)
        return None

    # 当日のretrospective.md該当セクションを抽出
    retro = (ROOT/"data"/"review"/"retrospective.md").read_text(encoding="utf-8")
    sec_pat = re.compile(rf"## {d.year}-{d.month:02d}-{d.day:02d}\([土日]\).*?(?=\n## |\Z)", re.S)
    sec = sec_pat.search(retro)
    sec_text = sec.group(0) if sec else ""

    # サマリ抽出
    n_races = len(results)
    win = sum(1 for r in results if any(h["finish"]==1 and h["name"]==r["horses"][0]["name"] for h in r["horses"]))
    # ↑↑ 注: これは1着馬を判定しているだけで、◎=1着の判定ではない(別途集計が必要)

    L = [f"# 【{fmt_date(d)} 振り返り】データが示した今日の手応えと取りこぼし", ""]
    L.append("## はじめに")
    L.append("")
    L.append(f"今日{fmt_date(d)}のJRA中央開催、全{n_races}Rの振り返りです。")
    L.append("")

    # 戦績まとめ(retrospective.md から抽出)
    summary_match = re.search(r"### 成績.*?(?=\n###|\Z)", sec_text, re.S)
    if summary_match:
        L.append("## 戦績")
        L.append("")
        L.append(summary_match.group(0).replace("### 成績（", "全").replace("R）",""))
        L.append("")

    # 本命1着
    win_match = re.search(r"### 本命的中.*?\| \|\n((?:\|[^\n]+\n)+)", sec_text)
    if win_match:
        L.append("## 🎯 本命的中(◎=1着)")
        L.append("")
        L.append("| レース | 馬 | 人気 | 単 |")
        L.append("|---|---|---:|---:|")
        for line in win_match.group(1).strip().split("\n"):
            L.append(line)
        L.append("")

    # 大穴ヒット
    dark_match = re.search(r"### 🐎 大穴3着内ヒット.*?(?=\n\*\*推奨ランク|\Z)", sec_text, re.S)
    if dark_match:
        L.append("## 🐴 大穴3着内ヒット (8人気以下)")
        L.append("")
        body = dark_match.group(0)
        # テーブル部分のみ
        tbl = re.search(r"\| レース.*?\n(\|[^\n]+\n)+", body, re.S)
        if tbl:
            L.append(tbl.group(0).strip())
        L.append("")

    # 取りこぼし
    miss_match = re.search(r"### ❌ 取りこぼし.*?(?=\n####|\n\n###|\Z)", sec_text, re.S)
    if miss_match:
        L.append("## ⚠️ 取りこぼし(◎○▲全滅)")
        L.append("")
        body = miss_match.group(0)
        tbl = re.search(r"\| レース.*?\n(\|[^\n]+\n)+", body, re.S)
        if tbl:
            L.append(tbl.group(0).strip())
        L.append("")

    # 学びサマリ
    summary_tail = re.search(r"### 📌 サマリ.*?(?=\n##|\Z)", sec_text, re.S)
    if summary_tail:
        L.append("## 📌 今日の学び")
        L.append("")
        L.append(summary_tail.group(0).replace("### 📌 サマリ", "").strip())
        L.append("")

    L.append("---")
    L.append("")
    L.append("## 来週への展望")
    L.append("")
    L.append("動的配分戦略 **v0.16** (3-4人気◎で単勝厚張り+3連複4頭流し / 5人気↓見送り) で来週も継続検証していきます。")
    L.append("")
    L.append("詳細レポート: https://shinkubota.github.io/keiba-bias/")
    L.append("")
    L.append("---")
    L.append("")
    L.append("*この予想は機械的スコアに基づきます。投資は自己責任で。*")

    out = "\n".join(L)
    fp = ART/f"note_review_{date_str}.md"
    fp.write_text(out, encoding="utf-8")
    print(f"saved: {fp}")
    return fp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=["predict","review"])
    ap.add_argument("date", help="YYYYMMDD")
    args = ap.parse_args()
    if args.type=="predict":
        write_predict(args.date)
    else:
        write_review(args.date)

if __name__ == "__main__":
    main()
