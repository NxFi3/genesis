"""Genesis 3 authoritative mechanics and integrated regional survival scenarios."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from genesis import actions, environment, persistence, production, survival
from genesis.models import Building, Wildlife
from genesis.registry import RESOURCES, PRODUCTION, mass, validate_registry
from genesis.validation import validate_world
from genesis.world import World, BUILDINGS
from genesis.server import Simulation
from genesis.cognition import Scheduler
from genesis.providers import InferenceConfig
from test_cognition_v2 import drain, result


class WorldV3Tests(unittest.TestCase):
    def setUp(self):
        self.w=World(42)
        self.a=self.w.agents['a2']
        self.a.x,self.a.y=9,10

    def tick_systems(self,count=1):
        for _ in range(count):
            self.w.tick+=1
            environment.update(self.w)
            survival.update(self.w)
            production.update(self.w)

    def test_registry_complete_and_legacy_inventory_defaults(self):
        self.assertTrue(validate_registry())
        required='iron_ore copper_ore gold_ore silver_ore coal stone clay sand wood plant_fiber seeds hides wool planks bricks charcoal iron_ingot copper_ingot gold_ingot silver_ingot tools equipment wheat vegetables fruit raw_meat cooked_meat fish bread water'.split()
        self.assertTrue(set(required)<=set(RESOURCES))
        data=self.w.snapshot(True)
        data['version']=1
        for field in ('climate','crops','fires','production_jobs','gates','threats','elevation'): data.pop(field,None)
        for a in data['agents'].values():
            for field in ('warmth','extraction','production_job','carry_capacity','equipment_condition'): a.pop(field,None)
            a['inventory']={k:v for k,v in a['inventory'].items() if k in ('food','water','wood','stone','metal','tools')}
        loaded=World.from_snapshot(json.loads(json.dumps(data)))
        self.assertIn('gold_ore',loaded.agents['a2'].inventory)
        self.assertEqual(loaded.agents['a2'].inventory['gold_ore'],0)
        self.assertEqual(loaded.snapshot()['version'],2)

    def test_finite_mining_takes_ticks_and_uses_real_mass(self):
        r=self.w.resources['a_iron_ore_vein']
        self.a.x,self.a.y=r.x-1,r.y
        before=r.quantity
        for i in range(3):
            self.w.tick+=1
            answer=actions.execute(self.w,{'action':'mine','resource':r.id},self.a.id,True)
            self.assertTrue(answer['pending'])
            self.assertEqual(r.quantity,before)
        # Repeated HTTP posts in the same tick cannot accelerate mining.
        actions.execute(self.w,{'action':'mine','resource':r.id},self.a.id,True)
        self.w.tick+=1
        self.assertFalse(actions.execute(self.w,{'action':'mine','resource':r.id},self.a.id,True)['pending'])
        self.assertEqual(r.quantity,before-1)
        self.assertEqual(self.a.inventory['iron_ore'],1)
        self.a.carry_capacity=mass(self.a.inventory)
        self.assertFalse(actions.execute(self.w,{'action':'mine','resource':r.id},self.a.id)['ok'])

    def test_timed_smelting_escrow_pause_resume_and_no_duplicate_output(self):
        b=self.w.buildings['a_furnace']; self.a.x,self.a.y=b.x,b.y
        self.a.inventory.update(iron_ore=2,coal=1)
        response=actions.execute(self.w,{'action':'produce','recipe':'smelt_iron'},self.a.id,True)
        self.assertTrue(response['pending'])
        job=self.w.production_jobs[response['job']]
        self.assertEqual(job['escrow'],{'iron_ore':2,'coal':1})
        self.assertEqual(self.a.inventory['iron_ingot'],0)
        self.a.x=2
        self.tick_systems(5)
        self.assertEqual(job['progress'],0)
        self.a.x,self.a.y=b.x,b.y
        self.tick_systems(12)
        self.assertEqual(self.a.inventory['iron_ingot'],1)
        self.assertEqual(job['state'],'completed')
        self.assertFalse(job['escrow'])
        self.tick_systems(10)
        self.assertEqual(self.a.inventory['iron_ingot'],1)
        self.assertFalse(actions.execute(self.w,{'action':'produce','recipe':'smelt_iron'},self.a.id,True)['pending'])

    def test_cancel_returns_escrow_exactly_once(self):
        b=self.w.buildings['a_carpenter']; self.a.x,self.a.y=b.x,b.y
        self.a.inventory['wood']=4
        self.assertTrue(production.start(self.w,self.a,'planks')['ok'])
        self.assertEqual(self.a.inventory['wood'],2)
        self.assertTrue(production.cancel(self.w,self.a)['ok'])
        self.assertEqual(self.a.inventory['wood'],4)
        self.assertFalse(production.cancel(self.w,self.a)['ok'])
        self.assertEqual(self.a.inventory['wood'],4)

    def test_ore_ingot_tools_chain_has_defined_inputs_and_outputs(self):
        b=self.w.buildings['a_furnace']; self.a.x,self.a.y=b.x,b.y
        self.a.inventory.update(iron_ore=2,coal=1,planks=2)
        self.assertTrue(production.start(self.w,self.a,'smelt_iron')['ok'])
        self.tick_systems(12)
        b=self.w.buildings['a_blacksmith'];self.a.x,self.a.y=b.x,b.y
        self.assertTrue(production.start(self.w,self.a,'refined_tools')['ok'])
        self.tick_systems(10)
        self.assertEqual(self.a.inventory['tools'],2)
        self.assertEqual(self.a.inventory['iron_ingot'],0)
        self.assertEqual(self.a.inventory['planks'],0)
        self.assertEqual(self.a.inventory['iron_ore'],0)
        self.assertEqual(self.a.inventory['coal'],0)

    def test_fire_fuel_cooking_and_extinguishing_are_mechanical(self):
        b=self.w.buildings['a_hearth'];self.a.x,self.a.y=b.x,b.y
        self.a.inventory.update(wood=3,raw_meat=2)
        self.assertFalse(production.start(self.w,self.a,'cook_meat')['ok'])
        self.assertTrue(actions.execute(self.w,{'action':'fuel','building':b.id},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['wood'],2)
        self.assertEqual(self.w.fires[b.id]['fuel_ticks'],40)
        self.assertTrue(production.start(self.w,self.a,'cook_meat')['ok'])
        self.tick_systems(6)
        self.assertGreater(self.a.inventory['cooked_meat'],1.9)
        self.assertLess(self.w.fires[b.id]['fuel_ticks'],40)
        self.a.hunger=80
        self.w._consume(self.a,'food','hunger')
        self.assertLess(self.a.hunger,40)
        self.assertTrue(actions.execute(self.w,{'action':'extinguish','building':b.id},self.a.id)['ok'])
        self.assertFalse(self.w.fires[b.id]['lit'])

    def test_spoilage_reduces_food_and_barn_preserves_more(self):
        actor=self.a; actor.inventory['raw_meat']=10
        store=self.w.settlements['a'];store.inventory['raw_meat']=10
        self.w.buildings['a_barn']=Building('a_barn','barn','a',8,10,18,True)
        self.w.tick=20;survival.update(self.w)
        self.assertLess(actor.inventory['raw_meat'],10)
        self.assertGreater(store.inventory['raw_meat'],actor.inventory['raw_meat'])
        self.assertGreater(self.w.stats['spoiled'],0)

    def test_non_graphic_hunt_has_single_real_yield(self):
        animal=Wildlife('prey',10,10)
        self.w.wildlife[animal.id]=animal
        initial=self.a.inventory['raw_meat']
        for _ in range(4): self.assertTrue(actions.execute(self.w,{'action':'hunt','target':animal.id},self.a.id)['ok'])
        self.assertEqual(animal.hp,0)
        self.assertEqual(self.a.inventory['raw_meat'],initial+3)
        self.assertEqual(self.a.inventory['hides'],1)
        self.assertFalse(actions.execute(self.w,{'action':'hunt','target':animal.id},self.a.id)['ok'])

    def test_fishing_consumes_stock_and_requires_time(self):
        r=self.w.resources['fish_stock_0'];self.a.x,self.a.y=r.x-1,r.y
        quantity=r.quantity
        for _ in range(3):
            self.w.tick+=1
            reply=actions.execute(self.w,{'action':'fish','resource':r.id},self.a.id,True)
        self.assertTrue(reply['ok'])
        self.assertEqual(r.quantity,quantity-1)
        self.assertEqual(self.a.inventory['fish'],1)

    def test_regional_drought_reduces_water_recharge_and_crop_growth(self):
        normal=World.from_snapshot(copy.deepcopy(self.w.snapshot(True)))
        for w in (self.w,normal):
            environment.intervene(w,{'operation':'weather','weather':'rain','region':'world','duration':500})
            w.buildings['a_farm']=Building('a_farm','farm','a',10,10,10,True)
            w.crops['a_farm']={'building':'a_farm','kind':'wheat','growth':0.,'stage':'seedling','yield':0.,'planted':0}
            w.resources['a_r1'].quantity=400
        environment.intervene(self.w,{'operation':'weather','weather':'drought','region':'a','duration':500})
        for _ in range(80):
            for w in (self.w,normal):
                w.tick+=1;environment.update(w);w._ecology();survival.update(w)
        self.assertLess(self.w.resources['a_r1'].quantity,normal.resources['a_r1'].quantity)
        self.assertLess(self.w.climate['regions']['a']['moisture'],normal.climate['regions']['a']['moisture'])
        self.assertLess(self.w.crops['a_farm']['growth'],normal.crops['a_farm']['growth'])
        self.assertEqual(environment.conditions(self.w,region='b')['weather'],'rain')
        self.assertTrue(any(e['kind']=='god_intervention' for e in self.w.events))
        self.assertTrue(any(e['kind']=='environment_observed' for e in self.w.events))

    def test_irrigation_uses_water_and_crop_harvest_is_owned(self):
        self.w.buildings['farm']=Building('farm','farm','a',10,10,10,True)
        self.a.inventory.update(seeds=2,water=5)
        self.assertTrue(actions.execute(self.w,{'action':'plant','building':'farm','crop':'wheat'},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['seeds'],1)
        self.assertEqual(self.a.inventory['water'],4)
        self.w.climate['regions']['a']['moisture']=.1
        self.assertTrue(actions.execute(self.w,{'action':'irrigate','building':'farm','amount':2},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['water'],2)
        self.assertAlmostEqual(self.w.climate['regions']['a']['moisture'],.3)
        self.w.crops['farm'].update(stage='mature',**{'yield':6})
        self.assertTrue(actions.execute(self.w,{'action':'harvest','building':'farm'},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['wheat'],6)
        self.assertFalse(actions.execute(self.w,{'action':'harvest','building':'farm'},self.a.id)['ok'])

    def test_cold_warmth_and_shelter_are_connected(self):
        environment.intervene(self.w,{'operation':'weather','weather':'blizzard','temperature':-25,'duration':200})
        self.a.x,self.a.y=18,10; self.a.warmth=60
        survival.update(self.w);self.assertGreater(self.a.warmth,60)
        self.assertTrue(survival.emergency(self.w,self.a))
        self.assertLess(self.a.x,18)
        self.a.x,self.a.y=9,10
        old=self.a.warmth
        for _ in range(10):survival.update(self.w)
        self.assertLess(self.a.warmth,old)

    def test_god_validation_atomic_natural_resume_and_persistence(self):
        before=copy.deepcopy(self.w.climate)
        with self.assertRaises(ValueError): environment.intervene(self.w,{'weather':'rain','temperature':float('nan')})
        self.assertEqual(before,self.w.climate)
        environment.intervene(self.w,{'operation':'weather','region':'a','weather':'drought','duration':2})
        environment.intervene(self.w,{'operation':'time','hour':16})
        self.assertEqual(self.w.hour,16)
        data=copy.deepcopy(self.w.snapshot(True)); loaded=World.from_snapshot(data)
        self.assertEqual(self.w.climate,loaded.climate)
        self.tick_systems(2)
        self.assertNotIn('a',self.w.climate['overrides'])
        environment.intervene(self.w,{'operation':'natural'})
        self.assertEqual(self.w.climate['clock_offset'],0)

    def test_barriers_and_gates_invalidate_paths_and_persist(self):
        b=Building('wall','wall','a',12,10,8,True)
        self.w.buildings[b.id]=b;self.w._blocked_tick=-1
        self.assertFalse(self.w.passable(12,10))
        b.kind='gate';self.w.gates[b.id]=False;self.w._blocked_tick=-1
        self.a.x,self.a.y=11,10
        self.assertTrue(actions.execute(self.w,{'action':'gate','building':b.id,'open':True},self.a.id)['ok'])
        self.assertTrue(self.w.passable(12,10))
        self.a.x=12
        self.assertFalse(actions.execute(self.w,{'action':'gate','building':b.id,'open':False},self.a.id)['ok'])
        loaded=World.from_snapshot(copy.deepcopy(self.w.snapshot(True)))
        self.assertTrue(loaded.gates['wall'])

    def test_active_production_weather_crops_and_dialogue_save_resume_exactly(self):
        b=self.w.buildings['a_furnace'];self.a.x,self.a.y=b.x,b.y
        self.a.inventory.update(iron_ore=2,coal=1)
        production.start(self.w,self.a,'smelt_iron')
        environment.intervene(self.w,{'operation':'weather','region':'b','weather':'snow','duration':200})
        self.w.conversations['persist']={'id':'persist','participants':['a0','player'],'state':'waiting_player','turns':[{'speaker':'a0','source':'llm','text':'A fixture conversation','tick':0}],'updated':0,'created':0,'next_speaker':None}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'v3.sqlite';persistence.save(self.w,path);loaded=persistence.load(path)
            self.assertEqual(self.w.snapshot(True),loaded.snapshot(True))
            self.w.step(20);loaded.step(20)
            self.assertEqual(self.w.snapshot(True),loaded.snapshot(True))

    def test_corrupt_new_system_state_rejected(self):
        for field,value in [('elevation',[[float('nan')]]),('climate',{'overrides':{},'regions':{},'difficulty':float('nan'),'threats_enabled':False,'season_override':None,'clock_offset':0})]:
            data=copy.deepcopy(self.w.snapshot(True));data[field]=value
            with self.assertRaises(ValueError):World.from_snapshot(data)

    def test_local_climate_reaches_private_llm_context_and_valid_irrigation(self):
        environment.intervene(self.w,{'operation':'weather','region':'a','weather':'drought','duration':100})
        self.w.buildings['farm']=Building('farm','farm','a',10,10,10,True)
        self.w.climate['regions']['a']['moisture']=.1
        self.a.inventory['water']=5
        seen=[]
        def fake_provider(config,system,payload):
            seen.append(payload)
            return result(goal='Protect the crop I can see from this drought',plan=[{'action':'irrigate','building':'farm','amount':2}])
        scheduler=Scheduler(InferenceConfig(enabled=True),fake_provider)
        try:
            scheduler.request(self.w,self.a.id,'observed drought')
            drain(scheduler,self.w,lambda:scheduler.metrics['completed']==1)
            self.assertEqual(seen[0]['agent']['perception']['climate']['weather'],'drought')
            self.assertNotIn('god',seen[0]['action_schemas'])
            from genesis.planning import execute_plan
            self.assertTrue(execute_plan(self.w,self.a))
            self.assertEqual(self.a.inventory['water'],3)
            self.assertGreater(self.w.climate['regions']['a']['moisture'],.1)
        finally:scheduler.close()

    def test_water_collection_and_rain_collector_have_real_reserves(self):
        r=self.w.resources['a_r1'];self.a.x,self.a.y=r.x,r.y
        before=r.quantity;carried=self.a.inventory['water']
        self.assertTrue(actions.execute(self.w,{'action':'collect_water','resource':r.id},self.a.id)['ok'])
        self.assertEqual(r.quantity,before-2)
        self.assertEqual(self.a.inventory['water'],carried+2)
        self.w.buildings['collector']=Building('collector','rain_collector','a',9,9,12,True)
        environment.intervene(self.w,{'operation':'weather','region':'a','weather':'heavy_rain','duration':20})
        before=self.w.settlements['a'].inventory['water']
        self.w.tick=10;self.w._ecology()
        self.assertGreater(self.w.settlements['a'].inventory['water'],before)

    def test_rectangular_intervention_is_local_and_validated(self):
        environment.intervene(self.w,{'operation':'weather','weather':'rain','region':'world'})
        environment.intervene(self.w,{'operation':'weather','weather':'drought','region':'region','bounds':[8,8,12,12]})
        self.assertEqual(environment.conditions(self.w,9,10)['weather'],'drought')
        self.assertEqual(environment.conditions(self.w,38,18)['weather'],'rain')
        self.tick_systems(10)
        self.assertLess(self.w.climate['regions']['region']['moisture'],.65)
        self.assertEqual(World.from_snapshot(copy.deepcopy(self.w.snapshot(True))).climate,self.w.climate)
        before=copy.deepcopy(self.w.climate)
        with self.assertRaises(ValueError):environment.intervene(self.w,{'operation':'weather','weather':'rain','region':'region','bounds':[20,20,1,1]})
        self.assertEqual(before,self.w.climate)

    def test_transfer_and_barter_respect_net_capacity_atomically(self):
        b=self.w.agents['a3'];b.x,b.y=self.a.x,self.a.y
        self.a.inventory['wood']=1;b.inventory['iron_ore']=1
        self.a.carry_capacity=mass(self.a.inventory)
        before=(dict(self.a.inventory),dict(b.inventory))
        self.assertFalse(self.w.trade(self.a,b,'wood','iron_ore',1,accepted=True))
        self.assertEqual(before,(self.a.inventory,b.inventory))
        self.assertFalse(self.w.transfer(b.inventory,self.a.inventory,'iron_ore',1))
        self.assertEqual(before,(self.a.inventory,b.inventory))

    def test_player_mining_continues_in_engine_and_movement_cancels(self):
        p=self.w.agents['player'];r=self.w.resources['a_coal_vein']
        p.x,p.y=r.x-1,r.y
        self.assertTrue(actions.execute(self.w,{'action':'mine','resource':r.id})['pending'])
        self.w.step(3)
        self.assertEqual(p.inventory['coal'],1)
        self.assertFalse(p.extraction['auto'])
        actions.execute(self.w,{'action':'mine','resource':r.id})
        actions.execute(self.w,{'action':'move','x':p.x,'y':p.y})
        self.assertFalse(p.extraction['auto'])

    def test_fuel_cap_refuses_without_consuming_fuel(self):
        b=self.w.buildings['a_hearth'];self.a.x,self.a.y=b.x,b.y
        self.w.fires[b.id]={'fuel_ticks':350,'lit':True};self.a.inventory['coal']=2
        self.assertFalse(actions.execute(self.w,{'action':'fuel','building':b.id,'kind':'coal','amount':1},self.a.id)['ok'])
        self.assertEqual(self.a.inventory['coal'],2)
        self.assertEqual(self.w.fires[b.id]['fuel_ticks'],350)

    def test_god_pause_speed_history_and_settings_resume_after_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'controls.sqlite';sim=Simulation(str(path))
            try:
                self.assertTrue(sim.command({'action':'god','operation':'pause','paused':True})['ok'])
                self.assertTrue(sim.command({'action':'god','operation':'speed','value':5})['ok'])
                self.assertEqual(sum(e['kind']=='god_intervention' for e in sim.world.events),2)
                sim.save()
            finally:sim.close()
            resumed=Simulation(str(path))
            try:self.assertTrue(resumed.paused);self.assertEqual(resumed.speed,5)
            finally:resumed.close()

    def test_optional_threats_are_off_by_default_capped_and_removable(self):
        from genesis.threats import update
        self.w.tick=180;update(self.w)
        self.assertFalse(self.w.threats)
        environment.intervene(self.w,{'operation':'threats','enabled':True})
        for tick in (180,360,540,720,900):self.w.tick=tick;update(self.w)
        self.assertTrue(self.w.threats)
        self.assertLessEqual(len(self.w.threats),3)
        restored=World.from_snapshot(copy.deepcopy(self.w.snapshot(True)))
        self.assertEqual(restored.threats,self.w.threats)
        environment.intervene(self.w,{'operation':'threats','enabled':False})
        update(self.w)
        self.assertFalse(self.w.threats)

    def test_defending_against_threat_costs_stamina_and_changes_real_hp(self):
        self.w.threats['test']={'id':'test','x':10,'y':10,'hp':35,'stamina':70,'species':'zombie','activity':'approach','created':0}
        old=self.a.stamina
        self.assertTrue(actions.execute(self.w,{'action':'repel','target':'test'},self.a.id)['ok'])
        self.assertEqual(self.a.stamina,old-8)
        self.assertLess(self.w.threats['test']['hp'],35)
        self.a.x=2
        self.assertFalse(actions.execute(self.w,{'action':'repel','target':'test'},self.a.id)['ok'])

    def test_fallback_gatherer_mines_stone_instead_of_waiting_forever(self):
        self.a.occupation='gatherer';self.a.x,self.a.y=9,12
        target=self.w.resources['a_r3'];before=target.quantity
        for r in self.w.resources.values():
            if r.id!=target.id:r.quantity=0
        for _ in range(4):self.w.tick+=1;self.w._routine(self.a)
        self.assertEqual(target.quantity,before-1)
        self.assertEqual(self.a.inventory['stone'],1)

    def test_farmer_retrieves_owned_shared_seed_and_replants_harvested_plot(self):
        self.w.buildings['farm']=Building('farm','farm','a',10,10,10,True)
        self.w.crops['farm']={'building':'farm','kind':'wheat','stage':'harvested','growth':100,'yield':6,'planted':0}
        self.a.occupation='farmer';self.a.inventory.update(seeds=0,water=5)
        before=self.w.settlements['a'].inventory['seeds']
        self.assertTrue(survival.autonomous(self.w,self.a))
        self.assertEqual(self.w.settlements['a'].inventory['seeds'],before-1)
        self.assertEqual(self.w.crops['farm']['stage'],'seedling')


    def test_full_pack_can_consume_at_store_without_recursive_transfer_failure(self):
        self.a.inventory.update(food=0,water=0,wood=120,seeds=0)
        self.a.hunger=90
        stock=self.w.settlements['a'].inventory['food']
        self.assertTrue(self.w._consume(self.a,'food','hunger'))
        self.assertEqual(self.a.hunger,52)
        self.assertEqual(self.w.settlements['a'].inventory['food'],stock-1)
        self.assertEqual(mass(self.a.inventory),120)


    def test_full_pack_can_drink_at_local_source_without_needing_carrying_space(self):
        source=self.w.resources['a_r1']
        self.a.x,self.a.y=source.x,source.y
        self.a.inventory.update(food=120,water=0,seeds=0)
        self.a.thirst=90
        before=source.quantity
        self.assertTrue(self.w._consume(self.a,'water','thirst'))
        self.assertEqual(self.a.thirst,52)
        self.assertEqual(source.quantity,before-1)
        self.assertEqual(mass(self.a.inventory),120)

    def test_fallback_producer_delivers_goods_before_accepting_more_work(self):
        self.a.occupation='craftsperson';self.a.inventory.update(planks=12,wood=3)
        self.w.tick=15
        self.assertFalse(production.autonomous(self.w,self.a))
        self.assertFalse(self.w.production_jobs)


    def test_mining_site_improves_work_rate_without_creating_ore(self):
        resource=self.w.resources['a_iron_ore_vein']
        self.a.x,self.a.y=resource.x-1,resource.y
        self.w.buildings['mine']=Building('mine','mine','a',resource.x,resource.y,18,True)
        before=resource.quantity
        for _ in range(3):
            self.w.tick+=1
            result=actions.execute(self.w,{'action':'mine','resource':resource.id},self.a.id,True)
        self.assertFalse(result['pending'])
        self.assertEqual(resource.quantity,before-1)
        self.assertEqual(self.a.inventory['iron_ore'],1)



if __name__=='__main__': unittest.main()
