import numpy as np, sys
from PIL import Image
from scipy import ndimage as ndi
from collections import Counter
a=np.array(Image.open(sys.argv[1]).convert('RGBA')); H,W=a.shape[:2]; op=a[...,3]>0
def Lab(c):
    c=np.array(c)/255.; c=np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
    y=c@[0.2126,0.7152,0.0722]; return 116*(y**(1/3) if y>0.008856 else 7.787*y+16/116)-16
hx=lambda y,x:'%02x%02x%02x'%tuple(a[y,x,:3])
cols=sorted({hx(y,x) for y in range(H) for x in range(W) if op[y,x]})
LL={c:Lab([int(c[i:i+2],16) for i in (0,2,4)]) for c in cols}
# 1. 2x2 opening per colour region => pixels in 1px-wide strokes
thin=Counter(); tot=Counter()
for c in cols:
    m=np.array([[op[y,x] and hx(y,x)==c for x in range(W)] for y in range(H)])
    o=ndi.binary_opening(m,structure=np.ones((2,2)))
    thin[c]=int(m.sum()-o.sum()); tot[c]=int(m.sum())
print('thin (not covered by any 2x2 same-colour block) per colour',[(c,thin[c],tot[c]) for c in cols]); print('sum',sum(thin.values()),'of',sum(tot.values()))
o=ndi.binary_opening(op,structure=np.ones((2,2))); print('silhouette px not in a 2x2 opaque block',int(op.sum()-o.sum()))
o3=ndi.binary_opening(op,structure=np.ones((3,3))); print('silhouette px not in a 3x3 block',int(op.sum()-o3.sum()))
# 2. edge contrast between 4-adjacent opaque differently coloured pixels
pairs=Counter()
for y in range(H):
  for x in range(W):
    if not op[y,x]: continue
    for dy,dx in((0,1),(1,0)):
      yy,xx=y+dy,x+dx
      if yy<H and xx<W and op[yy,xx] and hx(y,x)!=hx(yy,xx): pairs[tuple(sorted((hx(y,x),hx(yy,xx))))]+=1
d=[(abs(LL[p]-LL[q]),n) for (p,q),n in pairs.items()]
tot_e=sum(n for _,n in d); print('colour-change edges',tot_e)
for th in(5,10,15,20): print('edges with dL<%d: %d (%.1f%%)'%(th,sum(n for v,n in d if v<th),100*sum(n for v,n in d if v<th)/tot_e))
print('lowest-contrast pairs',sorted([(round(abs(LL[p]-LL[q]),1),p,q,n) for (p,q),n in pairs.items()])[:12])
# 3. checker/dither: 2x2 windows with pattern ABAB diag
cnt=0;L=[]
for y in range(H-1):
  for x in range(W-1):
    if op[y:y+2,x:x+2].all():
      p,q,r,s=hx(y,x),hx(y,x+1),hx(y+1,x),hx(y+1,x+1)
      if p==s and q==r and p!=q: cnt+=1;L.append((x,y,p,q))
print('2x2 diagonal checker windows',cnt,L)
# 4. mirror symmetry of silhouette about best vertical axis (full, head rows 5-20)
def sym(m):
    best=(0,0)
    for ax2 in range(10,100):  # axis at ax2/2
        mm=np.zeros_like(m)
        for x in range(W):
            xr=ax2-x
            if 0<=xr<W: mm[:,x]=m[:,xr]
        iou=(m&mm).sum()/(m|mm).sum()
        if iou>best[0]: best=(iou,ax2/2)
    return best
print('silhouette mirror IoU full',sym(op)); h=op.copy(); h[21:]=False; print('head rows<21',sym(h))
# 5. skin/hair/etc palette per hue family: pixel counts
fam={'skin':['ffdbce','dea294','ce8273'],'hair/brown+outline':['a56952','7b5952','4a3039'],'red':['ff615a','c64142'],'green':['8cdb73','639a5a'],'neutral cool':['fffbff','cecbde','636173','293842','000000']}
for f,l in fam.items(): print(f,[(c,round(LL[c],1)) for c in sorted(l,key=lambda c:-LL[c])],'px',sum(tot[c] for c in l),'dL steps',[round(LL[x]-LL[y],1) for x,y in zip(sorted(l,key=lambda c:-LL[c]),sorted(l,key=lambda c:-LL[c])[1:])])
# 6. blobs: eyes region (x23-33,y13-17); dark/white comps within face
def comps(colset,box):
    x0,y0,x1,y1=box; m=np.zeros((H,W),bool)
    for y in range(y0,y1+1):
        for x in range(x0,x1+1):
            if op[y,x] and hx(y,x) in colset: m[y,x]=1
    l,n=ndi.label(m,structure=np.ones((3,3)))
    return [(int((l==i).sum()),[tuple(map(int,p[::-1])) for p in np.argwhere(l==i)]) for i in range(1,n+1)]
print('dark/white blobs face',comps({'000000','636173','fffbff','cecbde'},(23,12,34,17)))
print('mouth red blobs',comps({'c64142','ff615a'},(25,17,31,20)))
print('gloves left',comps({'000000','636173','cecbde','fffbff','c64142','ff615a'},(8,23,17,31)))
print('gloves right',comps({'000000','636173','cecbde','fffbff','293842'},(38,31,46,37)))
print('hand skin left', comps({'ffdbce','dea294','ce8273'},(8,23,25,31)))
print('hand skin right', comps({'ffdbce','dea294','ce8273'},(33,28,40,37)))
