#!/usr/bin/env python3
"""精査結果を (1) Markdown表 (2) 静的HTML(GitHub Pages用) で出力。
HTMLは bias/docs/ に出力 → GitHub Pagesの公開ディレクトリにできる。
Usage: python3 build_web.py YYYYMMDD [--track 東京,京都] [--top 4]
"""
import json, argparse, pathlib, importlib.util, datetime, html

ROOT = pathlib.Path(__file__).parent.parent          # .../bias/app
SITE = ROOT.parent / "docs"                          # .../bias/docs (GitHub Pages)
SITE.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("analyze", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

WD = ["月","火","水","木","金","土","日"]

def shares(scores):
    t = sum(scores); return [s/t if t else 0 for s in scores]

def collect(date_str, tracks, top):
    data = json.loads((ROOT/"data"/f"shutuba_{date_str}.json").read_text(encoding="utf-8"))
    db = az.load_horses(date_str)
    races = []
    for race in data:
        if tracks and race["track"] not in tracks: continue
        if len(race["horses"]) < 2: continue
        a = az.analyze_race(race, db)
        if a.get("warn"):
            races.append({"r": race, "warn": a["warn"]}); continue
        ranked = a["horses"]
        sh = shares([x["score"] for x in ranked])
        rows = []
        for i,(x,s) in enumerate(zip(ranked, sh)):
            if i >= top or x["score"] <= 0: break
            h = x["horse"]
            rows.append({
                "rank": i+1, "umaban": h["umaban"], "name": h["name"],
                "sexage": h.get("sex_age",""), "jockey": h.get("jockey",""),
                "kg": h.get("jockey_weight",""), "pct": round(s*100),
                "score": x["score"], "reasons": x["reasons"],
            })
        races.append({"r": race, "headline": a["headline"], "rows": rows})
    return races

# ── Markdown表（チャット確認用） ──────────────────────────
def to_markdown(date_str, races):
    d = datetime.date(int(date_str[:4]),int(date_str[4:6]),int(date_str[6:8]))
    L = [f"# {d.month}/{d.day}({WD[d.weekday()]}) 推奨（表形式）", ""]
    for item in races:
        r = item["r"]
        title = f"{r['track']}{r['race_no']}R {r['surface']}{r['distance']}m {r['race_name']}"
        if "warn" in item:
            L.append(f"### {title}\n_対象外（{item['warn']}）_\n"); continue
        L.append(f"### {title}（{len(r['horses'])}頭）")
        L.append(f"狙い: {item['headline']}")
        L.append("")
        L.append("| 印 | 馬番 | 馬名 | 性齢 | 騎手 | 斤量 | % | score | 根拠 |")
        L.append("|--|--|--|--|--|--|--|--|--|")
        marks = ["◎","○","▲","△"]
        for row in item["rows"]:
            mark = marks[row["rank"]-1] if row["rank"]<=len(marks) else str(row["rank"])
            reasons = "／".join(row["reasons"][:4])
            L.append(f"| {mark} | {row['umaban']} | {row['name']} | {row['sexage']} | {row['jockey']} | {row['kg']} | {row['pct']}% | {row['score']} | {reasons} |")
        L.append("")
    return "\n".join(L)

# ── HTML（GitHub Pages用） ──────────────────────────────
CSS = """
:root{--bg:#0f1115;--card:#1a1d24;--ink:#e6e8ec;--mut:#9aa3b2;--line:#2a2f3a;--acc:#4da3ff;--win:#ffce54}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif;line-height:1.5}
header{padding:16px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
h1{font-size:18px;margin:0}.sub{color:var(--mut);font-size:12px;margin-top:4px}
.wrap{max-width:960px;margin:0 auto;padding:12px}
.race{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:12px 0;overflow:hidden}
.rhead{padding:10px 12px;border-bottom:1px solid var(--line)}
.rt{font-weight:700}.rh{color:var(--mut);font-size:12px;margin-top:2px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:7px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:11px}
.mark{font-size:16px;width:28px}.um{font-weight:700;width:30px;text-align:center}
.nm{font-weight:600}.pct{color:var(--acc);font-weight:700;text-align:right;white-space:nowrap}
.sc{color:var(--mut);text-align:right}
.rs{color:var(--mut);font-size:11px}
.warn{padding:12px;color:var(--mut);font-style:italic}
.note{color:var(--mut);font-size:11px;padding:8px 12px}
a{color:var(--acc)}.idx a{display:block;padding:10px 12px;border-bottom:1px solid var(--line)}
.badge{display:inline-block;background:#243; color:#7fd; font-size:10px;padding:1px 6px;border-radius:6px;margin-left:6px}
"""

def esc(s): return html.escape(str(s))

def to_html(date_str, races):
    d = datetime.date(int(date_str[:4]),int(date_str[4:6]),int(date_str[6:8]))
    title = f"{d.year}/{d.month}/{d.day}({WD[d.weekday()]}) トラックバイアス推奨"
    parts = [f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body>
<header><div class="wrap"><h1>🐎 {esc(title)}</h1>
<div class="sub">%＝レース内バイアス適合スコアの占有率（勝率予測ではありません）。枠順確定後の自動算出。<a href="./">← 一覧</a></div>
</div></header><div class="wrap">"""]
    marks = ["◎","○","▲","△"]
    for item in races:
        r = item["r"]
        rt = f"{esc(r['track'])}{r['race_no']}R"
        meta = f"{esc(r['surface'])}{r['distance']}m {esc(r['race_name'])}・{len(r['horses'])}頭"
        if "warn" in item:
            parts.append(f'<div class="race"><div class="rhead"><span class="rt">{rt}</span> <span class="rh">{meta}</span></div><div class="warn">対象外（{esc(item["warn"])}）</div></div>')
            continue
        rows_html = ""
        for row in item["rows"]:
            mark = marks[row["rank"]-1] if row["rank"]<=len(marks) else str(row["rank"])
            reasons = " / ".join(esc(x) for x in row["reasons"][:4])
            rows_html += (f'<tr><td class="mark">{mark}</td><td class="um">{esc(row["umaban"])}</td>'
                          f'<td><div class="nm">{esc(row["name"])}</div>'
                          f'<div class="rs">{esc(row["sexage"])} {esc(row["jockey"])} {esc(row["kg"])}kg</div></td>'
                          f'<td class="pct">{row["pct"]}%</td><td class="sc">{row["score"]}</td>'
                          f'<td class="rs">{reasons}</td></tr>')
        parts.append(f'''<div class="race">
<div class="rhead"><span class="rt">{rt}</span> <span class="rh">{meta}</span><div class="rh">狙い: {esc(item["headline"])}</div></div>
<table><thead><tr><th>印</th><th>番</th><th>馬名/騎手</th><th>%</th><th>pt</th><th>根拠</th></tr></thead>
<tbody>{rows_html}</tbody></table></div>''')
    parts.append(f'<div class="note">生成: {datetime.datetime.now():%Y-%m-%d %H:%M}・馬券は自己責任で</div>')
    parts.append("</div></body></html>")
    return "\n".join(parts)

def rebuild_index():
    """docs/内のpredict_*.htmlからindex.htmlを生成。"""
    pages = sorted(SITE.glob("predict_*.html"), reverse=True)
    links = ""
    for p in pages:
        ds = p.stem.replace("predict_","")
        try:
            d = datetime.date(int(ds[:4]),int(ds[4:6]),int(ds[6:8]))
            label = f"{d.year}/{d.month}/{d.day}({WD[d.weekday()]})"
        except Exception:
            label = ds
        links += f'<a href="{p.name}">{label} の推奨 →</a>'
    idx = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>トラックバイアス予想</title><style>{CSS}</style></head><body>
<header><div class="wrap"><h1>🐎 トラックバイアス予想</h1>
<div class="sub">コース事典×血統×前走×能力をスコア化した自動予想アーカイブ</div></div></header>
<div class="wrap idx">{links or '<div class="note">まだ予想がありません</div>'}</div></body></html>"""
    (SITE/"index.html").write_text(idx, encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date"); ap.add_argument("--track", default="東京,京都"); ap.add_argument("--top", type=int, default=4)
    args = ap.parse_args()
    tracks = set(args.track.split(",")) if args.track else set()
    races = collect(args.date, tracks, args.top)

    md = to_markdown(args.date, races)
    (ROOT/"data"/f"table_{args.date}.md").write_text(md, encoding="utf-8")
    (SITE/f"predict_{args.date}.html").write_text(to_html(args.date, races), encoding="utf-8")
    rebuild_index()
    print(md)
    print(f"\n# HTML: {SITE}/predict_{args.date}.html", flush=True)

if __name__ == "__main__":
    main()
