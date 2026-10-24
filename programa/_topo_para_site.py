"""Converte a topologia do mapshaper no formato compacto do mapa-mun.json (ver gerar_mapa_municipios.py)."""
import json,sys,math
t=json.load(open(sys.argv[1]))
obj=list(t['objects'].values())[0]
arcs=t['arcs']
xs=[p[0] for a in arcs for p in a]; ys=[p[1] for a in arcs for p in a]
minx,maxx,miny,maxy=min(xs),max(xs),min(ys),max(ys)
W=1000.0; esc=W/(maxx-minx); H=(maxy-miny)*esc
Q=4  # quartos de unidade
def tela(p): return (round((p[0]-minx)*esc*Q), round((maxy-p[1])*esc*Q))
earcs=[];npts=0
for a in arcs:
    pts=[tela(p) for p in a]
    # remove duplicados consecutivos
    out=[pts[0]]
    for p in pts[1:]:
        if p!=out[-1]: out.append(p)
    if len(out)<2: out.append(out[0])
    flat=[out[0][0],out[0][1]]
    for i in range(1,len(out)):
        flat+= [out[i][0]-out[i-1][0], out[i][1]-out[i-1][1]]
    npts+=len(out); earcs.append(flat)
mun={};uso={}
def rings(g):
    if g['type']=='Polygon': return g['arcs']
    if g['type']=='MultiPolygon': return [r for poly in g['arcs'] for r in poly]
    return []
geoms=obj['geometries']
for g in geoms:
    k=g['properties']['k']; uf=g['properties']['uf']
    rs=rings(g)
    if not rs: continue
    mun[k]=rs
    for r in rs:
        for ai in r:
            j=ai if ai>=0 else ~ai
            uso.setdefault(j,set()).add(uf)
# arcos de fronteira de UF: usados por 2 UFs diferentes, ou por uma só vez (borda externa)
cont={}
for g in geoms:
    for r in rings(g):
        for ai in r:
            j=ai if ai>=0 else ~ai; cont[j]=cont.get(j,0)+1
bord=[j for j in range(len(arcs)) if len(uso.get(j,()))>1]
fora=[j for j in range(len(arcs)) if cont.get(j,0)==1]
# rotulos por UF: centroide da maior area de cada UF (aprox: centroide ponderado dos municipios)
def decode(j):
    f=earcs[j];x,y=f[0],f[1];pts=[(x,y)]
    for i in range(2,len(f),2): x+=f[i];y+=f[i+1];pts.append((x,y))
    return pts
def ringpts(r):
    pts=[]
    for ai in r:
        p=decode(ai if ai>=0 else ~ai)
        if ai<0: p=p[::-1]
        pts+= p if not pts else p[1:]
    return pts
def area_c(p):
    a=cx=cy=0
    for i in range(len(p)-1):
        f=p[i][0]*p[i+1][1]-p[i+1][0]*p[i][1]; a+=f; cx+=(p[i][0]+p[i+1][0])*f; cy+=(p[i][1]+p[i+1][1])*f
    return a/2,(cx/(3*a) if a else 0),(cy/(3*a) if a else 0)
cen={}
for k,rs in mun.items():
    uf=k.split('/')[0]
    for r in rs:
        a,cx,cy=area_c(ringpts(r)); a=abs(a)
        s=cen.setdefault(uf,[0,0,0]); s[0]+=a; s[1]+=cx*a; s[2]+=cy*a
rot={uf.upper():[round(s[1]/s[0]/Q,1),round(s[2]/s[0]/Q,1)] for uf,s in cen.items()}
saida={'fonte':'IBGE (malha municipal via tbrugz/geodata-br), Albers','q':Q,'w':1000,'h':round(H,1),
 'arcs':earcs,'mun':mun,'ufBorda':bord,'fora':fora,'rotulos':rot}
json.dump(saida,open(sys.argv[2],'w'),separators=(',',':'))
print('pontos',npts,'arcos',len(arcs),'mun',len(mun),'H',H)
