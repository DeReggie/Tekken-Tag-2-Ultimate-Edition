import copy
import os
import sys
import types
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ttt2char.convert import move_overrides as O, tagsystem as T

class DownedReactions(unittest.TestCase):
    def test_shared_standing_and_air_reactions_are_preserved(self):
        normal = dict(default=1, ch=2, crouch=3, downed=4)
        tables = {'moves': [dict(hit_condition=0), dict(hit_condition=1)],
                  'reactions': [normal],
                  'requirements': [dict(condition=T.AIR, param=0), dict(condition=T.TT_END, param=0)],
                  'hit_conditions': [dict(req=0, damage=22, reactions=0),
                                     dict(req=None, damage=22, reactions=0)]}
        # Write terminator-backed hit lists using the same public table writer.
        tables['moves'][0]['hit_condition'] = T.write(tables, 'hit_conditions', tables['hit_conditions'][:])
        before = copy.deepcopy(tables)
        c = types.SimpleNamespace(T=tables, kn={'attack':0}, newidx={0:0}, dn={'flip':9})
        def add(table, value):
            tables[table].append(value)
            return len(tables[table])-1
        c.add = add
        O.downed_reaction(c, 'attack', 'flip')
        hits = T.hits(tables, tables['moves'][0]['hit_condition'])
        self.assertEqual(hits[0], dict(req=0,damage=22,reactions=0))
        self.assertEqual(tables['reactions'][0], normal)
        self.assertEqual(tables['reactions'][hits[1]['reactions']], dict(normal, downed=9))
        self.assertEqual(hits[1]['damage'],22)
        self.assertEqual(tables['moves'][1],before['moves'][1])
if __name__ == '__main__': unittest.main()
