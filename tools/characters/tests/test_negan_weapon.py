import os,sys,unittest
from pathlib import Path
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..'))
from ttt2char.characters import negan
from ttt2char.tekken7 import tkmvst
from ttt2char.convert import arcs

class NeganBatAnimation(unittest.TestCase):
    def test_bat_uses_the_pair_animated_by_reported_attacks(self):
        path=Path.home()/'.local/share/ttt2/tekken7/movesets/T7_Negan.tkmvst'
        if not path.exists():self.skipTest('local T7 Negan export unavailable')
        m=tkmvst.read(str(path));names={m.move_name(i):i for i in range(len(m.tables['moves']))}
        for name in ('Na_lprp','Na_rkrp'):
            v=m.tables['moves'][names[name]];a=arcs.decode_t7(m,v['anim'])['values']
            # Compare the actual attacking interval to entry; the parked copy
            # retains its fixed rotation while the active bat sweeps.
            frame=v['first_active'];changes=[]
            for pair in range(2):
                changes.append(float(abs(a[frame,24+2*pair]-a[0,24+2*pair]).max()))
            with self.subTest(move=name):
                self.assertGreater(changes[0],0.5)
                self.assertLess(changes[1],0.1)
                self.assertEqual(negan.WEAPONS[0]['pair'],0)
