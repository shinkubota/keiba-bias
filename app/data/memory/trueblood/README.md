# trueblood/ — 種牡馬データ(パーフェクト種牡馬辞典2026-2027)

`trueblood/` の94枚PNG(本のページ画像)をOCRして構造化したデータ。

## ファイル
- `raw_*.json` — 8バッチ(aa〜ah)のOCR生結果。各画像の type(profile/data/toc/feature)と抽出値
- `trueblood_long.csv` — 集約ロングテーブル(分析用)
  - 列: `sire,rank,category,surface,key,runs,win_pct,rentai_pct,place_pct,tan_return,fuku_return`
  - category: pace(脚質)/baba(馬場)/course(コース)/distance/draw(枠)/popularity(人気)/klass/grade/age/sex/interval
- `sire_aptitude.json` — 予想取込用の正規化(種牡馬→catchphrase/aim/baba_place/course_place/pace_place)

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
- 種牡馬110頭をカバー(馬場適性48頭、狙い目テキスト51頭)
- **BEST30(1〜30位)は完全取得**(プロフィール+おもしろデータ、回収率まで)
- 注目種牡馬の一部は勝率/連対率/複勝率の3列のみ(回収率は本に無い)
- **af欠損**: IMG_1590〜1601(注目種牡馬の一部 約12〜24頭)はセッション制限でOCR未完
  → 再OCRするには `trueblood/IMG_1590.PNG`〜`IMG_1601.PNG` を再処理
- 巻末COMPACTランキング表(ag/ah)は極小フォントで数値判読不可、構造のみ記録

## TODO
- [ ] af(IMG_1590-1601)の再OCR
- [ ] pace(脚質)データが10頭と少ない → 上位馬のおもしろデータから脚質を補完
- [ ] catchphrase/aim テキストの狙い目を予想理由に表示(現状は馬場適性のみ加点)
