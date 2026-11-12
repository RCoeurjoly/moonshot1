"""Verified optimized RTL, shared frontend helpers and candidate record schema."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
BASELINE = REPO / 'SparkleDemo'
spec = importlib.util.spec_from_file_location('sparkle_baseline_runner', BASELINE/'run.py')
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
identity = baseline.file_identity


def verify_pins(pins):
    for value in pins['inputs'].values():
        baseline.verify_identity(value)


def reference_schema(reference, native, netnames=None):
    registers = {r['name']:r['width'] for r in native['registers']}
    if len(registers) != len(native['registers']):
        raise ValueError('register correspondence is not bijective')
    states, memories = [], []
    for index, state in enumerate(reference['states']):
        if state['sort']['kind'] == 'memory':
            memories.append(index)
            continue
        wire = re.sub(r'[^A-Za-z0-9_]', '_', state['name'].removeprefix('$driver$'))
        width = state['sort']['width']
        if wire not in registers and netnames and wire in netnames:
            bits=netnames[wire]['bits']
            aliases=[name for name in registers if name in netnames and netnames[name]['bits']==bits]
            if len(aliases)==1: wire=aliases[0]
        if wire not in registers or registers[wire] != width:
            raise ValueError(f'register name/width correspondence missing: {wire} ({width})')
        states.append({'index':index,'wire':wire,'width':width})
    if len(states) != len(registers) or len({s['wire'] for s in states}) != len(registers):
        raise ValueError('register correspondence is not bijective')
    return {'inputs':reference['inputs'], 'outputs':reference['outputs'],
            'states':states,'state_count':len(reference['states']),
            'memory_indices':memories,'group_size':128}


def execute(command, log, records, env=None, timeout=600):
    """Record wall time and GNU-time maximum process RSS, never a tree sum."""
    log = Path(log)
    resource = log.with_suffix(log.suffix+'.resource.json')
    started = time.monotonic()
    resource.unlink(missing_ok=True)
    timed_out=False
    with log.open('w') as stream:
        process=subprocess.Popen(['/usr/bin/time','-f',
            '{"seconds":%e,"peak_process_rss_kib":%M}', '-o',str(resource),
            *map(str,command)],cwd=ROOT,env=env,stdout=stream,
            stderr=subprocess.STDOUT,start_new_session=True)
        try:process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(process.pid,signal.SIGKILL)
            process.wait()
    resources=None
    if resource.exists() and resource.read_text().strip():
        resources=json.loads(resource.read_text().splitlines()[-1])
    record={'command':list(map(str,command)),'returncode':process.returncode,
            'status':'timed_out' if timed_out else 'completed',
            'seconds':round(time.monotonic()-started,6),'log':identity(log),'resources':resources}
    records.append(record)
    if timed_out:raise RuntimeError(f'command timed out after {timeout}s; see {log}')
    if process.returncode:
        raise RuntimeError(f'command failed: {log}\n'+log.read_text()[-5000:])
    return record


def lower_reductions(out,pins,records):
    """Use Yosys gates for reduction/logical operators before Sparkle parsing."""
    script=out/'reductions.ys'
    script.write_text('\n'.join([
        f'read_json {out/"normalized.json"}',
        'simplemap t:$reduce_bool t:$reduce_or t:$reduce_and t:$logic_or t:$logic_and t:$logic_not',
        'opt_clean', 'splitnets -driver -format ___', 'rename -unescape', 'check -assert',
        f'write_json {out/"normalized.json"}',
        f'write_verilog -noattr -nodec -simple-lhs {out/"yosys-task2.v"}', '']))
    execute([pins['yosys'],'-Q','-T','-s',script],out/'reductions.log',records)
    hardware=json.loads((out/'normalized.json').read_text())['modules']['task2']
    (out/'task2.sv').write_text(baseline.ansi_header((out/'yosys-task2.v').read_text(),hardware))


def prepare_candidate(out, pins, records):
    verify_pins(pins)
    rtl = out/'rtl'
    rtl.mkdir(parents=True,exist_ok=True)
    script = out/'opt-full.ys'
    checkpoint = pins['inputs']['baseline_checkpoint']['path']
    script.write_text('\n'.join([
        f'read_rtlil {checkpoint}', 'hierarchy -top main', 'check',
        f'write_json {out/"before.json"}', 'opt -full', 'check',
        f'write_rtlil {out/"candidate.il"}', f'write_json {out/"after.json"}',
        f'write_verilog -noattr {rtl/"main.sv"}', '']))
    execute([pins['yosys'],'-Q','-T','-s',script],out/'opt-full.log',records)
    expected = pins['inputs']['candidate']['sha256']
    if identity(rtl/'main.sv')['sha256'] != expected:
        raise ValueError('fresh opt-full candidate identity differs from frozen RTL')
    # Compare structural statistics at exactly the original physical checkpoint.
    spec = importlib.util.spec_from_file_location('original_variant', REPO/'scripts/variant.py')
    variant = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(variant)
    before = json.loads((out/'before.json').read_text())['modules']['main']
    after = json.loads((out/'after.json').read_text())['modules']['main']
    delta = variant.structural_delta(before,after)
    if delta['status'] != 'prepared' or any(delta[k] != pins['physical_stats'][k] for k in ['before','after']):
        raise ValueError('opt-full structural change does not reproduce the recorded experiment')
    (rtl/'sources.f').write_text(str(rtl/'main.sv')+'\n')
    frontend_pins = dict(pins,rtl={'path':str(rtl),'files':{
        p.name:identity(p)['sha256'] for p in rtl.iterdir() if p.is_file()}})
    original_executor=baseline.execute
    baseline.execute=execute
    try:baseline.prepare_frontend(out,frontend_pins,records)
    finally:baseline.execute=original_executor
    lower_reductions(out,pins,records)
    (out/'structural-result.json').write_text(json.dumps(delta,indent=2)+'\n')
    return rtl
