#!/usr/bin/env python3
"""福島・函館・小倉(ローカル小回り3場)のコースバイアスを courses.json に登録。
trueblood の競馬場別好相性種牡馬を sire_favored に反映。
"""
import json, pathlib
ROOT = pathlib.Path(__file__).parent.parent
CPATH = ROOT/"data"/"memory"/"courses.json"
APATH = ROOT/"data"/"memory"/"trueblood"/"sire_aptitude.json"

c = json.loads(CPATH.read_text(encoding="utf-8"))
apt = json.loads(APATH.read_text(encoding="utf-8"))

# 3場を一旦削除(誤登録クリーンアップ)
for k in list(c):
    if any(k.startswith(t) for t in ("福島","函館","小倉")):
        del c[k]

def favored(surf, trk):
    key = f"{surf}{trk}"
    good = []
    for name, e in apt.items():
        tp = (e.get("track_place") or {}).get(key)
        if not tp: continue
        pl = tp.get("place") or 0; rt = tp.get("ret") or 0
        if pl >= 33 or rt >= 85:
            good.append((name, pl, rt))
    good.sort(key=lambda x: -x[1])
    return [g[0] for g in good[:6]]

VENUE = {
 "函館": dict(tag="洋芝・小回り", st=262, sd=260,
   note="洋芝でパワー/スタミナ要。小回りで内枠先行が有利、前残り傾向"),
 "福島": dict(tag="小回り・直線最短級292m", st=292, sd=295,
   note="直線292mと短く小回り。内枠先行が有利、時計のかかる芝"),
 "小倉": dict(tag="平坦小回り・直線293m", st=293, sd=291,
   note="平坦小回りで先行有利・前残り。夏開催後半は芝が荒れ外差し台頭"),
}
DIST = {
 "函館": [("芝",1200),("芝",1800),("芝",2000),("ダ",1000),("ダ",1700)],
 "福島": [("芝",1200),("芝",1800),("芝",2000),("ダ",1150),("ダ",1700)],
 "小倉": [("芝",1200),("芝",1800),("芝",2000),("ダ",1000),("ダ",1700)],
}

added = 0
for trk, cos in DIST.items():
    v = VENUE[trk]
    for surf, dist in cos:
        key = f"{trk}{surf}{dist}m"
        fav = favored(surf, trk)
        straight = v["st"] if surf == "芝" else v["sd"]
        rsp = ["先行","逃げ"] if (surf == "ダ" or dist <= 1200) else ["先行","差し"]
        c[key] = {
          "track": trk, "surface": surf, "distance": dist, "straight_m": straight,
          "headline": v["tag"] + "。内枠・先行有利の傾向",
          "rules": ["内枠有利","先行・逃げ脚質有利","同距離&距離短縮ローテ","データ欄の注目血統"],
          "gate_bias": {"general":"内枠有利","exception":"開催後半の荒れ馬場時は外差し台頭"},
          "running_style_pref": rsp,
          "sire_favored": fav,
          "notes": v["note"] + "(trueblood競馬場別好相性種牡馬を反映)",
        }
        added += 1

CPATH.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"追加 {added}コース / 総 {len(c)}コース")
for trk in ("福島","函館","小倉"):
    ks = sorted(k[len(trk):] for k in c if k.startswith(trk))
    print(f"  {trk}: {ks}")
