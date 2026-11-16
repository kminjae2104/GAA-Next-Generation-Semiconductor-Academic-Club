"""Plot only real, natively cross-checked diagnostic currents. No synthetic curves."""
import argparse
import json
from pathlib import Path
import analyze


def main():
    p=argparse.ArgumentParser();p.add_argument('collection',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();folder=a.collection/'gaa'/'execution'
    config=json.loads((a.collection/'run_config.json').read_text())
    parameters=config['parameters'];perimeter=parameters['effective_perimeter_um']
    curves={t:analyze.read_curve(folder/('low_'+t+'.dat'),min_points=5) for t in ['drain','source','gate']}
    checks=analyze.validate_native_log(folder/'idvg_low.log',.05,curves)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x=[v for v,i in curves['drain']];y=[abs(i)/perimeter for v,i in curves['drain']]
    fig,axs=plt.subplots(1,2,figsize=(9,3.8))
    axs[0].plot(x,[v*1e6 for v in y],'o-');axs[1].semilogy(x,y,'o-')
    for ax in axs:ax.set_xlabel('Vgs (V)');ax.grid(True,alpha=.25)
    axs[0].set_ylabel('|Id| (uA/um perimeter)');axs[1].set_ylabel('|Id| (A/um perimeter)')
    fig.suptitle('3D GAA diagnostic: Vds = 0.05 V, 300 K; Lg = 40 nm, Si = 10 x 10 nm')
    fig.text(.5,.01,'Real 5-point smoke sweep; DD model, diagnostic mesh; performance/quantum validation pending',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.05,1,.93]);a.out.parent.mkdir(parents=True,exist_ok=True)
    if a.out.exists():raise FileExistsError('Preserve existing figure')
    fig.savefig(a.out,dpi=180);plt.close(fig)
    print(json.dumps({'figure':str(a.out),'native_export_check':checks,'performance_validation':'PENDING'}))


if __name__=='__main__':main()
