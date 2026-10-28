import sys, numpy as np
from PIL import Image
from collections import Counter
from scipy import ndimage as ndi
im=Image.open(sys.argv[1]); print(im.size, im.mode)
a=np.array(im.convert('RGBA')); H,W=a.shape[:2]
op=a[...,3]>0; print('alpha values',np.unique(a[...,3]))
rgb=a[...,:3]
def L(c):
    c=np.array(c)/255.; c=np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
    y=c@[0.2126,0.7152,0.0722]; return 116*(y**(1/3) if y>0.008856 else 7.787*y+16/116)-16
cnt=Counter(map(tuple,rgb[op])); print('n colors',len(cnt),'opaque px',op.sum())
import colorsys
for c,n in cnt.most_common():
    h,s,v=colorsys.rgb_to_hsv(*[x/255 for x in c]); print(c,'#%02x%02x%02x'%c,n,'L*=%.1f H=%.0f S=%.2f'%(L(c),h*360,s))
ys,xs=np.where(op); print('bbox x',xs.min(),xs.max(),'y',ys.min(),ys.max(),'w',xs.max()-xs.min()+1,'h',ys.max()-ys.min()+1,'margins L,R,T,B',xs.min(),W-1-xs.max(),ys.min(),H-1-ys.max())
print('opaque fill of bbox',op.sum()/((xs.max()-xs.min()+1)*(ys.max()-ys.min()+1)))
# outline: opaque px with 4-neighbour transparent/outside
pad=np.pad(op,1); bd=op&~(pad[:-2,1:-1]&pad[2:,1:-1]&pad[1:-1,:-2]&pad[1:-1,2:])
print('silhouette-boundary px',bd.sum(),bd.sum()/op.sum())
bc=Counter(map(tuple,rgb[bd])); print('boundary colors',[(('#%02x%02x%02x'%c),n) for c,n in bc.most_common()])
# row widths / column profile
rw=op.sum(1); print('row widths',list(rw[ys.min():ys.max()+1]))
# components of opaque
lab,n=ndi.label(op,structure=np.ones((3,3))); print('opaque components',n,[int((lab==i).sum()) for i in range(1,n+1)])
# orphans
idx={c:i for i,c in enumerate(cnt)}
ci=np.full((H,W),-1); 
for y in range(H):
  for x in range(W):
    if op[y,x]: ci[y,x]=idx[tuple(rgb[y,x])]
orph=[]; 
for y in range(H):
  for x in range(W):
    if ci[y,x]<0: continue
    ok=False
    for dy in(-1,0,1):
      for dx in(-1,0,1):
        if (dy or dx) and 0<=y+dy<H and 0<=x+dx<W and ci[y+dy,x+dx]==ci[y,x]: ok=True
    if not ok: orph.append((x,y,'#%02x%02x%02x'%tuple(rgb[y,x])))
print('orphans (8-neigh)',len(orph),orph)
# 4-neighbour orphans
o4=0
# 1px wide features: per color region, runs of width1 both horizontally and vertically (pixel has no same-colour 4-neighbour on left/right AND none up/down => thin dot) ; and thin line: no same colour neighbours in one axis
th=0;thl=[]
for y in range(H):
  for x in range(W):
    c=ci[y,x]
    if c<0: continue
    s=lambda yy,xx:0<=yy<H and 0<=xx<W and ci[yy,xx]==c
    hz=s(y,x-1) or s(y,x+1); vt=s(y-1,x) or s(y+1,x)
    if not hz and not vt: o4+=1
    if not hz or not vt: th+=1
print('4-orphans',o4,'px lacking same-colour neighbour in a whole axis (1px-wide in some direction)',th)
# color regions (4-conn) size histogram
regs=[]
for c in range(len(cnt)):
    l,m=ndi.label(ci==c)
    for i in range(1,m+1): regs.append((c,int((l==i).sum())))
print('regions',len(regs),'size<=2:',sum(1 for r in regs if r[1]<=2),'size<=4:',sum(1 for r in regs if r[1]<=4))
# checkerboard: px whose 4 neighbours all same other colour & 2 colours
cb=0;cbl=[]
for y in range(1,H-1):
  for x in range(1,W-1):
    c=ci[y,x]
    if c<0: continue
    n4=[ci[y-1,x],ci[y+1,x],ci[y,x-1],ci[y,x+1]]
    if n4[0]==n4[1]==n4[2]==n4[3]!=c and n4[0]>=0 and ci[y-1,x-1]==c and ci[y+1,x+1]==c and ci[y-1,x+1]==c and ci[y+1,x-1]==c:
        cb+=1;cbl.append((x,y))
print('checker pixels',cb,cbl[:20])
np.save('ci.npy',ci)
