# trueblood/ — 種牡馬データ(パーフェクト種牡馬辞典2026-2027)

`trueblood/` の94枚PNG(本のページ画像)をOCRして構造化したデータ。

## ファイル
- `raw_*.json` — 11バッチ(aa〜ah + af1〜af3)のOCR生結果
- `trueblood_long.csv` — 詳細成績ロングテーブル(BEST30中心, 2929行)
  - 列: `sire,rank,category,surface,key,runs,win_pct,rentai_pct,place_pct,tan_return,fuku_return`
  - category: pace(脚質)/baba(馬場)/course(コース)/distance/draw(枠)/popularity(人気)/klass/grade/age/sex/interval
- `trueblood_catalog.csv` — 種牡馬名鑑(注目新種牡馬/海外種牡馬/母父など125頭)
  - 列: `sire,section,line,country,f_sire,f_dam,f_damsire,baba_pos,dirt_pos,distance_pos,catchphrase,aim,comment`
  - baba_pos/dirt_pos/distance_pos = 適性スライダー位置(1=得意/短〜5=拙/長)
- `sire_aptitude.json` — 予想取込用の正規化(**232頭**: catchphrase/aim/baba_place/course_place/pace_place/baba_slider)

## 再生成
```bash
python3 scripts/build_trueblood.py   # raw_*.json → CSV + sire_aptitude.json
```

## 予想への取り込み(analyze.py)
- `sire_aptitude()` で種牡馬の馬場適性を参照
- **道悪巧者ボーナス(weights["sire_tb"]=2)**: 当日が湿馬場(稍/重/不良)で、
  その父産駒の当該馬場複勝率が良馬場比+2pt以上高い馬に加点
- 例: ダイワメジャー(良22%→重32%)、ゴールドドリーム、ベンバトル 等13頭が該当

## カバー状況 / 既知の制約
- 種牡馬**232頭**をカバー(うち実数複勝率データ48頭、狙い目テキスト51頭、名鑑125頭)
- **BEST30(1〜30位)は完全取得**(プロフィール+おもしろデータ、回収率まで)
- 注目種牡馬の一部は勝率/連対率/複勝率の3列のみ(回収率は本に無い)
- **af(IMG_1590-1601)再OCR完了**: 名鑑形式(1ページ複数頭)だったため catalog.csv に収録
- 巻末COMPACTランキング表(ag/ah)は極小フォントで数値判読不可、構造のみ記録

## TODO
- [ ] pace(脚質)データが10頭と少ない → 上位馬のおもしろデータから脚質を補完
- [ ] catchphrase/aim テキストの狙い目を予想理由に表示(現状は馬場適性のみ加点)
- [ ] 名鑑スライダー(baba_pos<=2の道悪得意24頭)を道悪判定の補助に使うか検証
      → 現状は複勝率データ48頭ベースのみbias加点。スライダーはOCR主観のため保留
