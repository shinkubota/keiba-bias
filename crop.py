#!/usr/bin/env python3
"""見開き画像を左ページ/右ページに分割し2倍拡大して /tmp/L.png /tmp/R.png に保存。
Usage: python3 crop.py IMG_xxxx.PNG
任意領域: python3 crop.py IMG_xxxx.PNG x0 y0 x1 y1  -> /tmp/crop.png
"""
import sys, os
from PIL import Image
BASE='/Users/kubota/Desktop/bias'
p=sys.argv[1]
path=p if os.path.isabs(p) else os.path.join(BASE,'blood',os.path.basename(p))
im=Image.open(path)
W,H=im.size
if len(sys.argv)>=6:
    x0,y0,x1,y1=map(float,sys.argv[2:6])
    box=(int(x0*W),int(y0*H),int(x1*W),int(y1*H))
    c=im.crop(box); c=c.resize((c.width*2,c.height*2)); c.save('/tmp/crop.png')
    print('saved',box,'->',c.size)
else:
    L=im.crop((0,0,W//2,H)); L=L.resize((L.width*2,L.height*2)); L.save('/tmp/L.png')
    R=im.crop((W//2,0,W,H)); R=R.resize((R.width*2,R.height*2)); R.save('/tmp/R.png')
    print('L /tmp/L.png',L.size,'R /tmp/R.png',R.size)
