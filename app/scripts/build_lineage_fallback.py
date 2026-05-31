#!/usr/bin/env python3
"""キャッシュ済みped HTMLの血統表から各種牡馬(父/母父)の大系統を
血統表の父系祖先名で事実判定し、lineage.jsonに無い種牡馬を補完して
lineage_fallback.json に出力する。書籍由来のlineage.jsonが常に優先。
"""
import json, re, pathlib, glob
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).parent.parent
MEMORY = ROOT/"data"/"memory"
tree = json.loads((MEMORY/"lineage_tree.json").read_text(encoding="utf-8"))["大系統"]
book = {k:v for k,v in json.loads((MEMORY/"lineage.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}

# 祖先名 → (大系統, 小系統) のマーカー表を tree から構築
FOUNDER = {}      # name -> daikei
INTER = {}        # name -> (daikei, shokei)
for dk, info in tree.items():
    for f in info.get("founders", []):
        FOUNDER[f] = dk
    for nm, sk in info.get("intermediate_founders", {}).items():
        INTER[nm] = (dk, sk)

def clean(n):
    if not n: return ""
    return n.split("(")[0].strip()

def key_name(n):
    """辞書キー用: 日本語先頭部のみ(analyze側のclean_sireと一致させる)"""
    if not n: return ""
    m = re.match(r"^([぀-ヿ一-鿿・ー]+)", n)
    return m.group(1) if m else n.split("(")[0].strip()

def norm(n):
    """英名・空白ゆれを吸収した比較キー"""
    return re.sub(r"[\s\.\-’']", "", n).lower()

FOUNDER_N = {norm(k):v for k,v in FOUNDER.items()}
INTER_N   = {norm(k):v for k,v in INTER.items()}

def male_line_from_ped(html):
    """血統表の(父系line, 母父系line)を返す。各々は祖先名リスト(近→遠)。"""
    soup = BeautifulSoup(html, "lxml")
    t = soup.select_one("table.blood_table")
    if not t: return [], []
    rows = t.find_all("tr", recursive=False)
    def names(tr):
        out = []
        for a in tr.find_all("a"):
            href = a.get("href","")
            txt = a.get_text(strip=True).split("\n")[0]
            if txt in ("血統","産駒","産"):    # ナビリンク除外
                continue
            if "/horse/" in href and "/ped/" not in href and "/sire/" not in href:
                out.append(clean(txt))
        return out
    # 父系: 先頭行
    sire_line = names(rows[0]) if rows else []
    # 母: 2つ目のrowspan=16 td を含む行
    bms_line = []
    big = [td for td in t.find_all("td") if td.get("rowspan")=="16"]
    if len(big) >= 2:
        mother_tr = big[1].find_parent("tr")
        all_names = names(mother_tr)
        # all_names[0]=母, [1]=母父, [2]=母父父... 母を除く
        bms_line = all_names[1:]
    return sire_line, bms_line

def name_keys(nm):
    """『サンデーサイレンスSunday Silence(米)』→ [全体, 日本語部, 英語部] のnorm集合"""
    base = nm.split("(")[0].strip()
    keys = {norm(base)}
    mjp = re.match(r"^([぀-ヿ一-鿿・ーヴ]+)", base)
    if mjp: keys.add(norm(mjp.group(1)))
    men = re.search(r"([A-Za-z][A-Za-z\s\.'\-]+)$", base)
    if men: keys.add(norm(men.group(1)))
    return keys

def classify(line_from_self):
    """祖先名リスト(自身は除く=父以降)から(大系統,小系統)を近い順で判定"""
    for nm in line_from_self:
        for k in name_keys(nm):
            if k in INTER_N: return INTER_N[k]
        for k in name_keys(nm):
            if k in FOUNDER_N: return (FOUNDER_N[k], None)
    return (None, None)

def main():
    # 種牡馬名 -> 判定結果(多数決用カウンタ)
    result = {}
    def record(sire_name, line_excl_self):
        kn = key_name(sire_name)
        if not kn: return
        if kn in book: return            # 書籍優先
        dk, sk = classify(line_excl_self)
        if not dk: return
        key = (kn, dk, sk)
        result[key] = result.get(key, 0) + 1

    for pth in glob.glob(str(ROOT/"cache"/"ped_*.html")):
        html = pathlib.Path(pth).read_text(encoding="utf-8")
        sire_line, bms_line = male_line_from_ped(html)
        if sire_line:
            # sire = sire_line[0], その祖先 = sire_line[1:]
            record(clean(sire_line[0]), sire_line[1:])
        if bms_line:
            record(clean(bms_line[0]), bms_line[1:])

    # 多数決で確定
    fallback = {}
    by_name = {}
    for (name, dk, sk), cnt in result.items():
        by_name.setdefault(name, []).append((cnt, dk, sk))
    for name, cands in by_name.items():
        cands.sort(key=lambda x: x[0], reverse=True)
        cnt, dk, sk = cands[0]
        fallback[name] = {"daikei": dk, "shokei": sk, "type": None, "src": "ped_fallback"}

    out = {"_meta":{"source":"netkeiba 5代血統表からの父系祖先判定(自動)","note":"書籍lineage.jsonに無い種牡馬の大系統補完。型は無し。"}}
    out.update(dict(sorted(fallback.items())))
    (MEMORY/"lineage_fallback.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fallback補完: {len(fallback)}種牡馬")

if __name__ == "__main__":
    main()
