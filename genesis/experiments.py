"""Local reproducible trial runner. No telemetry, model secrets or paid API dependency."""
import argparse
import copy
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time

from .world import World
from . import analytics, controls, families, environment, persistence
from .cognition import Scheduler
from .providers import InferenceConfig,generate
from .validation import validate_world

VERSION=1
DEFAULT={'schema_version':1,'name':'society-study','seeds':[42],'repeats':1,'ticks':1000,'sample_interval':25,
         'world':{'width':64,'height':64,'population':5,'generator':'coherent'},'conditions':{},'demography':{},
         'resource_scale':1.,'settlement_stocks':{},'personalities':{},'threats':False,'climate':None,
         'inference':{'enabled':False},'tick_seconds':0.,'drain_seconds':2.,'record_model_content':False,
         'groups':[{'id':'baseline','conditions':{}}]}


def timestamp():return datetime.now(timezone.utc).isoformat()


def validate(raw):
    if not isinstance(raw,dict) or set(raw)-set(DEFAULT):raise ValueError('Unknown experiment field')
    data={**copy.deepcopy(DEFAULT),**copy.deepcopy(raw)}
    if data['schema_version']!=1:raise ValueError('Unsupported experiment schema')
    if not isinstance(data['name'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',data['name']):raise ValueError('Use a simple experiment name')
    if not isinstance(data['seeds'],list) or not 1<=len(data['seeds'])<=100 or any(type(s) is not int or not 0<=s<=2147483647 for s in data['seeds']) or len(set(data['seeds']))!=len(data['seeds']):raise ValueError('Use 1..100 distinct nonnegative seeds')
    for key,lo,hi in [('repeats',1,20),('ticks',1,1000000),('sample_interval',1,10000)]:
        if type(data[key]) is not int or not lo<=data[key]<=hi:raise ValueError('Invalid experiment '+key)
    world=data['world']
    for key in ('conditions','demography','inference','settlement_stocks','personalities'):
        if not isinstance(data[key],dict):raise ValueError(key+' must be an object')
    if not isinstance(world,dict) or set(world)-{'width','height','population','generator'}:raise ValueError('Unknown world setting')
    data['world']={**DEFAULT['world'],**world}
    for k,lo,hi in [('width',32,512),('height',24,512),('population',1,100)]:
        if type(data['world'][k]) is not int or not lo<=data['world'][k]<=hi:raise ValueError('Invalid world '+k)
    if data['world']['generator'] not in ('legacy','coherent'):raise ValueError('Unknown generator')
    controls.validate({**controls.DEFAULTS,**data['conditions']})
    if set(data['demography'])-set(families.DEFAULTS):raise ValueError('Unknown demographic setting')
    limits={**families.DEFAULTS,**data['demography']}
    for k,lo,hi in [('ticks_per_year',10,1000000),('population_cap',1,400),('max_age',18,150),('birth_interval_years',1,20)]:
        if type(limits[k]) is not int or not lo<=limits[k]<=hi:raise ValueError('Invalid demographic '+k)
    if any(type(limits[k]) is not bool for k in ('enabled','offline_fallback')):raise ValueError('Invalid demographic switch')
    for k,lo,hi in [('resource_scale',0,10),('tick_seconds',0,2),('drain_seconds',0,120)]:
        if type(data[k]) not in (int,float) or not math.isfinite(data[k]) or not lo<=data[k]<=hi:raise ValueError('Invalid '+k)
    if type(data['threats']) is not bool or type(data['record_model_content']) is not bool:raise ValueError('Use boolean threat/privacy switches')
    config=InferenceConfig(**data['inference']).validate()
    if config.enabled and data['tick_seconds']==0:raise ValueError('Live/fixture LLM conditions need explicit nonzero tick pacing; offline throughput is not an inference budget')
    if not isinstance(data['groups'],list) or not 1<=len(data['groups'])<=20:raise ValueError('Use 1..20 experimental groups')
    ids=set()
    for group in data['groups']:
        if not isinstance(group,dict) or set(group)-{'id','conditions','inference','resource_scale','climate','threats'}:raise ValueError('Unknown group factor')
        if not isinstance(group.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',group['id']) or group['id'] in ids:raise ValueError('Group IDs must be unique safe names')
        ids.add(group['id']);controls.validate({**controls.DEFAULTS,**data['conditions'],**group.get('conditions',{})})
        InferenceConfig(**{**data['inference'],**group.get('inference',{})}).validate()
        if {**data['inference'],**group.get('inference',{})}.get('enabled') and data['tick_seconds']==0:raise ValueError('Model group needs nonzero pacing')
        if 'resource_scale' in group and (type(group['resource_scale']) not in (int,float) or not math.isfinite(group['resource_scale']) or not 0<=group['resource_scale']<=10):raise ValueError('Invalid group abundance')
        if 'threats' in group and type(group['threats']) is not bool:raise ValueError('Invalid group threats')
    return data


def prepare(config,group,seed):
    wc=config['world'];world=World(seed,wc['population'],wc['width'],wc['height'],wc['generator'])
    world.controls={**controls.DEFAULTS,**config['conditions'],**group.get('conditions',{}),'audit':True}
    controls.initialize(world)
    world.demography.update(config['demography'])
    for a in world.agents.values():a.birth_tick=-int(a.age*world.demography['ticks_per_year'])
    factor=group.get('resource_scale',config['resource_scale'])
    for r in world.resources.values():r.quantity*=factor;r.capacity*=factor;r.regeneration*=factor
    for s in world.settlements.values():
        for k in s.inventory:s.inventory[k]*=factor
    from .registry import RESOURCES
    for sid,stock in config['settlement_stocks'].items():
        if sid not in world.settlements or not isinstance(stock,dict):raise ValueError('Unknown settlement stock override')
        for k,v in stock.items():
            if k not in RESOURCES or type(v) not in (int,float) or not math.isfinite(v) or v<0:raise ValueError('Invalid initial stock')
        world.settlements[sid].inventory.update(stock)
    for aid,personality in config['personalities'].items():
        if aid not in world.agents or not isinstance(personality,dict) or set(personality)-{'aggression','courage','sociability'} or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in personality.values()):raise ValueError('Invalid personality override')
        world.agents[aid].personality.update(personality)
    world.climate['threats_enabled']=group.get('threats',config['threats'])
    climate=group.get('climate',config['climate'])
    if climate:environment.intervene(world,{'action':'god','operation':'weather',**climate})
    validate_world(world);return world


def source_revision():
    try:return subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):return 'source-archive-unidentified'


def source_identity():
    root=Path(__file__).resolve().parents[1];digest=hashlib.sha256()
    for file in sorted((root/'genesis').rglob('*')):
        if file.suffix in ('.py','.json','.html'):
            digest.update(str(file.relative_to(root)).encode());digest.update(file.read_bytes())
    try:dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True,stderr=subprocess.DEVNULL))
    except (OSError,subprocess.CalledProcessError):dirty=None
    return {'source_tree_sha256':digest.hexdigest(),'working_tree_dirty':dirty}


def write_json(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


class Recorder:
    def __init__(self,directory,record_content=False):
        self.events=(directory/'events.jsonl').open('w');self.actions=(directory/'actions.jsonl').open('w');self.models=(directory/'models.jsonl').open('w');self.record_content=record_content
    def event(self,event):
        row=copy.deepcopy(event)
        if not self.record_content and row['kind'] in ('dialogue','claim','reasoning'):row['text']='[content redacted by research privacy policy]'
        self.events.write(json.dumps(row,allow_nan=False)+'\n')
    def audit(self,row):
        row=copy.deepcopy(row)
        if not self.record_content and row.get('kind')=='model_proposal':
            from .planning import SCHEMAS
            row['steps']=[{'action':s.get('action') if s.get('action') in SCHEMAS else '[unsupported]',
                           'argument_keys':sorted(str(k) for k in s)[:32],
                           'sha256':hashlib.sha256(json.dumps(s,sort_keys=True).encode()).hexdigest()}
                          for s in row.get('steps',[]) if isinstance(s,dict)]
        self.actions.write(json.dumps(row,allow_nan=False)+'\n')
    def provider(self,provider):
        def call(config,system,payload):
            start=time.perf_counter();result=provider(config,system,payload)
            row={'actor':payload.get('agent',{}).get('identity',{}).get('id'),'request_sha256':hashlib.sha256(json.dumps([system,payload],sort_keys=True).encode()).hexdigest(),
                 'ok':result.get('ok',False),'seconds':time.perf_counter()-start,'usage':result.get('usage',{}),'error':result.get('error')}
            if self.record_content:row.update(request=payload,response=result,system=system)
            # Writes are synchronized across the shared inference worker threads.
            import threading
            with self.model_lock:
                if not self.models.closed:self.models.write(json.dumps(row,allow_nan=False)+'\n');self.models.flush()
            return result
        import threading
        self.model_lock=threading.Lock();return call
    def close(self):
        self.events.close();self.actions.close()
        with self.model_lock:self.models.close()


def trial(config,group,seed,repetition,directory,provider=None):
    directory.mkdir(parents=True,exist_ok=False)
    try:world=prepare(config,group,seed)
    except Exception as exc:
        write_json(directory/'manifest.json',{'schema_version':1,'configuration':config,'group':group['id'],'seed':seed,'repetition':repetition,'status':'failed','genesis_commit':source_revision(),**source_identity(),'error':f'{type(exc).__name__}: {exc}'})
        raise
    cfg=InferenceConfig(**{**config['inference'],**group.get('inference',{})}).validate()
    world.cognition_config=cfg.public()
    recorder=Recorder(directory,config['record_model_content'])
    scheduler=Scheduler(cfg,recorder.provider(provider or generate))
    world.event_sink=recorder.event;world.audit_sink=recorder.audit
    world.dialogue_sink=lambda a,b,text,source='llm':scheduler.speak(world,a,b,text,source)
    manifest={'schema_version':1,'group':group['id'],'seed':seed,'repetition':repetition,'genesis_commit':source_revision(),
              'python':platform.python_version(),'platform':platform.platform(),'configuration':config,'group_factors':group,'inference':cfg.public(),
              'inference_kind':'protocol_fixture' if provider else 'live_provider' if cfg.enabled else 'offline_deterministic',
              'started':timestamp(),'status':'running','offline_reproducible':not cfg.enabled,'initial_state_sha256':analytics.fingerprint(world),**source_identity()}
    write_json(directory/'manifest.json',manifest)
    initial_events=copy.deepcopy(world.events)
    for e in initial_events:recorder.event(e)
    from collections import deque
    started=time.perf_counter();samples=deque(maxlen=2048)
    try:
        with (directory/'metrics.csv').open('w',newline='') as handle:
            first=analytics.sample(world,scheduler);writer=csv.DictWriter(handle,fieldnames=list(first));writer.writeheader();writer.writerow(first);samples.append(first)
            for tick in range(config['ticks']):
                begin=time.perf_counter();world.step();scheduler.pump(world)
                if world.tick%config['sample_interval']==0 or tick==config['ticks']-1:
                    validate_world(world);sample=analytics.sample(world,scheduler);writer.writerow(sample);handle.flush();samples.append(sample)
                if cfg.enabled and config['tick_seconds']>0:time.sleep(max(0,config['tick_seconds']-(time.perf_counter()-begin)))
            deadline=time.monotonic()+config['drain_seconds'] if cfg.enabled else time.monotonic()
            while (scheduler.inflight or scheduler.queue) and time.monotonic()<deadline:
                scheduler.pump(world,schedule=False);time.sleep(.01)
        manifest.update(status='completed',completed=timestamp(),seconds=time.perf_counter()-started,
                        final_state_sha256=analytics.fingerprint(world),outcome=analytics.sample(world,scheduler),
                        inference_metrics=scheduler.status()['metrics'],pending_inference=len(scheduler.queue)+len(scheduler.inflight),
                        navigation=world.navigation)
        persistence.save(world,directory/'world.sqlite')
        write_json(directory/'relationships.json',[{'from':a.id,'to':b,**r} for a in world.agents.values() for b,r in a.relationships.items()])
        write_json(directory/'agents.json',[{'id':a.id,'age':a.age,'life_stage':a.life_stage,'household':a.household,'occupation':a.occupation,
                    'goals':a.goals if config['record_model_content'] else '[content redacted]','plan_status':a.plan_status,
                    'metrics':world.research_stats['agents'].get(a.id,{})} for a in world.agents.values()])
        write_json(directory/'metrics.json',list(samples))
    except BaseException as exc:
        manifest.update(status='failed',completed=timestamp(),seconds=time.perf_counter()-started,error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        scheduler.close()
        # Running providers may outlive logical cancellation. They own detached data;
        # preserve open model logs until their bounded calls finish rather than racing close.
        recorder.close()
        write_json(directory/'manifest.json',manifest)
    return manifest


_T={1:12.706,2:4.303,3:3.182,4:2.776,5:2.571,6:2.447,7:2.365,8:2.306,9:2.262,10:2.228,15:2.131,20:2.086,30:2.042}

def statistics_for(values):
    values=list(values);n=len(values)
    if not n:return {'n':0,'mean':None,'sd':None,'ci95':None}
    avg=statistics.mean(values)
    if n<2:return {'n':n,'mean':avg,'sd':None,'ci95':None}
    sd=statistics.stdev(values);df=n-1;critical=_T[max(k for k in _T if k<=df)] if df<=30 else 1.96
    margin=critical*sd/math.sqrt(n)
    return {'n':n,'mean':avg,'sd':sd,'ci95':[avg-margin,avg+margin],'ci_method':'Student t; conservative tabulation' if df<=30 else 'normal approximation'}


def aggregate(trials):
    # Repeated runs of the same seed do not create extra independent seed samples.
    groups={}
    numeric=('population','births','deaths','food_stock','water_stock','trade_volume','buildings','conversations','offline_social_events','personal_food_gini')
    for trial in trials:
        if trial['status']!='completed':continue
        groups.setdefault(trial['group'],{}).setdefault(trial['seed'],[]).append(trial['outcome'])
    output={'schema_version':1,'independent_unit':'seed; repetitions averaged within seed','groups':{},'comparisons':[]}
    for name,seeds in groups.items():
        outcomes={str(seed):{key:statistics.mean(r[key] for r in runs) for key in numeric} for seed,runs in seeds.items()}
        output['groups'][name]={'per_seed':outcomes,'metrics':{key:statistics_for(r[key] for r in outcomes.values()) for key in numeric}}
    names=list(groups)
    if names:
        baseline=names[0]
        for name in names[1:]:
            common=sorted(set(groups[baseline])&set(groups[name]))
            output['comparisons'].append({'baseline':baseline,'condition':name,'paired_seeds':common,
                'differences':{key:statistics_for(output['groups'][name]['per_seed'][str(seed)][key]-output['groups'][baseline]['per_seed'][str(seed)][key] for seed in common) for key in numeric}})
    return output


def run(config,output,provider=None):
    config=validate(config);output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise ValueError('Choose an empty experiment directory; existing research is never overwritten')
    write_json(output/'configuration.json',config);trials=[]
    for group in config['groups']:
        for seed in config['seeds']:
            for repeat in range(config['repeats']):
                path=output/f'{group["id"]}-seed{seed}-r{repeat}'
                preview=[{k:t[k] for k in ('group','seed','repetition','status','seconds')}|{'directory':f'{t["group"]}-seed{t["seed"]}-r{t["repetition"]}'} for t in trials]
                write_json(output/'index.json',preview+[{'group':group['id'],'seed':seed,'repetition':repeat,'status':'running','seconds':0,'directory':path.name}])
                try:trials.append(trial(config,group,seed,repeat,path,provider))
                except Exception:
                    failure=json.loads((path/'manifest.json').read_text());failure.setdefault('seconds',0);trials.append(failure)
                    write_json(output/'index.json',preview+[{'group':group['id'],'seed':seed,'repetition':repeat,'status':'failed','seconds':failure['seconds'],'directory':path.name}])
                    write_json(output/'aggregate.json',aggregate(trials));raise
                write_json(output/'index.json',[{k:t[k] for k in ('group','seed','repetition','status','seconds')}|{'directory':f'{t["group"]}-seed{t["seed"]}-r{t["repetition"]}'} for t in trials])
    result=aggregate(trials);write_json(output/'aggregate.json',result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('configuration');parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        result=run(json.loads(Path(args.configuration).read_text()),args.output)
        print(json.dumps(result,indent=2))
    except (ValueError,OSError,TypeError) as exc:parser.exit(1,str(exc)+'\n')

if __name__=='__main__':main()
