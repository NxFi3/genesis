"""Regression tests for model-authored free-form modular construction."""
import copy
import unittest

from genesis import architecture
from genesis.actions import execute
from genesis.planning import validate_plan
from genesis.validation import validate_world
from genesis.world import World


class EmergentArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.world = World(42, 6, 48, 30)
        self.actor = self.world.agents['player']
        self.actor.x, self.actor.y = 19, 15
        self.actor.inventory.update(stone=20, wood=20, bricks=20, planks=20)
        self.anchor = (18, 16)

    def design(self, layout='0,0,0,stone;1,0,0,door;2,0,0,wood;0,0,1,bricks;1,0,1,planks',
               title='An original fortification'):
        return execute(self.world, {
            'action': 'design_structure', 'title': title,
            'purpose': 'A shape freely selected by its author',
            'x': self.anchor[0], 'y': self.anchor[1], 'layout': layout,
        }, self.actor.id)

    def test_planning_accepts_freeform_layout_as_one_validated_action(self):
        proposal = validate_plan({'goal':'Make a shelter I choose', 'plan':[{
            'action':'design_structure', 'title':'My place', 'purpose':'private space',
            'x':18,'y':16, 'layout':'0,0,0,stone;1,0,0,door'
        },{'action':'work_structure'}]})
        self.assertEqual(len(proposal['plan']),2)
        self.assertIn('design_structure', proposal['plan'][0]['action'])

    def test_design_is_not_free_construction_and_makes_one_persistent_job(self):
        old_stock = dict(self.actor.inventory)
        proposal = self.design()
        self.assertTrue(proposal['ok'],proposal)
        self.assertEqual(self.world.blocks,{})
        self.assertEqual(self.actor.inventory,old_stock)
        job = self.world.architecture_projects[proposal['project']]
        self.assertEqual(job['state'],'active')
        self.assertEqual(len(job['parts']),5)
        validate_world(self.world)

    def test_physical_build_consumes_real_materials_and_updates_collision(self):
        project = self.design()
        self.assertTrue(project['ok'],project)
        original = dict(self.actor.inventory)
        for tick in range(5):
            self.world.tick += 1
            result = execute(self.world,{'action':'work_structure','project':project['project']},self.actor.id)
            self.assertTrue(result['ok'],result)
        built = self.world.architecture_projects[project['project']]
        self.assertEqual(built['state'],'completed')
        self.assertEqual(built['progress'],5)
        self.assertEqual(len(self.world.blocks),5)
        self.assertEqual(self.actor.inventory['stone'],original['stone']-1)
        self.assertEqual(self.actor.inventory['wood'],original['wood']-2)
        self.assertEqual(self.actor.inventory['planks'],original['planks']-2)
        self.assertEqual(self.actor.inventory['bricks'],original['bricks']-1)
        self.assertFalse(self.world.passable(18,16))
        self.assertTrue(self.world.passable(19,16))
        self.assertIn(self.actor.id,built['workers'])
        validate_world(self.world)

    def test_modular_door_changes_real_navigation(self):
        job=self.design('0,0,0,door')
        self.assertTrue(job['ok'],job)
        self.world.tick+=1
        self.assertTrue(execute(self.world,{'action':'work_structure','project':job['project']})['ok'])
        self.assertTrue(self.world.passable(18,16))
        closed=execute(self.world,{'action':'toggle_modular_door','x':18,'y':16,'z':0,'open':False})
        self.assertTrue(closed['ok'],closed)
        self.assertFalse(self.world.passable(18,16))
        opened=execute(self.world,{'action':'toggle_modular_door','x':18,'y':16,'z':0,'open':True})
        self.assertTrue(opened['ok'],opened)
        self.assertTrue(self.world.passable(18,16))
        validate_world(self.world)

    def test_model_authored_design_is_applied_by_engine_not_hardcoded_castle_logic(self):
        import time
        from genesis.cognition import Scheduler
        from genesis.providers import InferenceConfig
        from genesis.planning import execute_plan
        designer=self.world.agents['a2']
        designer.x, designer.y = 19, 15
        builder=self.world.agents['a1']
        builder.x, builder.y = 19, 15
        builder.inventory.update(stone=4,wood=4)
        seen=[]
        def fake_model(_config, _system, private_context):
            seen.append(private_context['agent']['identity']['id'])
            return {'ok':True, 'data':{
                'goal':'I want to create an original courtyard',
                'plan':[{'action':'design_structure','title':'Stone-corner courtyard',
                         'purpose':'My own invented geometry',
                         'x':18,'y':16,'layout':'0,0,0,stone;2,0,0,wood'}]}}
        scheduler=Scheduler(InferenceConfig(enabled=True),fake_model)
        try:
            self.assertTrue(scheduler.request(self.world,designer.id,'create something',1))
            deadline=time.monotonic()+3
            while designer.plan_status!='active' and time.monotonic()<deadline:
                scheduler.pump(self.world,schedule=False)
                time.sleep(.005)
            self.assertEqual(designer.plan_status,'active',scheduler.status())
            self.assertEqual(seen,[designer.id])
            self.assertTrue(execute_plan(self.world,designer))
            self.assertEqual(len(self.world.architecture_projects),1)
            project=next(iter(self.world.architecture_projects.values()))
            self.assertEqual(project['author'],designer.id)
            self.assertEqual(len(self.world.blocks),0)
            self.world.tick+=1
            self.assertTrue(architecture.autonomous(self.world,builder))
            self.world.tick+=1
            self.assertTrue(architecture.autonomous(self.world,builder))
            self.assertEqual(project['state'],'completed')
            self.assertEqual(len(self.world.blocks),2)
            self.assertIn(builder.id,project['workers'])
            validate_world(self.world)
        finally:
            scheduler.close()

    def test_missing_supplies_cannot_materialize_blocks(self):
        self.actor.inventory['stone']=0
        self.world.settlements['a'].inventory['stone']=0
        proposal=self.design('0,0,0,stone')
        self.assertTrue(proposal['ok'],proposal)
        result=execute(self.world,{'action':'work_structure','project':proposal['project']})
        self.assertFalse(result['ok'])
        self.assertEqual(len(self.world.blocks),0)
        self.assertEqual(self.world.architecture_projects[proposal['project']]['progress'],0)

    def test_malformed_and_floating_designs_are_rejected_without_mutation(self):
        for layout in ('0,0,2,wood','0,0,0,diamond','0,0,0,wood;0,0,0,wood',
                       '0,0,0,stone;1,1,3,wood','0,0,0,stone;0,0,9,wood'):
            self.assertFalse(self.design(layout)['ok'],layout)
        self.assertEqual(len(self.world.architecture_projects),0)
        self.assertEqual(self.world.blocks,{})

    def test_people_cannot_be_encased_or_resources_duplicated(self):
        self.assertFalse(execute(self.world,{
            'action':'place_block','x':19,'y':15,'z':0,'kind':'stone'
        })['ok'])
        original=self.actor.inventory['stone']
        self.assertTrue(execute(self.world,{
            'action':'place_block','x':18,'y':16,'z':0,'kind':'stone'
        })['ok'])
        self.assertEqual(self.actor.inventory['stone'],original-1)
        self.assertTrue(execute(self.world,{
            'action':'remove_block','x':18,'y':16,'z':0
        })['ok'])
        self.assertEqual(self.actor.inventory['stone'],original-1)
        self.assertEqual(self.world.blocks,{})
        validate_world(self.world)

    def test_shared_worker_and_exact_snapshot_round_trip(self):
        proposal=self.design('0,0,0,stone;1,0,0,stone')
        self.assertTrue(proposal['ok'],proposal)
        other=self.world.agents['a1']
        other.x,other.y=19,15
        other.inventory['stone']=2
        self.world.tick+=1
        first=execute(self.world,{'action':'work_structure','project':proposal['project']},other.id,planned=True)
        self.assertTrue(first['ok'],first)
        self.assertEqual(self.world.architecture_projects[proposal['project']]['progress'],1)
        saved=copy.deepcopy(self.world.snapshot(True))
        restored=World.from_snapshot(saved)
        self.assertEqual(saved,restored.snapshot(True))
        restored.tick+=1
        second=execute(restored,{'action':'work_structure','project':proposal['project']},other.id,planned=True)
        self.assertTrue(second['ok'],second)
        self.assertEqual(restored.architecture_projects[proposal['project']]['state'],'completed')
        validate_world(restored)

    def test_rejects_unknown_project_and_invalid_direct_material(self):
        self.assertFalse(execute(self.world,{'action':'work_structure','project':'imaginary'})['ok'])
        self.assertFalse(execute(self.world,{'action':'place_block','x':18,'y':16,'z':0,'kind':'laser'})['ok'])
        self.assertFalse(execute(self.world,{'action':'place_block','x':18.5,'y':16,'z':0,'kind':'stone'})['ok'])
        self.assertEqual(self.world.blocks,{})

    def test_cancel_keeps_paid_blocks_but_stops_remaining_jobs(self):
        proposal=self.design('0,0,0,stone;1,0,0,wood')
        self.assertTrue(proposal['ok'],proposal)
        self.world.tick+=1
        self.assertTrue(execute(self.world,{'action':'work_structure','project':proposal['project']})['ok'])
        cancel=execute(self.world,{'action':'cancel_structure','project':proposal['project']})
        self.assertTrue(cancel['ok'],cancel)
        self.assertEqual(self.world.architecture_projects[proposal['project']]['state'],'cancelled')
        self.assertEqual(len(self.world.blocks),1)
        self.assertFalse(execute(self.world,{'action':'work_structure','project':proposal['project']})['ok'])
        validate_world(self.world)


if __name__ == '__main__':
    unittest.main()
