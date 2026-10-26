"""Geese's MAX and special-to-super routes must retain their original gates."""
import types
import unittest
import test_specialcancels as fixtures
from ttt2char.convert import specialcancels as S, tagsystem as TS, moveset

class GeeseSpecials(unittest.TestCase):
    def converter(self):
        c = fixtures.SpecialCancels().converter()
        c.defn.MOVESET.update(buffered_special_cancels=True, free_meter_specials=True,
                             free_max_mode=True, strict_special_cancel_gates=True)
        c.T.update(move_begin_props=[], move_end_props=[], cancel_extras=[])
        c.extra_index = {}
        return c

    def test_special_to_super_contact_buffer_is_not_dropped(self):
        c = self.converter()
        # Geese sets T7's second word on hit/block, then checks it at dispatch.
        for row in c.k.tables['requirements']:
            if row['condition'] == 49:
                row.update(condition=353, param=1)
        S.apply(c)
        rows = TS.cancels(c.T, c.T['moves'][0]['cancel'])
        dispatch = [r for r in rows if r['move_id'] == 1]
        self.assertEqual(len(dispatch), 2)
        self.assertTrue(all(TS.reqs(c.T, r['req']) == [(307, 3), (308, 1)] for r in dispatch))
        self.assertEqual(sum((0x80a5, 1) in TS.reqs(c.T, r['req']) for r in rows), 2)

    def test_unknown_dispatch_guard_fails_closed(self):
        c = self.converter()
        c.k.tables['requirements'][3].update(condition=999, param=1)
        c.defn.MOVESET['noncontact_special_cancels'] = ('normal',)
        with self.assertRaisesRegex(ValueError, 'unsupported special dispatch'):
            S.apply(c)

    def test_unknown_capture_guard_fails_closed(self):
        c = self.converter()
        c.k.tables['requirements'].insert(0, dict(condition=999, param=1))
        for row in c.k.tables['cancels'][1:]:
            row['req'] += 1
        with self.assertRaisesRegex(ValueError, 'unsupported special capture'):
            S.apply(c)

    def test_max_mode_requirement_is_only_removed_for_opt_in(self):
        for free in (False, True):
            c = types.SimpleNamespace(game='t7', end=881, defn=types.SimpleNamespace(MOVESET={'free_max_mode': free}),
                k=types.SimpleNamespace(game='t7', tables={'requirements': [
                    dict(condition=176, param=0), dict(condition=881, param=0)]}),
                cache={}, T={'requirements': []}, stats=__import__('collections').Counter(),
                map_req=lambda _: None)
            c.k.iter_list = types.MethodType(fixtures.Moveset.iter_list, c.k)
            converter = moveset.Converter.__new__(moveset.Converter)
            converter.__dict__.update(vars(c))
            c = converter
            _, ok = c.conv_reqs(0)
            self.assertEqual(ok, free)

    def test_buffered_normal_string_cannot_steal_a_special(self):
        c = self.converter()
        c.defn.MOVESET['buffered_normal_followups'] = True
        rows = c.k.tables['cancels']
        # A contact-confirmed normal input beside the special's dispatch.
        rq = len(c.k.tables['requirements'])
        c.k.tables['requirements'] += [dict(condition=a, param=b) for a, b in
                                       [(49, 0), (346, 0), (881, 0)]]
        rows.insert(-1, dict(rows[1], direction=0, button=0x40000001, req=rq))
        S.apply(c)
        rows = TS.cancels(c.T, c.T['moves'][0]['cancel'])
        normal = next(r for r in rows if r['button'] == 0x40000001)
        self.assertEqual(TS.reqs(c.T, normal['req']), [(307, 0), (308, 1)])
        special = next(r for r in rows if r['move_id'] == 1 and r['button'] == 0)
        self.assertLess(rows.index(special), rows.index(normal))
