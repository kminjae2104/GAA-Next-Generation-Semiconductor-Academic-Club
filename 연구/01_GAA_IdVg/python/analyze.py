"""Validate real exported terminal currents and extract explicit GAA metrics."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def read_curve(path):
    rows=[]
    for number,line in enumerate(Path(path).read_text(errors='strict').splitlines(),1):
        text=line.strip()
        if not text or text.startswith(('#','"')):continue
        fields=text.replace(',',' ').replace('D','E').replace('d','e').split()
        try:
            if len(fields)!=2:raise ValueError('Expected two columns')
            x,y=map(float,fields)
        except ValueError:
            if rows:raise ValueError('Malformed data line %s:%d'%(path,number))
            if any(s in text.lower() for s in ['nan','inf']):raise ValueError('Nonfinite data')
            continue
        if not all(math.isfinite(v) for v in (x,y)):raise ValueError('Nonfinite data')
        if rows and x<=rows[-1][0]:raise ValueError('Duplicate or decreasing gate bias')
        rows.append((x,y))
    if len(rows)<6:raise ValueError('Insufficient curve points')
    return rows


def crossing(curve,target):
    for (x1,i1),(x2,i2) in zip(curve,curve[1:]):
        a,b=abs(i1),abs(i2)
        if a==target:return x1
        if 0<a<target<=b:
            return x1+(x2-x1)*(math.log10(target)-math.log10(a))/(math.log10(b)-math.log10(a))
    return None


def at(curve,bias):
    matches=[abs(i) for v,i in curve if abs(v-bias)<1e-6]
    if len(matches)!=1:raise ValueError('Missing or duplicate required gate voltage '+str(bias))
    return matches[0]


def metric(curves,perimeter_um,step=.02):
    if not math.isfinite(perimeter_um) or perimeter_um<=0:raise ValueError('Invalid perimeter')
    grids=[[v for v,i in curves[t]] for t in ['drain','source','gate']]
    if not (len(grids[0])==len(grids[1])==len(grids[2])):raise ValueError('Terminal lengths differ')
    for triple in zip(*grids):
        if max(triple)-min(triple)>1e-8:raise ValueError('Terminal voltage grids differ')
    grid=grids[0]
    if abs(grid[0]+.2)>1e-6 or abs(grid[-1]-.8)>1e-6:raise ValueError('Truncated or incorrect sweep')
    if any(abs(b-a-step)>1e-6 for a,b in zip(grid,grid[1:])):raise ValueError('Missing/incorrect gate steps')
    drain=curves['drain']
    normalized=[(v,i/perimeter_um) for v,i in drain]
    ion,ioff=at(drain,.6),at(drain,0)
    if ioff<=0:raise ValueError('Zero Ioff cannot prove a current ratio')
    if any(abs(i)<=0 for _,i in drain):raise ValueError('Zero current requires floor/model inspection')
    signs={1 if i>0 else -1 for v,i in drain if v>=0}
    if len(signs)>1:raise ValueError('Drain-current sign reversal in operating range')
    nonmonotonic=[n for n,((v,a),(w,b)) in enumerate(zip(drain,drain[1:])) if v>=0 and abs(b)<abs(a)*.95]
    kcl=[]
    for sample in zip(curves['drain'],curves['source'],curves['gate']):
        currents=[row[1] for row in sample]
        residual=abs(sum(currents));limit=max(1e-14,max(map(abs,currents))*.001)
        kcl.append((residual,limit))
    window=[(v,math.log10(abs(i))) for v,i in normalized if 1e-10<=abs(i)<=1e-8]
    ss=None;ss_reason='INSUFFICIENT_FIXED_CURRENT_WINDOW'
    boundaries=[crossing(normalized,t) for t in [1e-10,1e-8]]
    if len(window)>=6 and all(v is not None for v in boundaries):
        window=sorted(set(window+[(boundaries[0],-10),(boundaries[1],-8)]))
        xs,ys=zip(*window);xm,ym=statistics.mean(xs),statistics.mean(ys)
        slope=sum((x-xm)*(y-ym) for x,y in window)/sum((x-xm)**2 for x in xs)
        if slope>0:ss=1000/slope;ss_reason='EXTRACTED'
    return dict(Ion_A=ion,Ioff_A=ioff,Ion_A_per_um=ion/perimeter_um,
                Ioff_A_per_um=ioff/perimeter_um,Ion_Ioff=ion/ioff,
                Vth_V=crossing(normalized,1e-7),SS_mV_dec=ss,SS_status=ss_reason,
                kcl_max_abs_A=max(x[0] for x in kcl),kcl_pass=all(a<=b for a,b in kcl),
                nonmonotonic_indices=nonmonotonic,sweep_points=len(drain),
                terminal_signs=sorted(signs))


def analyze(folder,perimeter):
    values={};raw={}
    for name in ['low','high']:
        raw[name]={t:read_curve(folder/(name+'_'+t+'.dat')) for t in ['drain','source','gate']}
        values[name]=metric(raw[name],perimeter)
    vl,vh=[values[k]['Vth_V'] for k in ['low','high']]
    dibl=(vl-vh)/.55*1000 if vl is not None and vh is not None else None
    targets=dict(ion=values['high']['Ion_A_per_um']>=100e-6,
                 ioff=values['high']['Ioff_A_per_um']<=1e-9,
                 ratio=values['high']['Ion_Ioff']>=1e6,
                 low_vth=vl is not None and .1<=vl<=.5,
                 dibl=dibl is not None and 0<=dibl<=50,
                 ss=all(v['SS_mV_dec'] is not None and 60<=v['SS_mV_dec']<=90 for v in values.values()),
                 kcl=all(v['kcl_pass'] for v in values.values()),
                 monotonic=all(not v['nonmonotonic_indices'] for v in values.values()))
    return dict(perimeter_um=perimeter,metrics=values,DIBL_mV_V=dibl,engineering_targets=targets,
                engineering_targets_pass=all(targets.values()),
                simulator_log_review='REQUIRED_SEPARATELY',mesh_validation='PENDING',
                physical_validation='NOT_VALIDATED',raw_exports_only=True),raw


def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--perimeter-um',type=float,default=.04);p.add_argument('--plot',action='store_true')
    a=p.parse_args();result,raw=analyze(a.folder,a.perimeter_um)
    a.out.mkdir(parents=True,exist_ok=False)
    (a.out/'metrics.json').write_text(json.dumps(result,indent=2)+'\n')
    with (a.out/'idvg.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['Vds_V','Vgs_V','Id_A','Is_A','Ig_A','Id_A_per_um'])
        for name,vd in [('low',.05),('high',.6)]:
            for d,s,g in zip(raw[name]['drain'],raw[name]['source'],raw[name]['gate']):
                writer.writerow([vd,d[0],d[1],s[1],g[1],d[1]/a.perimeter_um])
    if a.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axs=plt.subplots(1,2,figsize=(10,4))
        for name,vd in [('low',.05),('high',.6)]:
            x=[v for v,i in raw[name]['drain']];y=[abs(i)/a.perimeter_um for v,i in raw[name]['drain']]
            axs[0].plot(x,[v*1e6 for v in y],label='Vds = %.2g V'%vd)
            axs[1].semilogy(x,y,label='Vds = %.2g V'%vd)
        for ax in axs:ax.set_xlabel('Vgs (V)');ax.grid(True,alpha=.25);ax.legend()
        axs[0].set_ylabel('|Id| (uA/um perimeter)');axs[1].set_ylabel('|Id| (A/um perimeter)')
        fig.suptitle('3D GAA DD diagnostic result; quantum/mesh validation pending')
        fig.tight_layout();fig.savefig(a.out/'idvg.png',dpi=180);plt.close(fig)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
