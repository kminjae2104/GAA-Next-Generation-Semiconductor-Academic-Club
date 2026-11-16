"""Generate a rectangular 3D GAA device; dimensions are nm in the specification."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PARAMETERS = dict(gate_nm=40, width_nm=10, height_nm=10, oxide_nm=1,
                  gate_metal_nm=3, extension_nm=20, contact_nm=5,
                  acceptor_cm3=1e16, donor_cm3=1e20, workfunction_eV=4.5,
                  temperature_K=300, vds_V=[0.05,0.6], gate_start_V=-0.2,
                  gate_stop_V=0.8, gate_step_V=0.02, effective_perimeter_um=0.04)


def geometry(p):
    w,h,t,m,e,l,c=[p[k] for k in ['width_nm','height_nm','oxide_nm','gate_metal_nm','extension_nm','gate_nm','contact_nm']]
    total=2*e+l
    boxes=[]
    def box(name,mat,x1,x2,y1,y2,z1,z2,electrode=None):
        if min(x2-x1,y2-y1,z2-z1)<=0:raise ValueError('Empty region')
        boxes.append(dict(id=len(boxes)+1,name=name,material=mat,
                          nm=[x1,x2,y1,y2,z1,z2],electrode=electrode))
    box('source_si','Silicon',0,w,0,h,0,e)
    box('channel','Silicon',0,w,0,h,e,e+l)
    box('drain_si','Silicon',0,w,0,h,e+l,total)
    box('source','Aluminum',0,w,0,h,-c,0,2)
    box('drain','Aluminum',0,w,0,h,total,total+c,3)
    # Four disjoint rectangles form each closed ring; only their faces touch.
    for name,x1,x2,y1,y2 in [('left',-t,0,-t,h+t),('right',w,w+t,-t,h+t),
                            ('top',0,w,-t,0),('bottom',0,w,h,h+t)]:
        box('oxide_'+name,'Silicon Oxide',x1,x2,y1,y2,0,total)
    for index,(side,x1,x2,y1,y2) in enumerate([('left',-t-m,-t,-t-m,h+t+m),
                            ('right',w+t,w+t+m,-t-m,h+t+m),
                            ('top',-t,w+t,-t-m,-t),('bottom',-t,w+t,h+t,h+t+m)]):
        box('gate' if index==0 else 'gate_'+side,'Aluminum',x1,x2,y1,y2,e,e+l,1 if index==0 else index+3)
    for a,b in itertools.combinations(boxes,2):
        overlap=[min(a['nm'][i+1],b['nm'][i+1])-max(a['nm'][i],b['nm'][i]) for i in (0,2,4)]
        if all(v>1e-10 for v in overlap):raise ValueError('Overlapping region volumes')
    assert len({r['id'] for r in boxes})==13
    assert {r['electrode'] for r in boxes if r['electrode']}=={1,2,3,4,5,6}
    return boxes


def deck(p, fine=False, smoke=False):
    # A two-layer-oxide diagnostic mesh is used only for the short smoke test.
    # Full and fine performance sweeps keep the specified 4-/8-layer oxide mesh.
    f=2 if smoke else 0.5 if fine else 1
    regions=geometry(p)
    lines=['# Generated GAA; nm converted to micrometers. DD diagnostic model.',
           '# See the repository reference index and design/targets document.',
           'go devedit simflags="-3d"','work.area x1=-0.004 y1=-0.004 x2=0.014 y2=0.014']
    for r in regions:
        x1,x2,y1,y2,z1,z2=[v/1000 for v in r['nm']]
        points=[(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)]
        s='region reg=%d name=%s mat="%s" z1=%.9g z2=%.9g'%(r['id'],r['name'],r['material'],z1,z2)
        if r['electrode']:s+=' elec.id=%d'%r['electrode']
        s+=' points="'+' '.join('%.9g,%.9g'%q for q in points)+'"'
        lines.append(s)
    lines+=['base.mesh height=%.9g width=%.9g'%(0.001*f,0.001*f),
            'bound.cond !apply max.slope=28 max.ratio=300 rnd.unit=0.00001 line.straightening=1 align.points when=automatic',
            'constr.mesh max.angle=90 max.ratio=300 max.height=0.003 max.width=0.003 min.height=0.00002 min.width=0.00002']
    for r in regions:
        step={'Silicon':0.001,'Silicon Oxide':0.00025,'Aluminum':0.003}[r['material']]*f
        lines.append('constr.mesh region=%d default max.height=%.9g max.width=%.9g'%(r['id'],step,step))
    e,l,c=[p[k]/1000 for k in ['extension_nm','gate_nm','contact_nm']]
    for z in [-c,0,e,e+l/2,e+l,2*e+l,2*e+l+c]:
        step=0.001*f if e<=z<=e+l else 0.002*f
        lines.append('z.plane z=%.9g spacing=%.9g'%(z,step))
    lines+=['z.plane maximum.spacing=%.9g maximum.ratio=1.5'%(0.002*f),
            'Mesh Mode=MeshBuild','structure outf=geometry.str','go atlas',
            'mesh infile=geometry.str',
            'doping uniform region=1 n.type conc=%.9g'%p['donor_cm3'],
            'doping uniform region=2 p.type conc=%.9g'%p['acceptor_cm3'],
            'doping uniform region=3 n.type conc=%.9g'%p['donor_cm3'],
            'contact name=gate workfunction=%.9g'%p['workfunction_eV'],
            'contact name=gate_right workfunction=%.9g common=gate short'%p['workfunction_eV'],
            'contact name=gate_top workfunction=%.9g common=gate short'%p['workfunction_eV'],
            'contact name=gate_bottom workfunction=%.9g common=gate short'%p['workfunction_eV'],
            'models fermi conmob fldmob srh bgn temperature=%.9g print'%p['temperature_K'],
            'method gummel newton trap maxtrap=10 itlimit=50','solve init',
            'save outf=equilibrium.str','method newton trap maxtrap=10 itlimit=50']
    for index,vd in enumerate([0.05] if smoke else p['vds_V']):
        name='low' if index==0 else 'high'
        if index:lines+=['load infile=equilibrium.str']
        lines+=['solve vdrain=0.01','solve name=drain vstep=0.01 vfinal=%.9g'%vd,
                'solve name=gate vstep=-0.02 vfinal=%.9g'%p['gate_start_V'],
                'log outf=idvg_%s.log'%name,'solve vgate=%.9g'%p['gate_start_V'],
                'solve name=gate vstep=%.9g vfinal=%.9g'%(0.1 if smoke else p['gate_step_V'],0.2 if smoke else p['gate_stop_V']),
                'log off','save outf=final_%s.str'%name,
                'extract init infile="idvg_%s.log"'%name]
        for terminal in ['drain','source','gate']:
            lines.append('extract name="%s_%s" curve(v."gate",i."%s") outfile="%s_%s.dat"'%(name,terminal,terminal,name,terminal))
    lines+=['quit']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=BASE/'tcad'/'v2_common_gate')
    p.add_argument('--fine',action='store_true');p.add_argument('--smoke',action='store_true')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    name='gaa_'+('fine' if a.fine else 'coarse')+('_smoke' if a.smoke else '')
    target=a.out/(name+'.in')
    data=deck(PARAMETERS,a.fine,a.smoke)
    if target.exists() and target.read_text(encoding='utf-8')!=data:
        raise FileExistsError('Preserve old deck and use a new --out directory')
    target.write_text(data,encoding='utf-8',newline='\n')
    metadata=dict(parameters=PARAMETERS,regions=geometry(PARAMETERS),fine=a.fine,smoke=a.smoke,
                  model_revision='v2_explicit_common_gate',diagnostic_mesh_scale=2 if a.smoke else None,
                  sha256=hashlib.sha256(data.encode()).hexdigest(),simulator_execution='NOT_RUN')
    (a.out/(name+'.json')).write_text(json.dumps(metadata,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(target)


if __name__=='__main__':main()
