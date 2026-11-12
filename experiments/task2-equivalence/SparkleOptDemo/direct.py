#!/usr/bin/env python3
"""Propose and kernel-check a relation using only the two native circuit models."""
import concurrent.futures
import json
from pathlib import Path
import re
import time
from prepare import ROOT, BASELINE, identity, verify_pins
import prove


def embedding_map(base,opt,netnames):
    registers={r['name']:r['width'] for r in opt['registers']}
    mapping=[]
    for register in base['registers']:
        name,width=register['name'],register['width']
        if name in registers:
            if registers[name]!=width:raise ValueError('same-name native widths differ')
            item={'baseline':name,'optimized':name,'kind':'copy','width':width}
        else:
            aliases=[]
            if name in netnames:
                aliases=[n for n in registers if n in netnames and netnames[n]['bits']==netnames[name]['bits']]
            bits=[(n,int(match.group(1))) for n in registers
                  if (match:=re.fullmatch(re.escape(name)+r'_reg_(\d+)_',n))]
            if len(aliases)==1:
                item={'baseline':name,'optimized':aliases[0],'kind':'copy','width':width}
            elif len(bits)==1 and registers[bits[0][0]]==1 and bits[0][1]<width:
                item={'baseline':name,'optimized':bits[0][0],'kind':'expand_bit','bit':bits[0][1],'width':width}
            else:item={'baseline':name,'kind':'zero','width':width}
        mapping.append(item)
    if {m['optimized'] for m in mapping if 'optimized' in m}!=set(registers):
        raise ValueError('unmapped optimized registers in direct relation')
    return mapping


def field(name):return '«'+name+'»'


def generate_models(mapping,base,opt):
    for kind in ['inputs','outputs']:
        if sorted(base[kind])!=sorted(opt[kind]):raise ValueError('native interfaces differ')
    source=['import NativeArtifact','set_option maxRecDepth 65536','set_option maxHeartbeats 0',
            'namespace SparkleDirect',
            'import_native_sparkle "../SparkleDemo/build/native/Task2RTL.lean" as Baseline',
            'import_native_sparkle "build/native/Task2RTL.lean" as Optimized',
            'def inputs (value : Optimized.Inputs) : Baseline.Inputs := {']
    source += [f'  {field(name)} := value.{field(name)}' for name,_ in opt['inputs']]
    source += ['}','def outputs (value : Baseline.Outputs) : Optimized.Outputs := {']
    source += [f'  {field(name)} := value.{field(name)}' for name,_ in opt['outputs']]
    source += ['}','-- An embedding, not equality of arbitrary unrelated raw states.',
               'def embed (state : Optimized.State) : Baseline.State := {']
    for item in mapping:
        value='0'
        if item['kind']=='copy':value='state.'+field(item['optimized'])
        elif item['kind']=='expand_bit':
            high=item['width']-item['bit']-1
            value=f"(0#{high} ++ state.{field(item['optimized'])})"
            if item['bit']:value=f"({value} ++ 0#{item['bit']})"
        source.append(f"  {field(item['baseline'])} := {value}")
    source += ['}','end SparkleDirect']
    (ROOT/'Proof/DirectModels.lean').write_text('\n'.join(source)+'\n')


def generate_fields(base,opt):
    dest=ROOT/'Proof/build/generated';dest.mkdir(parents=True,exist_ok=True)
    fields=[('state_'+str(i),f'nextState.{field(r["name"])}',
             f'(embed (Optimized.evaluate input state).nextState).{field(r["name"])}')
             for i,r in enumerate(base['registers'])]
    fields += [('output_'+str(i),f'outputs.{field(name)}',
                f'(Optimized.evaluate input state).outputs.{field(name)}')
               for i,(name,_) in enumerate(opt['outputs'])]
    modules=[]
    for start in range(0,len(fields),16):
        module=f'DirectFields{start//16}';modules.append(module)
        source=['import DirectHelpers','set_option maxRecDepth 65536','set_option maxHeartbeats 0',
                'set_option linter.unusedSimpArgs false','namespace SparkleDirect']
        for name,left,right in fields[start:start+16]:
            source += [f'theorem agrees_{name} (input : Optimized.Inputs) (state : Optimized.State) :\n'
                       f'    (Baseline.evaluate (inputs input) (embed state)).{left} =\n'
                       f'    {right} := by\n  close_direct_transition\n#print axioms agrees_{name}']
        source += ['end SparkleDirect']
        (dest/f'{module}.lean').write_text('\n\n'.join(source)+'\n')
    return modules


def generate_assembly(modules,base,opt):
    source=[*(f'import {m}' for m in modules),'set_option maxRecDepth 65536',
            'set_option maxHeartbeats 0','namespace SparkleDirect']
    def ext(name,ty,fields):
        rows=[f'private theorem {name} {{a b : {ty}}}']
        rows += [f'    (h{i} : a.{field(f)} = b.{field(f)})' for i,f in enumerate(fields)]
        rows += ['    : a = b := by','  cases a','  cases b']
        rows += [f'  cases h{i}' for i in range(len(fields))]+['  rfl']
        source.append('\n'.join(rows))
    registers=base['registers'];groups=(len(registers)+63)//64
    for g in range(groups):
        ext(f'group{g}_ext',f'Baseline.StateGroup{g}',[r['name'] for r in registers[g*64:(g+1)*64]])
    ext('state_ext','Baseline.State',[f'toStateGroup{g}' for g in range(groups)])
    ext('outputs_ext','Optimized.Outputs',[name for name,_ in opt['outputs']])
    source += ['theorem nextState_agrees (input : Optimized.Inputs) (state : Optimized.State) :\n'
               '    (Baseline.evaluate (inputs input) (embed state)).nextState =\n'
               '    embed (Optimized.evaluate input state).nextState := by','  apply state_ext']
    for g in range(groups):
        source += [f'  · apply group{g}_ext']
        source += [f'    · exact agrees_state_{i} input state' for i in range(g*64,min(len(registers),(g+1)*64))]
    source += ['theorem outputs_agree (input : Optimized.Inputs) (state : Optimized.State) :\n'
               '    outputs (Baseline.evaluate (inputs input) (embed state)).outputs =\n'
               '    (Optimized.evaluate input state).outputs := by','  apply outputs_ext']
    source += [f'  · exact agrees_output_{i} input state' for i in range(len(opt['outputs']))]
    source += ['theorem initial_agrees : embed Optimized.initialState = Baseline.initialState := by rfl',
               '#print axioms nextState_agrees','#print axioms outputs_agree','#print axioms initial_agrees',
               'end SparkleDirect']
    (ROOT/'Proof/build/generated/DirectAssemble.lean').write_text('\n\n'.join(source)+'\n')


def generate_fresh_main(base,opt):
    source=['import DirectRuns','import DirectAudit','import Task2.ProofTools',
            'set_option maxRecDepth 65536','set_option maxHeartbeats 0',
            'namespace SparkleDirect.Main',
            'import_native_sparkle "../SparkleDemo/build/native/Task2RTL.lean" as FreshBaseline',
            'import_native_sparkle "build/native/Task2RTL.lean" as FreshOptimized']
    for label,metadata in [('Baseline',base),('Optimized',opt)]:
        source += [f'def checked{label} (input : {label}.Inputs) (state : {label}.State) : {label}.Evaluation :=',
                   f'  let native := Fresh{label}.evaluate',
                   '    { '+', '.join(f'{field(n)} := input.{field(n)}' for n,_ in metadata['inputs'])+' }',
                   '    { '+', '.join(f'{field(r["name"])} := state.{field(r["name"])}' for r in metadata['registers'])+' }',
                   '  { outputs := { '+', '.join(f'{field(n)} := native.outputs.{field(n)}' for n,_ in metadata['outputs'])+' }',
                   '    nextState := { '+', '.join(f'{field(r["name"])} := native.nextState.{field(r["name"])}' for r in metadata['registers'])+' } }',
                   f'def initial{label} : {label}.State :=',
                   '  { '+', '.join(f'{field(r["name"])} := Fresh{label}.initialState.{field(r["name"])}' for r in metadata['registers'])+' }',
                   f'theorem artifact_checked_{label} : checked{label} = {label}.evaluate := by',
                   '  funext input state','  kernel_rfl',
                   f'theorem initial_checked_{label} : initial{label} = {label}.initialState := by kernel_rfl']
    source += ['theorem transition_equivalence (input : Optimized.Inputs) (state : Optimized.State) :\n'
               '    (checkedBaseline (inputs input) (embed state)).nextState =\n'
               '      embed (checkedOptimized input state).nextState ∧\n'
               '    outputs (checkedBaseline (inputs input) (embed state)).outputs =\n'
               '      (checkedOptimized input state).outputs := by\n'
               '  rw [artifact_checked_Baseline, artifact_checked_Optimized]\n'
               '  exact ⟨nextState_agrees input state, outputs_agree input state⟩',
               'theorem observable_trace_equivalence (stream : Nat → Optimized.Inputs)\n'
               '    (state : Optimized.State) (n : Nat) :\n'
               '    outputs (checkedBaseline (inputs (stream n))\n'
               '      (runBaseline checkedBaseline stream (embed state) n)).outputs =\n'
               '    (checkedOptimized (stream n) (runOptimized checkedOptimized stream state n)).outputs := by\n'
               '  rw [artifact_checked_Baseline, artifact_checked_Optimized]\n'
               '  exact trace_outputs_agree stream state n',
               'theorem initial_states_related : embed initialOptimized = initialBaseline := by\n'
               '  rw [initial_checked_Baseline, initial_checked_Optimized]\n'
               '  exact initial_agrees',
               '#print axioms transition_equivalence','#print axioms observable_trace_equivalence',
               '#print axioms initial_states_related',
               'audit_native_dependencies transition_equivalence',
               'audit_native_dependencies observable_trace_equivalence',
               'audit_native_dependencies initial_states_related','end SparkleDirect.Main']
    (ROOT/'Proof/build/generated/DirectMain.lean').write_text('\n\n'.join(source)+'\n')



def reject_mutations(env):
    original=(ROOT/'Proof/build/generated/DirectMain.lean').read_text()
    evidence={}
    for label,source_path,target in [
        ('Baseline',BASELINE/'build/native/Task2RTL.lean','../SparkleDemo/build/native/Task2RTL.lean'),
        ('Optimized',ROOT/'build/native/Task2RTL.lean','build/native/Task2RTL.lean')]:
        changed,count=re.subn(r'(?m)^(    «in2_st0» := )(.+)$',r'\1(\2) ^^^ (1 : BitVec 32)',source_path.read_text())
        if count!=1:raise ValueError(f'expected one {label} output')
        artifact=ROOT/f'build/native/DirectMutated{label}.lean';artifact.write_text(changed)
        module=f'DirectMutation{label}'
        source=original.replace('"'+target+'"',f'"build/native/DirectMutated{label}.lean"')
        source=source.replace('namespace SparkleDirect.Main',f'namespace SparkleDirect.{module}')
        source=source.replace('end SparkleDirect.Main',f'end SparkleDirect.{module}')
        (ROOT/f'Proof/build/generated/{module}.lean').write_text(source)
        try:prove.check(module,env)
        except RuntimeError:
            log=ROOT/f'Proof/build/{module}.log'
            if f'artifact_checked_{label}' not in log.read_text():
                raise ValueError('direct mutation failed outside the fresh evaluator check')
            evidence[label]={'artifact':identity(artifact),'log':identity(log)}
            print(f'DIRECT_MUTATION_REJECTED {label}',flush=True)
        else:raise ValueError(f'{label} mutation inherited a direct proof')
    return evidence



def main():
    started=time.monotonic()
    path=ROOT/'build/direct-result.json';path.unlink(missing_ok=True)
    prove.verify_controls()
    pins=json.loads((ROOT/'pins.json').read_text());verify_pins(pins)
    base=json.loads((BASELINE/'build/native/Task2RTL.json').read_text())
    opt=json.loads((ROOT/'build/native/Task2RTL.json').read_text())
    nets=json.loads((ROOT/'build/normalized.json').read_text())['modules']['task2']['netnames']
    mapping=embedding_map(base,opt,nets)
    (ROOT/'build/direct-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n')
    generate_models(mapping,base,opt)
    env=prove.environment()
    checks=[prove.check(m,env) for m in ['SharedMath','DirectModels','DirectHelpers']]
    modules=generate_fields(base,opt)
    generate_assembly(modules,base,opt)
    generate_fresh_main(base,opt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fs=[pool.submit(prove.check,m,env) for m in modules]
        for future in concurrent.futures.as_completed(fs):checks.append(future.result())
    for module in ['DirectAssemble','DirectRuns','DirectAudit','DirectMain']:
        checks.append(prove.check(module,env))
    public=checks[-1]['axioms']
    expected={f'SparkleDirect.Main.{name}' for name in [
        'transition_equivalence','observable_trace_equivalence','initial_states_related']}
    if not expected<=set(public):raise ValueError('missing direct theorem axiom audit')
    text=(ROOT/'Proof/build/DirectMain.log').read_text()
    dependencies=re.findall(r'NATIVE_DEPENDENCIES_CHECKED (\w+): (\d+) declarations; no retained circuit',text)
    if {name for name,_ in dependencies}!={name.rsplit('.',1)[-1] for name in expected}:
        raise ValueError('missing transitive direct dependency audit')
    count=sum(len(c['axioms']) for c in checks if c['module'].startswith('DirectFields'))
    if count!=len(base['registers'])+len(opt['outputs']):raise ValueError('missing direct field audit')
    mutation=reject_mutations(env)
    prove.verify_controls();verify_pins(pins)
    result={'status':'proved','elapsed_seconds':round(time.monotonic()-started,6),'axioms':public,'checks':checks,
        'state_fields':len(base['registers']),'outputs':len(opt['outputs']),
        'public_theorem':'SparkleDirect.Main.observable_trace_equivalence',
        'scope':'All cycles and arbitrary lifted input streams, starting from states related by embed',
        'relation':{'copy':sum(m['kind']=='copy' for m in mapping),
                    'expand_bit':sum(m['kind']=='expand_bit' for m in mapping),
                    'zero':sum(m['kind']=='zero' for m in mapping)},
        'retained_circuit_dependencies':False,
        'dependency_audits':dict(dependencies),'mutations_rejected':mutation,
        'native_models':[identity(BASELINE/'build/native/Task2RTL.lean'),identity(ROOT/'build/native/Task2RTL.lean')],
        'mapping':identity(ROOT/'build/direct-mapping.json'),
        'inputs':[identity(p) for p in sorted((ROOT/'Proof').glob('*.lean'))]+[
                  identity(ROOT/'direct.py'),identity(ROOT/'prove.py'),identity(ROOT/'prepare.py'),
                  identity(ROOT/'build/result.json')]}
    path.write_text(json.dumps(result,indent=2)+'\n')
    print('SPARKLE_DIRECT_TRACE_EQUIVALENCE_PROVED',flush=True)

if __name__=='__main__':main()
