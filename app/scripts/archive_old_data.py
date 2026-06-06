#!/usr/bin/env python3
"""data直下の日付付きファイル(shutuba_/horses_/odds_/results_/recommend_wide_/table_/evaluation_/article_/watch_report_)を
N日より古いものを data/archive/YYYY/MM/ に移動。
直近(N日以内)はdata直下に残し、推奨/分析で参照可能にする。

Usage:
  python3 archive_old_data.py             # デフォルト: 7日より古いものを退避
  python3 archive_old_data.py --keep 14   # 14日以内は残す
  python3 archive_old_data.py --dry-run   # 移動せず表示のみ
"""
import sys, re, datetime, pathlib, argparse, shutil

ROOT = pathlib.Path(__file__).parent.parent
DATA = ROOT/"data"
ARC = DATA/"archive"

# 対象プレフィックス
TARGET_PREFIXES = ("shutuba_","horses_","odds_","results_",
                   "recommend_wide_","recommend_","table_","evaluation_",
                   "article_","watch_report_")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=7, help="保持日数(N日以内は残す)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=args.keep)
    print(f"[{today.isoformat()}] 保持日数={args.keep}日 (cutoff={cutoff.isoformat()})")
    moved = 0; kept = 0
    for p in sorted(DATA.iterdir()):
        if not p.is_file(): continue
        name = p.name
        # プレフィックスマッチ
        if not any(name.startswith(pre) for pre in TARGET_PREFIXES): continue
        # YYYYMMDD抽出
        m = re.search(r"_(20\d{6})[\._]", name + ".")
        if not m: continue
        try:
            d = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError: continue
        if d >= cutoff:
            kept += 1; continue
        dest_dir = ARC/f"{d.year:04d}"/f"{d.month:02d}"
        dest = dest_dir/name
        if args.dry_run:
            print(f"  [dry] {name} -> archive/{d.year:04d}/{d.month:02d}/")
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            print(f"  moved: {name} -> archive/{d.year:04d}/{d.month:02d}/")
        moved += 1
    print(f"\n結果: 移動{moved}件 / 保持{kept}件")

if __name__ == "__main__":
    main()
