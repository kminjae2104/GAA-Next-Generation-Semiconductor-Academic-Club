"""Plot native ATLAS data without interpolation, extrapolation, or changing source logs."""
from pathlib import Path
import hashlib,json,math,shlex
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/'그림/발표선정_20261118'
OUT=SOURCE/'그래프'

def main():
    OUT.mkdir(exist_ok=False)
    records=[]
    for path in sorted(SOURCE.glob('*.log')):
        original=path.read_bytes();names=None;rows=[]
        for line in original.decode().splitlines():
            if line.startswith('f '):
                f=shlex.split(line);names=f[2:]
                if f[1]!='3' or names!=['gate','source','drain']:raise ValueError('Unknown terminal layout')
            elif line.startswith('d '):
                v=list(map(float,line.split()[1:]))
                if names is None or len(v)!=9 or not all(math.isfinite(x) for x in v):raise ValueError('Invalid native data')
                rows.append(v)
        if not rows:raise ValueError('Empty native log')
        vg=[v[0] for v in rows];id_abs=[abs(v[8]) for v in rows]
        if any(x<=0 for x in id_abs):raise ValueError('Zero current: logarithmic display requires explicit review')
        vd=[v[6] for v in rows]
        if max(vd)-min(vd)>1e-6:raise ValueError('Changing Vds within sweep')
        if any(abs(v[3])>1e-8 for v in rows):raise ValueError('Nonzero source voltage')
        valid=abs(vd[0]-.6)<=1e-6 and abs(vg[0]+.2)<=1e-6 and abs(vg[-1]-.8)<=1e-6 and len(rows)==51 and all(abs(b-a-.02)<=1e-6 for a,b in zip(vg,vg[1:]))
        reason='Target bias and 51-point gate grid reached' if valid else 'Vds target NOT reached' if abs(vd[0]-.6)>1e-6 else 'Gate sweep incomplete / adaptive steps'
        fig,axes=plt.subplots(1,2,figsize=(12,5.2),layout='constrained')
        axes[0].plot(vg,[x*1e6 for x in id_abs],'-o',markersize=2.5,lw=1.4)
        axes[1].semilogy(vg,id_abs,'-o',markersize=2.5,lw=1.4)
        for ax in axes:
            ax.set_xlabel('$V_{GS}$ (V)');ax.grid(True,which='both',alpha=.22);ax.set_xlim(-.22,.82)
        axes[0].set_ylabel('$|I_D|$ (µA / single wire)');axes[1].set_ylabel('$|I_D|$ (A / single wire)')
        axes[0].set_ylim(bottom=0)
        fig.suptitle(path.stem+' — Id–Vg\n'+f'Actual Vds = {vd[0]:.9g} V; {len(rows)} native points; '+reason,fontsize=12)
        fig.text(.5,-.035,'Observed samples only; no extrapolation. Gate perimeter = 0.04 µm; divide I by 0.04 for A/µm.\nSource: '+path.name+' | Physics calibration remains unvalidated.',ha='center',fontsize=9)
        target=OUT/(path.stem+'_IdVg.png');fig.savefig(target,dpi=200,bbox_inches='tight',facecolor='white');plt.close(fig)
        assert path.read_bytes()==original
        records.append({'source':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(original).hexdigest(),'output':target.name,'points':len(rows),'vgs_range_V':[min(vg),max(vg)],'actual_vds_V':vd[0],'target_bias_and_grid_reached':valid,'note':reason,'current_unit':'A per single wire','interpolation_or_extrapolation':False})
    (OUT/'검증기록.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(records,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
