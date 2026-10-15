"""The added fighter's item database (`<code>.xml`, BXML), made from the donor's.

A fighter's database has two top-level elements: InstanceInfo (one Instance per costume item: its Data, the Model
sections A/B naming part models in the fighter's own packs, effects) and OffsetInfo. The added fighter has no parts
of its own (everything is in its body model), so it keeps only the donor's default-costume Instances (same labels
and indices: upper and lower body, head, the default effects and the rage aura) with their part lists emptied. A
database naming parts the fighter's packs do not have makes the loading screen hang.
"""
import copy

from ..ttt2 import bxml

DEFAULT_COSTUME = 'デフォルトコスチューム'       # the EquipType of default-costume items ("default costume")


def body_only(donor_db):
    info, offsets = bxml.parse(donor_db)[:2]
    instances = []
    for inst in info['children']:
        data = [c for c in inst['children'] if c['tag'] == 'Data']
        if not data or dict(data[0]['attrs']).get('EquipType') != DEFAULT_COSTUME:
            continue
        inst = copy.deepcopy(inst)
        kids = []
        for c in inst['children']:
            if c['tag'] == 'Model' and not any(g['tag'] == 'EffectGroup' for g in c['children']):
                c['children'] = []               # no part model; effect groups stay
            if c['tag'] != 'ModelBConditions':
                kids.append(c)
        inst['children'] = kids
        instances.append(inst)
    return bxml.write([dict(tag=info['tag'], attrs=info['attrs'], children=instances),
                       dict(tag=offsets['tag'], attrs=offsets['attrs'], children=[])])
