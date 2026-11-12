#!/usr/bin/env python3
"""Kernel-check the optimized native import against the candidate reference."""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import subprocess
from prepare import ROOT, REPO, BASELINE, baseline, execute, identity, reference_schema, verify_pins

LEAN_BIN=Path(os.environ.get('SPARKLE_PROOF_LEAN_BIN',
    '/nix/store/wzr0jh4q335z1d4rcdq0xw9i26ahxvg3-lean-4.35.0/bin'))
NAMESPACE='SparkleOptProof'
CORE='Task2.Imported.CandidateCore'
WORKERS=4
BATCH_SIZE=16
ALLOWED_AXIOMS={'propext','Classical.choice','Quot.sound'}


def environment():
    env=dict(os.environ)
    env['PATH']=str(LEAN_BIN)+':'+env['PATH']
    path=subprocess.check_output([str(LEAN_BIN/'lake'),'env','printenv','LEAN_PATH'],
                                 cwd=REPO,env=env,text=True).strip()
    env['LEAN_PATH']=':'.join([str(ROOT/'Proof/build'),str(BASELINE/'Proof/build'),
        *[str((REPO/part).resolve()) for part in path.split(':')]])
    env['LEAN_NUM_THREADS']='2'
    return env


def check(module,env):
    output=ROOT/'Proof/build';output.mkdir(parents=True,exist_ok=True)
    source=ROOT/f'Proof/{module}.lean'
    if not source.exists():source=output/f'generated/{module}.lean'
    record=execute([LEAN_BIN/'lean','--root='+str(source.parent),'-o',output/f'{module}.olean',source],
                   output/f'{module}.log',[],env)
    text=(output/f'{module}.log').read_text()
    axioms={}
    for name,names in re.findall(r"'([^']+)' depends on axioms:\s*\[([^\]]*)\]",text):
        values=[v.strip() for v in names.split(',') if v.strip()]
        if not set(values)<=ALLOWED_AXIOMS:raise ValueError(f'unexpected axioms: {name}: {values}')
        axioms[name]=values
    for name in re.findall(r"'([^']+)' does not depend on any axioms",text):axioms[name]=[]
    record.update(module=module,source=identity(source),object=identity(output/f'{module}.olean'),axioms=axioms)
    print(f'PROOF_CHECKED {module}',flush=True)
    return record


def generate_fields(schema):
    dest=ROOT/'Proof/build/generated';dest.mkdir(parents=True,exist_ok=True)
    fields=[(f's{i}',f'nextState.g{i//128}.s{i}') for i in range(schema['state_count'])]
    fields += [(f'o{i}',f'outputs.o{i}') for i in range(len(schema['outputs']))]
    memories={f's{i}' for i in schema['memory_indices']}
    modules=[]
    for start in range(0,len(fields),BATCH_SIZE):
        name=f'OptFields{start//BATCH_SIZE}';modules.append(name)
        source=['import OptHelpers','set_option maxRecDepth 65536','set_option maxHeartbeats 0',
                'set_option linter.unusedSimpArgs false',f'namespace {NAMESPACE}']
        for field,projection in fields[start:start+BATCH_SIZE]:
            tactic='rfl' if field in memories else 'close_opt_transition'
            source.append(f'theorem agrees_{field} (inputs : {CORE}.Inputs) (state : {CORE}.State) :\n'
                          f'    (evaluate inputs state).{projection} =\n'
                          f'    ({CORE}.evaluate inputs state).{projection} := by\n'
                          f'  {tactic}\n#print axioms agrees_{field}')
        source.append(f'end {NAMESPACE}')
        (dest/f'{name}.lean').write_text('\n\n'.join(source)+'\n')
    return modules


def generate_assembly(modules,schema):
    count=schema['state_count'];groups=(count+127)//128
    source=[*(f'import {m}' for m in modules),'import Task2.ProofTools',
            'set_option maxRecDepth 65536','set_option maxHeartbeats 0',f'namespace {NAMESPACE}']
    def ext(name,ty,fields):
        lines=[f'private theorem {name} {{a b : {CORE}.{ty}}}']
        lines += [f'    (h{k} : a.{field} = b.{field})' for k,field in enumerate(fields)]
        lines += ['    : a = b := by','  cases a','  cases b']
        lines += [f'  cases h{k}' for k in range(len(fields))]+['  rfl']
        source.append('\n'.join(lines))
    for g in range(groups):ext(f'group{g}_ext',f'StateGroup{g}',[f's{i}' for i in range(g*128,min(count,(g+1)*128))])
    ext('state_ext','State',[f'g{i}' for i in range(groups)])
    ext('outputs_ext','Outputs',[f'o{i}' for i in range(len(schema['outputs']))])
    ext('evaluation_ext','Evaluation',['outputs','nextState','outputDefined','transitionDefined'])
    source += [f'theorem transfer_agrees (inputs : {CORE}.Inputs) (state : {CORE}.State) :\n'
               f'    evaluate inputs state = {CORE}.evaluate inputs state := by',
               '  apply evaluation_ext','  · apply outputs_ext']
    source += [f'    · exact agrees_o{i} inputs state' for i in range(len(schema['outputs']))]
    source += ['  · apply state_ext']
    for g in range(groups):
        source += [f'    · apply group{g}_ext']
        source += [f'      · exact agrees_s{i} inputs state' for i in range(g*128,min(count,(g+1)*128))]
    source += ['  · rfl','  · rfl','#print axioms transfer_agrees',f'end {NAMESPACE}']
    (ROOT/'Proof/build/generated/OptAssemble.lean').write_text('\n\n'.join(source)+'\n')


def verify_controls():
    controls=json.loads((ROOT/'build/result.json').read_text())
    if controls['status']!='passed_controls' or len(controls['cases'])!=7:
        raise ValueError('fresh candidate controls required')
    for value in controls['inputs']+controls['artifacts']:baseline.verify_identity(value)
    for name in ['native/Task2RTL.lean','native/Task2RTL.json','normalized.json']:
        expected=(ROOT/'build'/name).resolve()
        matches=[v for v in controls['artifacts'] if Path(v['path']).resolve()==expected]
        if len(matches)!=1:raise ValueError(f'native artifact missing or duplicated: {name}')
        baseline.verify_identity(matches[0])
    return controls


def reject_mutation(env):
    text=(ROOT/'build/native/Task2RTL.lean').read_text()
    changed,count=re.subn(r'(?m)^(    «in2_st0» := )(.+)$',r'\1(\2) ^^^ (1 : BitVec 32)',text)
    if count!=1:raise ValueError('expected one native output')
    artifact=ROOT/'build/native/MutatedTask2RTL.lean';artifact.write_text(changed)
    source=(ROOT/'Proof/OptMain.lean').read_text().replace('Task2RTL.lean','MutatedTask2RTL.lean')
    source=source.replace('SparkleOptProof.Main','SparkleOptProof.Mutation')
    (ROOT/'Proof/build/generated/OptMutation.lean').write_text(source)
    try:check('OptMutation',env)
    except RuntimeError:
        log=ROOT/'Proof/build/OptMutation.log'
        if 'artifact_checked' not in log.read_text():raise ValueError('mutation failed outside artifact equality')
        print('OPT_NATIVE_MUTATION_REJECTED',flush=True)
        return {'artifact':identity(artifact),'log':identity(log)}
    raise ValueError('mutated native circuit inherited cached proof')


def main():
    started=time.monotonic()
    path=ROOT/'build/universal-result.json';path.unlink(missing_ok=True)
    verify_controls()
    pins=json.loads((ROOT/'pins.json').read_text());verify_pins(pins)
    reference=json.loads(Path(pins['inputs']['reference_schema']['path']).read_text())
    schema=reference_schema(reference,json.loads((ROOT/'build/native/Task2RTL.json').read_text()),
        json.loads((ROOT/'build/normalized.json').read_text())['modules']['task2']['netnames'])
    (ROOT/'build/bindings.json').write_text(json.dumps(schema,indent=2)+'\n')
    env=environment()
    version=subprocess.check_output([str(LEAN_BIN/'lean'),'--version'],text=True).strip()
    if not version.startswith('Lean (version 4.35.0,'):raise ValueError('wrong proof toolchain')
    print('[proof 1/4] Checking candidate model and shared kernel lemmas',flush=True)
    records=[]
    for module in ['SharedMath','OptReferenceAdapter','OptModel','OptHelpers']:records.append(check(module,env))
    modules=generate_fields(schema);generate_assembly(modules,schema)
    print(f"[proof 2/4] Checking {schema['state_count']} next-state fields and {len(schema['outputs'])} outputs",flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures=[pool.submit(check,m,env) for m in modules]
        for future in concurrent.futures.as_completed(futures):records.append(future.result())
    count=sum(len(r['axioms']) for r in records if r['module'].startswith('OptFields'))
    if count!=schema['state_count']+len(schema['outputs']):raise ValueError('missing field axiom audits')
    print('[proof 3/4] Assembling complete equality and the candidate temporal theorem',flush=True)
    for module in ['OptAssemble','OptEquivalence','OptMain']:records.append(check(module,env))
    public=records[-1]['axioms']
    if not all(f'{NAMESPACE}.Main.{n}' in public for n in ['observable_equivalence','first_result']):
        raise ValueError('missing public theorem audits')
    print('[proof 4/4] Rejecting native output mutation',flush=True)
    mutation=reject_mutation(env)
    verify_controls();verify_pins(pins)
    result={'status':'proved','elapsed_seconds':round(time.monotonic()-started,6),'state_fields_checked':schema['state_count'],'outputs_checked':len(schema['outputs']),
            'completion_edges':436,'public_theorem':f'{NAMESPACE}.Main.observable_equivalence',
            'first_result_theorem':f'{NAMESPACE}.Main.first_result','axioms':public,
            'controls':identity(ROOT/'build/result.json'),'native_model':identity(ROOT/'build/native/Task2RTL.lean'),
            'checks':records,'mutation_rejected':mutation,
            'proof_reuse':'Complete new transition equality followed by the retained candidate temporal theorem',
            'inputs':[identity(p) for p in sorted((ROOT/'Proof').glob('*.lean'))]+
                     [identity(ROOT/'prove.py'),identity(ROOT/'prepare.py'),identity(ROOT/'build/bindings.json')]}
    path.write_text(json.dumps(result,indent=2)+'\n')
    print('SPARKLE_OPT_UNIVERSAL_EQUIVALENCE_PROVED',flush=True)

if __name__=='__main__':main()
