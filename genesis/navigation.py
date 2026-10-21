"""Exact cardinal A*: deterministic tie-breaking, no renderer dependency."""
import heapq
import itertools


def route(world,start,goal):
    serial=itertools.count();frontier=[(0,next(serial),start)]
    cost={start:0};previous={start:None};expanded=0
    while frontier:
        _,_,point=heapq.heappop(frontier)
        expanded+=1
        if point==goal:break
        for neighbor in world.neighbors(*point):
            candidate=cost[point]+1
            if candidate<cost.get(neighbor,float('inf')):
                cost[neighbor]=candidate;previous[neighbor]=point
                estimate=candidate+abs(neighbor[0]-goal[0])+abs(neighbor[1]-goal[1])
                heapq.heappush(frontier,(estimate,next(serial),neighbor))
    world.navigation['searches']+=1;world.navigation['expanded']+=expanded
    world.navigation['max_expanded']=max(world.navigation['max_expanded'],expanded)
    if goal not in previous:return None
    path=[];point=goal
    while point!=start:path.append(point);point=previous[point]
    return list(reversed(path))
