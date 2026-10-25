import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ttt2char.movesets import Moveset
from ttt2char.convert.moveset import Converter, T7_END, TT_END
class MovementReferences(unittest.TestCase):
    def test_movement_and_cancel_action_relocate_source_row(self):
        c = Converter.__new__(Converter)
        c.cache = {}
        c.k = Moveset()
        c.k.game = 't7'
        c.k.tables = {
            'pushbacks': [dict(duration=40, displacement=40, loops=2, extradata=0)],
            'pushback_extras': [dict(value=0), dict(value=7)],
            'requirements': [dict(condition=0x81e8, param=0), dict(condition=T7_END, param=0)]}
        c.T = {'pushbacks': [dict(duration=0, displacement=0, loops=0, extradata=None)],
               'pushback_extras': [dict(value=99)], 'requirements': []}
        c.map_req = lambda x: {0x81e8: 0x813b, T7_END: TT_END}[x]
        index = c.conv_value(0x81e8, 0)
        self.assertEqual(index, 1)
        self.assertEqual(c.T['pushbacks'][index], dict(duration=40, displacement=40, loops=2, extradata=1))
        self.assertEqual(c.T['pushback_extras'][1:], c.k.tables['pushback_extras'])
        start, ok = c.conv_reqs(0)
        self.assertTrue(ok)
        self.assertEqual(c.T['requirements'][start], dict(condition=0x813b, param=index))
        self.assertEqual(len(c.T['pushbacks']), 2)
if __name__ == '__main__': unittest.main()
