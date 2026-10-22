"""Priority-scheduled, budgeted shared inference with per-agent private contexts.

Only pump(), called under Simulation.lock, may mutate the world. Worker threads
operate on detached JSON and return proposals; every resulting action is validated.
"""
from concurrent.futures import Future
import threading
from dataclasses import dataclass, field
import heapq
import itertools
import json
import time

from . import combat
from .memory import context, remember
from .planning import SCHEMAS, validate_plan, adopt_plan
from .providers import InferenceConfig, generate
from .registry import PRODUCTION
from .social import hear, upkeep
from .communication import opportunities, dialogue_context
from .families import adult

SYSTEM = (
    'You are ONE independent human inhabitant in the fictional medieval world GENESIS. '
    'Use only your supplied private knowledge and local perceptions; other agents may disagree. '
    'Form your own practical goals. You may refuse the player. Never claim resources or actions changed before engine confirmation. '
    'YOU choose routine work, movement, socializing, resource gathering and architecture; without your valid plan an adult waits, instead of scripted village chores. '
    'If you have no active plan, propose one useful achievable action grounded in nearby observations, or explicitly reflect why waiting is preferable. '
    'You may initiate a genuine, purposeful conversation with any visible nearby adult using conversation:{target,topic,message}. '
    'You are not required to speak, build or work when it does not serve your own goals. '
    'Choose actions ONLY from the provided schemas, using exact known entity IDs. Gather needs reach; move first. '
    'Plan up to 16 steps with flat arguments. No direct world edits, damage values, or invented capabilities. '
    'You can invent original structures without a pre-scripted castle: choose a design goal and a layout. '
    'design_structure uses integer x,y, title, purpose and layout="dx,dy,z,material;..."; '
    'materials stone/wood/bricks/planks/door/stairs, layers z=0..5, up to 96 parts. '
    'work_structure completes an approved design one resource-paid part at a time; nearby builders may help. '
    'Choose location and shape from local evidence, respect physical limits, and never claim unbuilt work is finished. '
    'When speaking, use natural language grounded in your own personality, memories and circumstances. '
    'To initiate conversation now, optionally return conversation:{target,topic,message}; choose a supplied opportunity or your own grounded reason. Never invent speech for others. '
    'For a reply use speech: concise, specific, in your own voice. Address the latest message and avoid repeated greetings. Reports remain uncertain. '
    'Only explicit recipient accept fulfills an offer. Optional dialogue_actions (up to 2: offer/accept/reject/help/teach/share/commit_work/conflict_response) act with this partner through engine validation. Check outcomes on your next turn; promising is not doing. Do not automatically obey or believe rumors. '
    'Keep useful ongoing plans during conversation. plan_policy defaults to keep; append adds steps; replace requires a concrete revision_reason explaining changed needs, evidence or failure. Never restart completed steps. Empty plan preserves current work. '
    'Threat reports have sources and timestamps, not live tracking. Choose your own threat_response, warning, cooperation or defensive construction when warranted; zombies cannot negotiate, but human disagreements can. Do not invent sightings. Use report_threat with a nearby partner to communicate a specific known sighting. '
    'Return a JSON object: {"goal":"free-form personal goal", "plan":[{"action":"observe"}], '
    '"speech":"optional reply", "stance":"agree|question|disagree|neutral", '
    '"reflection":"brief lesson or reconsideration", "end_conversation":false}.'
)


class InferenceWorkers:
    """Scheduler bounds active work; daemon threads cannot strand process shutdown.

    Running network calls are logically cancelled by epoch and retain their HTTP
    timeout. They hold detached data only, never simulation objects or DB handles.
    """
    def submit(self, function, *arguments):
        future = Future()
        def invoke():
            if future.set_running_or_notify_cancel():
                try:
                    future.set_result(function(*arguments))
                except BaseException as exc:
                    future.set_exception(exc)
        threading.Thread(target=invoke, name='genesis-inference', daemon=True).start()
        return future

    def shutdown(self, **_):
        pass


def fit_context(payload, limit):
    """Bound the complete serialized user message, preserving valid JSON and IDs."""
    data = json.loads(json.dumps(payload))
    def size():
        return len(SYSTEM)+len(json.dumps(data, ensure_ascii=False))
    turns = data.get('conversation', {}).get('turns', [])
    while len(turns) > 2 and size() > limit:
        turns.pop(0)
    if size() > limit:
        for turn in turns:
            turn['text'] = turn['text'][-600:]
        data['pending_offers'] = data.get('pending_offers', [])[-2:]
    if size() > limit:
        agent = data['agent']
        for key in ('memories', 'knowledge', 'long_term_goals', 'commitments', 'plan', 'semantic_memory', 'projects'):
            if key in agent:
                agent[key] = agent[key][-2:]
        agent['reflection'] = agent.get('reflection', '')[-300:]
        if 'perception' in agent:
            agent['perception']['resources'] = agent['perception'].get('resources', [])[-3:]
            agent['perception']['nearby_agents'] = agent['perception'].get('nearby_agents', [])[:3]
    if size() > limit:
        data.pop('capabilities', None)
        original = data['agent']
        data['agent'] = {key: original[key] for key in ('identity', 'needs', 'inventory', 'location', 'failure','family') if key in original}
        if 'perception' in original:
            data['agent']['perception']={key:original['perception'][key] for key in ('tick','climate') if key in original['perception']}
        reports = original.get('perception',{}).get('threat_reports',[])[-2:]
        if reports: data['agent']['threat_reports'] = reports
        data['pending_offers'] = data.get('pending_offers', [])[-1:]
        data['social_opportunities'] = data.get('social_opportunities', [])[:1]
        if 'conversation' in data:
            data['conversation'].pop('instruction', None)
            partner = data['conversation'].get('partner', {})
            partner.pop('your_reports_from_them', None)
        for turn in turns:
            turn['text'] = turn['text'][-300:]
    if size() > limit:
        # A small context exposes a useful subset of schemas instead of losing the reply.
        keep = ('move', 'observe', 'eat', 'drink', 'rest', 'talk', 'offer', 'accept', 'reject', 'help', 'conflict_response', 'threat_response', 'warn', 'report_threat','propose_union','accept_union','decline_union','family_plan','household_transfer')
        data['action_schemas'] = {k: v for k, v in data.get('action_schemas', {}).items() if k in keep}
        if 'conversation' in data:
            data['conversation']['outcomes'] = data['conversation'].get('outcomes', [])[-2:]
    if size() > limit:
        # The last dialogue turn is more valuable than old turns, large family
        # profiles or optional action lists in a strict 6k-character budget.
        data.pop('social_opportunities', None)
        data.pop('pending_offers', None)
        if 'conversation' in data:
            conversation = data['conversation']
            conversation['turns'] = conversation.get('turns', [])[-1:]
            conversation.pop('instruction', None)
            conversation.pop('outcomes', None)
            partner = conversation.get('partner')
            if isinstance(partner, dict):
                conversation['partner'] = {k: partner[k] for k in ('id','name') if k in partner}
        data['agent'].pop('family', None)
        data['action_schemas'] = {k:v for k,v in data.get('action_schemas',{}).items()
                                  if k in ('observe','talk','offer','accept','reject','help','move')}
    if size() > limit:
        # Preserve agent identity, physiological state and the latest actual
        # message rather than rejecting all conversation at low budgets.
        original = data['agent']
        identity = original.get('identity',{})
        data['agent'] = {'identity':{k:identity[k] for k in ('id','name') if k in identity},
                         'needs':original.get('needs',{}), 'failure':original.get('failure','')}
        if 'conversation' in data:
            data['conversation']['turns'] = data['conversation'].get('turns',[])[-1:]
    if size() > limit:
        raise ValueError('Cannot fit the minimal private context within configured budget')
    return data


@dataclass(order=True)
class Request:
    priority: int
    sequence: int
    agent: str = field(compare=False)
    kind: str = field(compare=False)
    epoch: int = field(compare=False)
    revision: int = field(compare=False)
    tick: int = field(compare=False)
    context: dict = field(compare=False)
    conversation: str | None = field(default=None, compare=False)


class Scheduler:
    def __init__(self, config=None, provider=None):
        self.config = (config or InferenceConfig()).validate()
        self.provider = provider or generate
        self.executor = InferenceWorkers()
        self.queue = []
        self.inflight = {}
        self.serial = itertools.count(1)
        self.epoch = 0
        self.closed = False
        self.window = -1
        self.budgets = {}
        self.global_used = 0
        self.started = time.monotonic()
        self.metrics = {'completed': 0, 'failed': 0, 'stale': 0, 'submitted': 0,
                        'latency_ms': 0., 'last_error': '', 'budget_deferred': 0,
                        'input_tokens':0,'output_tokens':0,'usage_available':False}
        self.events_seen = {}

    def status(self):
        states = {job.agent: 'queued' for job in self.queue if job.epoch == self.epoch}
        states.update({job.agent: 'thinking' for job, _ in self.inflight.values() if job.epoch == self.epoch})
        return {'agents': states, 'mode': 'llm' if self.config.enabled else 'offline', 'config': self.config.public(),
                'metrics': {**self.metrics, 'queued': len(self.queue), 'inflight': len(self.inflight),
                            'throughput_per_minute': round(self.metrics['completed']*60/max(1, time.monotonic()-self.started), 3),
                            'global_budget_used': self.global_used}}

    def invalidate(self):
        self.epoch += 1
        self.queue.clear()
        self.events_seen.clear()
        self.budgets.clear()
        self.global_used = 0
        self.window = -1
        for future in self.inflight:
            future.cancel()  # Running HTTP calls finish within their configured timeout.

    def configure(self, changes):
        if not isinstance(changes, dict):
            raise ValueError('Cognition config must be an object')
        if set(changes)-set(self.config.public()):
            raise ValueError('Unknown cognition setting')
        candidate = InferenceConfig(**{**self.config.public(), **changes}).validate()
        self.invalidate()
        self.config = candidate

    def close(self):
        self.closed = True
        self.invalidate()
        self.executor.shutdown(wait=False, cancel_futures=True)

    def _busy(self, aid):
        return any(job.agent == aid and job.epoch == self.epoch for job in self.queue) or any(job.agent == aid and job.epoch == self.epoch for job, _ in self.inflight.values())

    def request(self, world, aid, reason='new goal', priority=5, conversation=None):
        agent = world.agents.get(aid)
        if not self.config.enabled or self.closed or not agent or not adult(agent) or agent.player or agent.incapacitated or self._busy(aid) or len(self.queue) >= self.config.max_queue:
            return False
        # Schema/system and recent conversation also consume the total context budget.
        allowance = max(1600, self.config.context_limit-len(SYSTEM)-len(json.dumps(SCHEMAS))-3000)
        c = world.conversations.get(conversation) if conversation else None
        partner_id = next((x for x in c['participants'] if x != aid), None) if c else None
        query = reason+' '+(' '.join(t['text'] for t in c['turns'][-2:]) if c else '')
        private = context(world, agent, query, allowance, partner_id=partner_id)
        from .world import BUILDINGS, RECIPES
        from .technology import TECHNOLOGIES
        data = {'reason': reason, 'agent': private, 'action_schemas': SCHEMAS,
                'capabilities': {'building_costs': {kind: {k: v for k, v in recipe.items() if k in agent.inventory or k == 'duration'} for kind, recipe in BUILDINGS.items()}, 'recipes': RECIPES, 'practical_methods': TECHNOLOGIES, 'production_recipes':PRODUCTION},
                'pending_offers': [x for x in world.agreements.values() if x['state'] == 'proposed' and aid in (x['proposer'], x['recipient'])][-6:]}
        if c:
            data['conversation'] = dialogue_context(world, agent, c)
        else:
            data['social_opportunities'] = opportunities(world, agent)
        heapq.heappush(self.queue, Request(priority, next(self.serial), aid,
                                         'conversation' if conversation else 'plan', self.epoch,
                                         agent.cognition_revision, world.tick, fit_context(data, self.config.context_limit), conversation))
        return True

    def speak(self, world, speaker_id, target_id, message, source='player', topic='conversation'):
        if not world.controls['communication']:raise ValueError('Communication is disabled by the experimental condition')
        speaker, target = world.agents.get(speaker_id), world.agents.get(target_id)
        if not speaker or not target or speaker_id == target_id or not isinstance(message, str) or not message.strip():
            raise ValueError('A conversation needs two distinct participants and a nonempty message')
        if not adult(speaker) or not adult(target):raise ValueError('Dependent children are learning; independent model dialogue begins at adulthood')
        if any(c['state'] == 'active' and set(c['participants']) & {speaker_id, target_id} for c in world.conversations.values()):
            raise ValueError('A participant is already speaking; wait for the current reply')
        if combat.distance(speaker, target) > 3 or speaker.incapacitated or target.incapacitated:
            raise ValueError('Speakers must be conscious and within three tiles')
        if not self.config.enabled:
            raise ValueError('LLM mode is disabled; enable it in settings or with --ollama')
        if not target.player and self.window == world.tick//self.config.budget_window and (self.global_used >= self.config.global_budget or self.budgets.get(target_id, 0) >= self.config.per_agent_budget):
            raise ValueError('Reasoning budget exhausted; advance the simulation to a new budget window or raise the budget in settings')
        existing = next((c for c in reversed(list(world.conversations.values())) if set(c['participants']) == {speaker_id, target_id} and c['state'] == 'waiting_player'), None)
        if existing:
            c = existing
        else:
            active = sum(c['state'] in ('active', 'queued') for c in world.conversations.values())
            if active >= 16:
                raise ValueError('Conversation capacity reached; let current conversations finish')
            cid = f'd{world.next_event}'
            c = {'id': cid, 'participants': [speaker_id, target_id], 'turns': [], 'state': 'active',
                 'created': world.tick, 'updated': world.tick, 'next_speaker': target_id,
                 'topic': str(topic)[:100], 'outcomes': [], 'assessed': []}
            world.conversations[cid] = c
        # A queued turn must not be overwritten by another player POST.
        if existing and c.get('next_speaker') and self._busy(target_id):
            raise ValueError('Wait for the current reply')
        for person, other in ((speaker, target), (target, speaker)):
            person.social_contacts[other.id] = world.tick
            person.social_contacts = dict(sorted(person.social_contacts.items(), key=lambda x: x[1])[-40:])
        # Drop obsolete queued reflection so direct dialogue takes its place.
        self.queue[:] = [job for job in self.queue if job.agent != target_id or job.conversation]
        heapq.heapify(self.queue)
        self._utterance(world, c, speaker, target, message, source)
        c['state'], c['next_speaker'] = ('waiting_player', None) if target.player else ('active', target_id)
        if not target.player:
            self.request(world, target_id, 'important conversation', 0, c['id'])
        return c['id']

    def _utterance(self, world, conversation, speaker, listener, speech, source):
        speech = str(speech).strip()[:2000]
        if not speech:
            return
        conversation['turns'].append({'speaker': speaker.id, 'text': speech, 'tick': world.tick, 'source': source})
        conversation['turns'] = conversation['turns'][-24:]
        conversation['updated'] = world.tick
        hear(world, listener, speaker, speech)
        listener.cognition_revision += 1
        world.event('dialogue', f'{speaker.name}: {speech}', [speaker.id, listener.id],
                    conversation=conversation['id'], source=source)

    def _apply(self, world, job, response):
        usage=response.get('usage',{})
        for key in ('input_tokens','output_tokens'):
            if type(usage.get(key)) is int and usage[key]>=0:
                self.metrics[key]+=usage[key];self.metrics['usage_available']=True
        agent = world.agents.get(job.agent)
        if job.epoch != self.epoch or not agent or agent.cognition_revision != job.revision or world.tick-job.tick > self.config.budget_window or agent.incapacitated:
            self.metrics['stale'] += 1
            return
        c = world.conversations.get(job.conversation) if job.conversation else None
        if c and c['state'] != 'active':
            self.metrics['stale'] += 1
            return
        if not response.get('ok'):
            self.metrics['failed'] += 1
            self.metrics['last_error'] = response.get('error', 'Provider failure')[:250]
            agent.next_reason_tick = world.tick+self.config.reasoning_interval
            if c:
                c['state'], c['error'] = 'failed', self.metrics['last_error']
            return
        try:
            from .analytics import proposal as audit_proposal
            audit_proposal(world,agent.id,response.get('data'), 'proposed')
            proposal = validate_plan(response['data'])
        except (ValueError, KeyError, TypeError) as exc:
            audit_proposal(world,agent.id,response.get('data'),'rejected')
            self.metrics['failed'] += 1
            agent.plan_error = f'Model proposal rejected: {exc}'
            agent.next_reason_tick = world.tick+5
            if c:
                c['state'], c['error'] = 'failed', agent.plan_error
            return
        self.metrics['completed'] += 1
        agent.last_reasoned = world.tick
        agent.next_reason_tick = world.tick+self.config.reasoning_interval
        agent.reasoning_count += 1
        agent.cognition_revision += 1
        if proposal['goal']:
            entry = {'description': proposal['goal'], 'source': 'llm', 'tick': world.tick}
            agent.goals.append(entry)
            if not any(x.get('description') == proposal['goal'] for x in agent.long_term_goals):
                agent.long_term_goals.append(dict(entry))
        adopted = adopt_plan(world, agent, proposal)
        audit_proposal(world,agent.id,proposal,'validated',adopted)
        if adopted and world.active(agent.id) and agent.plan and agent.plan[0].get('action') == 'conflict_response':
            from .actions import execute
            outcome = execute(world, agent.plan[0], actor_id=agent.id, planned=True)
            if outcome['ok']:
                agent.plan_index = 1
                if agent.plan_index == len(agent.plan):
                    agent.plan_status = 'completed'
            else:
                agent.plan_error, agent.plan_status = outcome['message'], 'failed'
        if proposal['reflection']:
            agent.reflection = (agent.reflection+' '+proposal['reflection'])[-2000:]
            agent.semantic_memory.append({'content': proposal['reflection'], 'source': 'reflection', 'tick': world.tick, 'confidence': .5})
        world.event('reasoning', f'{agent.name} reconsidered: {proposal["goal"] or job.context["reason"]}', [agent.id], source='llm')
        if c:
            other_id = next(x for x in c['participants'] if x != agent.id)
            other = world.agents.get(other_id)
            if not other or other.incapacitated or combat.distance(agent, other) > 4:
                c['state'], c['error'] = 'ended', 'Participants moved out of conversational range'
                return
            if not proposal['speech']:
                c['state'] = 'ended'
                return
            self._utterance(world, c, agent, other, proposal['speech'], 'llm')
            self._dialogue_actions(world, c, agent, other, proposal['dialogue_actions'])
            stance = response['data'].get('stance', 'neutral')
            # Engine interprets a bounded social assessment of an actual heard statement.
            if stance in ('agree', 'disagree', 'question') and agent.id not in c.setdefault('assessed', []):
                c['assessed'].append(agent.id)
                change = {'agree': .025, 'disagree': -.025, 'question': -.005}[stance]
                world.relate(agent, other, change)
            if self._repeated(c, agent.id):
                c['state'], c['next_speaker'] = 'ended', None
                c['closure'] = 'Repeated statements; conversation concluded without inventing a new outcome'
            elif other.player:
                # Keep the thread replyable even if the NPC considers this topic settled.
                c['state'], c['next_speaker'] = 'waiting_player', None
            elif proposal['end_conversation'] or len(c['turns']) >= self.config.max_turns:
                c['state'], c['next_speaker'] = 'ended', None
            else:
                c['next_speaker'] = other.id
        elif proposal['conversation']:
            intent = proposal['conversation']
            try:
                self.speak(world, agent.id, intent['target'], intent['message'], 'llm', intent['topic'])
            except ValueError as exc:
                agent.plan_feedback = 'Conversation could not start: '+str(exc)
                remember(agent, world.tick, agent.plan_feedback, 'action_feedback')
        elif proposal['speech']:
            # Unaddressed prose is private reflection, not a fabricated conversation.
            remember(agent, world.tick, proposal['speech'], 'private_reasoning', 1, .5)

    @staticmethod
    def _repeated(conversation, speaker_id):
        import re
        own = [re.sub(r'\W+', ' ', t['text'].lower()).strip() for t in conversation['turns'] if t['speaker'] == speaker_id]
        return len(own) >= 3 and own[-1] == own[-2] == own[-3]

    def _dialogue_actions(self, world, conversation, actor, partner, commands):
        from .actions import execute
        for command in commands:
            related = command.get('target', partner.id) == partner.id
            if command['action'] in ('accept', 'reject'):
                agreement = world.agreements.get(command.get('agreement'), {})
                related = {agreement.get('proposer'), agreement.get('recipient')} == {actor.id, partner.id}
            result = execute(world, command, actor.id, planned=True,origin='llm') if related else {'ok': False, 'message': 'Dialogue actions must involve this conversation partner'}
            outcome = {'tick': world.tick, 'actor': actor.id, 'action': command['action'],
                       'ok': result['ok'], 'message': result['message']}
            if 'agreement' in result:
                outcome['agreement'] = result['agreement']
            conversation.setdefault('outcomes', []).append(outcome)
            conversation['outcomes'] = conversation['outcomes'][-16:]
            for person in (actor, partner):
                remember(person, world.tick, f'{actor.name}: {command["action"]} — {result["message"]}', 'engine_confirmation', 3)
            if not result['ok']:
                actor.plan_feedback = result['message']

    def pump(self, world, schedule=True):
        if self.closed:
            return
        # Completed proposals are applied on the simulation thread only, even while paused.
        for future, (job, start) in list(self.inflight.items()):
            if not future.done():
                continue
            del self.inflight[future]
            self.metrics['latency_ms'] = round((time.monotonic()-start)*1000, 2)
            if future.cancelled():
                self.metrics['stale'] += 1
                continue
            try:
                response = future.result()
            except Exception as exc:
                response = {'ok': False, 'error': f'Provider exception: {type(exc).__name__}'}
            self._apply(world, job, response)
        upkeep(world)
        if not self.config.enabled:
            for c in world.conversations.values():
                if c['state'] == 'active':
                    c['state'], c['next_speaker'], c['error'] = 'failed', None, 'LLM cognition was disabled before the reply completed'
            return
        window = world.tick//self.config.budget_window
        if self.window != window:
            self.window, self.budgets, self.global_used = window, {}, 0
        for c in list(world.conversations.values()):
            if c['state'] == 'active':
                if world.tick-c['updated'] > 150:
                    c['state'], c['error'] = 'ended', 'Conversation timed out'
                elif c.get('next_speaker'):
                    self.request(world, c['next_speaker'], 'continue conversation', 0, c['id'])
        if len(world.conversations) > 80:
            for key in list(world.conversations):
                if len(world.conversations) <= 80:
                    break
                if world.conversations[key]['state'] not in ('active', 'queued'):
                    del world.conversations[key]
        if schedule:
            for agent in sorted(world.agents.values(), key=lambda a: (a.last_reasoned, a.id)):
                if agent.player or agent.incapacitated or not adult(agent):
                    continue
                seen = self.events_seen.get(agent.id, 0)
                important = any(e['id'] > seen and agent.id in e['actors'] and e['kind'] in
                                ('claim', 'conflict_start', 'witness', 'offer', 'help', 'plan_failed', 'dialogue', 'proposal', 'council_decision','environment_observed','production_completed','threat_observed','threat_contact','threat_warning','threat_report','settlement_warning') for e in world.events[-80:])
                if world.events:
                    self.events_seen[agent.id] = world.events[-1]['id']
                # Conversation turns have their own priority and should not trigger unrelated reflection loops.
                engaged = any(c['state'] == 'active' and agent.id in c['participants'] for c in world.conversations.values())
                social = opportunities(world, agent) if not engaged and world.tick >= agent.next_reason_tick else []
                if not engaged and (important or social or (world.tick >= agent.next_reason_tick and (agent.plan_status != 'active' or world.tick-agent.last_reasoned >= self.config.reasoning_interval*3))):
                    reason = ('new important information; preserve useful ongoing work' if important else
                              'consider a voluntary conversation: '+social[0]['reason'] if social else
                              'failed plan: '+agent.plan_error if agent.plan_status == 'failed' else 'review progress or choose a new goal')
                    self.request(world, agent.id, reason, 2 if important else 4 if social else 5)
        # Fair budget enforcement; queue stays bounded and no futures pile up inside executor.
        deferred = []
        while self.queue and len(self.inflight) < self.config.max_concurrency:
            job = heapq.heappop(self.queue)
            if job.epoch != self.epoch or world.tick-job.tick > self.config.budget_window:
                self.metrics['stale'] += 1
                continue
            if self.budgets.get(job.agent, 0) >= self.config.per_agent_budget or self.global_used >= self.config.global_budget:
                if job.conversation:
                    conversation = world.conversations.get(job.conversation)
                    if conversation:
                        conversation['state'] = 'failed'
                        conversation['error'] = 'Reasoning budget exhausted; advance time or increase the configured budget'
                else:
                    deferred.append(job)
                continue
            agent = world.agents.get(job.agent)
            if not agent or agent.incapacitated:
                self.metrics['stale'] += 1
                continue
            if job.conversation:
                c = world.conversations.get(job.conversation)
                if not c or c['state'] != 'active' or c.get('next_speaker') != job.agent:
                    self.metrics['stale'] += 1
                    continue
            changed_inventory = (job.context.get('agent', {}).get('inventory') != agent.inventory)
            if job.revision != agent.cognition_revision or world.tick - job.tick > 40 or changed_inventory:
                # Discard changed or very old observations, but DO NOT require
                # the exact same tick: otherwise a busy local GPU starves jobs
                # waiting in the queue while the simulation continues.
                self.request(world, job.agent, job.context['reason'], job.priority, job.conversation)
                continue
            self.budgets[job.agent] = self.budgets.get(job.agent, 0)+1
            self.global_used += 1
            self.metrics['submitted'] += 1
            config = self.config  # Immutable replacement on configure, not edited by workers.
            future = self.executor.submit(self.provider, config, SYSTEM, job.context)
            self.inflight[future] = (job, time.monotonic())
        for job in deferred:
            heapq.heappush(self.queue, job)
        self.metrics['budget_deferred'] = len(deferred)
