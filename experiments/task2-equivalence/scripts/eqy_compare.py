"""Contract-aware EQY comparison with shared, symbolic input-memory words.

The memory lift is a declared trusted translation, separate from the Lean proof.
Shared input sequences are constrained to remain stable after their first sampled
edge, covering every Device.initial memory pair and its preservation lemmas.
"""
import copy
import json
import os
from pathlib import Path
import subprocess


def number(value):
    return int(value,2) if isinstance(value,str) else int(value)


def lift_input_memories(module):
    lifted=copy.deepcopy(module)
    all_bits=[bit for p in module['ports'].values() for bit in p['bits']]
    all_bits += [bit for c in module['cells'].values() for bits in c['connections'].values() for bit in bits]
    next_bit=max((b for b in all_bits if isinstance(b,int)),default=1)+1
    evidence=[]
    for name,port in [("handshake_memory0._handshake_memory_5","task2_words_a"),
                      ("handshake_memory1._handshake_memory_4","task2_words_b")]:
        cell=lifted['cells'].get(name)
        if cell is None or cell['type']!='$mem_v2':raise ValueError("input memory contract: missing read-only memory")
        p,c=cell['parameters'],cell['connections']
        expected={'SIZE':16,'WIDTH':32,'ABITS':4,'OFFSET':0,'WR_PORTS':0,'RD_PORTS':1,'RD_CLK_ENABLE':0}
        if any(number(p[k])!=v for k,v in expected.items()) or len(p['INIT'])!=512 or set(p['INIT'])-set('xz'):
            raise ValueError("input memory contract: only unrestricted asynchronous read-only 16x32 memories are supported")
        if c.get('RD_ARST',['0'])!=['0'] or c.get('RD_SRST',['0'])!=['0'] or len(c['RD_ADDR'])!=4 or len(c['RD_DATA'])!=32:
            raise ValueError("input memory contract: unexpected read/reset wiring")
        if port in lifted['ports']:raise ValueError("input memory contract: reserved port already exists")
        symbols=list(range(next_bit,next_bit+512));next_bit+=512
        lifted['ports'][port]={'direction':'input','bits':symbols}
        lifted.setdefault('netnames',{})[port]={'hide_name':0,'bits':symbols,'attributes':{}}
        del lifted['cells'][name]
        lifted['cells']['task2_read_'+port]={
            'hide_name':0,'type':'$shiftx',
            'parameters':{key:format(value,'032b') for key,value in {'A_SIGNED':0,'B_SIGNED':0,'A_WIDTH':512,'B_WIDTH':9,'Y_WIDTH':32}.items()},
            'attributes':{},'port_directions':{'A':'input','B':'input','Y':'output'},
            'connections':{'A':symbols,'B':['0']*5+c['RD_ADDR'],'Y':c['RD_DATA']}}
        evidence.append({'memory':name,'port':port,'words':16,'word_bits':32,
                         'mapping':'word i occupies bits [32*i +: 32]; shift amount is address << 5',
                         'initialization':'all 512 bits symbolic; no source-defined fixed bits',
                         'readonly':True})
    return lifted,evidence


def wrapper_text():
    return '''module task2_compare # (parameter MUTATE_PAYLOAD = 0) (
  input clock,
  input [511:0] task2_words_a, task2_words_b,
  output accepted_valid,
  output [31:0] accepted_data
);
  reg [9:0] driver_cycle = 0;
  reg driver_start;
  reg seen_payload = 0;
  reg past_inputs_valid = 0;
  reg [511:0] past_words_a, past_words_b;
  wire reset = driver_cycle < 4;
  wire start_ready, payload_valid;
  wire [31:0] payload_data;
  task2_design dut (
    .clock(clock), .reset(reset), .in3_valid(driver_start), .in3_ready(start_ready),
    .out0_ready(1'b1), .in2_st0_ready(1'b1), .in2_st0_done_valid(1'b0),
    .out0_valid(), .in2_st0_done_ready(), .in2_st0_valid(payload_valid), .in2_st0(payload_data),
    .task2_words_a(task2_words_a), .task2_words_b(task2_words_b)
  );
  always @(posedge clock) begin
    past_inputs_valid <= 1;
    past_words_a <= task2_words_a;
    past_words_b <= task2_words_b;
    if (driver_cycle < 512) driver_cycle <= driver_cycle + 1;
    if (reset) driver_start <= 1;
    else if (start_ready) driver_start <= 0;
    if (!reset && payload_valid) seen_payload <= 1;
  end
  always @* if (past_inputs_valid) begin
    assume(task2_words_a == past_words_a);
    assume(task2_words_b == past_words_b);
  end
  assign accepted_valid = !reset && !seen_payload && payload_valid;
  assign accepted_data = accepted_valid ? (payload_data ^ (MUTATE_PAYLOAD ? 32'd1 : 32'd0)) : 32'd0;
endmodule
'''


def prepare_comparison(out,label='initial',mutate_gate=False):
    from run import ROOT,artifact,execute,verify_manifest
    out=Path(out).resolve();folder=out/'formal'/label;folder.mkdir(parents=True,exist_ok=True)
    pins=json.loads((ROOT/'tool-pins.json').read_text());yosys=str(Path(pins['verification_yosys']['package'])/'bin/yosys')
    results=[json.loads((out/'check-baseline-result.json').read_text()),
             json.loads((out/'hardware-candidate-result.json').read_text())]
    for result in results:verify_manifest(result)
    if results[0]['status']!='proved' or results[1]['status']!='passed_control':
        raise ValueError('comparison requires a proved baseline and checked candidate import')
    runs=[];bindings={};relation=[]
    for role,result in zip(['gold','gate'],results):
        source=Path(result['artifacts']['canonical']['path'])
        exported=folder/(role+'-original.json');script=folder/(role+'-json.ys')
        script.write_text('read_rtlil '+json.dumps(str(source))+'\nwrite_json '+json.dumps(str(exported))+'\n')
        run=execute([yosys,'-Q','-T','-s',str(script)],folder/(role+'-json.log'))
        runs.append(run)
        if run['status']!='prepared':raise ValueError('failed to export comparison checkpoint')
        design=json.loads(exported.read_text());lifted,evidence=lift_input_memories(design['modules']['main'])
        design['modules']['main']=lifted
        path=folder/(role+'-lifted.json');path.write_text(json.dumps(design,indent=2)+'\n')
        bindings[role+'_canonical']=artifact(source);bindings[role+'_lifted']=artifact(path)
        relation.append({'role':role,'memories':evidence})
    harness=folder/'driver.sv';harness.write_text(wrapper_text());bindings['driver']=artifact(harness)
    config=folder/'candidate.eqy'
    sections=['[options]','splitnets on','']
    for role in ['gold','gate']:
        sections += ['['+role+']','read_json '+json.dumps(str(folder/(role+'-lifted.json'))),
                     'rename main task2_design','read_verilog -formal '+json.dumps(str(harness))]
        if role=='gate' and mutate_gate:sections += ['chparam -set MUTATE_PAYLOAD 1 task2_compare']
        sections += ['prep -top task2_compare','flatten','opt_clean','']
    sections += ['[match task2_compare]','gold-nomatch dut._*','gate-nomatch dut._*',
                 'gold-match clock,task2_words_*,accepted_*,driver_*,seen_payload,past_*',
                 'gold-match dut.*reg*,dut.*emitted*,dut.handshake_memory2.*handshake_memory_3*',
                 'gold-nomatch *','gate-nomatch *','',
                 '[strategy induction]','use sby','engine smtbmc z3','depth 8','xprop on','']
    config.write_text('\n'.join(sections));bindings['configuration']=artifact(config)
    relation_file=folder/'memory-relation.json'
    relation_file.write_text(json.dumps({'mapping':relation,
       'shared_inputs':'EQY matches the same top-level task2_words_a/b primary inputs on gold and gate',
       'contract_relation':'The same primary words feed both designs. Stability assumptions hold for every constant input sequence, encoding every Device.initial memory pair; no words are fixed to a sample.',
       'startup':'four reset edges, start initially unspecified then held through acceptance, both ready=1, done_valid=0',
       'observation':'first accepted payload only; pre-edge event at k corresponds to Device.result after k+1 steps',
       'trust_boundary':'read-only memory lifting and wrapper elaboration are trusted translations; no EQY result enters Lean as an axiom',
       'documentation':'https://yosyshq.readthedocs.io/projects/eqy/en/latest/xprop.html'},indent=2)+'\n')
    bindings['memory_relation']=artifact(relation_file)
    return folder,config,runs,bindings,pins


def run_comparison(out,timeout=600,label='initial',mutate_gate=False):
    from run import ROOT,artifact,execute
    try:
        folder,config,runs,bindings,pins=prepare_comparison(out,label,mutate_gate)
    except (ValueError,KeyError) as error:
        return {'status':'unsupported','scope':'no contract-matched EQY claim','reason':str(error)}
    tools=pins['comparison_tools']
    env=dict(os.environ)
    env['PATH']=':'.join(str(Path(tools[t]['package'])/'bin') for t in ['eqy','sby','z3'])+':'+str(Path(pins['verification_yosys']['package'])/'bin')+':'+env['PATH']
    eqy=str(Path(tools['eqy']['package'])/'bin/eqy');work=folder/'work'
    run=execute([eqy,'-f','-j','8','-d',str(work),str(config)],folder/'eqy.log',env=env,timeout=timeout)
    runs.append(run)
    status_file=work/'status'
    status='timeout' if run['status']=='timeout' else 'failed'
    if run['status']=='prepared' and status_file.exists() and status_file.read_text().strip()=='PASS':status='proved'
    if status_file.exists():bindings['engine_status']=artifact(status_file)
    result={'status':status,'claim':'EQY refinement under the shared symbolic input-memory harness',
            'scope':'shared input words stable after the first sampled edge; every Device.initial pair; fixed startup/first-payload observation',
            'mutate_gate':mutate_gate,'engine':'SBY smtbmc z3, depth8, xprop on','runs':runs,'artifacts':bindings,
            'tools':tools,'verdict_trust':'EQY/SBY/Z3 toolchain; separate from the kernel-checked Lean theorem'}
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
