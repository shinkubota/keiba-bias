#!/usr/bin/env python3
"""金曜夜のデータ更新ルーティーン。
- jockey_stats.json を月1更新（古ければ）
- lineage_fallback.json を再構築（ped cache全部から）
- 30日超のresult/dbraceキャッシュを削除（ディスク掃除）
"""
import json, pathlib, subprocess, sys, time, datetime

ROOT = pathlib.Path(__file__).parent.parent
CACHE = ROOT/"cache"
MEMORY = ROOT/"data"/"memory"

def main():
    # 1. jockey_stats: 21日以上古ければ再取得（"今週末日付"指定が必要なので翌日)
    p = MEMORY/"jockey_stats.json"
    need_jky = (not p.exists()) or (time.time() - p.stat().st_mtime > 21*86400)
    if need_jky:
        # 翌日（土曜）日付で取得
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y%m%d")
        # まずshutubaがないと騎手IDが集まらないので、簡易チェック
        sh_p = ROOT/"data"/f"shutuba_{tomorrow}.json"
        if sh_p.exists():
            print(f"refreshing jockey_stats (using shutuba_{tomorrow})")
            subprocess.run([sys.executable, "scripts/fetch_jockey_stats.py", tomorrow], cwd=ROOT, check=False)
        else:
            print(f"skip jockey_stats refresh — shutuba_{tomorrow}.json がまだ無い")
    else:
        age = (time.time() - p.stat().st_mtime) / 86400
        print(f"jockey_stats up-to-date (age={age:.0f}日)")

    # 2. lineage_fallback 再構築
    print("rebuilding lineage_fallback...")
    subprocess.run([sys.executable, "scripts/build_lineage_fallback.py"], cwd=ROOT, check=False)

    # 3. 古いキャッシュ掃除（30日超）
    cutoff = time.time() - 30 * 86400
    removed = 0
    for f in CACHE.glob("*.html"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(); removed += 1
        except Exception:
            pass
    print(f"cache cleanup: removed {removed} files >30d")

if __name__ == "__main__":
    main()
