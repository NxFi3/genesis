"""Exact cardinal A*: deterministic tie-breaking, no renderer dependency."""
import heapq
import itertools


def route(world,start,goal):
    serial=itertools.count();initial=abs(start[0]-goal[0])+abs(start[1]-goal[1])
    frontier=[(initial,initial,next(serial),start)]
    cost={start:0};previous={start:None};expanded=0
    while frontier:
        estimate,heuristic,_,point=heapq.heappop(frontier)
        if estimate!=cost[point]+heuristic:continue
        expanded+=1
        if point==goal:break
        for neighbor in world.neighbors(*point):
            candidate=cost[point]+1
            if candidate<cost.get(neighbor,float('inf')):
                cost[neighbor]=candidate;previous[neighbor]=point
                heuristic=abs(neighbor[0]-goal[0])+abs(neighbor[1]-goal[1])
                # Prefer progress toward the destination among equally optimal paths.
                # FIFO ties can expand an entire large rectangle before following it.
                heapq.heappush(frontier,(candidate+heuristic,heuristic,next(serial),neighbor))
    world.navigation['searches']+=1;world.navigation['expanded']+=expanded
    world.navigation['max_expanded']=max(world.navigation['max_expanded'],expanded)
    if goal not in previous:return None
    path=[];point=goal
    while point!=start:path.append(point);point=previous[point]
    return list(reversed(path))
