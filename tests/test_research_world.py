import copy
import unittest
from genesis.world import World
from genesis.terrain import cell,chunk
from genesis.navigation import route
from genesis.validation import validate_world


class ResearchWorldTests(unittest.TestCase):
    def test_chunk_order_and_coordinates_are_reproducible(self):
        for cx,cy in ((0,0),(3,1),(7,7)):
            generated=chunk(41,cx,cy,128,128)
            self.assertEqual(generated[5][3],cell(41,cx*16+3,cy*16+5,128,128))
            self.assertEqual(generated,chunk(41,cx,cy,128,128))
        self.assertNotEqual(chunk(41,0,0,128,128),chunk(42,0,0,128,128))

    def test_large_world_survival_and_exact_reload(self):
        w=World(42,3,256,256)
        self.assertEqual(w.worldgen['mode'],'coherent')
        self.assertGreater(len(w.resources),256)
        w.step(60);validate_world(w)
        loaded=World.from_snapshot(copy.deepcopy(w.snapshot(True)))
        w.step(10);loaded.step(10)
        self.assertEqual(w.snapshot(True),loaded.snapshot(True))
        self.assertGreater(w.navigation['searches'],0)

    def test_navigation_obeys_closed_barriers_and_returns_cardinal_path(self):
        from genesis.models import Building
        w=World(42,1,128,128);w.terrain=[['plains']*128 for _ in range(128)]
        w.buildings['block']=Building('block','wall','a',11,10,8,True);w._blocked_tick=-1
        path=route(w,(10,10),(15,10));previous=(10,10)
        self.assertNotIn((11,10),path)
        for point in path:
            self.assertEqual(abs(point[0]-previous[0])+abs(point[1]-previous[1]),1);previous=point
        self.assertEqual(path[-1],(15,10))
        self.assertLess(w.navigation['expanded'],128*128)

    def test_river_bed_flows_downhill_and_geography_supplies_resources(self):
        w=World(11,1,128,128)
        river=[w.elevation[y][x] for y in range(128) for x in range(128) if w.terrain[y][x]=='river']
        self.assertGreater(len(river),100)
        self.assertGreater(river[0],river[-1])
        for r in w.resources.values():
            if r.id.startswith('geo_') and r.kind=='wood':self.assertEqual(w.terrain[r.y][r.x],'forest')

    def test_legacy_save_defaults_and_world_size_bounds(self):
        data=copy.deepcopy(World().snapshot(True));data.pop('worldgen');data.pop('navigation')
        self.assertEqual(World.from_snapshot(data).worldgen['mode'],'legacy')
        with self.assertRaises(ValueError):World(width=1024,height=1024)
