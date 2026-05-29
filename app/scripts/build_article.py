#!/usr/bin/env python3
"""recommend結果を note 記事風の markdown に整形する。
配信スキーマの「コンテンツ生成」層。出力は media-agnostic な記事JSON+MD。
Usage: python3 build_article.py YYYYMMDD [--track 東京,京都] [--pickup 東京10,京都11]
"""
import json, argparse, pathlib, importlib.util, datetime

ROOT = pathlib.Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("analyze", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

WEEKDAY_JP = ["月","火","水","木","金","土","日"]

def softmax_or_share(scores):
    tot = sum(scores)
    return [s/tot if tot else 0 for s in scores]

def emoji_rank(i):
    return ["🥇","🥈","🥉"][i] if i < 3 else f"{i+1}."

def build(date_str, tracks, pickups):
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    wd = WEEKDAY_JP[d.weekday()]
    data = json.loads((ROOT/"data"/f"shutuba_{date_str}.json").read_text(encoding="utf-8"))
    db = az.load_horses(date_str)

    races = []
    for race in data:
        if tracks and race["track"] not in tracks: continue
        if len(race["horses"]) < 2: continue
        a = az.analyze_race(race, db)
        if a.get("warn"):
            races.append({"race": race, "warn": a["warn"]}); continue
        ranked = a["horses"]
        sh = softmax_or_share([r["score"] for r in ranked])
        for r, s in zip(ranked, sh): r["share"] = s
        races.append({"race": race, "a": a, "ranked": ranked})

    # ── 記事本文(note風) ──────────────────────────────
    L = []
    L.append(f"# 【トラックバイアス予想】{d.month}/{d.day}({wd}) {'・'.join(sorted(tracks)) if tracks else '中央競馬'}")
    L.append("")
    L.append("> 競馬場コース事典のトラックバイアス × 血統 × 前走傾向を、枠順確定後に機械的にスコア化した予想です。")
    L.append("> **数字(%)は「バイアス適合度のレース内シェア」で、勝率予測ではありません。** あくまで\"この条件に合う馬\"の相対指標としてご覧ください。")
    L.append("")
    L.append("---")
    L.append("")

    # ピックアップ（注目レース）
    if pickups:
        L.append("## 🎯 今日の注目レース")
        L.append("")
        for item in races:
            r = item["race"]
            tag = f"{r['track']}{r['race_no']}"
            if tag not in pickups or "warn" in item: continue
            L += _race_block(item, headline_level="###", spotlight=True)
        L.append("---")
        L.append("")

    # 全レース
    L.append("## 📋 全レース推奨（上位3頭）")
    L.append("")
    for item in races:
        if "warn" in item:
            r = item["race"]
            L.append(f"### {r['track']}{r['race_no']}R {r['surface']}{r['distance']}m {r['race_name']}")
            L.append(f"_対象外（{item['warn']}）_")
            L.append("")
            continue
        L += _race_block(item, headline_level="###", spotlight=False)

    L.append("---")
    L.append("")
    L.append("### 📝 この予想の作り方")
    L.append("- 枠順バイアス（内/外/1枠有利）＝コース事典準拠")
    L.append("- 血統（父・母父が好走系統か）＝系統辞書で判定")
    L.append("- 前走条件（同距離/距離短縮/先行・差し脚質/着順 など）")
    L.append("- 斤量（レース内で軽量級か）")
    L.append("")
    L.append("※馬券は自己責任で。当記事は分析の共有であり購入を推奨するものではありません。")

    md = "\n".join(L)

    # ── media-agnostic な記事オブジェクト ──────────────
    article = {
        "date": date_str,
        "title": f"【トラックバイアス予想】{d.month}/{d.day}({wd}) {'・'.join(sorted(tracks)) if tracks else '中央競馬'}",
        "tags": ["競馬", "予想", "トラックバイアス", "血統"] + sorted(list(tracks)),
        "body_markdown": md,
        "summary": _summary(races, pickups),
        "x_post": _x_post(date_str, races, pickups),
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    return article

def _race_block(item, headline_level, spotlight):
    r = item["race"]; a = item["a"]; ranked = item["ranked"]
    out = []
    star = "⭐ " if spotlight else ""
    out.append(f"{headline_level} {star}{r['track']}{r['race_no']}R {r['surface']}{r['distance']}m {r['race_name']}（{len(r['horses'])}頭）")
    out.append(f"**狙い目**：{a['headline']}")
    out.append("")
    shown = 0
    for i, row in enumerate(ranked):
        if shown >= 3: break
        if row["score"] <= 0: break
        h = row["horse"]
        kg = h.get("jockey_weight") or "?"
        reasons = "／".join(row["reasons"][:4]) or "—"
        out.append(f"{emoji_rank(shown)} **{h['umaban']}番 {h['name']}**（{h.get('sex_age','')} {h.get('jockey','')} {kg}kg）　{row['share']*100:.0f}%")
        out.append(f"　└ {reasons}")
        shown += 1
    if shown == 0:
        out.append("_バイアス該当馬なし（実力・人気で取捨を）_")
    out.append("")
    return out

def _summary(races, pickups):
    """SNS用の短文(X等)。注目レースの本命だけ。"""
    parts = []
    for item in races:
        if "warn" in item: continue
        r = item["race"]; tag = f"{r['track']}{r['race_no']}"
        if pickups and tag not in pickups: continue
        top = item["ranked"][0]
        if top["score"] <= 0: continue
        h = top["horse"]
        parts.append(f"{r['track']}{r['race_no']}R {h['name']}({h['umaban']})")
    return " / ".join(parts)

def _x_post(date_str, races, pickups, note_url=""):
    """X(Twitter)投稿文を組み立てる。140字目安、ハッシュタグ付き。
    注目レースの本命を列挙し、超過しそうなら自動で頭数を削る。"""
    d = datetime.date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
    wd = WEEKDAY_JP[d.weekday()]
    picks = []
    for item in races:
        if "warn" in item: continue
        r = item["race"]; tag = f"{r['track']}{r['race_no']}"
        if pickups and tag not in pickups: continue
        top = item["ranked"][0]
        if top["score"] <= 0: continue
        h = top["horse"]
        picks.append(f"{r['track']}{r['race_no']}R {h['umaban']}{h['name']}")

    header = f"🐎{d.month}/{d.day}({wd}) トラックバイアス予想・本命"
    tags = "#競馬 #競馬予想"
    tail = (f"\n詳細▶ {note_url}" if note_url else "")

    def assemble(n):
        body = "\n".join(f"◎{p}" for p in picks[:n])
        return f"{header}\n{body}\n{tags}{tail}"

    n = len(picks)
    text = assemble(n)
    # 140字超なら本命を減らす（最低1件は残す）
    while len(text) > 140 and n > 1:
        n -= 1
        text = assemble(n)
    if n < len(picks):
        text = text.replace(tags, f"他{len(picks)-n}R {tags}")
    return text

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--track", default="東京,京都")
    ap.add_argument("--pickup", default="", help="例: 東京10,京都11")
    args = ap.parse_args()
    tracks = set(args.track.split(",")) if args.track else set()
    pickups = set(args.pickup.split(",")) if args.pickup else set()

    article = build(args.date, tracks, pickups)
    # 記事JSON（配信層が読む中間生成物）
    (ROOT/"data"/f"article_{args.date}.json").write_text(
        json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
    # 人が読む/コピペ用MD（note等へ貼る）
    (ROOT/"data"/f"article_{args.date}.md").write_text(
        article["body_markdown"], encoding="utf-8")
    # X(Twitter)用短文（そのまま投稿欄に貼る）
    (ROOT/"data"/f"article_{args.date}_x.txt").write_text(
        article["x_post"], encoding="utf-8")
    print(article["body_markdown"])
    print("\n" + "="*40 + "\n【X投稿用】\n" + "="*40)
    print(article["x_post"])
    print(f"\n(文字数: {len(article['x_post'])})")

if __name__ == "__main__":
    main()
