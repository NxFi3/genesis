"""Actual deterministic scenarios; provider fixtures are explicitly protocol tests."""
import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from genesis import actions, environment, persistence, predators, production, threats
from genesis.cognition import Scheduler
from genesis.communication import opportunities
from genesis.memory import context
from genesis.models import Building, Wildlife
from genesis.planning import validate_plan
from genesis.providers import InferenceConfig
from genesis.validation import validate_world
from genesis.world import World, BUILDINGS
from test_cognition_v2 import drain, result


class DynamicThreatTests(unittest.TestCase):
    def setUp(self):
        self.w = World(42)
        self.w.terrain = [['plains']*self.w.width for _ in range(self.w.height)]
        self.w.wildlife.clear()
        self.w._blocked_tick = -1
        self.a = self.w.agents['a2']
        for actor in self.w.agents.values(): actor.x, actor.y = 42, 26
        self.a.x, self.a.y = 10, 10
        self.w.tick = 4
        self.w.climate['threats_enabled'] = True
        self.w.climate['threat_settings'].update(night_only=False, grace_ticks=10000)

    def zombie(self, x=13, y=10):
        tid = 'z'+str(len(self.w.threats))
        zombie = {'id':tid,'x':x,'y':y,'hp':35.,'stamina':70.,'species':'zombie','activity':'wander','created':self.w.tick}
        self.w.threats[tid] = zombie
        threats.initialize(self.w)
        return zombie

    def step_threats(self, count):
        for _ in range(count):
            self.w.tick += 1
            threats.update(self.w)

    def test_detection_is_local_and_warning_does_not_reveal_private_history(self):
        z = self.zombie()
        far = self.w.agents['b2']
        self.a.knowledge.append({'claim':'private unrelated memory','source':'self','tick':0})
        threats.update(self.w)
        self.assertIn(z['id'], self.a.observations)
        self.assertNotIn(z['id'], far.observations)
        self.assertFalse(any('private unrelated' in k['claim'] for k in far.knowledge))
        self.assertTrue(self.w.settlements['a'].threat_alert['active'])
        self.assertFalse(self.w.settlements['b'].threat_alert['active'])
        self.assertTrue(any(e['kind']=='settlement_warning' for e in self.w.events))

    def test_closed_wall_interrupts_detection_and_contact(self):
        self.zombie(12,10)
        wall = Building('barrier','wall','a',11,10,8,True)
        self.w.buildings[wall.id] = wall
        threats.update(self.w)
        self.assertFalse(any(o.get('kind')=='threat' for o in self.a.observations.values()))
        self.assertEqual(self.a.hp,100)
        self.assertFalse(actions.execute(self.w,{'action':'repel','target':'z0'},self.a.id)['ok'])

    def test_warn_reaches_nearby_guard_but_not_remote_settlement(self):
        z = self.zombie(14,10)
        guard = self.w.agents['a0']; guard.x, guard.y = 5,10
        threats.observe(self.w)
        self.assertEqual(guard.observations[z['id']]['kind'],'threat_report')
        self.assertEqual(guard.observations[z['id']]['source'],self.a.id)
        self.assertTrue(threats.respond(self.w,guard))
        self.assertGreater(guard.x,5)
        self.assertNotIn(z['id'],self.w.agents['b0'].observations)

    def test_guard_follows_reported_location_without_hidden_live_tracking(self):
        z=self.zombie(14,10)
        guard=self.w.agents['a0'];guard.x,guard.y=5,10
        threats.observe(self.w)
        z['x']=20  # Moved beyond perception after the alarm.
        self.assertTrue(threats.respond(self.w,guard))
        self.assertEqual(self.w._paths[guard.id][0],(14,10))
        self.assertEqual(guard.observations[z['id']]['x'],14)

    def test_pursuit_uses_time_stamina_and_actual_paths(self):
        z = self.zombie(15,10)
        old = z['x']
        threats.update(self.w)
        self.assertEqual(z['activity'],'pursue')
        self.assertEqual(z['target'],self.a.id)
        self.assertLess(z['x'],old)
        self.assertLessEqual(old-z['x'],.65)
        self.assertLess(z['stamina'],70)
        before = (z['x'],z['y'])
        self.w.tick += 1; threats.update(self.w)
        self.assertEqual((z['x'],z['y']),before)

    def test_escape_expires_pursuit_without_live_target_tracking(self):
        z = self.zombie(14,10)
        threats.update(self.w)
        last = z['last_location'][:]
        self.a.x,self.a.y = 30,15
        self.step_threats(12)
        self.assertEqual(z['activity'],'search')
        self.assertEqual(z['last_location'],last)
        self.step_threats(24)
        self.assertIsNone(z['target'])
        self.assertEqual(z['activity'],'wander')
        self.assertTrue(any(e['kind']=='threat_escape' for e in self.w.events))

    def test_day_dormancy_and_night_activity(self):
        z = self.zombie(14,10)
        self.w.climate['threat_settings']['night_only'] = True
        environment.intervene(self.w,{'operation':'time','hour':12})
        threats.update(self.w)
        self.assertEqual(z['activity'],'dormant')
        self.assertEqual(z['x'],14)
        environment.intervene(self.w,{'operation':'time','hour':23})
        self.w.tick += 4; threats.update(self.w)
        self.assertEqual(z['activity'],'pursue')
        self.assertLess(z['x'],14)

    def test_spawn_regions_obey_settlement_building_and_person_exclusions(self):
        self.w.climate['threat_settings'].update(spawn_regions=[[1,1,5,3]], grace_ticks=0, spawn_interval=60, max_zombies=2)
        for tick in (60,120,180): self.w.tick=tick; threats.update(self.w)
        self.assertTrue(self.w.threats)
        self.assertLessEqual(len(self.w.threats),2)
        for z in self.w.threats.values():
            self.assertTrue(1<=z['x']<=5 and 1<=z['y']<=3)
            self.assertTrue(all(math.hypot(s.x-z['x'],s.y-z['y'])>=9 for s in self.w.settlements.values()))
            self.assertTrue(all(math.hypot(b.x-z['x'],b.y-z['y'])>=4 for b in self.w.buildings.values()))
        self.w.threats.clear()
        self.w.climate['threat_settings']['spawn_regions']=[[8,10,8,10]]
        self.w.tick=240; threats.update(self.w)
        self.assertFalse(self.w.threats)

    def test_spawn_suppressed_during_day_grace_and_peaceful_intensity(self):
        config = self.w.climate['threat_settings']
        config.update(grace_ticks=10000, spawn_interval=60)
        self.w.tick=60; threats.update(self.w); self.assertFalse(self.w.threats)
        config.update(grace_ticks=0, night_only=True)
        environment.intervene(self.w,{'operation':'time','hour':12})
        self.w.tick=120; threats.update(self.w); self.assertFalse(self.w.threats)
        self.w.climate['threat_settings'].update(night_only=False,intensity=0)
        self.w.tick=180; threats.update(self.w); self.assertFalse(self.w.threats)

    def test_disable_removes_zombies_and_live_alarms_without_erasing_memories(self):
        self.zombie(); threats.update(self.w)
        remembered = len(self.a.memories)
        environment.intervene(self.w,{'operation':'threats','enabled':False})
        self.assertFalse(self.w.threats, 'Disabling must take effect while paused')
        threats.update(self.w)
        self.assertFalse(self.w.threats)
        self.assertFalse(self.w.settlements['a'].threat_alert['active'])
        self.assertNotIn('z0',self.a.observations)
        self.assertGreaterEqual(len(self.a.memories),remembered)

    def test_reducing_cap_retires_excess_without_resource_or_history_loss(self):
        self.zombie(13,10);self.zombie(13,12);self.zombie(13,14)
        before={a.id:dict(a.inventory) for a in self.w.agents.values()}
        environment.intervene(self.w,{'operation':'threats','settings':{'max_zombies':1}})
        self.assertEqual(len(self.w.threats),1)
        self.assertEqual(before,{a.id:a.inventory for a in self.w.agents.values()})
        self.assertTrue(any(e['kind']=='threats_rebalanced' for e in self.w.events))

    def test_closing_completing_and_repairing_barriers_cannot_trap_nonhumans(self):
        z=self.zombie(11,10)
        gate=Building('gate','gate','a',11,10,8,True)
        self.w.buildings[gate.id]=gate;self.w.gates[gate.id]=True
        self.assertFalse(actions.execute(self.w,{'action':'gate','building':gate.id,'open':False},self.a.id)['ok'])
        gate.kind='wall';gate.complete=False;gate.progress=7.9
        self.w.gates.pop(gate.id)
        self.assertFalse(actions.execute(self.w,{'action':'work','building':gate.id},self.a.id,True)['ok'])
        self.assertFalse(gate.complete)
        gate.complete=True;gate.condition=0;self.a.inventory['wood']=1
        self.assertFalse(actions.execute(self.w,{'action':'repair','building':gate.id},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['wood'],1)
        self.assertEqual(gate.condition,0)
        z['x']=12
        self.assertTrue(actions.execute(self.w,{'action':'repair','building':gate.id},self.a.id)['ok'])
        self.assertFalse(self.w.passable(11,10))
        z.update(x=11,hp=0,activity='dispersed',ended=self.w.tick)
        validate_world(self.w)  # Dispersed remains do not block a new barrier or corrupt saves.

    def test_destroyed_defenses_do_not_repair_themselves_through_decay_or_storms(self):
        wall=Building('ruin','wall','a',12,10,8,True,0)
        self.w.buildings[wall.id]=wall
        self.w.tick=100;self.w._institutions()
        self.assertEqual(wall.condition,0)
        environment.intervene(self.w,{'operation':'weather','region':'a','weather':'thunderstorm','duration':200})
        self.w.tick=120;environment.update(self.w)
        self.assertEqual(wall.condition,0)

    def test_wolf_reproduction_cannot_create_threats_inside_a_settlement(self):
        s=self.w.settlements['a']
        self.w.wildlife={'one':Wildlife('one',s.x,s.y,species='wolf'), 'two':Wildlife('two',s.x+1,s.y,species='wolf')}
        self.w.tick=600;self.w._institutions()
        self.assertEqual(len(self.w.wildlife),2)

    def test_production_escrow_pauses_during_defense_then_resumes(self):
        b=self.w.buildings['a_furnace'];self.a.x,self.a.y=b.x,b.y
        self.a.inventory.update(iron_ore=2,coal=1)
        answer=production.start(self.w,self.a,'smelt_iron',b.id)
        self.assertTrue(answer['ok']);job=self.w.production_jobs[answer['job']]
        z=self.zombie(b.x+2,b.y);threats.observe(self.w)
        actions.execute(self.w,{'action':'threat_response','target':z['id'],'choice':'defend'},self.a.id)
        threats.respond(self.w,self.a);production.update(self.w)
        self.assertEqual(job['progress'],0)
        self.assertEqual(job['escrow'],{'iron_ore':2,'coal':1})
        self.w.threats.clear();self.w.tick+=1;production.update(self.w)
        self.assertGreater(job['progress'],0)
        self.assertEqual(self.a.inventory['iron_ingot'],0)

    def test_provider_failure_preserves_guard_response_and_never_schedules_zombies(self):
        self.a.occupation='guard';self.zombie(12,10)
        scheduler=Scheduler(InferenceConfig(enabled=True),lambda *_:{'ok':False,'error':'provider disconnected'})
        try:
            self.assertFalse(scheduler.request(self.w,'z0','not a human'))
            scheduler.request(self.w,self.a.id,'threat strategy')
            drain(scheduler,self.w,lambda:scheduler.metrics['failed']==1)
            self.w.step(20)
            self.assertTrue(any(e['kind']=='threat_repelled' for e in self.w.events))
            self.assertGreater(self.a.hp,0)
            validate_world(self.w)
        finally:scheduler.close()

    def test_guard_approaches_defends_and_ends_actual_encounter(self):
        self.a.occupation = 'guard'
        z=self.zombie(14,10)
        for _ in range(60):
            self.w.tick += 1; threats.update(self.w); threats.respond(self.w,self.a)
            self.a.stamina=min(100,self.a.stamina+2)
            if z['hp']==0: break
        self.assertEqual(z['hp'],0)
        self.assertEqual(z['activity'],'dispersed')
        self.assertGreater(self.a.hp,0)
        hp=self.a.hp;self.step_threats(20)
        self.assertEqual(self.a.hp,hp)
        self.assertFalse(threats.respond(self.w,self.a))

    def test_civilian_choices_depend_on_health_personality_and_intention(self):
        self.zombie();threats.observe(self.w)
        self.a.personality.update(courage=.1,sociability=.1,aggression=.1)
        threats.respond(self.w,self.a)
        self.assertIn(self.a.threat_state['choice'],('shelter','flee'))
        self.a.x,self.a.y=10,10;self.a.personality.update(courage=.9,sociability=.1,aggression=.9)
        threats.respond(self.w,self.a)
        self.assertEqual(self.a.threat_state['choice'],'defend')
        actions.execute(self.w,{'action':'threat_response','target':'z0','choice':'request_help'},self.a.id)
        threats.respond(self.w,self.a)
        self.assertEqual(self.a.threat_state['choice'],'request_help')
        self.a.hp=25
        actions.execute(self.w,{'action':'threat_response','target':'z0','choice':'defend'},self.a.id)
        threats.respond(self.w,self.a)
        self.assertIn(self.a.threat_state['choice'],('shelter','flee'))

    def test_flee_increases_distance_and_consumes_stamina(self):
        self.a.x,self.a.y=20,10
        z=self.zombie(22,10);threats.observe(self.w)
        actions.execute(self.w,{'action':'threat_response','target':z['id'],'choice':'flee'},self.a.id)
        before=threats.separation(self.a,z);stamina=self.a.stamina
        threats.respond(self.w,self.a)
        self.assertGreater(threats.separation(self.a,z),before)
        self.assertLess(self.a.stamina,stamina)
        self.assertTrue(self.w.passable(self.a.x,self.a.y))

    def test_plan_and_reserved_work_are_preserved_during_danger(self):
        self.zombie();threats.observe(self.w)
        self.a.plan=[{'action':'rest','_started':1}];self.a.plan_status='active'
        self.w.tick=20;threats.respond(self.w,self.a)
        self.assertEqual(self.a.plan_status,'active');self.assertEqual(self.a.plan_index,0)
        self.assertEqual(self.a.plan[0]['_started'],2)

    def test_llm_intention_step_executes_before_routine_safety_fallback(self):
        self.zombie();threats.observe(self.w)
        self.a.plan=validate_plan({'plan':[{'action':'threat_response','target':'z0','choice':'cooperate'},{'action':'observe'}]})['plan']
        self.a.plan_status='active'
        threats.respond(self.w,self.a)
        self.assertEqual(self.a.threat_intent['choice'],'cooperate')
        self.assertEqual(self.a.plan_index,1)
        self.assertEqual(self.a.activity,'cooperate')

    def test_defense_costs_armor_cooldown_and_combat_outcomes(self):
        z=self.zombie(11,10);self.a.equipment=['staff','shield']
        before=dict(self.a.inventory)
        self.assertTrue(actions.execute(self.w,{'action':'repel','target':z['id']},self.a.id)['ok'])
        self.assertEqual(self.a.stamina,92)
        hp=z['hp'];self.assertLess(hp,35)
        self.assertFalse(actions.execute(self.w,{'action':'repel','target':z['id']},self.a.id)['ok'])
        self.assertEqual(z['hp'],hp)
        self.assertLess(self.a.equipment_condition['staff'],100)
        self.assertEqual(self.a.inventory,before)
        self.w.tick+=4;threats.update(self.w)
        self.assertGreaterEqual(self.a.hp,99)

    def test_watchtower_protects_against_real_contact(self):
        z=self.zombie(11,10);threats.update(self.w)
        unprotected=100-self.a.hp
        self.w.buildings['tower']=Building('tower','watchtower','a',10,11,20,True)
        self.a.hp=100;self.w.tick+=8;threats.update(self.w)
        self.assertLess(100-self.a.hp,unprotected)
        self.a.hp=1;self.w.tick+=8;threats.update(self.w)
        self.assertTrue(self.a.incapacitated)
        hp=self.a.hp;self.w.tick+=8;threats.update(self.w)
        self.assertEqual(self.a.hp,hp)

    def test_builder_defense_project_and_repair_have_material_costs(self):
        self.a.occupation='builder';s=self.w.settlements['a'];self.a.x,self.a.y=s.x,s.y
        s.inventory.update(wood=40,stone=40)
        s.threat_alert={'active':True,'until':104,'reports':{}}
        before=dict(s.inventory)
        self.assertTrue(threats.maintain(self.w,self.a))
        tower=self.w.buildings['a_watchtower']
        self.assertFalse(tower.complete)
        for kind in ('wood','stone'):self.assertEqual(s.inventory[kind],before[kind]-BUILDINGS['watchtower'][kind])
        for _ in range(40):self.w.tick+=1;threats.maintain(self.w,self.a)
        self.assertTrue(tower.complete)
        tower.condition=60;self.a.x,self.a.y=tower.x-1,tower.y;self.a.inventory['wood']=2;self.a.stamina=100
        self.assertTrue(threats.maintain(self.w,self.a))
        self.assertEqual(tower.condition,70);self.assertEqual(self.a.inventory['wood'],1);self.assertEqual(self.a.stamina,97)
        self.a.inventory['wood']=0;s.inventory['wood']=0
        self.assertFalse(actions.execute(self.w,{'action':'repair','building':tower.id},self.a.id)['ok'])
        self.assertEqual(tower.condition,70)

    def test_settings_validation_is_atomic_and_persisted(self):
        before=copy.deepcopy(self.w.climate)
        for settings in ({'intensity':float('nan')},{'max_zombies':99},{'max_zombies':1.5},{'night_only':'yes'},{'spawn_regions':[[8,10,8,99]]},{'unknown':1}):
            with self.assertRaises(ValueError):environment.intervene(self.w,{'operation':'threats','enabled':False,'settings':settings})
            self.assertEqual(self.w.climate,before)
        environment.intervene(self.w,{'operation':'threats','settings':{'intensity':.5,'max_zombies':2,'spawn_regions':[[1,1,3,3]]}})
        loaded=World.from_snapshot(json.loads(json.dumps(self.w.snapshot(True))))
        self.assertEqual(self.w.climate,loaded.climate)
        self.assertEqual(self.w.events[-1]['kind'],'god_intervention')

    def test_wolf_hunts_only_real_prey_and_carcass_cannot_be_double_harvested(self):
        self.a.x,self.a.y=30,20
        wolf=Wildlife('wolf',5,5,species='wolf',hunger=60)
        prey=Wildlife('deer',5,6,hp=10)
        self.w.wildlife={wolf.id:wolf,prey.id:prey}
        predators.wolf(self.w,wolf)
        self.assertEqual(prey.hp,0);self.assertTrue(prey.harvested)
        self.assertLess(wolf.hunger,60);self.assertLess(wolf.stamina,70)
        self.a.x,self.a.y=5,6
        self.assertFalse(actions.execute(self.w,{'action':'hunt','target':prey.id},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['raw_meat'],0)

    def test_wolf_avoids_guard_and_returns_to_territory_without_human_pursuit(self):
        wolf=Wildlife('wolf',12,10,species='wolf')
        self.w.wildlife[wolf.id]=wolf
        self.a.occupation='guard'
        before=math.hypot(wolf.x-self.a.x,wolf.y-self.a.y)
        predators.wolf(self.w,wolf)
        self.assertEqual(wolf.activity,'avoid')
        self.assertGreater(math.hypot(wolf.x-self.a.x,wolf.y-self.a.y),before)
        self.a.x,self.a.y=30,20
        for tick in range(8,160,4):self.w.tick=tick;predators.wolf(self.w,wolf)
        self.assertLessEqual(math.hypot(wolf.x-12,wolf.y-10),6.5)

    def test_wolf_warning_is_not_an_automatic_attack_but_territory_can_be_defended(self):
        wolf=Wildlife('wolf',11,10,species='wolf')
        self.w.wildlife[wolf.id]=wolf
        predators.wolf(self.w,wolf);threats.update(self.w)
        self.assertEqual(wolf.activity,'warning');self.assertEqual(self.a.hp,100)
        self.w.climate['threat_settings']['wolf_aggression']=1
        self.w.tick+=4;predators.wolf(self.w,wolf);threats.update(self.w)
        self.assertEqual(wolf.activity,'territorial');self.assertLess(self.a.hp,100)

    def test_predator_observer_spawn_cannot_overlap_people_or_settlements(self):
        with self.assertRaises(ValueError):environment.intervene(self.w,{'operation':'spawn','species':'wolf','x':10,'y':10})
        self.assertNotIn('wolf',self.w.wildlife)
        self.assertTrue(environment.intervene(self.w,{'operation':'spawn','species':'wolf','x':2,'y':2})['ok'])

    def test_warning_expiry_and_sourced_conversation_report(self):
        self.zombie();threats.observe(self.w)
        partner=self.w.agents['a3'];partner.x,partner.y=10,11
        unrelated=self.w.agents['b3']
        self.assertNotIn('z0',partner.observations)
        self.assertTrue(actions.execute(self.w,{'action':'report_threat','target':partner.id,'threat':'z0'},self.a.id)['ok'])
        self.assertEqual(partner.observations['z0']['kind'],'threat_report')
        self.assertEqual(partner.observations['z0']['source'],self.a.id)
        self.assertNotIn('z0',unrelated.observations)
        self.w.threats.clear();self.w.tick+=101;threats.observe(self.w)
        self.assertFalse(self.w.settlements['a'].threat_alert['active'])
        self.assertFalse(actions.execute(self.w,{'action':'report_threat','target':partner.id,'threat':'z0'},self.a.id)['ok'])

    def test_protocol_conversation_shares_one_report_into_persistent_private_memory(self):
        self.zombie();threats.observe(self.w)
        partner=self.w.agents['a3'];partner.x,partner.y=10,11
        captured=[]
        def provider(config,system,payload):
            captured.append(payload)
            if 'conversation' not in payload:
                return result(plan=[],conversation={'target':partner.id,'topic':'threat warning','message':'I saw a wanderer nearby; can we arrange a watch?'})
            if payload['agent']['identity']['id']==self.a.id:
                return result(plan=[],speech='It was near the eastern field; I will share the location I observed.',dialogue_actions=[{'action':'report_threat','target':partner.id,'threat':'z0'}],end_conversation=True)
            return result(plan=[],speech='Tell me where you saw it; I can help keep watch.')
        scheduler=Scheduler(InferenceConfig(enabled=True),provider)
        try:
            self.assertEqual(opportunities(self.w,self.a)[0]['topic'],'threat warning')
            scheduler.request(self.w,self.a.id,'important sighting',1)
            drain(scheduler,self.w,lambda:bool(self.w.conversations) and next(iter(self.w.conversations.values()))['state']=='ended')
            private=captured[0]['agent']
            self.assertTrue(private.get('threat_reports',private.get('perception',{}).get('threat_reports',[])))
            self.assertTrue(any('wanderer' in k['claim'] and k['source']==self.a.id for k in partner.knowledge))
            self.assertEqual(partner.observations['z0']['kind'],'threat_report')
            self.assertEqual(partner.observations['z0']['source'],self.a.id)
            self.assertTrue(any(o['action']=='report_threat' and o['ok'] for o in next(iter(self.w.conversations.values()))['outcomes']))
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'talk.sqlite';persistence.save(self.w,path);loaded=persistence.load(path)
                self.assertEqual(loaded.agents[partner.id].knowledge,partner.knowledge)
                self.assertEqual(loaded.conversations,self.w.conversations)
        finally:scheduler.close()

    def test_active_pursuit_alarms_intentions_and_wolf_state_resume_exactly(self):
        self.zombie();wolf=Wildlife('wolf',3,3,species='wolf',behavior={'territory':[3,3]});self.w.wildlife['wolf']=wolf
        threats.update(self.w)
        actions.execute(self.w,{'action':'threat_response','target':'z0','choice':'shelter'},self.a.id)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'threat.sqlite';persistence.save(self.w,path);loaded=persistence.load(path)
            self.assertEqual(self.w.snapshot(True),loaded.snapshot(True))
            self.w.step(40);loaded.step(40)
            self.assertEqual(self.w.snapshot(True),loaded.snapshot(True))
            validate_world(loaded)

    def test_legacy_saves_receive_safe_optional_defaults_and_invalid_threats_rejected(self):
        data=copy.deepcopy(self.w.snapshot(True));data['climate'].pop('threat_settings')
        for actor in data['agents'].values():
            actor.pop('threat_intent');actor.pop('threat_state')
        for home in data['settlements'].values():home.pop('threat_alert')
        loaded=World.from_snapshot(data)
        self.assertEqual(loaded.climate['threat_settings'],threats.DEFAULTS)
        z=self.zombie();bad=copy.deepcopy(self.w.snapshot(True));bad['threats'][z['id']]['stamina']=-1
        with self.assertRaises(ValueError):World.from_snapshot(bad)
        bad=copy.deepcopy(self.w.snapshot(True));bad['threats'][z['id']]['species']='human'
        with self.assertRaises(ValueError):World.from_snapshot(bad)


if __name__=='__main__':unittest.main()
