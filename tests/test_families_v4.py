import copy
import json
from pathlib import Path
import tempfile
import unittest
from genesis import actions,families,genetics,persistence
from genesis.cognition import Scheduler
from genesis.providers import InferenceConfig
from genesis.validation import validate_world
from genesis.world import World


class FamilyTests(unittest.TestCase):
    def setUp(self):
        self.w=World(42,3);self.a=self.w.agents['a1'];self.b=self.w.agents['a2']
        self.a.x=self.b.x=9;self.a.y=self.b.y=10
        self.w.relate(self.a,self.b,.4);self.w.relate(self.b,self.a,.4)
        for _ in range(6):self.w.relate(self.a,self.b,0);self.w.relate(self.b,self.a,0)
        self.w.event('social','Two adults developed familiarity through interaction.',[self.a.id,self.b.id])

    def act(self,a,action,**fields):return actions.execute(self.w,{'action':action,**fields},a.id)

    def union(self):
        self.assertTrue(self.act(self.a,'propose_union',target=self.b.id)['ok'])
        self.assertTrue(self.act(self.b,'accept_union',target=self.a.id)['ok'])
        return self.w.households[self.a.household]

    def prepare_birth(self):
        h=self.union()
        self.w.demography['ticks_per_year']=100
        for a in self.w.agents.values():a.birth_tick=-int(a.age*100)
        self.a.inventory.update(food=22,water=22)
        for kind in ('food','water'):self.assertTrue(self.act(self.a,'household_transfer',kind=kind,amount=20)['ok'])
        for p,q in ((self.a,self.b),(self.b,self.a)):self.assertTrue(self.act(p,'family_plan',target=q.id,choice='raise_child')['ok'])
        families.update(self.w);return h

    def test_union_needs_actual_familiarity_mutual_consent_and_adults(self):
        before={a.id:dict(a.inventory) for a in self.w.agents.values()}
        self.assertFalse(self.act(self.b,'accept_union',target=self.a.id)['ok'])
        h=self.union();self.assertEqual(self.a.partner,self.b.id);self.assertEqual(self.b.partner,self.a.id)
        self.assertEqual(self.a.household,self.b.household)
        self.assertEqual(before,{a.id:a.inventory for a in self.w.agents.values()})
        self.assertEqual(sum(h['inventory'].values()),0)

    def test_decline_and_unfamiliar_proposals_do_not_pair_people(self):
        self.a.relationships[self.b.id]['familiarity']=0
        self.assertFalse(self.act(self.a,'propose_union',target=self.b.id)['ok'])
        self.a.relationships[self.b.id]['familiarity']=.5
        self.assertTrue(self.act(self.a,'propose_union',target=self.b.id)['ok'])
        self.assertTrue(self.act(self.b,'decline_union',target=self.a.id)['ok'])
        self.assertIsNone(self.a.partner);self.assertIsNone(self.b.partner)

    def test_household_stock_ownership_and_leaving_do_not_duplicate_resources(self):
        previous=self.b.household;self.b.inventory['wood']=10
        self.assertTrue(self.act(self.b,'household_transfer',kind='wood',amount=5)['ok'])
        h=self.union()
        self.assertEqual(h['inventory']['wood'],0)
        self.assertTrue(self.act(self.b,'household_transfer',household=previous,direction='withdraw',kind='wood',amount=2)['ok'])
        self.assertEqual(self.b.inventory['wood'],7)
        self.assertEqual(self.w.households[previous]['inventory']['wood'],3)
        self.assertFalse(self.act(self.a,'household_transfer',household=previous,direction='withdraw',kind='wood',amount=1)['ok'])
        self.assertTrue(self.act(self.a,'leave_union')['ok']);self.assertIsNone(self.b.partner)
        self.assertNotEqual(self.a.household,self.b.household);validate_world(self.w)

    def test_birth_requires_both_intentions_shelter_and_real_stock(self):
        h=self.union()
        self.act(self.a,'family_plan',target=self.b.id,choice='raise_child')
        families.update(self.w);self.assertNotIn('birth_due',h)
        self.act(self.b,'family_plan',target=self.a.id,choice='raise_child')
        families.update(self.w);self.assertNotIn('birth_due',h)
        h['inventory'].update(food=20,water=20)
        families.update(self.w);self.assertIn('birth_due',h)
        self.w.buildings[h['residence']].complete=False
        self.w.tick=h['birth_due'];families.update(self.w)
        self.assertFalse(self.a.children)

    def test_birth_parentage_costs_and_caregiving(self):
        h=self.prepare_birth();before=dict(h['inventory'])
        self.w.tick=h['birth_due'];families.update(self.w)
        child=self.w.agents[self.a.children[0]]
        self.assertEqual(child.parents,[self.a.id,self.b.id]);self.assertIn(child.id,self.b.children)
        self.assertEqual(child.age,0);self.assertEqual(child.life_stage,'infant')
        self.assertEqual(sum(child.inventory.values()),0)
        for kind in ('food','water'):self.assertEqual(h['inventory'][kind],before[kind]-2)
        child.hunger=60;child.thirst=60;stock=dict(h['inventory']);families.dependent(self.w,child)
        self.assertLess(child.hunger,60);self.assertEqual(h['inventory']['food'],stock['food']-1)
        self.assertEqual(h['inventory']['water'],stock['water']-1)
        self.assertFalse(self.act(child,'gather',resource='a_r0')['ok'])
        validate_world(self.w)

    def test_child_adulthood_learning_and_independent_cognition_eligibility(self):
        h=self.prepare_birth();self.w.tick=h['birth_due'];families.update(self.w)
        child=self.w.agents[self.a.children[0]]
        self.a.skills['gather']=2;self.a.knowledge.append({'claim':'The western field provides grain.','source':'observation','confidence':1,'tick':self.w.tick})
        self.a.plan=[{'action':'rest'}];self.a.plan_status='active'
        self.b.plan=[{'action':'rest'}];self.b.plan_status='active'
        self.w.step(1800)
        self.assertEqual(child.life_stage,'adult');self.assertTrue(families.adult(child))
        self.assertGreater(child.skills['gather'],.1)
        self.assertTrue(child.knowledge)
        self.assertEqual(child.occupation,'gatherer')
        r=self.w.resources['a_r0'];child.x,child.y=r.x,r.y;before=r.quantity
        child.stamina=100
        self.assertTrue(self.act(child,'gather',resource=r.id)['ok']);self.assertLess(r.quantity,before)
        scheduler=Scheduler(InferenceConfig(enabled=True),lambda *_:{'ok':False,'error':'fixture'})
        try:self.assertTrue(scheduler.request(self.w,child.id,'independent adult goal'))
        finally:scheduler.close()
        validate_world(self.w)

    def test_population_cap_blocks_birth_and_no_automatic_pairing_by_proximity(self):
        h=self.prepare_birth();self.w.demography['population_cap']=6
        self.w.tick=h['birth_due'];families.update(self.w)
        self.assertFalse(self.a.children)
        other=World(42,3);other.demography['offline_fallback']=True;families.fallback(other)
        self.assertTrue(all(not a.partner for a in other.agents.values()))

    def test_inheritance_is_seeded_stable_and_appearance_only(self):
        first=genetics.profile(1,'first');second=genetics.profile(2,'second')
        child=genetics.profile(42,'offspring',[first,second])
        self.assertEqual(child,genetics.profile(42,'offspring',[first,second]))
        self.assertNotEqual(child,genetics.profile(42,'other',[first,second]))
        genetics.validate(child)
        for trait in genetics.PALETTES:
            self.assertIn(child['alleles'][trait][0],first['alleles'][trait]);self.assertIn(child['alleles'][trait][1],second['alleles'][trait])
        self.assertTrue(0<=child['skin']<=1)
        self.assertNotIn('intelligence',child)

    def test_ancestry_cycles_and_underage_unions_rejected(self):
        self.b.age=15;self.b.life_stage='adolescent'
        self.assertFalse(self.act(self.a,'propose_union',target=self.b.id)['ok'])
        self.b.age=25;self.b.life_stage='adult'
        self.a.parents=[self.b.id,self.w.agents['b1'].id];self.b.children=[self.a.id]
        self.b.parents=[self.a.id,self.w.agents['b2'].id];self.a.children=[self.b.id]
        with self.assertRaises(ValueError):validate_world(self.w)

    def test_natural_death_keeps_genealogy_and_estate_without_runtime_cognition(self):
        self.union();self.a.inventory['wood']=7;identity=self.a.id;self.a.birth_tick=-80*10000
        families.update(self.w)
        self.assertNotIn(identity,self.w.agents);self.assertIn(identity,self.w.family_archive)
        self.assertEqual(self.w.estates[identity]['inventory']['wood'],7)
        self.assertIsNone(self.b.partner)
        self.assertTrue(self.act(self.b,'inherit',estate=identity,kind='wood',amount=3)['ok'])
        self.assertEqual(self.w.estates[identity]['inventory']['wood'],4)
        self.assertEqual(self.b.inventory['wood'],3)
        self.assertIsNotNone(families.tree(self.w,identity))
        validate_world(self.w)

    def test_birth_save_load_and_second_generation_family_tree(self):
        h=self.prepare_birth();self.w.tick=h['birth_due'];families.update(self.w)
        child=self.w.agents[self.a.children[0]]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'family.sqlite';persistence.save(self.w,path);loaded=persistence.load(path)
            self.assertEqual(self.w.snapshot(True),loaded.snapshot(True));self.assertEqual(child.appearance,loaded.agents[child.id].appearance)
            self.w.step(30);loaded.step(30);self.assertEqual(self.w.snapshot(True),loaded.snapshot(True))
        tree=families.tree(self.w,child.id);self.assertEqual(len(tree['parents']),2)
        self.assertEqual(tree['parents'][0]['children'],[child.id])

    def test_older_saves_get_households_without_new_resources(self):
        data=copy.deepcopy(self.w.snapshot(True))
        for key in ('demography','households','family_archive','family_offers','estates','next_person'):data.pop(key)
        for person in data['agents'].values():
            for field in ('birth_tick','life_stage','household','residence','parents','children','partner','appearance','family_history','family_intent'):person.pop(field)
        loaded=World.from_snapshot(json.loads(json.dumps(data)))
        self.assertEqual(sum(sum(h['inventory'].values()) for h in loaded.households.values()),0)
        validate_world(loaded)

    def test_grandchild_links_and_inheritance_span_three_generations(self):
        h=self.prepare_birth();self.w.tick=h['birth_due'];families.update(self.w)
        child=self.w.agents[self.a.children[0]]
        self.w.tick=child.birth_tick+1800;families.update(self.w)
        partner=self.w.agents['a0'];child.x,child.y=9,10;partner.x,partner.y=9,10
        self.assertTrue(self.act(child,'create_household')['ok'])
        for _ in range(6):self.w.relate(child,partner,.1);self.w.relate(partner,child,.1)
        self.assertTrue(self.act(child,'propose_union',target=partner.id)['ok'])
        self.assertTrue(self.act(partner,'accept_union',target=child.id)['ok'])
        for kind in ('food','water'):
            self.assertTrue(self.act(child,'retrieve',kind=kind,amount=20)['ok'])
            self.assertTrue(self.act(child,'household_transfer',kind=kind,amount=20)['ok'])
        self.act(child,'family_plan',target=partner.id,choice='raise_child');self.act(partner,'family_plan',target=child.id,choice='raise_child')
        families.update(self.w);new_home=self.w.households[child.household]
        self.w.tick=new_home['birth_due'];families.update(self.w)
        grandchild=self.w.agents[child.children[0]]
        self.assertIn(self.a.id,families.ancestors(self.w,grandchild.id))
        self.assertEqual(families.tree(self.w,grandchild.id)['parents'][0]['id'],child.id)
        loaded=World.from_snapshot(copy.deepcopy(self.w.snapshot(True)))
        self.assertEqual(grandchild.appearance,loaded.agents[grandchild.id].appearance)
        validate_world(loaded)
