"""LLM-first authority boundary: model chooses, engine enforces."""
import time
import unittest

from genesis.world import World
from genesis.cognition import Scheduler
from genesis.providers import InferenceConfig
from genesis.planning import execute_plan


class ModelAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.world = World(42, 4, 48, 30)
        self.agent = self.world.agents['a1']
        self.agent.x, self.agent.y = 10, 10
        self.agent.hunger = 5
        self.agent.thirst = 5
        self.agent.fatigue = 0
        self.agent.stamina = 100
        self.agent.hp = 100
        self.agent.social = 10
        self.agent.occupation = 'guard'
        self.agent.plan_status = 'idle'

    def test_enabled_llm_waits_instead_of_rule_based_patrol(self):
        self.world.cognition_config = {'enabled':True}
        pos = (self.agent.x,self.agent.y)
        self.world._routine(self.agent)
        self.assertEqual(pos,(self.agent.x,self.agent.y))
        self.assertEqual(self.agent.activity,'consider')
        self.assertIn('Awaiting LLM',self.agent.reason)
        self.assertEqual(self.agent.plan_status,'idle')

    def test_unchanged_offline_fallback_remains_available(self):
        self.world.cognition_config = {'enabled':False}
        self.world._routine(self.agent)
        self.assertNotEqual(self.agent.activity,'consider')
        self.assertEqual(self.agent.activity,'patrol')

    def test_model_plan_controls_actual_action(self):
        self.world.cognition_config = {'enabled':True}
        calls=[]
        def fake(config, system, data):
            calls.append(data['agent']['identity']['id'])
            return {'ok':True,'data':{'goal':'I choose to observe instead of patrolling',
                     'plan':[{'action':'observe'}],
                     'speech':''}}
        s=Scheduler(InferenceConfig(enabled=True),fake)
        try:
            self.assertTrue(s.request(self.world,self.agent.id))
            end=time.monotonic()+3
            while self.agent.reasoning_count==0 and time.monotonic()<end:
                s.pump(self.world,schedule=False)
                time.sleep(.005)
            self.assertEqual(calls,[self.agent.id])
            self.assertEqual(self.agent.reasoning_count,1,s.status())
            self.assertEqual(self.agent.plan_status,'active')
            self.assertTrue(execute_plan(self.world,self.agent))
            self.assertEqual(self.agent.plan_status,'completed')
            self.assertEqual(self.agent.goals[-1]['source'],'llm')
        finally:
            s.close()

    def test_stale_tick_does_not_force_snapshot_requeue_each_step(self):
        self.world.cognition_config={'enabled':True}
        seen=[]
        def fake(config, system, data):
            seen.append(data['agent']['identity']['id'])
            return {'ok':True,'data':{'goal':'Survey the environment','plan':[{'action':'observe'}]}}
        s=Scheduler(InferenceConfig(enabled=True),fake)
        try:
            self.assertTrue(s.request(self.world,self.agent.id))
            self.world.tick+=1
            deadline=time.monotonic()+3
            while self.agent.reasoning_count==0 and time.monotonic()<deadline:
                s.pump(self.world,schedule=False)
                time.sleep(.005)
            self.assertEqual(self.agent.reasoning_count,1,s.status())
            self.assertEqual(seen,[self.agent.id])
        finally:
            s.close()


if __name__=='__main__':
    unittest.main()
