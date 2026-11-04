"""Bind freshly checked sources to the exact resolved compiled import closure."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

INVENTORY=Path(__file__).with_name('CacheClosure.lean')


def remaining(deadline):
    seconds=600 if deadline is None else deadline-time.monotonic()
    if seconds<=0:raise TimeoutError('cache validation exhausted the replay budget')
    return seconds


def inventory(module,env,cwd,deadline=None):
    try:
        output=subprocess.check_output(['lean','--run',str(INVENTORY),module],env=env,cwd=cwd,text=True,timeout=remaining(deadline))
    except subprocess.TimeoutExpired as error:
        raise TimeoutError('compiled dependency inventory exceeded the replay budget') from error
    return dict(line.split('\t',1) for line in output.splitlines() if line.strip())


def compiled_files(closure):
    files={}
    for name,path in closure.items():
        base=Path(path)
        candidates=[base,Path(str(base)+'.server'),Path(str(base)+'.private'),
                    base.with_suffix('.ir'),base.with_suffix('.ir.sig')]
        for candidate in candidates:
            if candidate.is_file():files[name+':'+candidate.name]=str(candidate)
    return files


def capture(root,out,design,checked_sources,env,module=None,checked_outputs=None):
    from run import artifact,digest
    root=Path(root);out=Path(out);module=module or f'Task2.{design.title()}'
    checked_outputs=checked_outputs or {}
    for info in checked_outputs.values():
        if digest(info['path'])!=info['sha256']:
            raise ValueError('compiled output changed since its successful check')
    closure=inventory(module,env,root)
    sources={}
    for name in closure:
        if not name.startswith('Task2.'):continue
        if name not in checked_sources or name not in checked_outputs:
            raise ValueError(f'fresh source/output receipt missing for {name}')
        if digest(closure[name])!=checked_outputs[name]['sha256']:
            raise ValueError(f'resolved compiled object was not produced by the fresh check: {name}')
        candidates=[root/(name.replace('.','/')+'.lean'),out/'generated'/(name.replace('.','/')+'.lean'),
                    out/'proof'/design/(name.rsplit('.',1)[-1]+'.lean')]
        if name=='Task2.Imported.Source':
            candidates.insert(0,root/'build/generated/Task2/Imported/Source.lean')
        source=next((p for p in candidates if p.is_file()),None)
        if source is None or digest(source)!=checked_sources[name]['sha256']:
            raise ValueError(f'live source for {name} is not among the freshly checked inputs')
        sources[name]=artifact(source)
    compiler=shutil.which('lean',path=env.get('PATH'))
    if compiler is None:raise ValueError('Lean compiler unavailable')
    return {'scope':'created only after successful fresh checking; exact resolved transitive olean closure',
            'project_root':str(root.resolve()),'module':module,'lean_path':env.get('LEAN_PATH',''),'compiler':artifact(compiler),
            'compiler_version':subprocess.check_output([compiler,'--version'],env=env,text=True).strip(),
            'compiled':{name:artifact(path) for name,path in compiled_files(closure).items()},'sources':sources,
            'pins':{name:artifact(root/name) for name in ['lake-manifest.json','lakefile.lean','lean-toolchain','tool-pins.json','flake.lock']}}


def require(result):
    from run import digest
    info=result.get('artifacts',{}).get('cache_attestation')
    if not info:raise ValueError('cache attestation missing; rerun check before warm replay')
    if digest(info['path'])!=info['sha256']:raise ValueError('cache attestation identity changed')
    return json.loads(Path(info['path']).read_text())


def validate(attestation,root,env,cwd=None,deadline=None):
    from run import digest
    if str(Path(root).resolve())!=attestation['project_root']:
        raise ValueError('project source root changed')
    for group in ['sources','compiled','pins']:
        for name,info in attestation[group].items():
            remaining(deadline)
            if digest(info['path'])!=info['sha256']:
                raise ValueError(f'{group} identity changed: {name}')
    compiler=shutil.which('lean',path=env.get('PATH'))
    if compiler is None or digest(compiler)!=attestation['compiler']['sha256']:
        raise ValueError('compiler identity changed')
    if env.get('LEAN_PATH','')!=attestation['lean_path']:
        raise ValueError('compiled dependency search path changed')
    resolved=inventory(attestation['module'],env,cwd or root,deadline)
    if compiled_files(resolved)!={name:info['path'] for name,info in attestation['compiled'].items()}:
        raise ValueError('resolved compiled dependency closure changed')
