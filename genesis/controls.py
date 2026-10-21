"""Explicit experimental ablations; normal worlds retain all existing mechanics."""
DEFAULTS={'communication':True,'memory':True,'shared_knowledge':False,'cooperation':True,'planning':True,'audit':False}
COMMUNICATION={'talk','share','claim','teach','report_threat','warn','propose_union','accept_union','decline_union','family_plan'}
COOPERATION={'trade','offer','accept','help','commit_work','shipment','teach'}


def initialize(world):
    if not hasattr(world,'controls'):world.controls=dict(DEFAULTS)
    if not hasattr(world,'shared_reports'):world.shared_reports=[]
    for key,value in DEFAULTS.items():world.controls.setdefault(key,value)
    for agent in world.agents.values():agent.memory_enabled=world.controls['memory']


def validate(settings):
    if not isinstance(settings,dict) or set(settings)!=set(DEFAULTS) or any(type(v) is not bool for v in settings.values()):raise ValueError('Experimental controls require known boolean fields')


def permitted(world,action):
    return ((world.controls['communication'] or action not in COMMUNICATION)
            and (world.controls['cooperation'] or action not in COOPERATION))


def shared(world):
    if not world.controls['shared_knowledge'] or not world.controls['memory']:return

    reports={(r['claim'],r['source']):dict(r) for r in world.shared_reports}
    for agent in world.agents.values():
        for report in agent.knowledge:
            key=(report['claim'],report['source'])
            if key not in reports or report['tick']>reports[key]['tick']:reports[key]=dict(report)
    world.shared_reports=sorted(reports.values(),key=lambda r:(r['tick'],r['claim'],r['source']))[-80:]
    for agent in world.agents.values():
        known={(r['claim'],r['source']) for r in agent.knowledge}
        for report in world.shared_reports:
            if (report['claim'],report['source']) not in known:
                agent.knowledge.append({**report,'status':'shared_experimental_pool'})
        agent.knowledge[:]=agent.knowledge[-80:]
