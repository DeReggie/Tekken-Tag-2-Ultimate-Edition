"""Unit tests of the cloth converter (cloth.py) and its spring file on made-up data (no game files needed).

    python3 -m unittest discover tools/characters/tests
"""
import os
import struct
import sys
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from ttt2char.convert import chains, cloth          # noqa: E402


def skirt(rows=12, around=24, radius=18.0, top=110.0, step=8.0):
    """A made-up skirt as Tekken 7 keeps a clothing asset (centimetres, Z up): rings of vertices from the waist
    down, the top ring pinned, the max distance growing downward."""
    v, md = [], []
    for r in range(rows):
        for a in range(around):
            t = 2 * np.pi * a / around
            rr = radius + r * 1.5
            v.append((rr * np.cos(t), rr * np.sin(t), top - r * step))
            md.append(0.0 if r == 0 else 10.0 * r)
    tris = []
    for r in range(rows - 1):
        for a in range(around):
            i, j = r * around + a, r * around + (a + 1) % around
            tris += [(i, j, i + around), (j, j + around, i + around)]
    return types.SimpleNamespace(vertices=np.array(v), max_distance=np.array(md), triangles=np.array(tris),
                                 bone_names=['Hip'], bones=np.zeros((len(v), 4), np.int64),
                                 weights=np.tile([1.0, 0, 0, 0], (len(v), 1)))


def model(asset):
    """A loaded model (as load_tekken7_model gives it) whose only vertices are the skirt's, skinned to Hip, and a
    body column inside it."""
    sim = cloth._points(asset.vertices)
    body_r = np.linspace(0, 2 * np.pi, 16, endpoint=False)
    body = np.array([(80 * np.cos(t), y, 80 * np.sin(t)) for y in np.linspace(0, 1500, 30) for t in body_r])
    pos = np.concatenate([sim, body])
    nrm = np.concatenate([np.zeros_like(sim), body * [1, 0, 1]])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    n = len(pos)
    joints = np.zeros((n, 8), np.int64)
    weights = np.zeros((n, 8))
    weights[:, 0] = 1.0
    world = np.tile(np.eye(4), (2, 1, 1))
    world[1, :3, 3] = (0, 1100, 0)
    tris = np.concatenate([asset.triangles, len(sim) + np.array([[0, 1, 2]])])
    prim = dict(part='bdu', material='m', pos=pos, nrm=nrm, tan=np.zeros((n, 4)), uv=np.zeros((n, 2)),
                joints=joints, weights=weights, tris=tris)
    k = {'bones': dict(names=['BASE', 'Hip'], parents=[-1, 0], world=world), 'prims': [prim], 'parts': {}}
    joints[:, 0] = 1
    return k, np.arange(len(sim))


class Rig(unittest.TestCase):
    def setUp(self):
        self.asset = skirt()
        self.k, self.drawn = model(self.asset)
        self.made = cloth.rig(self.k, [dict(part='bdu', asset=self.asset, vertices=self.drawn, name='skirt')],
                              log=lambda s: None)

    def test_chains_round_the_waist_hanging_down(self):
        self.assertGreaterEqual(len(self.made), 6)
        world = self.k['bones']['world']
        for c in self.made:
            ys = [world[b][1, 3] for b in c['bones']]
            self.assertTrue(all(a > b for a, b in zip(ys, ys[1:])))           # each bone below the one before
            self.assertEqual(c['parent'], 1)                                   # hung from Hip
            self.assertEqual(len(c['neighbours']), 2)                          # a closed ring: two neighbours each
            x = world[c['bones'][0]][:3, 0]
            self.assertLess(x[1], -0.8)                                        # local X points down

    def test_skinned_to_the_chains_below_the_waist_only(self):
        s = self.k['prims'][0]
        first = min(b for c in self.made for b in c['bones'])
        sim = self.asset.max_distance
        cloth_w = np.where(s['joints'] >= first, s['weights'], 0).sum(1)[self.drawn]
        np.testing.assert_allclose(s['weights'].sum(1), 1.0, atol=1e-9)
        self.assertTrue(np.all(cloth_w[sim == 0] == 0))                        # the pinned ring keeps Hip
        self.assertTrue(np.all(cloth_w[sim >= 30] > 0.99))                     # the skirt below hangs on chains
        self.assertTrue(np.all((s['weights'] > 0).sum(1) <= 8))

    def test_spring_entries_pairs_and_links(self):
        names = ['cha:HARA_ROT1', 'cha:KOSHI_jnt', 'cha:HIZA_R_jnt', 'cha:HIZA_L_jnt']
        world = [np.eye(4) for _ in names]
        world[1][1, 3], world[2][1, 3], world[3][1, 3] = 1100, 500, 500
        made, number = [], cloth.OPT_FIRST
        for c, chain in enumerate(self.made):
            idx = []
            for j, b in enumerate(chain['bones']):
                idx.append(len(names))
                names.append('cha:OPT%d_cloth0_%d_%d' % (number, c, j))
                world.append(self.k['bones']['world'][b])
                number += 1
            made.append(idx)
        for name, y in (('MOMO_R_jnt', 1000), ('MOMO_L_jnt', 1000), ('ASHI_R_jnt', 100), ('ASHI_L_jnt', 100),
                        ('MUNE1_jnt', 1150), ('MUNE2_jnt', 1300), ('KUBI_jnt', 1500), ('ATAMA_jnt', 1600)):
            names.append('cha:' + name)
            world.append(np.eye(4))
            world[-1][:3, 3] = (100 if '_L_' in name else -100 if '_R_' in name else 0, y, 0)
        for name in [a for pair in cloth.OTHER for a in pair]:
            if 'cha:' + name not in names:
                names.append('cha:' + name)
                world.append(np.eye(4))
                world[-1][:3, 3] = (500, 1400, 0)
        world[2][:3, 3], world[3][:3, 3] = (-100, 500, 0), (100, 500, 0)
        skel = dict(names=names, parent=[-1] * len(names))
        body = np.array([(x, y, z) for x in (-100, 100) for y in range(150, 1000, 25) for z in (-60, 60)]
                        + [(x, y, z) for x in (-60, 60) for y in range(1000, 1500, 25) for z in (-90, 90)], float)
        cloth_bone = types.SimpleNamespace(world_matrices=lambda s: np.array(world))
        saved, cloth.bone = cloth.bone, cloth_bone
        try:
            sp = cloth.springs(skel, made, self.made, body)
        finally:
            cloth.bone = saved
        self.assertEqual(len(sp['entries']), sum(map(len, made)))
        tops = {cloth.OPT_FIRST + sum(map(len, made[:c])) for c in range(len(made))}
        self.assertFalse(any(n in tops for n, _ in sp['pairs']))               # top bones touch no capsule
        self.assertTrue(sp['links'])
        self.assertTrue(sp['pairs'])
        self.assertGreaterEqual(len(sp['capsules']), 5)                       # (a made-up body: no hips)
        caps = {names[b]: size for b, _, size in sp['capsules']}
        self.assertGreater(caps['cha:MOMO_R_jnt'][1], cloth.LEG_MARGIN)          # round the thigh: its radius and more
        self.assertEqual({j for _, _, j in sp['links']}, set(range(min(map(len, made)))))


def entry(number, pairs=0, links=0):
    e = bytearray(cloth.MOP_ENTRY)
    struct.pack_into('>I11f', e, 0, number, 30, 10, 70, 200, .05, -.05, .2, -.04, 1, 1, .05)
    struct.pack_into('>III', e, 0x30, 0x60, pairs, links)
    return bytes(e)


def mop(entries, capsules=(), tail=b''):
    return (struct.pack('>f', 5.0) + bytes(28) + struct.pack('>I', len(entries)) + bytes(12) + b''.join(entries)
            + struct.pack('>I', len(capsules)) + bytes(12) + b''.join(capsules) + tail)


class SpringFile(unittest.TestCase):
    def template(self):
        caps = [struct.pack('>II', 1, b) + bytes(cloth.MOP_CAPSULE - 8) for b in (26, 25, 52, 56)]
        return mop([entry(cloth.TEMPLATE_FIRST + j) for j in range(cloth.TEMPLATE_LINKS)], caps)

    def test_pairs_before_links_and_capsules_numbered_after_the_old(self):
        old_pair = struct.pack('>II8x', 7, 0)
        old_link = struct.pack('>IIff36x', 7, 8, 0.8, 50.0)
        old = mop([entry(7, 1, 1), entry(8)], [struct.pack('>II', 1, 73) + bytes(cloth.MOP_CAPSULE - 8)],
                  old_pair + old_link)
        sp = dict(entries=[(400, 0, 210.0, None), (401, 1, 190.0, (cloth.OUTWARD, None)), (402, 0, 210.0, None),
                           (403, 1, 190.0, (cloth.OUTWARD, cloth.DRAPED_INWARD))],
                  capsules=[(3, (50.0, 0, 0), (100.0, 150, 120)), (14, (200.0, 0, 0), (240.0, 130, 110)),
                            (17, (200.0, 0, 0), (240.0, 130, 110))],
                  pairs=[(401, 2)], links=[(400, 402, 0), (401, 403, 1)])
        out = cloth.spring_file(old, self.template(), sp)
        entries, capsules, pairs, links, rest = cloth.parse(out)
        self.assertEqual(len(entries), 6)
        self.assertEqual(len(capsules), 4)
        self.assertEqual(struct.unpack_from('>II', capsules[3]), (1, 17))
        self.assertEqual(struct.unpack_from('>3f', capsules[3], 32), (200.0, 0.0, 0.0))
        self.assertEqual(struct.unpack_from('>3f', capsules[3], 48), (240.0, 130.0, 110.0))
        self.assertEqual(rest, b'')
        self.assertEqual(pairs, old_pair + struct.pack('>II8x', 401, 1 + 2))
        self.assertEqual(links[:cloth.MOP_LINK], old_link)
        a, b, stiffness, value = struct.unpack_from('>IIff', links, cloth.MOP_LINK * 2)
        self.assertEqual((a, b, value), (401, 403, 80.0))
        self.assertAlmostEqual(stiffness, 0.8, 6)
        e = {struct.unpack_from('>I', x)[0]: x for x in entries}
        self.assertEqual(struct.unpack_from('>II', e[400], 0x34), (0, 1))
        self.assertEqual(struct.unpack_from('>II', e[401], 0x34), (1, 1))
        self.assertAlmostEqual(struct.unpack_from('>f', e[401], 16)[0], 190.0, 3)
        np.testing.assert_allclose(struct.unpack_from('>4f', e[401], 20), (.05, -.05, cloth.OUTWARD, -.04),
                                   atol=1e-6)                                  # (only the outward limit wider)
        np.testing.assert_allclose(struct.unpack_from('>4f', e[403], 20), (.05, -.05, cloth.OUTWARD,
                                                                          -cloth.DRAPED_INWARD), atol=1e-6)
        np.testing.assert_allclose(struct.unpack_from('>4f', e[400], 20), (.05, -.05, .2, -.04), atol=1e-6)

    def test_hair_entries_keep_the_cloth_pairs_and_links(self):
        cl = cloth.spring_file(mop([]), self.template(), dict(entries=[(400, 0, 200.0, None), (401, 1, 200.0, None)],
                                                               capsules=[(3, (0, 0, 0), (100, 100, 100))],
                                                               pairs=[(401, 0)], links=[]))
        lili = mop([entry(160)], [struct.pack('>II', 1, 73) + bytes(cloth.MOP_CAPSULE - 8)])
        out = chains.spring_file(cl, lili, [800], template=160, links=False)
        entries, capsules, pairs, links, rest = cloth.parse(out)
        self.assertEqual(len(entries), 3)
        self.assertEqual(pairs, struct.pack('>II8x', 401, 0))
        self.assertEqual(rest, b'')


class Drape(unittest.TestCase):
    def test_flowing_chain_hangs_hanging_one_stays(self):
        body = np.array([[0.0, 0.0, 0.0]])
        normals = np.array([[0.0, 0.0, 1.0]])
        flowing = np.array([[0, 1400, 300], [0, 1250, 150], [0, 1100, 0.0]])           # 45 degrees behind
        dirs = cloth._drape(flowing + [0, 0, 500], body, normals)
        self.assertIsNotNone(dirs)
        for d in dirs:
            self.assertLess(np.degrees(np.arccos(-d[1])), np.degrees(cloth.HANG) + 0.1)
        hanging = np.array([[0, 1400, 0], [30, 1200, 0], [60, 1000, 0.0]])            # 8.5 degrees out
        self.assertIsNone(cloth._drape(hanging + [0, 0, 500], body, normals))

    def test_kept_outside_the_body(self):
        body = np.array([[0.0, y, 0.0] for y in range(0, 1500, 20)])
        normals = np.tile([0.0, 0.0, 1.0], (len(body), 1))
        flowing = np.array([[0, 1400, 10], [0, 1300, -90], [0, 1200, -190.0]])        # flowing into the body
        dirs = cloth._drape(flowing, body, normals)
        p = flowing[0].copy()
        for i, d in enumerate(dirs):
            p = p + np.linalg.norm(flowing[i + 1] - flowing[i]) * d
            self.assertGreater(p[2], cloth.MARGIN - 1)


def skeleton():
    """A made-up TTT2 skeleton: the 22 body bones in the game's order, every local frame the world's but the legs'
    (local X down them, as the game's)."""
    from ttt2char.ttt2 import bone
    rows = [('HARA_ROT1', -1, (0, 1100, 0)), ('MUNE1_jnt', 0, (0, 0, 0)), ('MUNE2_jnt', 1, (0, 150, 0)),
            ('KOSHI_jnt', 0, (0, 0, 0)), ('KUBI_jnt', 2, (0, 250, 0)), ('ATAMA_jnt', 4, (0, 100, 0)),
            ('SAKOTSU_R_jnt', 2, (-100, 200, 0)), ('KATA_R_jnt', 6, (-100, 0, 0)), ('UDE_R_jnt', 7, (-300, 0, 0)),
            ('TE_R_jnt', 8, (-250, 0, 0)), ('SAKOTSU_L_jnt', 2, (100, 200, 0)), ('KATA_L_jnt', 10, (100, 0, 0)),
            ('UDE_L_jnt', 11, (300, 0, 0)), ('TE_L_jnt', 12, (250, 0, 0)), ('MOMO_R_jnt', 3, (-100, -100, 0)),
            ('HIZA_R_jnt', 14, (450, 0, 0)), ('ASHI_R_jnt', 15, (450, 0, 0)), ('MOMO_L_jnt', 3, (100, -100, 0)),
            ('HIZA_L_jnt', 17, (450, 0, 0)), ('ASHI_L_jnt', 18, (450, 0, 0)), ('TSUMASAKI_R_jnt', 16, (0, 0, 0)),
            ('TSUMASAKI_L_jnt', 19, (0, 0, 0))]
    down = bone.euler_xyz_from_matrix(np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1.0]]))     # local X -> world -Y
    r = [down if n.startswith('MOMO') else np.zeros(3) for n, _, _ in rows]
    return dict(names=['cha:' + n for n, _, _ in rows], parent=[p for _, p, _ in rows],
                t=np.array([t for _, _, t in rows], float), r=np.array(r))


def legs_and_trunk():
    """Body vertices (mm): legs 70 mm thick round x = +-100, a trunk 120 mm thick."""
    ring = np.linspace(0, 2 * np.pi, 12, endpoint=False)
    legs = [(x + 70 * np.cos(t), y, 70 * np.sin(t)) for x in (-100, 100) for y in range(150, 1000, 25) for t in ring]
    trunk = [(120 * np.cos(t), y, 120 * np.sin(t)) for y in range(1000, 1500, 25) for t in ring]
    return np.array(legs + trunk, float)


class Settle(unittest.TestCase):
    def test_cloth_rests_outside_a_thigh_that_stands_forward(self):
        from ttt2char.ttt2 import animation, bone
        asset = skirt(radius=17.0)
        k, drawn = model(asset)
        made = cloth.rig(k, [dict(part='bdu', asset=asset, vertices=drawn, name='skirt')], log=lambda s: None)
        skel = skeleton()
        values = np.zeros((len(animation.BODY_BONES), 3), np.float32)
        for c, b in enumerate(animation.BODY_BONES):
            if b >= 0:
                values[c] = skel['r'][b]
        values[1] = (0, 1100, 0)
        forward = np.radians(40.0)                                             # the left thigh: knee forward (+z)
        tilt = np.array([[1, 0, 0], [0, np.cos(forward), np.sin(forward)], [0, -np.sin(forward), np.cos(forward)]])
        values[animation.BODY_BONES.index(17)] = bone.euler_xyz_from_matrix(
            tilt @ bone.matrix_from_euler_xyz(skel['r'][17]))
        still = (values, animation.RAW)
        posed = cloth.pose(skel, still)
        self.assertGreater(posed[18][2, 3], 250)                               # (the left knee stands forward)
        before = k['bones']['world'].copy()
        pos = k['prims'][0]['pos'].copy()
        body = legs_and_trunk()
        legs = [c for c in cloth.capsules(skel, body) if skel['names'][c[0]][4:8] in ('MOMO', 'HIZA')]
        to_pose = posed[3] @ np.linalg.inv(bone.world_matrices(skel)[3])

        def outside(world, b, t=1.0):
            p, up = (to_pose @ world[b])[:3, 3], (to_pose @ world[b - 1])[:3, 3]
            p = up + t * (p - up)
            return min(np.linalg.norm(((p - posed[at][:3, 3]) @ posed[at][:3, :3] - offset) /
                                      (size + cloth.SETTLE_MARGIN)) for at, offset, size in legs)
        hit = [c for c in made if min(outside(before, b, t) for b in c['bones'][1:] for t in cloth.SETTLE_ALONG) < 1]
        free = [c for c in made if c not in hit]
        self.assertTrue(hit and free)
        turned, moved = cloth.settle(k, made, skel, [3] * len(made), still, body)
        self.assertGreater(turned, 0)
        self.assertGreater(moved, 0)
        world = k['bones']['world']
        for chain in made:
            for b in chain['bones'][1:]:
                for t in cloth.SETTLE_ALONG:
                    self.assertGreater(outside(world, b, t), 0.99)             # outside the leg, standing
        self.assertTrue(all(c.get('draped') for c in hit))
        self.assertFalse(any(c.get('draped') for c in free))
        for c in hit:                                                          # turned off it, at rest too
            self.assertGreater(max(np.linalg.norm(world[b][:3, 3] - before[b][:3, 3]) for b in c['bones']), 1)
        for c in free:                                                         # clear of it: untouched
            np.testing.assert_allclose(world[c['bones'][-1]], before[c['bones'][-1]])
        self.assertTrue(np.any(np.abs(k['prims'][0]['pos'] - pos) > 20))     # its vertices followed
        np.testing.assert_allclose(k['prims'][0]['pos'][len(drawn):], pos[len(drawn):])   # the body did not


class Graph(unittest.TestCase):
    def test_geodesic_from_the_pinned(self):
        pts = np.array([[0, 0, 0], [0, -10, 0], [0, -20, 0], [5, -20, 0.0]])
        _, adj = cloth._edges(np.array([[0, 1, 2], [1, 2, 3]]), 4)
        g, src = cloth._hang(pts, np.array([True, False, False, False]), adj)
        np.testing.assert_allclose(g[:3], [0, 10, 20])
        self.assertTrue(np.all(src == 0))

    def test_spread_covers(self):
        pts = np.array([[x, 0, 0] for x in range(0, 1000, 10)], float)
        chosen = cloth._spread(pts, 100)
        d = np.min(np.abs(pts[:, None, 0] - pts[chosen][None, :, 0]), 1)
        self.assertLessEqual(d.max(), 100)
        self.assertLess(len(chosen), 12)


if __name__ == '__main__':
    unittest.main()
