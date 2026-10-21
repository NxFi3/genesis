from dataclasses import dataclass, field


@dataclass
class Agent:
    id: str
    name: str
    x: float
    y: float
    home: str
    age: int = 25
    birth_tick: int | None = None
    life_stage: str = 'adult'
    household: str | None = None
    residence: str | None = None
    parents: list = field(default_factory=list)
    children: list = field(default_factory=list)
    partner: str | None = None
    appearance: dict = field(default_factory=dict)
    family_history: list = field(default_factory=list)
    family_intent: dict = field(default_factory=dict)
    hp: float = 100
    max_hp: float = 100
    stamina: float = 100
    hunger: float = 15
    thirst: float = 15
    fatigue: float = 10
    speed: float = 1.0
    defense: float = 2
    equipment: list = field(default_factory=list)
    inventory: dict = field(default_factory=lambda: {'food': 5, 'water': 5, 'wood': 0, 'stone': 0, 'metal': 0, 'tools': 0})
    personality: dict = field(default_factory=lambda: {'aggression': .2, 'courage': .5, 'sociability': .5})
    skills: dict = field(default_factory=lambda: {'gather': 1, 'build': 1, 'combat': 1})
    relationships: dict = field(default_factory=dict)
    memories: list = field(default_factory=list)
    knowledge: list = field(default_factory=list)
    goals: list = field(default_factory=list)
    occupation: str = 'gatherer'
    activity: str = 'observe'
    reason: str = 'Surveying opportunities'
    target: str | None = None
    incapacitated: bool = False
    defending: bool = False
    player: bool = False
    combat_choice: str = 'avoid'
    combat_intent: dict = field(default_factory=dict)
    threat_intent: dict = field(default_factory=dict)
    threat_state: dict = field(default_factory=dict)
    patrol_index: int = 0
    shelter: float = 0
    safety: float = 0
    social: float = 15
    warmth: float = 10
    carry_capacity: float = 120
    extraction: dict = field(default_factory=dict)
    production_job: str | None = None
    equipment_condition: dict = field(default_factory=dict)
    plan: list = field(default_factory=list)
    plan_index: int = 0
    plan_status: str = 'idle'
    plan_error: str = ''
    plan_goal: str = ''
    plan_feedback: str = ''
    social_contacts: dict = field(default_factory=dict)
    cognition_revision: int = 0
    last_reasoned: int = -1000
    next_reason_tick: int = 0
    reasoning_count: int = 0
    beliefs: list = field(default_factory=list)
    semantic_memory: list = field(default_factory=list)
    long_term_goals: list = field(default_factory=list)
    commitments: list = field(default_factory=list)
    property: list = field(default_factory=list)
    reflection: str = ''
    observations: dict = field(default_factory=dict)


@dataclass
class Settlement:
    id: str
    name: str
    x: float
    y: float
    inventory: dict = field(default_factory=lambda: {'food': 100, 'water': 100, 'wood': 12, 'stone': 8, 'metal': 0, 'tools': 0})
    stability: float = 100
    conflict: str = 'peace'
    diplomacy: dict = field(default_factory=dict)
    council: list = field(default_factory=list)
    policy: str = 'share_surplus'
    threat_alert: dict = field(default_factory=dict)


@dataclass
class Resource:
    id: str
    kind: str
    x: float
    y: float
    quantity: float
    capacity: float
    regeneration: float = 0
    source: str = ''


@dataclass
class Building:
    id: str
    kind: str
    home: str
    x: float
    y: float
    progress: float = 0
    complete: bool = False
    condition: float = 100


@dataclass
class Wildlife:
    id: str
    x: float
    y: float
    hp: float = 40
    stamina: float = 70
    species: str = 'deer'
    activity: str = 'graze'
    threat: str | None = None
    harvested: bool = False
    age: int = 0
    hunger: float = 0
    behavior: dict = field(default_factory=dict)


@dataclass
class Conflict:
    id: str
    a: str
    b: str
    started: int
    cause: str
    state: str = 'active'
    ended: int | None = None
    outcome: str = ''
    last_contact: int = 0
    cooldown: int = 0
