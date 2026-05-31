#!/usr/bin/env python3
"""netkeiba から想定/朝オッズ(単勝・複勝・人気)を取得して JSON 保存。

Usage:
    python3 fetch_odds.py YYYYMMDD          # その日の shutuba にある全レース
    python3 fetch_odds.py --race-id ...     # 単発

出力: app/data/odds_YYYYMMDD.json
  形式: { race_id: { umaban(int): {"win": float, "place_min": float, "place_max": float, "pop": int} } }
"""
from __future__ import annotations
import sys, os, json, time, argparse, pathlib
import requests

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"; DATA = ROOT/"data"
CACHE.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def fetch_json(url, key, ttl=1800):
    p = CACHE/key
    if p.exists() and (time.time()-p.stat().st_mtime) < ttl:
        return json.loads(p.read_text(encoding="utf-8"))
    r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    r.raise_for_status()
    p.write_text(r.text, encoding="utf-8")
    time.sleep(0.3)
    return r.json()

def fetch_race_odds(race_id):
    j = fetch_json(f"https://race.netkeiba.com/api/api_get_jra_odds.html?race_id={race_id}&type=1",
                   f"odds_win_{race_id}.json")
    j2 = fetch_json(f"https://race.netkeiba.com/api/api_get_jra_odds.html?race_id={race_id}&type=2",
                    f"odds_place_{race_id}.json")
    win = j.get("data", {}).get("odds", {}).get("1", {})
    plc = j2.get("data", {}).get("odds", {}).get("2", {})
    out = {}
    for u_str, vals in win.items():
        umaban = int(u_str.lstrip("0") or "0")
        try:
            wodd = float(vals[0])
            pop = int(vals[2])
        except Exception:
            continue
        out[umaban] = {"win": wodd, "pop": pop}
    for u_str, vals in plc.items():
        umaban = int(u_str.lstrip("0") or "0")
        try:
            pmin = float(vals[0]); pmax = float(vals[1])
        except Exception:
            continue
        out.setdefault(umaban, {}).update({"place_min": pmin, "place_max": pmax})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?")
    ap.add_argument("--race-id")
    args = ap.parse_args()

    if args.race_id:
        result = {args.race_id: fetch_race_odds(args.race_id)}
        out = DATA/f"odds_single_{args.race_id}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        print(out)
        return

    if not args.date:
        ap.error("date or --race-id required")
    shutuba = json.loads((DATA/f"shutuba_{args.date}.json").read_text(encoding="utf-8"))
    out = {}
    for r in shutuba:
        rid = r["race_id"]
        try:
            out[rid] = fetch_race_odds(rid)
            print(f"  {r['track']}{r['race_no']:>2}R odds: {len(out[rid])}頭", file=sys.stderr)
        except Exception as e:
            print(f"  ! {rid}: {e}", file=sys.stderr)
            out[rid] = {}
    (DATA/f"odds_{args.date}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"saved: odds_{args.date}.json")

if __name__ == "__main__":
    main()
