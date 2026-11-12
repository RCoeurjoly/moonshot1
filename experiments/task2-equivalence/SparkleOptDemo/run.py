#!/usr/bin/env python3
"""Fresh opt-full RTL, upstream Sparkle import and seven three-way controls."""
import json
import os
from pathlib import Path
import subprocess
from prepare import ROOT, BASELINE, baseline, execute, identity, prepare_candidate, verify_pins


def main():
    out = ROOT/'build'
    out.mkdir(exist_ok=True)
    for name in ['result.json','universal-result.json','direct-result.json']:
        (out/name).unlink(missing_ok=True)
    pins = json.loads((ROOT/'pins.json').read_text())
    verify_pins(pins)
    version = subprocess.check_output(['lean','--version'],text=True).strip()
    if not version.startswith(f"Lean (version {pins['lean']},"):
        raise ValueError(f'wrong Sparkle Lean toolchain: {version}')
    cases = json.loads((ROOT/'controls.json').read_text())
    for case in cases:
        if case['expected_output_words'] != [[sum(a*b for a,b in zip(*case['input_words'])) % 2**32]]:
            raise ValueError('incorrect modular control result')
    records = []
    rtl = prepare_candidate(out,pins,records)
    print('[1/4] Exact frozen opt-full RTL and structural statistics reproduced',flush=True)
    dependency = ROOT/'.lake/packages/sparkle'
    revision = subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
    if revision != pins['sparkle']['revision']: raise ValueError('Sparkle revision changed')
    subprocess.run(['git','-C',str(dependency),'diff','--exit-code','HEAD'],check=True,
                   stdout=subprocess.DEVNULL)
    execute(['lake','build','NativeExport','sparkle-import'],out/'lake-build.log',records)
    execute([ROOT/'.lake/build/bin/sparkle-import',out/'task2.sv',out],out/'sparkle-import.log',records)
    execute(['lake','env','lean','ExportTask2.lean'],out/'native-export.log',records)
    execute(['lake','build','native-traces'],out/'native-build.log',records)
    execute([ROOT/'.lake/build/bin/native-traces',ROOT/'controls.json',out],out/'native-traces.log',records)
    print('[2/4] Candidate native model reflected and executed by Sparkle',flush=True)
    env = dict(os.environ)
    env['PATH'] = ':'.join(str(Path(p)/'bin') for p in pins['simulation_build_inputs'])+':'+env['PATH']
    c_source = out/'task2-sim.c'
    c_source.write_text((out/'sparkle.c').read_text()+baseline.c_harness(cases))
    execute([baseline.compiler_for(env),'-O2','-std=c11',c_source,'-o',out/'sparkle-sim'],out/'c-build.log',records,env)
    execute([out/'sparkle-sim',out],out/'c-run.log',records,env)
    verilator = next(Path(p)/'bin/verilator' for p in pins['simulation_build_inputs'] if 'verilator' in p)
    execute([verilator,'--binary','--timing','--language','1800-2017','-Wno-fatal',
             '-top','tb_control','-Mdir',out/'obj_dir','-o','sim_control',
             '-f',rtl/'sources.f',ROOT/'control_tb.sv'],out/'verilator-build.log',records,env)
    print('[3/4] Sparkle C and original optimized RTL built',flush=True)
    comparison = []
    for index, case in enumerate(cases):
        files=[]
        for label,words in zip(['a','b'],case['input_words']):
            path=out/f'case-{index}-{label}.hex'
            path.write_text(''.join(f'{word:08x}\n' for word in words));files.append(path)
        expected=case['expected_output_words'][0][0]
        trace=out/f'case-{index}-rtl.csv'
        execute([out/'obj_dir/sim_control',f'+A={files[0]}',f'+B={files[1]}',
                 f'+TRACE={trace}',f'+EXPECTED={expected:08x}'],out/f'case-{index}-rtl.log',records)
        golden=baseline.read_trace(trace)
        if len(golden)!=436:raise ValueError('first result must have 436 edges')
        evidence={'case':index}
        for backend in ['lean','c']:
            evidence[backend]=baseline.compare_traces(golden,baseline.read_trace(out/f'case-{index}-{backend}.csv'),expected)
        comparison.append(evidence)
        print(f'case {index}: optimized RTL = Sparkle Lean = Sparkle C; payload={expected}; 436 edges',flush=True)
    wrong=baseline.read_trace(out/'case-6-lean.csv');wrong[-1]['in2_st0']^=1
    try:baseline.compare_traces(baseline.read_trace(out/'case-6-rtl.csv'),wrong,816)
    except ValueError as error:mutation=str(error)
    else:raise ValueError('mutated payload accepted')
    for value in pins['inputs'].values():baseline.verify_identity(value)
    sources=[identity(ROOT/name) for name in ['run.py','prepare.py','run.sh','setup.sh']]+[
        identity(ROOT/name) for name in ['pins.json','controls.json','control_tb.sv','ExportTask2.lean',
        'NativeExport.lean','NativeTraces.lean','Import.lean','lakefile.lean','lake-manifest.json','lean-toolchain']]
    names=['rtl/main.sv','rtl/sources.f','opt-full.ys','before.json','after.json','candidate.il','structural-result.json',
           'frontend.ys','premap.json','normalize.ys','normalized.json','reductions.ys',
           'yosys-task2.v','task2.sv','native/Task2RTL.lean','native/Task2RTL.json',
           'sparkle-ir.txt','sparkle.c','roundtrip.sv','task2-sim.c','sparkle-sim','obj_dir/sim_control']
    for index in range(len(cases)):
        names += [f'case-{index}-{suffix}' for suffix in ['a.hex','b.hex','rtl.csv','lean.csv','c.csv']]
    artifacts=[identity(out/name) for name in names]
    for record in records:
        log=Path(record['log']['path'])
        artifacts += [identity(log),identity(log.with_suffix(log.suffix+'.resource.json'))]
    result={'status':'passed_controls','cases':comparison,'sparkle':pins['sparkle'],
            'model_semantics':'upstream Tools.SVParser.VerifyEmit.denote',
            'native_model':identity(out/'native/Task2RTL.lean'),
            'inputs':sources,'artifacts':artifacts,
            'runs':records,'mutation_rejected':mutation,
            'structural_change':json.loads((out/'structural-result.json').read_text())}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('[4/4] SPARKLE_OPT_CONTROLS_PASS',flush=True)

if __name__=='__main__':main()
