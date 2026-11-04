"""Warm incremental proof-composition replay, separate from construction/setup costs."""
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys


def summarize_runs(runs):
    times=[r['elapsed_seconds'] for r in runs if 'elapsed_seconds' in r]
    proved=bool(runs) and all(r['status']=='proved' for r in runs)
    return {'all_proved':proved,'median_attempt_wall_seconds':statistics.median(times) if times else None,
            'median_proved_wall_seconds':statistics.median(times) if proved and len(times)==len(runs) else None,
            'peak_process_rss_kib':max((r.get('peak_rss_kib',0) for r in runs),default=None),'runs':runs}


def replay_composition(out,design,repeat,timeout):
    from run import ROOT,artifact,execute,audit_axioms,verify_manifest,require_current_artifact
    result_path=out/f'check-{design}-result.json';result=json.loads(result_path.read_text());verify_manifest(result)
    if result['status']!='proved':raise ValueError('a complete checked theorem bundle is required for warm replay')
    for name in ['Hardware','WordDot']:
        require_current_artifact(result,f'proof_support_{name}.lean',ROOT/f'Task2/{name}.lean')
    folder=out/'compare'/design/f'repeat-{repeat}';folder.mkdir(parents=True,exist_ok=True)
    original=Path(result['artifacts'][f'certificate_{design.title()}TraceCorrect']['path'])
    code=original.read_text()+f'''
namespace Task2.WarmReplay
theorem {design}_claim : Task2.Implements Task2.Imported.{design} Task2.sourceEval :=
  Task2.Imported.{design.title()}Trace.correct
end Task2.WarmReplay
#print axioms Task2.WarmReplay.{design}_claim
'''
    source=folder/'Replay.lean';source.write_text(code)
    lean=shutil.which('lean')
    if lean is None:raise ValueError('run comparison inside the pinned Nix environment')
    env=dict(os.environ);env['LEAN_PATH']=subprocess.check_output(['lake','env','printenv','LEAN_PATH'],cwd=ROOT,text=True).strip()
    # Only this retained proof source is present in the working directory. No
    # exploratory symbolic scripts/DAGs are consulted; dependencies are cached.
    command=[sys.executable,'-c','import os,sys;os.chdir(sys.argv[1]);os.execv(sys.argv[2],sys.argv[2:])',
             str(folder),lean,'-o',str(folder/'Replay.olean'),str(source)]
    replay=execute(command,folder/'replay.log',env=env,timeout=timeout)
    if replay['status']=='prepared':
        try:
            replay['axioms']=audit_axioms(Path(replay['log']['path']).read_text(),f'Task2.WarmReplay.{design}_claim')
            replay['status']='proved'
        except ValueError as error:replay['status']='failed';replay['error']=str(error)
    replay.update(design=design,cache_state='prechecked dependency/chunk/transition oleans; freshly kernel-check final first-result/correctness composition',
                  search_artifacts='absent from isolated working directory; retained Lean source only',
                  claim=f'Implements Imported.{design} sourceEval, final composition replay',
                  artifacts={'retained_composition':artifact(original),'replay_source':artifact(source),'proved_stage_result':artifact(result_path)})
    (folder/'result.json').write_text(json.dumps(replay,indent=2)+'\n')
    return replay


def compare_designs(out,repeats=3,timeout=600):
    from run import artifact,verify_manifest
    from eqy_compare import run_comparison
    out=Path(out).resolve()
    if repeats<1 or timeout<=0:raise ValueError('positive repeat count and timeout are required')
    proof_results={}
    for design in ['baseline','candidate']:
        path=out/f'check-{design}-result.json';proof_results[design]=json.loads(path.read_text());verify_manifest(proof_results[design])
        if proof_results[design]['status']!='proved':raise ValueError('both complete Lean proofs are required')
    lean={}
    # Keep measurements serial. A faster replay is never interpreted as lower
    # engineering effort by the milestone report.
    for design in ['baseline','candidate']:
        samples=[]
        for i in range(repeats):
            samples.append(replay_composition(out,design,i,timeout))
            print(f'warm {design} {i}: {samples[-1]["status"]} {samples[-1]["elapsed_seconds"]:.3f}s',flush=True)
        lean[design]=summarize_runs(samples)
    eqy_runs=[]
    for i in range(repeats):
        run=run_comparison(out,timeout,label=f'warm-{i}')
        primary=run.get('runs',[])
        if primary:
            run['elapsed_seconds']=primary[-1]['elapsed_seconds'];run['peak_rss_kib']=primary[-1]['peak_rss_kib']
        run['cache_state']='warm tool/filesystem caches; fresh EQY work directory and solver jobs'
        eqy_runs.append(run)
    bindings={design+'_proof':artifact(out/f'check-{design}-result.json') for design in ['baseline','candidate']}
    return {'status':'prepared','scope':'warm incremental Lean composition replay and separate EQY refinement; different claims and trust bases',
            'repeats':repeats,'timeout_seconds_per_run':timeout,'lean':lean,'eqy':summarize_runs(eqy_runs),
            'first_run_costs':{design:proof_results[design]['elapsed_seconds'] for design in ['baseline','candidate']},
            'construction_cache_state':'fresh generated proof modules, existing dependency caches; recorded separately from warm replay',
            'engineering_effort_inference':'none; active engineering duration must be measured separately',
            'artifacts':bindings}
