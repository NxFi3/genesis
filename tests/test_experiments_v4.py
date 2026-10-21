import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

from genesis import actions,analytics,controls,experiments,memory,production
from genesis.cognition import Scheduler
from genesis.planning import execute_plan,validate_plan
from genesis.providers import InferenceConfig
from genesis.world import World
from test_cognition_v2 import drain,result


class ExperimentTests(unittest.TestCase):
    def config(self,**kw):return {'name':'test','ticks':40,'sample_interval':10,'world':{'width':48,'height':30,'population':3,'generator':'legacy'},**kw}

    def test_configuration_rejects_uncontrolled_or_invalid_conditions(self):
        for data in ({'unexpected':True},{'seeds':[42,42]},{'conditions':{'communication':'yes'}},{'demography':{'ticks_per_year':0}},{'groups':[{'id':'../escape'}]},{'inference':{'enabled':True}}):
            with self.assertRaises((ValueError,TypeError)):experiments.validate(self.config(**data))

    def test_ablation_keeps_initial_physical_world_equivalent(self):
        config=experiments.validate(self.config())
        a=experiments.prepare(config,{'id':'on','conditions':{'communication':True}},42)
        b=experiments.prepare(config,{'id':'off','conditions':{'communication':False}},42)
        sa=copy.deepcopy(a.snapshot(True));sb=copy.deepcopy(b.snapshot(True))
        sa.pop('controls');sb.pop('controls')
        self.assertEqual(sa,sb)
        self.assertEqual(a.rng.getstate(),b.rng.getstate())

    def test_memory_ablation_does_not_erase_authoritative_events_or_active_plans(self):
        w=World();w.controls['memory']=False;controls.initialize(w);a=w.agents['a2']
        previous=len(a.memories);memory.remember(a,0,'secret','test');memory.learn(a,0,'secret','test')
        self.assertEqual(len(a.memories),previous);self.assertFalse(a.knowledge)
        w.event('test','World events remain observable.',[a.id])
        self.assertEqual(w.events[-1]['kind'],'test');self.assertEqual(len(a.memories),previous)

    def test_shared_knowledge_only_in_explicit_experimental_pool(self):
        w=World();a=w.agents['a2'];b=w.agents['b2']
        memory.learn(a,0,'Private known fact',a.id,1,True)
        controls.shared(w);self.assertFalse(b.knowledge)
        w.controls['shared_knowledge']=True;controls.shared(w)
        self.assertEqual(b.knowledge[0]['claim'],'Private known fact')
        self.assertEqual(b.knowledge[0]['status'],'shared_experimental_pool')

    def test_action_sources_distinguish_llm_fallback_player_and_observer(self):
        w=World();rows=[];w.audit_sink=rows.append;a=w.agents['a2'];a.x,a.y=9,10
        actions.execute(w,{'action':'observe'},a.id,origin='llm')
        actions.execute(w,{'action':'observe'},a.id)
        actions.execute(w,{'action':'observe'})
        self.assertEqual([r['source'] for r in rows],['llm','deterministic_fallback','player'])
        from genesis.environment import intervene
        intervene(w,{'operation':'weather','weather':'clear'})
        self.assertEqual(w.events[-1]['source'],'observer')
        self.assertEqual(len(a.memories),0,'Research audits must not become private cognitive input')

    def test_proposed_validated_and_completed_are_not_conflated(self):
        w=World();rows=[];w.audit_sink=rows.append;a=w.agents['a2']
        scheduler=Scheduler(InferenceConfig(enabled=True),lambda *_:result(plan=[{'action':'move','x':-1,'y':0}]))
        try:
            scheduler.request(w,a.id);drain(scheduler,w,lambda:scheduler.metrics['completed']==1)
            self.assertTrue(any(r['kind']=='model_proposal' and r['stage']=='proposed' for r in rows))
            self.assertFalse(any(r.get('completed') for r in rows))
            execute_plan(w,a)
            request=next(r for r in rows if r['kind']=='action')
            self.assertFalse(request['accepted']);self.assertFalse(request['completed']);self.assertEqual(request['source'],'llm')
            self.assertEqual(a.plan_status,'failed')
        finally:scheduler.close()

    def test_invalid_model_proposals_are_counted_without_execution(self):
        w=World();rows=[];w.audit_sink=rows.append
        scheduler=Scheduler(InferenceConfig(enabled=True),lambda *_:result(plan=[{'action':'invent_unsupported_power'}]))
        try:
            scheduler.request(w,'a2');drain(scheduler,w,lambda:scheduler.metrics['failed']==1)
            self.assertTrue(any(r.get('stage')=='rejected' for r in rows))
            self.assertEqual(w.research_stats['agents']['a2']['invalid_proposals'],1)
            self.assertFalse(any(r['kind']=='action' for r in rows))
        finally:scheduler.close()

    def test_delayed_production_completion_links_to_accepted_action(self):
        w=World();rows=[];w.audit_sink=rows.append;a=w.agents['a2'];b=w.buildings['a_furnace'];a.x,a.y=b.x,b.y
        a.inventory.update(iron_ore=2,coal=1)
        self.assertTrue(actions.execute(w,{'action':'produce','recipe':'smelt_iron'},a.id,True,origin='llm')['pending'])
        initial=rows[-1];self.assertTrue(initial['accepted']);self.assertFalse(initial['completed'])
        for _ in range(12):w.tick+=1;production.update(w)
        complete=[r for r in rows if r['kind']=='completion']
        self.assertEqual(len(complete),1);self.assertEqual(complete[0]['accepted_action'],initial['id'])
        self.assertEqual(a.inventory['iron_ingot'],1)

    def test_private_content_is_redacted_from_default_model_and_proposal_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            recorder=experiments.Recorder(Path(tmp))
            provider=recorder.provider(lambda *_:result(plan=[{'action':'talk','target':'a1','message':'private phrase'}]))
            provider(InferenceConfig(), 'private system', {'agent':{'identity':{'id':'a2'}},'message':'private phrase'})
            recorder.audit({'kind':'model_proposal','steps':[{'action':'talk','message':'private phrase'}]})
            recorder.event({'kind':'dialogue','text':'private phrase','actors':['a2']})
            recorder.close()
            for name in ('models.jsonl','actions.jsonl','events.jsonl'):self.assertNotIn('private phrase',(Path(tmp)/name).read_text())

    def test_repeated_offline_trials_export_exact_physical_results_and_manifests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'run';summary=experiments.run(self.config(repeats=2),root)
            trials=[json.loads(p.read_text()) for p in sorted(root.glob('*/manifest.json'))]
            self.assertEqual(len(trials),2);self.assertEqual(trials[0]['final_state_sha256'],trials[1]['final_state_sha256'])
            self.assertEqual(trials[0]['outcome'],trials[1]['outcome'])
            self.assertEqual(trials[0]['inference_kind'],'offline_deterministic')
            self.assertIn('source_tree_sha256',trials[0]);self.assertIn('genesis_commit',trials[0])
            self.assertEqual(summary['groups']['baseline']['metrics']['population']['n'],1)
            self.assertIsNone(summary['groups']['baseline']['metrics']['population']['ci95'])
            folder=root/'baseline-seed42-r0'
            for name in ('metrics.csv','metrics.json','actions.jsonl','events.jsonl','agents.json','relationships.json','world.sqlite'):self.assertTrue((folder/name).exists())
            with (folder/'metrics.csv').open() as handle:self.assertEqual(len(list(csv.DictReader(handle))),5)
            with self.assertRaises(ValueError):experiments.run(self.config(),root)

    def test_controlled_communication_comparison_measures_actual_different_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'comparison'
            summary=experiments.run(self.config(ticks=400,world={'width':48,'height':30,'population':5,'generator':'legacy'},seeds=[41,42],groups=[{'id':'on','conditions':{'communication':True}},{'id':'off','conditions':{'communication':False}}]),root)
            on=summary['groups']['on']['metrics']['offline_social_events']['mean'];off=summary['groups']['off']['metrics']['offline_social_events']['mean']
            self.assertGreater(on,0);self.assertEqual(off,0)
            self.assertEqual(summary['comparisons'][0]['paired_seeds'],[41,42])
            for manifest in root.glob('*/manifest.json'):
                result=json.loads(manifest.read_text());self.assertEqual(result['inference_metrics']['submitted'],0)

    def test_confidence_intervals_require_independent_samples_and_use_sample_sd(self):
        self.assertIsNone(experiments.statistics_for([1])['ci95'])
        values=experiments.statistics_for([1,2,3])
        self.assertEqual(values['mean'],2);self.assertEqual(values['sd'],1)
        self.assertLess(values['ci95'][0],1);self.assertGreater(values['ci95'][1],3)
        self.assertAlmostEqual(analytics.gini([0,0,3]),2/3)
        self.assertEqual(analytics.gini([0,0]),0)

    def test_cooperation_and_planning_ablation_reject_actions_through_engine(self):
        from genesis.planning import adopt_plan
        w=World();w.controls.update(cooperation=False,planning=False)
        self.assertFalse(actions.execute(w,{'action':'trade','target':'a2'})['ok'])
        a=w.agents['a2'];self.assertFalse(adopt_plan(w,a,validate_plan({'plan':[{'action':'observe'}]})))
        self.assertFalse(a.plan)

    def test_failed_initial_conditions_are_recorded_as_failed_trials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bad'
            with self.assertRaises(ValueError):experiments.run(self.config(settlement_stocks={'unknown':{'food':3}}),root)
            manifest=json.loads((root/'baseline-seed42-r0'/'manifest.json').read_text())
            self.assertEqual(manifest['status'],'failed')
            self.assertEqual(json.loads((root/'index.json').read_text())[0]['status'],'failed')

    def test_dashboard_http_serves_recorded_data_and_rejects_traversal(self):
        import socket,subprocess,sys,time,urllib.request,urllib.error
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'results';experiments.run(self.config(ticks=5),root)
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            process=subprocess.Popen([sys.executable,'-m','genesis.dashboard',str(root),'--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                base=f'http://127.0.0.1:{port}'
                deadline=time.monotonic()+5
                while True:
                    try:
                        with urllib.request.urlopen(base+'/api/index',timeout=1) as r:index=json.load(r)
                        break
                    except OSError:
                        if time.monotonic()>deadline:raise
                        time.sleep(.02)
                self.assertEqual(index['trials'][0]['status'],'completed')
                with urllib.request.urlopen(base+'/api/trial?id=baseline-seed42-r0') as r:trial=json.load(r)
                self.assertEqual(trial['manifest']['outcome']['tick'],5)
                self.assertTrue(trial['metrics']);self.assertTrue(trial['events'])
                for route in ('/api/trial?id=../','/world.sqlite'):
                    with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+route)
                with urllib.request.urlopen(base) as r:self.assertIn(b'Artificial Society Laboratory',r.read())
            finally:process.terminate();process.wait(timeout=5)
