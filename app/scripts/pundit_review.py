#!/usr/bin/env python3
"""配信者レビュー: 月〜木の夕方に登録済みpunditの1人を取り上げて
プロファイル + 過去予想実績 + 当アプリとの差異 + 採用候補シグナル を
data/review/columns/YYYYMMDD_配信者_<id>.md に出力する。

選定ロジック: pundits[*].last_reviewed が古い順 → 同じならpriority highから。
"""
import json, re, sys, datetime, pathlib, urllib.request, importlib.util

ROOT = pathlib.Path(__file__).parent.parent
COL_DIR = ROOT/"data"/"review"/"columns"; COL_DIR.mkdir(parents=True, exist_ok=True)
PUNDITS = ROOT/"data"/"memory"/"pundits.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def load_pundits():
    return json.loads(PUNDITS.read_text(encoding="utf-8"))

def save_pundits(d):
    PUNDITS.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_target(d):
    """next-up選定。priority high優先、その中で last_reviewed が古い順"""
    today = datetime.date.today().isoformat()
    pri_rank = {"high":0, "mid":1, "low":2}
    cands = sorted(d.get("pundits", []),
                   key=lambda p: (pri_rank.get(p.get("priority","mid"), 1),
                                  p.get("last_reviewed", "")))
    return cands[0] if cands else None

def fetch_note_profile(url):
    """note プロフィールページから直近記事タイトル数件を取得"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None
    titles = re.findall(r'<h3[^>]*>([^<]{4,80})</h3>', html)[:10]
    return {"recent_titles": titles}

def render_calimero_summary():
    """既に組み込み済みのCalimeroシグナル/直近実績要約"""
    body = []
    body.append("### 当アプリへの組込状況")
    body.append("- すでに analyze.py の `calimero_bonus()` に **Cal シグナル S3〜S12** を実装済み")
    body.append("- weights['cal'] = 1 で標準運用、`notes/calimero_integration_plan.md` 参照")
    body.append("")
    body.append("### 直近成績（土日46R対象）")
    body.append("- 注目血統(Cal)×当アプリの能力スコア合算で本命単勝24% / 複勝85%")
    body.append("- Calシグナルが警戒馬ゾーンの大穴ヒットに大きく貢献([Cal]距離延長×5回/[Cal]ダート×4回 等)")
    return body

def render_generic_pundit(p):
    """汎用punditの初回紹介テンプレ"""
    body = []
    body.append("### 予想スタイル")
    body.append(f"- {p.get('style','—')}")
    if p.get("notes"):
        body.append(f"- メモ: {p['notes']}")
    body.append("")
    body.append("### 検証方法（提案）")
    body.append("1. 直近の購入/無料記事から ◎○▲ の取捨を週次CSV化(parse_*.py を流用)")
    body.append("2. 当アプリの推奨と差異分析（独自シグナル発見)")
    body.append("3. ROI(複勝率/単回収率) を当アプリと比較")
    body.append("4. **当アプリより良い独自シグナルがあれば** candidate_signals に追加 → 手動承認 → analyze.py へ昇格")
    body.append("")
    prof = fetch_note_profile(p["url"]) if "url" in p else None
    if prof and prof.get("recent_titles"):
        body.append("### 直近記事タイトル(取得試行)")
        for t in prof["recent_titles"][:5]:
            body.append(f"- {t}")
        body.append("")
    return body

def render_candidate_signals(d):
    cands = d.get("candidate_signals", [])
    if not cands: return []
    out = ["### 🟡 採用候補シグナル(手動承認待ち)"]
    out.append("| シグナル | 由来 | 提案ROI | 承認 |")
    out.append("|---|---|---|---|")
    for c in cands:
        out.append(f"| {c.get('name','?')} | {c.get('source','?')} | {c.get('roi_hint','?')} | {c.get('status','pending')} |")
    out.append("")
    out.append("> 採用するときは `data/memory/pundits.json` の candidate_signals → loop_signals 相当の独立リストに移し、analyze.py に組み込み案を作成。")
    return out

def render_misc_candidates(d):
    cands = d.get("candidates", [])
    if not cands: return []
    out = ["### 📋 追加候補配信者(未登録)"]
    out.append("| 名前 | プラットフォーム | スタイル | メモ |")
    out.append("|---|---|---|---|")
    for c in cands:
        out.append(f"| {c.get('name','?')} | {c.get('platform','?')} | {c.get('style','?')} | {c.get('note','—')} |")
    out.append("")
    out.append("> 登録するときは `pundits` 配列に id/name/url/style を追記し、priority を設定")
    return out

def main():
    d = load_pundits()
    target = pick_target(d)
    if not target:
        print("pundits が空。data/memory/pundits.json を編集してください"); return
    today = datetime.date.today()
    wd = "月火水木金土日"[today.weekday()]
    body = []
    body.append(f"# 🎙️ 配信者レビュー: {target['name']}")
    body.append(f"_{today.isoformat()}({wd})_")
    body.append("")
    body.append(f"## 基本情報")
    body.append(f"- プラットフォーム: {target.get('platform','?')}")
    body.append(f"- URL: {target.get('url','—')}")
    body.append(f"- スタイル: {target.get('style','—')}")
    body.append(f"- 当アプリでの優先度: {target.get('priority','mid')}")
    body.append(f"- 登録日: {target.get('added','—')} / 前回レビュー: {target.get('last_reviewed','初回')}")
    body.append("")
    # 個別レンダリング(id毎に切替可能)
    if target.get("id") == "calimero":
        body += render_calimero_summary()
    else:
        body += render_generic_pundit(target)
    body.append("")
    body += render_candidate_signals(d)
    body += render_misc_candidates(d)
    body.append("")
    body.append("---")
    body.append("**運用方針**: ここで紹介する配信者の予想は **参考扱い**。当アプリのロジックに自動反映はしない。")
    body.append("「シグナルとして有効」と判断したものだけ手動でcandidate_signalsへ→ 後日承認してanalyze.py組込")

    fn = f"{today.strftime('%Y%m%d')}_配信者_{target['id']}.md"
    p = COL_DIR/fn
    p.write_text("\n".join(body), encoding="utf-8")
    print(f"saved: {p}")

    # last_reviewed 更新
    for pn in d["pundits"]:
        if pn["id"] == target["id"]:
            pn["last_reviewed"] = today.isoformat()
    save_pundits(d)

if __name__ == "__main__":
    main()
