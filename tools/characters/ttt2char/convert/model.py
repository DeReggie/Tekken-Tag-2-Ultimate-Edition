"""A Tekken 7 fighter's default costume -> the added fighter's body files: model (.nud), textures (.nut) and
skeleton (.bon). Everything goes into the body files, no costume parts.

1. Tekken 7 side: the costume's skeletal meshes are read from the paks and merged into one skinned mesh with a union
   skeleton. Coordinates go to TTT2's: Y and Z swapped, centimetres -> millimetres, by way of metres in float32 (the
   precision the converted files have always had). Each material's colour is baked into one albedo texture with the
   costume's colours (the formulas of Tekken 7's character shaders, recovered from their compiled pixel shaders).
2. TTT2 side: the donor's skeleton gets the Tekken 7 joint positions (skeleton.py); skin weights go to TTT2 bones
   (four per vertex); triangles become strips; each material is a copy of one of the donor's materials (flags,
   shader properties, texture slots) with new textures: the baked albedo, the normal map, and flat textures of the
   template's own average colour for the other slots.
Textures are at most 512 texels on a side, with at most 3 mip levels (longer chains make the game bind garbage).
"""
import copy

import numpy as np
from PIL import Image

from ..tekken7 import mesh as t7mesh
from ..tekken7.material import Materials, short_ref
from ..tekken7.texture import Texture2D
from ..tekken7.uasset import load
from ..ttt2 import bone, nud, nut
from ..ttt2.archive import key_of
from . import skeleton, strips

GIDX_BASE = 0x10408000          # texture ids above every id the game's own textures use (0x10404fac at most)
MAX_TEX = 512                   # longest side of a converted texture
MIPS = 3                        # mip levels per texture (the game's own fighter textures have 3 or 1)
M_TO_MM = 1000.0


# ------------------------------------------------------------------------------------------------ Tekken 7 side
def _ue_to_ttt2_points(p):
    """UE centimetres (x, y, z) -> (x, z, y) metres in float32 (multiply by M_TO_MM for TTT2)."""
    p = np.asarray(p, np.float32)
    return np.stack([p[..., 0], p[..., 2], p[..., 1]], axis=-1) * 0.01


def _ue_to_ttt2_dirs(d):
    d = np.asarray(d, np.float32)
    return np.stack([d[..., 0], d[..., 2], d[..., 1]], axis=-1)


_SWAP = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], np.float64)


def _ue_to_ttt2_matrix(m):
    out = (_SWAP @ m @ _SWAP).copy()
    out[..., :3, 3] *= 0.01
    return out


def merge_skeletons(parts):
    """Union skeleton of several meshes by bone name (names are case-insensitive). parts: [(tag, mesh, weighted
    bone set)] with the owners first (face joints from the face mesh, body joints from the body meshes).

    A part's bone maps to a merged bone of the same name and parent if their bind matrices agree (0.05 cm, 1e-3)
    or if nothing is skinned to it; a weighted bone that disagrees becomes a copy '<name>@<tag>'. Other bones keep
    their part's bind matrix under the (shared) parent. Generic cloth bone names (transform9, Hair_OPT001, ...) are
    reused by different items under different parents, hence the parent test.
    Returns ({'names', 'parents', 'pose' (float32)}, {tag: part bone -> merged bone})."""
    names, parents, poses, by_name, glob = [], [], [], {}, []
    remaps = {}
    for tag, m, weighted in parts:
        sk = m.skeleton
        g = t7mesh.global_matrices(sk['pose'], sk['parents'])
        remap = np.zeros(len(sk['names']), np.int32)
        for i, nm in enumerate(sk['names']):
            par = sk['parents'][i]
            par_new = int(remap[par]) if par >= 0 else -1
            j = by_name.get(nm.lower())
            if j is not None:
                same = (np.abs(glob[j][:3, 3] - g[i][:3, 3]).max() < 0.05 and
                        np.abs(glob[j][:3, :3] - g[i][:3, :3]).max() < 1e-3)
                if parents[j] == par_new and (same or i not in weighted):
                    remap[i] = j
                    continue
                nm = '%s@%s' % (nm, tag)
                pose = t7mesh.matrix_to_pose(np.linalg.inv(glob[par_new]) @ g[i] if par_new >= 0 else g[i])
            elif par_new >= 0:
                pose = t7mesh.matrix_to_pose(np.linalg.inv(glob[par_new]) @ g[i])
            else:
                pose = sk['pose'][i]
            by_name[nm.lower()] = len(names)
            remap[i] = len(names)
            names.append(nm)
            parents.append(par_new)
            poses.append(np.asarray(pose, np.float32))
            gl = t7mesh.local_matrices(np.asarray(pose)[None])[0]
            glob.append(glob[par_new] @ gl if par_new >= 0 else gl)
        remaps[tag] = remap
    return {'names': names, 'parents': parents, 'pose': np.array(poses)}, remaps


def load_tekken7_model(paks, parts, merge_order):
    """The costume's meshes as one skinned mesh in TTT2 space.
    parts: [(tag, skeletal mesh path)] in mesh order; merge_order: the tags in skeleton-merge order.
    Returns {'bones': {'names', 'parents', 'world' (n, 4, 4) bind matrices, mm}, 'prims': [{'part', 'material',
    'pos' (mm), 'nrm', 'tan', 'uv', 'joints' (n, 8), 'weights' (n, 8), 'tris'}]} (prims share the vertex arrays)."""
    loaded = []
    for tag, path in parts:
        m = t7mesh.SkeletalMesh(load(paks, path))
        loaded.append((tag, m, m.geometry(0)))
    by_tag = {tag: (m, geo) for tag, m, geo in loaded}
    merged, remaps = merge_skeletons(
        [(t, by_tag[t][0], set(np.unique(by_tag[t][1]['joints'][by_tag[t][1]['weights'] > 0]).tolist()))
         for t in merge_order])
    pos, nrm, tan, uvs, jnt, wts, sections = [], [], [], [], [], [], []
    base = 0
    for tag, m, geo in loaded:
        n = len(geo['positions'])
        pos.append(geo['positions'])
        nrm.append(geo['normals'])
        tan.append(geo['tangents'])
        uvs.append(geo['uvs'][:, 0])
        j, w = remaps[tag][geo['joints']], geo['weights']
        if w.shape[1] == 4:
            j = np.concatenate([j, np.zeros_like(j)], 1)
            w = np.concatenate([w, np.zeros_like(w)], 1)
        jnt.append(j)
        wts.append(w)
        for si, s in enumerate(m.lods[0].sections):
            if s.cloth_mapping:                  # the cloth simulation's copy of a disabled section
                continue
            ref = m.materials[s.material_index]['material']
            sections.append((tag, short_ref(ref).split('.')[-1] if ref else 'None', geo['triangles'][si] + base))
        base += n
    # the precision of the vertex streams: float32 metres, normalised float32 weights
    p = _ue_to_ttt2_points(np.concatenate(pos)).astype(np.float64) * M_TO_MM
    nr = _ue_to_ttt2_dirs(np.concatenate(nrm)).astype(np.float32).astype(np.float64)
    tg = np.concatenate(tan).astype(np.float32).copy()
    tg[:, :3] = _ue_to_ttt2_dirs(tg[:, :3])
    tg[:, 3] = -tg[:, 3]                         # the axis swap is a reflection: the bitangent sign flips
    uv = np.concatenate(uvs).astype(np.float32).astype(np.float64)
    weights = np.concatenate(wts).astype(np.float32)
    weights = weights / np.maximum(weights.sum(1, keepdims=True), 1e-8)
    joints = np.where(weights > 0, np.concatenate(jnt), 0).astype(np.uint16).astype(np.int64)
    streams = dict(pos=p, nrm=nr, tan=tg.astype(np.float64), uv=uv, joints=joints, weights=weights.astype(np.float64))
    prims = [dict(part=tag, material=mat, tris=tri.astype(np.uint32)[:, [0, 2, 1]].astype(np.int64), **streams)
             for tag, mat, tri in sections]
    # bind matrices: the inverse bind matrices are kept in float32
    g = t7mesh.global_matrices(merged['pose'], merged['parents'])
    ibm = np.linalg.inv(_ue_to_ttt2_matrix(g)).astype(np.float32)
    world = np.linalg.inv(ibm.astype(np.float64))
    world[:, :3, 3] *= M_TO_MM
    return {'bones': dict(names=merged['names'], parents=merged['parents'], world=world), 'prims': prims}


# ------------------------------------------------------------------------------------------------ albedo baking
MASK_MATERIALS = ('M_CH_Aniso', 'M_CH_aniso', 'M_CH_Base', 'M_CH_Base_mask', 'M_CH_Aniso_machieru')


def srgb_to_linear(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


class Textures:
    """Tekken 7 textures by object path, decoded once."""

    def __init__(self, paks):
        self.paks = paks
        self._cache = {}

    def exists(self, path):
        return bool(path) and self.paks.find(path) is not None

    def get(self, path):
        """-> (RGBA uint8 array, sRGB flag)"""
        if path not in self._cache:
            t = Texture2D(load(self.paks, path))
            self._cache[path] = (t.decode(), t.srgb)
        return self._cache[path]

    def linear(self, path):
        """-> (linear RGB float32, alpha float32)"""
        img, srgb = self.get(path)
        a = img.astype(np.float32) / 255.0
        return (srgb_to_linear(a[..., :3]) if srgb else a[..., :3]), a[..., 3]


def _col(v):
    return np.array([v['r'], v['g'], v['b']], np.float32)


def _resize_to(a, shape):
    if a.shape[:2] == shape:
        return a
    if a.ndim == 2:
        return np.asarray(Image.fromarray(a.astype(np.float32)).resize((shape[1], shape[0]), Image.BILINEAR))
    return np.stack([_resize_to(a[..., c], shape) for c in range(a.shape[-1])], -1)


def bake_albedo(eff, textures):
    """Linear albedo (H, W, 3) and alpha (H, W) of a material instance with its parameters in effect, or (None,
    None) without a colour texture.

    Colour-customisable materials (MF_CH_ColorCustomize):
        C = lerp(lerp(lerp(Color02, Color01, M.r), Color03, M.g), Color04, M.b)    (M = mask texture)
        k = max(1, 1 + 20 (max(M.r, M.g, M.b) - 0.9))
        albedo = D (1 - M.a) + k D C M.a          (the pattern layer is empty in default costumes)
      M_CH_Aniso_machieru also multiplies by Multiply * lerp(DetalDiffuse(uv * Detail_Normal_Scale), 1,
      detail_diffuse_pow).
    Hair (pass 1): lo = sat(BaseLowerContrast); s = (min(Up, 0) + min(Lo, 0) + 1) / (1 - (sat(Up) + sat(Lo)));
        albedo = sat((T - lo) s - min(Lo, 0)) * Color01.
    Skin: lerp(D, luma(D), Desaturation) * Multiply (the view-dependent terms left out).
    Anything else: its colour texture as it is."""
    base = eff['base']
    t, v, s = eff['textures'], eff['vectors'], eff['scalars']
    if base in MASK_MATERIALS:
        D, Da = textures.linear(t['DiffuseMap'])
        M, Ma = textures.linear(t['MaskMap'])
        M, Ma = _resize_to(M, D.shape[:2]), _resize_to(Ma, D.shape[:2])
        C = _col(v['Color02'])[None, None] + M[..., 0:1] * (_col(v['Color01']) - _col(v['Color02']))
        C = C + M[..., 1:2] * (_col(v['Color03']) - C)
        C = C + M[..., 2:3] * (_col(v['Color04']) - C)
        k = np.maximum(1.0, 1.0 + 20.0 * (M.max(-1, keepdims=True) - 0.9))
        out = D * (1 - Ma[..., None]) + k * D * C * Ma[..., None]
        if base == 'M_CH_Aniso_machieru' and t.get('DetalDiffuse'):
            det, _ = textures.linear(t['DetalDiffuse'])
            scale = s.get('Detail_Normal_Scale', 1.0)
            h, w = D.shape[:2]
            yy = ((np.arange(h) + 0.5) / h * scale * det.shape[0]).astype(np.int64) % det.shape[0]
            xx = ((np.arange(w) + 0.5) / w * scale * det.shape[1]).astype(np.int64) % det.shape[1]
            dt = det[yy][:, xx]
            p = s.get('detail_diffuse_pow', 0.0)
            out = out * s.get('Multiply', 1.0) * (dt + p * (1 - dt))
        return np.clip(out, 0, 1), Da
    if base.startswith('M_CH_AnisoHair'):
        T, Ta = textures.linear(t['ColorTexture'])
        lo_, up_ = s.get('BaseLowerContrast', 0.0), s.get('BaseUpperContrast', 0.0)
        lo = np.clip(lo_, 0, 1)
        sc = (min(up_, 0) + min(lo_, 0) + 1) / (1 - (np.clip(up_, 0, 1) + np.clip(lo_, 0, 1)))
        return np.clip((T - lo) * sc - min(lo_, 0), 0, 1) * _col(v['Color01']), Ta
    if base == 'M_CH_skin_wet_SSP':
        D, Da = textures.linear(t['Diffuse'])
        luma = (D * np.array([0.3, 0.59, 0.11], np.float32)).sum(-1, keepdims=True)
        out = (D + s.get('Desaturation', 0.0) * (luma - D)) * s.get('Multiply', 1.0)
        return np.clip(out, 0, 1), Da
    for slot in ('DiffuseMap', 'Diffuse', 'Color', 'ColorTexture'):
        if textures.exists(t.get(slot)):
            return textures.linear(t[slot])
    return None, None


def albedo_image(rgb, alpha):
    """The baked albedo as an 8-bit sRGB image (RGBA only where some texel is not opaque)."""
    a = (linear_to_srgb(rgb) * 255 + 0.5).astype(np.uint8)
    if alpha is not None and (alpha < 1).any():
        a = np.concatenate([a, (np.clip(alpha, 0, 1) * 255 + 0.5).astype(np.uint8)[..., None]], -1)
    return Image.fromarray(a)


# ------------------------------------------------------------------------------------------------ TTT2 side
def pow2_size(w, h, cap=MAX_TEX):
    def p2(x):
        return 1 << max(2, int(round(np.log2(max(4, x)))))
    s = min(1.0, cap / max(w, h))
    return min(cap, p2(w * s)), min(cap, p2(h * s))


class TextureBank:
    """The new textures, numbered from GIDX_BASE in the order they are made; identical requests share one."""

    def __init__(self):
        self.textures, self.by_key = [], {}

    def add(self, key, rgba, fmt):
        if key not in self.by_key:
            self.by_key[key] = GIDX_BASE + len(self.textures)
            self.textures.append(nut.make_texture(rgba, self.by_key[key], fmt, mips=MIPS))
        return self.by_key[key]

    def constant(self, rgba, fmt, size=32):
        img = np.zeros((size, size, 4), np.uint8)
        img[:] = rgba
        return self.add(('const', tuple(int(x) for x in rgba), fmt), img, fmt)

    def image(self, key, im, fmt, alpha):
        if ('img', key, fmt, alpha) in self.by_key:
            return self.by_key[('img', key, fmt, alpha)]
        im = im.convert('RGBA')
        a = np.array(im.resize(pow2_size(*im.size), Image.LANCZOS))
        if not alpha:
            a[..., 3] = 255
        return self.add(('img', key, fmt, alpha), a, fmt)

    def normal(self, key, im):
        """A Tekken 7 normal map (R = X, G = Y towards +v) -> TTT2's BC3 layout (A = X, G = Y towards -v)."""
        if ('nrm', key) in self.by_key:
            return self.by_key[('nrm', key)]
        im = im.convert('RGB')
        w, h = pow2_size(*im.size)
        a = np.array(im.resize((w, h), Image.LANCZOS))
        out = np.zeros((h, w, 4), np.uint8)
        out[..., 3] = a[..., 0]
        out[..., 1] = 255 - a[..., 1]
        return self.add(('nrm', key), out, 2)


def find_mesh(model, name):
    for m in model['meshes']:
        if m['name'] == name:
            return m
    raise ValueError('the donor model has no mesh %s' % name)


def load_templates(archives, templates, texture_sources):
    """Material templates from the donor's files. templates: {kind: (entry name or key, mesh name, polygon)};
    texture_sources: NUTs (names or keys) holding the templates' textures (a later one wins).
    -> {kind: (material, vertex type, slots [{'fmt', 'mean' RGBA or None}])}"""
    def read(ref):
        return archives.read(key_of(ref) if isinstance(ref, str) else ref)
    found = {}
    for src in texture_sources:
        for t in nut.read(read(src))['textures']:
            found[t['gidx']] = t
    models, out = {}, {}
    for kind, (src, mesh_name, poly_index) in templates.items():
        if src not in models:
            models[src] = nud.read(read(src))
        poly = find_mesh(models[src], mesh_name)['polys'][poly_index]
        slots = []
        for t in poly['materials'][0]['textures']:
            tex = found.get(t['id'])
            mean = nut.decode(tex).reshape(-1, 4).mean(0).round().astype(int) if tex is not None else None
            slots.append(dict(fmt=tex['fmt'] if tex is not None else 0, mean=mean))
        out[kind] = (copy.deepcopy(poly['materials'][0]), poly['vtype'], slots)
    return out


ORDER = {'mouth': 0, 'skin': 0, 'cloth': 0, 'eye': 1, 'hair': 2, 'overlay': 3}   # draw order of a mesh's polygons


def convert(paks, archives, d, log=print):
    """d: the character definition. -> (nud bytes, nut bytes, bon bytes)"""
    t7 = d.TEKKEN7
    k = load_tekken7_model(paks, t7['parts'], t7['merge_order'])
    log('  Tekken 7 model: %d bones, %d sections' % (len(k['bones']['names']), len(k['prims'])))
    donor = bone.read(archives.read_name(d.DONOR + '.bon'))
    skel = skeleton.build(k['bones'], donor)
    names = [n[4:] if n.startswith('cha:') else n for n in skel['names']]
    bidx = {n: i for i, n in enumerate(names)}
    weight_maps = {tag: skeleton.weight_map(k['bones'], skel['names'], lambda i, tag=tag: tag)[0]
                   for tag, _ in t7['parts']}
    templates = load_templates(archives, d.TEMPLATES, d.TEMPLATE_TEXTURES)
    materials = Materials(paks)
    colours = materials.costume_colours(t7['costume'])
    textures = Textures(paks)
    mat_paths = {}
    for tag, path in t7['parts']:
        m = t7mesh.SkeletalMesh(load(paks, path))
        for x in m.materials:
            if x['material']:
                ref = short_ref(x['material'])
                mat_paths.setdefault(ref.split('.')[-1], ref)
    bank = TextureBank()
    built = {}

    def build_material(name):
        kind, use_normal, alpha = d.MATERIALS[name]
        mat, vtype, slots = templates[kind]
        if name not in built:
            eff = materials.effective(mat_paths[name], colours)
            rgb, al = bake_albedo(eff, textures)
            if rgb is None:
                raise ValueError('material %s has no colour texture' % name)
            built[name] = albedo_image(rgb, al), eff['textures'].get('Normal') if use_normal else None
        albedo, normal = built[name]
        mat = copy.deepcopy(mat)
        ids = []
        for i, slot in enumerate(slots):
            if i == 0:
                ids.append(bank.image(name, albedo, 2 if alpha else 0, alpha))
            elif i == 1 and slot['mean'] is not None and abs(slot['mean'][1] - 128) < 8 and \
                    abs(slot['mean'][3] - 128) < 8:
                # a normal map slot (R = 0, G = Y, B = 0, A = X)
                if textures.exists(normal):
                    ids.append(bank.normal(normal, Image.fromarray(textures.get(normal)[0])))
                else:
                    ids.append(bank.constant((0, 128, 0, 128), 2))
            else:
                mean = slot['mean'] if slot['mean'] is not None else np.array([128, 128, 128, 255])
                ids.append(bank.constant(tuple(mean), slot['fmt']))
        for t, gid in zip(mat['textures'], ids):
            t['id'] = gid
        return mat, vtype, kind

    meshes, dropped = {}, []
    for prim in k['prims']:
        name = prim['material']
        if name not in d.MATERIALS:
            raise ValueError('the character definition does not say what to do with material %s' % name)
        if d.MATERIALS[name] is None:
            dropped.append(name)
            continue
        mat, vtype, kind = build_material(name)
        used = np.unique(prim['tris'])
        remap = np.full(len(prim['pos']), -1, np.int64)
        remap[used] = np.arange(len(used))
        tris = remap[prim['tris']]
        n = len(used)
        if n >= 0xFFFF:
            raise ValueError('section of %s has too many vertices for one NUD polygon' % name)
        pos = prim['pos'][used]
        nrm = prim['nrm'][used]
        # winding: TTT2's front faces are counter-clockwise around the vertex normal; orient by the normals
        g = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
        if float(((g * nrm[tris].sum(1)).sum(1) < 0).mean()) > 0.5:
            tris = tris[:, [0, 2, 1]]
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        uv = prim['uv'][used]
        # skin weights: Tekken 7 bones -> TTT2 bones, merged, the four largest, renormalised
        tj = weight_maps[prim['part']][prim['joints'][used]]
        tw = prim['weights'][used]
        bones = np.zeros((n, 4), np.int64)
        wts = np.zeros((n, 4))
        for v in range(n):
            acc = {}
            for j, w in zip(tj[v], tw[v]):
                if w > 0:
                    acc[int(j)] = acc.get(int(j), 0.0) + float(w)
            top = sorted(acc.items(), key=lambda x: -x[1])[:4]
            s = sum(w for _, w in top)
            for q, (j, w) in enumerate(top):
                bones[v, q] = j
                wts[v, q] = w / s
            for q in range(len(top), 4):
                bones[v, q] = top[0][0]
        # tangent frame: TTT2's tangent is +dP/du, its bitangent -dP/dv
        tan = prim['tan'][used][:, :3]
        tan = tan - nrm * (tan * nrm).sum(1, keepdims=True)
        tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-9)
        a, b, c = tris.T
        e1, e2 = pos[b] - pos[a], pos[c] - pos[a]
        du1, dv1 = uv[b, 0] - uv[a, 0], uv[b, 1] - uv[a, 1]
        du2, dv2 = uv[c, 0] - uv[a, 0], uv[c, 1] - uv[a, 1]
        det = du1 * dv2 - du2 * dv1
        ok = np.abs(det) > 1e-12
        dPdv = (e2 * du1[:, None] - e1 * du2[:, None]) / np.where(ok, det, 1)[:, None]
        acc = np.zeros((n, 3))
        for col in (a, b, c):
            np.add.at(acc, col[ok], dPdv[ok])
        bit = np.cross(nrm, tan)
        bit *= np.where((bit * -acc).sum(1) >= 0, 1.0, -1.0)[:, None]
        # the template's vertex type when it has float bone weights, else 0x13 (u32 bones, f32 weights,
        # f32 normal / bitangent / tangent)
        vt = vtype if (vtype & 0xF0) == 0x10 else 0x13
        verts = np.zeros(n, nud.vertex_dtype(vt, 0x10))
        verts['pos'] = pos
        if 'pw' in verts.dtype.names:
            verts['pw'] = 100.0                      # what the game's files store
        verts['nrm'][:, :3] = nrm
        verts['nrm'][:, 3] = 1.0
        if 'tan' in verts.dtype.names:
            verts['tan'][:, :3] = tan
            verts['tan'][:, 3] = 1.0
            verts['bitan'][:, :3] = bit
            verts['bitan'][:, 3] = 1.0
        verts['bones'] = bones
        verts['w'] = wts
        verts['uv'][:, 0, :] = uv
        strip = strips.stripify(tris)
        if not strips.check(tris, strip) or len(strip) >= 0x10000:
            raise ValueError('could not make triangle strips for %s' % name)
        meshes.setdefault(prim['part'], []).append(dict(vtype=vt, uvtype=0x10, pflag=4, tail=bytes(12),
                                                        indices=np.array(strip, np.uint16), verts=verts,
                                                        materials=[mat], _order=ORDER[kind]))
    nmeshes = []
    for tag in sorted(meshes, key=lambda p: d.MESHES[p][2]):
        mname, singlebind, _ = d.MESHES[tag]
        polys = sorted(meshes[tag], key=lambda p: p['_order'])
        for p in polys:
            del p['_order']
        sph = nud.bounding_sphere(np.concatenate([p['verts']['pos'] for p in polys]))
        nmeshes.append(dict(name=mname, sphere=sph, center=sph[:3], sort_bias=0.0, zero=0, boneflag=0x2c,
                            singlebind=bidx[singlebind], polys=polys))
    allp = np.concatenate([p['verts']['pos'] for m in nmeshes for p in m['polys']])
    model = dict(version=0x0201, sphere=nud.bounding_sphere(allp), bone_first=None, meshes=nmeshes)
    log('  model: %d meshes, %d polygons, %d textures (dropped: %s)' % (
        len(nmeshes), sum(len(m['polys']) for m in nmeshes), len(bank.textures), ', '.join(dropped) or 'none'))
    return nud.write(model), nut.write(bank.textures), bone.write(skel)
