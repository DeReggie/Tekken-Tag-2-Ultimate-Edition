"""Keep the recovered local character choices together across rebuilds."""
import importlib
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import unittest
from ttt2char.characters import akuma, eliza, geese, fahkumram, kunimitsu2, noctis

class LocalCustomizations(unittest.TestCase):
    def test_all_preset_definitions_survive_consolidation(self):
        expected = {'akuma':7,'chloe':10,'claudio':9,'eliza':8,'fahkumram':7,
                    'geese':7,'gigas':9,'josie':10,'katarina':10,'kazumi':9,
                    'kunimitsu2':9,'leroy':7,'lidia':7,'master_raven':7,
                    'negan':4,'noctis':8,'shaheen':9}
        for name, count in expected.items():
            with self.subTest(fighter=name):
                self.assertEqual(len(importlib.import_module('ttt2char.characters.'+name).PRESETS),count)
    def test_free_meter_routes_remain_in_all_three_2d_fighters(self):
        for c in (akuma,eliza,geese):
            self.assertTrue(c.MOVESET['free_meter_specials'],c.NAME)
        targets=set(akuma.MOVESET['special_cancels']['Mx_rp00'])
        self.assertTrue({'Ry_EX_hadoh','Ry_EXtatumaki','Ry_shoryuBEX','Ry_shinhadouken'}<=targets)
        self.assertEqual(akuma.MOVESET['special_cancels']['Ry_shoryu'],('Mx_saving_cn',))
        self.assertTrue(geese.MOVESET['free_max_mode'])
    def test_recent_move_choices_and_assist_fixes_survive(self):
        self.assertTrue(geese.MOVESET['bounds']['My_623B2'])
        self.assertNotIn('My_623B',geese.MOVESET['bounds'])
        self.assertEqual(geese.MOVESET['air_reactions']['My_WPF'],(40,'J8_jprk00'))
        self.assertEqual(akuma.MOVESET['startup_trim'],{'Mx_3lrp':4,'Mx_66rk':4})
        self.assertEqual(akuma.MOVESET['recovery_trim'],{'Mx_3rplp':4})
        self.assertEqual(kunimitsu2.MOVESET['buffered_stance_transitions'],{'Kt_rk00F':'Kt_shoryu02'})
        self.assertTrue(fahkumram.MOVESET['bounds']['Nc_3rplp'])
        self.assertFalse(noctis.MOVESET['bounds']['Mz_t_srk03F'])
