"""Publish checked results without turning missing effort data into success."""
import json
import math
from pathlib import Path


def effort_verdict(effort):
    phases=[effort.get(key,{}) for key in ['baseline_proof','candidate_proof']]
    complete=all(p.get('actor') and type(p.get('active_seconds')) in (float,int) and
                 math.isfinite(p['active_seconds']) and
                 p['active_seconds']>=0 and isinstance(p.get('interventions'),list) and
                 isinstance(p.get('changed_obligations'),list) for p in phases)
    if not complete:
        return {'less_work':False,'result':'inconclusive','reason':'active proof-engineering time was not instrumented; replay time and line counts cannot fill that gap'}
    smaller=phases[1]['active_seconds']<phases[0]['active_seconds']
    return {'less_work':smaller,'result':'less_work' if smaller else 'not_less_work',
            'baseline_active_seconds':phases[0]['active_seconds'],'candidate_active_seconds':phases[1]['active_seconds'],
            'excludes':'dependency provisioning, source/import setup, and proof-replay time'}


def milestone_verdict(technical,effort):
    return {'achieved':technical and effort['less_work'],
            'result':('failed' if not technical or effort['result']=='not_less_work' else
                      ('success' if effort['less_work'] else 'inconclusive')),
            'technical_equivalence_and_change_demonstrated':technical,'effort':effort}


def build_report(out):
    from run import ROOT,artifact,verify_manifest
    from compare import qualify_replay_evidence
    out=Path(out).resolve()
    names=['manifest','reference-result','hardware-baseline-result','hardware-candidate-result',
           'check-baseline-result','check-candidate-result','variant-result','compare-result']
    stages={name:json.loads((out/(name+'.json')).read_text()) for name in names}
    for result in stages.values():verify_manifest(result)
    baseline,candidate,variant=[stages[name] for name in ['check-baseline-result','check-candidate-result','variant-result']]
    proofs=all(r['status']=='proved' and r.get('completion_bound_edges',0)>0 and
               r['completion_bound_edges']==r.get('obligations',{}).get('cycles') and
               not(set(r['axioms'])-{'propext','Classical.choice','Quot.sound'}) for r in [baseline,candidate])
    common=['model','torch','word_semantics','source_semantics','imported_source','lake_manifest','proof_support_Hardware.lean']
    same_contract=all(baseline['artifacts'][key]['sha256']==candidate['artifacts'][key]['sha256'] for key in common)
    manifest=stages['manifest']
    identities=(baseline['artifacts']['baseline']['sha256']==candidate['artifacts']['baseline']['sha256']==manifest['artifacts']['baseline']['sha256'] and
                candidate['artifacts']['candidate']['sha256']==variant['artifacts']['candidate']['sha256']==manifest['artifacts']['candidate']['sha256'] and
                variant['artifacts']['baseline_checkpoint']['sha256']==baseline['artifacts']['canonical']['sha256'])
    changed=variant['status']=='prepared' and variant['before']!=variant['after']
    effort_path=ROOT/'reports/effort.json'
    effort=json.loads(effort_path.read_text());verdict=effort_verdict(effort)
    technical=proofs and same_contract and identities and changed
    milestone=milestone_verdict(technical,verdict)
    report={'status':'prepared','scope':'single Task2 int32 transaction and one opt -full transformation',
            'milestone':milestone,'baseline':{k:baseline[k] for k in ['claim','completion_bound_edges','axioms','elapsed_seconds','obligations']},
            'candidate':{k:candidate[k] for k in ['claim','completion_bound_edges','axioms','elapsed_seconds','obligations']},
            'structural_change':{k:variant[k] for k in ['transformation','criterion','before','after']},
            'shared_contract_sources_identical':same_contract,'fixed_artifact_identities':identities,
            'nonvacuity':'both Implements theorems include initialized-state existence for every input pair',
            'warm_comparison':qualify_replay_evidence(stages['compare-result']),'engineering_effort':effort,
            'trust_boundary':json.loads((ROOT/'contract.json').read_text())['trust_boundary'],
            'integer_extension':'narrow modular int32 semantics for the actual checked matmul graph; upstream TorchLean lacks int32 arithmetic',
            'artifacts':{name:artifact(out/(name+'.json')) for name in names}}
    report['artifacts']['effort']=artifact(effort_path)
    verify_manifest(report)
    (ROOT/'reports/comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
