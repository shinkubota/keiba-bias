#!/usr/bin/env python3
"""推奨買い目mdをGmail SMTPで自分宛に送信。
アプリパスワードは環境変数 GMAIL_APP_PASSWORD から読む（コードに残さない）。

Usage:
  export GMAIL_APP_PASSWORD='xxxxxxxxxxxxxxxx'   # 16桁(空白除去)
  python3 scripts/send_mail.py 20260530 [--track 東京,京都] [--to other@example.com]

複数ファイル添付/本文化:
  recommend_{date}.md があれば本文に。無ければ recommend_{date}_東京.md 等を結合。
"""
import os, sys, ssl, smtplib, argparse, pathlib, glob
from email.message import EmailMessage

ROOT = pathlib.Path(__file__).parent.parent
FROM = "shinkbt0427i@gmail.com"
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465

def collect_body(date, track):
    parts = []
    # 1) 統合md優先
    main = ROOT/"data"/f"recommend_{date}.md"
    if main.exists():
        parts.append(main.read_text(encoding="utf-8"))
    else:
        for f in sorted(glob.glob(str(ROOT/"data"/f"recommend_{date}_*.md"))):
            parts.append(pathlib.Path(f).read_text(encoding="utf-8"))
    if not parts:
        sys.exit(f"本文となる recommend_{date}*.md が見つかりません。先に recommend.py を実行してください。")
    return "\n\n".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--to", default=FROM)
    ap.add_argument("--track", default="")
    args = ap.parse_args()

    pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    if not pw:
        sys.exit("環境変数 GMAIL_APP_PASSWORD が未設定です。\n"
                 "  export GMAIL_APP_PASSWORD='16桁のアプリパスワード'")

    body = collect_body(args.date, args.track)
    y, m, d = args.date[:4], args.date[4:6], args.date[6:8]

    msg = EmailMessage()
    msg["Subject"] = f"【トラックバイアス推奨】{y}/{m}/{d} 東京・京都"
    msg["From"] = FROM
    msg["To"] = args.to
    msg.set_content(
        "土曜分のトラックバイアス推奨買い目です（査読用）。\n"
        "※ %は『レース内バイアス適合スコアの占有率』。勝率予測ではありません。\n"
        "※ オッズ・人気は当日変動のため未反映。斤量は反映済み。\n\n"
        + body
    )
    # mdファイルも添付
    md = ROOT/"data"/f"recommend_{args.date}.md"
    if md.exists():
        msg.add_attachment(md.read_bytes(), maintype="text", subtype="markdown",
                           filename=md.name)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(FROM, pw)
        s.send_message(msg)
    print(f"送信完了: {args.to}  件名=「{msg['Subject']}」")

if __name__ == "__main__":
    main()
