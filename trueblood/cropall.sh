#!/bin/zsh
# Usage: ./cropall.sh <IMGNUM>
# Generates legible 2x crops for both sires (L=left, R=right) of a page.
# Full image is 2388x1668, two sires side by side. Left sire x:0-1194, right sire x:1194-2388.
# sips -c HEIGHT WIDTH --cropOffset YOFF XOFF
set -e
n=$1
d=/Users/kubota/Desktop/bias/trueblood
out=$d/crops_$n
mkdir -p $out
cd $d

# Left sire offset base X=0, Right sire base X=1190
for side in L R; do
  if [ "$side" = "L" ]; then bx=0; else bx=1190; fi
  # Header + name + pedigree (top area)  x bx+200 .. bx+990 , y 30..470
  sips -c 440 800 --cropOffset 30 $((bx+195)) IMG_$n.PNG --out $out/${side}_head.png >/dev/null
  sips -z 880 1600 $out/${side}_head.png --out $out/${side}_head2x.png >/dev/null
  # Comment column  x bx+195 .. bx+660 (w465), y 470..1180 (h710)
  sips -c 710 465 --cropOffset 470 $((bx+195)) IMG_$n.PNG --out $out/${side}_com.png >/dev/null
  sips -z 1420 930 $out/${side}_com.png --out $out/${side}_com2x.png >/dev/null
  # Left grid (distance/surface/course/age) x bx+225 .. bx+730 (w505), y 1175..1660 (h485)
  sips -c 485 505 --cropOffset 1175 $((bx+225)) IMG_$n.PNG --out $out/${side}_g1.png >/dev/null
  sips -z 970 1010 $out/${side}_g1.png --out $out/${side}_g1x.png >/dev/null
  # Right categorical grid (baba/draw/class/pop/style) x bx+700 .. bx+1190 (w490), y 1175..1660 (h485)
  sips -c 485 490 --cropOffset 1175 $((bx+700)) IMG_$n.PNG --out $out/${side}_g2.png >/dev/null
  sips -z 970 980 $out/${side}_g2.png --out $out/${side}_g2x.png >/dev/null
done
ls $out
