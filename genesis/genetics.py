"""Fictional appearance inheritance only; no ability/personality or medical claims."""
import hashlib
import random

PALETTES={'hair':['#302b29','#76503b','#c6a365','#ac5941','#d1ccba'],
          'eyes':['#574337','#789398','#778064','#999092'],
          'texture':['straight','wavy','curly'],'face':['round','angular','oval']}


def profile(seed,identity,parents=None):
    rng=random.Random(int.from_bytes(hashlib.sha256(f'{seed}:appearance:{identity}'.encode()).digest()[:8],'big'))
    alleles={}
    for trait,values in PALETTES.items():
        alleles[trait]=[rng.choice(parent['alleles'][trait]) for parent in parents] if parents else [rng.randrange(len(values)) for _ in range(2)]
    alleles['skin']=[max(0,min(1,rng.choice(parent['alleles']['skin'])+rng.uniform(-.04,.04))) for parent in parents] if parents else [rng.random(),rng.random()]
    return {'alleles':alleles,**{trait:values[rng.choice(pair)] for trait,pair in alleles.items() if trait!='skin' for values in [PALETTES[trait]]},'skin':round(sum(alleles['skin'])/2,4)}


def validate(appearance):
    if not isinstance(appearance,dict) or not isinstance(appearance.get('alleles'),dict):raise ValueError('Invalid appearance profile')
    for trait,values in PALETTES.items():
        pair=appearance['alleles'].get(trait)
        if not isinstance(pair,list) or len(pair)!=2 or any(type(x) is not int or not 0<=x<len(values) for x in pair) or appearance.get(trait) not in [values[x] for x in pair]:raise ValueError('Invalid inherited appearance')
    pair=appearance['alleles'].get('skin')
    if not isinstance(pair,list) or len(pair)!=2 or any(type(x) not in (int,float) or not 0<=x<=1 for x in pair) or appearance.get('skin')!=round(sum(pair)/2,4):raise ValueError('Invalid appearance variation')
