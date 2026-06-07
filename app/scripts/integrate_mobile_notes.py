#!/usr/bin/env python3
"""data/review/mobile_inbox.md の新規メモを retrospective.md に統合し、
inbox からは削除する(取り込み済みクリーンアップ)。

スマホ(GitHubアプリ)から書き殴ったメモを正規ファイルに移すスクリプト。
週次運用に組み込む想定: weekly_runner.sh の weekly_recap で月曜朝に実行。

Usage:
  python3 integrate_mobile_notes.py             # 取り込み実行
  python3 integrate_mobile_notes.py --dry-run   # 取り込まず確認のみ
"""
import sys, re, pathlib, argparse, datetime

ROOT = pathlib.Path(__file__).parent.parent
INBOX = ROOT / "data" / "review" / "mobile_inbox.md"
RETRO = ROOT / "data" / "review" / "retrospective.md"

# inbox の中で「実メモ」とみなす範囲: 最初の `<!-- ↓` 以降〜末尾
START_MARKER = "<!-- ↓ ここから下に新しいメモを書く ↓ -->"
# 取り込まないテンプレ的なサンプル見出し
SKIP_HEADERS = {"## 使い方サンプル"}

def parse_blocks(text):
    """`## YYYY-MM-DD` で始まるブロックを抽出。
    戻り値: [(header, body), ...] 上から下の順
    """
    body = text.split(START_MARKER, 1)
    if len(body) < 2: return []
    content = body[1]
    blocks = []
    # ## 行で分割
    parts = re.split(r"(?m)^(?=## )", content)
    for p in parts:
        p = p.strip()
        if not p: continue
        first_line = p.split("\n", 1)[0].strip()
        if first_line in SKIP_HEADERS: continue
        # YYYY-MM-DD を含むメモのみ取り込み対象
        if not re.search(r"\d{4}-\d{2}-\d{2}", first_line): continue
        blocks.append((first_line, p))
    return blocks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not INBOX.exists():
        print("inbox not found, skip."); return
    inbox_text = INBOX.read_text(encoding="utf-8")
    blocks = parse_blocks(inbox_text)
    if not blocks:
        print("no new memos."); return

    print(f"found {len(blocks)} memo(s) to integrate:")
    for h, _ in blocks:
        print(f"  - {h}")

    if args.dry_run:
        print("[dry-run] no changes."); return

    # retrospective.md 末尾に追記
    retro_text = RETRO.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()
    appended = f"\n\n## 📱 モバイルメモ取り込み ({today})\n\n"
    for _, body in blocks:
        appended += body + "\n\n---\n"
    # 既存の <!-- 次週はここに追記 --> マーカーがあれば上書き
    if "<!-- 次週はここに追記 -->" in retro_text:
        retro_text = retro_text.replace("<!-- 次週はここに追記 -->",
                                        appended.strip() + "\n\n<!-- 次週はここに追記 -->")
    else:
        retro_text += appended
    RETRO.write_text(retro_text, encoding="utf-8")

    # inbox から取り込み済みブロックを削除(START_MARKER以降は空にする+サンプル復活)
    header = inbox_text.split(START_MARKER, 1)[0]
    sample = "\n## 使い方サンプル\n\nスマホから:\n1. GitHubアプリを開く → `shinkubota/keiba-bias` を選択\n2. `app/data/review/mobile_inbox.md` をタップ\n3. 右上の鉛筆アイコン → 上の「---」のすぐ下に新規ブロック追加\n4. 「Commit changes」→ メッセージに `memo: 6/13土曜の感想` など → Commit\n"
    INBOX.write_text(header + START_MARKER + "\n" + sample, encoding="utf-8")
    print(f"integrated {len(blocks)} memo(s) into retrospective.md, inbox cleaned.")

if __name__ == "__main__":
    main()
