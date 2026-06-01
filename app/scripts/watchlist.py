#!/usr/bin/env python3
"""注目馬watchlist管理＋出走時の詳細評価レポート生成。

Usage:
  python3 watchlist.py add <馬名> --reason "理由" [--horse-id <id>] [--until YYYY-MM-DD]
  python3 watchlist.py list                          # 登録中の馬一覧
  python3 watchlist.py remove <馬名>
  python3 watchlist.py check YYYYMMDD               # 指定日の出馬表で登録馬が出走しているか確認
                                                     # 出走していれば詳細評価レポートをdata/watch_report_*.mdに出力
"""
import json, sys, argparse, pathlib, importlib.util, datetime

ROOT = pathlib.Path(__file__).parent.parent
WL_PATH = ROOT/"data"/"memory"/"watchlist.json"
spec = importlib.util.spec_from_file_location("az", ROOT/"scripts"/"analyze.py")
az = importlib.util.module_from_spec(spec); spec.loader.exec_module(az)

def load():
    if not WL_PATH.exists(): return {"_meta":{}, "horses":[]}
    return json.loads(WL_PATH.read_text(encoding="utf-8"))

def save(d):
    WL_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def cmd_add(args):
    d = load()
    today = datetime.date.today().isoformat()
    # 既存チェック
    if any(h["name"] == args.name for h in d["horses"]):
        print(f"already in watchlist: {args.name}"); return
    d["horses"].append({
        "name": args.name,
        "horse_id": args.horse_id or "",
        "reason": args.reason,
        "watch_until": args.until or "",
        "added": today,
    })
    save(d)
    print(f"added: {args.name}")

def cmd_list(args):
    d = load()
    today = datetime.date.today().isoformat()
    for h in d["horses"]:
        expired = h["watch_until"] and h["watch_until"] < today
        mark = " (期限切れ)" if expired else ""
        print(f"- {h['name']}{mark}  hid={h['horse_id']}  追加{h['added']}  期限{h['watch_until'] or '無期限'}")
        print(f"    理由: {h['reason']}")

def cmd_remove(args):
    d = load()
    before = len(d["horses"])
    d["horses"] = [h for h in d["horses"] if h["name"] != args.name]
    save(d)
    print(f"removed: {args.name} ({before - len(d['horses'])}件)")

def cmd_check(args):
    """指定日の出馬表に登録馬が出走しているかチェック→詳細レポート生成"""
    date = args.date
    sh_path = ROOT/"data"/f"shutuba_{date}.json"
    if not sh_path.exists():
        print(f"shutuba_{date}.json がありません。先に fetch_shutuba.py {date} を実行してください")
        sys.exit(1)
    shutuba = json.loads(sh_path.read_text(encoding="utf-8"))
    db = az.load_horses(date)
    wl = load()
    if not wl["horses"]:
        print("watchlistが空です"); return
    # 名前/IDマップ
    name_set = {h["name"] for h in wl["horses"]}
    id_set = {h["horse_id"] for h in wl["horses"] if h["horse_id"]}
    wl_by_name = {h["name"]: h for h in wl["horses"]}

    hits = []
    for race in shutuba:
        for h in race["horses"]:
            if h["name"] in name_set or (h.get("horse_id") and h["horse_id"] in id_set):
                hits.append((race, h))
    if not hits:
        print(f"{date}: watchlist馬の出走なし")
        return

    # 詳細レポート
    d_obj = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
    wd = "月火水木金土日"[d_obj.weekday()]
    out = [f"# 📡 watchlist出走レポート {d_obj.year}/{d_obj.month}/{d_obj.day}({wd})", ""]
    out.append(f"登録{len(wl['horses'])}頭中 {len(hits)}件が出走")
    out.append("")
    for race, h in hits:
        # 該当馬を分析
        a = az.analyze_race(race, db)
        if a.get("warn"):
            out.append(f"### {race['track']}{race['race_no']}R {race['race_name']} — 対象外({a['warn']})\n")
            continue
        # 推奨ランクと評価詳細
        target_row = None
        rank = None
        for idx, row in enumerate(a["horses"], start=1):
            if row["horse"]["umaban"] == h["umaban"] and row["horse"]["name"] == h["name"]:
                target_row = row; rank = idx; break
        if not target_row:
            continue
        wl_info = wl_by_name.get(h["name"], {})
        out.append(f"### ⭐ {race['track']}{race['race_no']}R {race['surface']}{race['distance']}m {race['race_name']}")
        out.append(f"**{h['umaban']}番 {h['name']}** ({h.get('sex_age','')} {h.get('jockey','')} {h.get('jockey_weight','')}kg)")
        out.append(f"- 推奨ランク: **{rank}位** / {len(a['horses'])}頭")
        out.append(f"- 能力: {target_row.get('ability','—')} / bias: {target_row.get('bias',0)} / 評価: **{target_row['score']}**")
        out.append(f"- 登録理由: {wl_info.get('reason','—')}")
        out.append(f"- バイアス根拠: {' ／ '.join(target_row.get('reasons',[]))}")
        # 馬場・天候
        baba = race.get("baba") or "?"
        weather = race.get("weather") or "?"
        out.append(f"- 当日条件: 天候{weather} 馬場{baba}")
        # 当日推奨上位3頭(比較対象)
        out.append(f"- 同レース当日◎○▲:")
        for i, r in enumerate(a["horses"][:3]):
            mark = "◎○▲"[i]
            rh = r["horse"]
            out.append(f"  - {mark} {rh['umaban']}番 {rh['name']}（能力{r.get('ability','—')}・評価{r['score']}）")
        # 狙い時判定
        rec = db.get(h.get("horse_id","")) or {}
        recent = rec.get("recent",[])
        nudges = []
        if rank and rank <= 3:
            nudges.append(f"🟢 推奨上位3位以内 — 当アプリでも軸候補")
        elif rank and rank <= 8:
            nudges.append(f"🟡 推奨{rank}位（警戒馬ゾーン）— 軸◎との組み合わせで狙い目")
        else:
            nudges.append(f"🔴 推奨{rank}位 — 当アプリでは推奨外。watchlist登録理由を再確認")
        if recent:
            prev = recent[0]
            try:
                fin = int(prev.get("finish") or 99)
                if fin <= 3:
                    nudges.append(f"🟢 前走{prev.get('venue','')}{prev.get('distance_text','')}・{fin}着 — 直近好走")
            except: pass
            # 間隔
            try:
                y,m,dy = prev["date"].split("/")
                prev_d = datetime.date(int(y),int(m),int(dy))
                days = (d_obj - prev_d).days
                if days <= 14:
                    nudges.append(f"🟡 前走から{days}日 — 連闘〜2週")
                elif days >= 180:
                    nudges.append(f"🔴 前走から{days}日 — 半年超休み明け")
            except: pass
        out.append("")
        out.append("**狙い目判定**:")
        for n in nudges:
            out.append(f"- {n}")
        out.append("")

    p = ROOT/"data"/f"watch_report_{date}.md"
    p.write_text("\n".join(out), encoding="utf-8")
    print(f"saved: {p}")

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("name"); a.add_argument("--reason", required=True)
    a.add_argument("--horse-id", default=""); a.add_argument("--until", default="")
    a.set_defaults(func=cmd_add)
    sub.add_parser("list").set_defaults(func=cmd_list)
    rm = sub.add_parser("remove"); rm.add_argument("name"); rm.set_defaults(func=cmd_remove)
    ck = sub.add_parser("check"); ck.add_argument("date"); ck.set_defaults(func=cmd_check)
    args = ap.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
