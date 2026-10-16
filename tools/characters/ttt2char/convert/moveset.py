"""A Tekken 7 fighter's moveset -> a TTT2 moveset (motbin) and motion pack for the added fighter.

The base is the donor's moveset and motion pack: its generic moves, the tag system, the embedded MOTAs, the hand,
face and camera animations. The Tekken 7 fighter's own moves (in its moveset but neither the donor's nor Tekken 7
Heihachi's) are converted and appended; the generic "hub" moves that lead into them (standing, crouching, ...) get
the Tekken 7 fighter's cancel lists, converted, plus the donor's cancels into TTT2-only moves (tag out, ...).

Converting a move: requirement and property ids through the derived id maps (idmaps.py), hit location codes
likewise, the bitfield bit-reversed (TTT2 bit 31 - i = Tekken 7 bit i), move ids by name, animations by reference:
0x8000 | i when the animation is in TTT2's common motions (data004), 0x4000 | i when the donor's pack has it,
otherwise it is appended (byte-swapped) to the pack's body MOTA. Whatever cannot be mapped is dropped with the
cancel, hit-condition entry or property that holds it, and counted; nothing is guessed.
"""
import collections
import copy
import hashlib
import re
import struct

from ..movesets import REACTION_MOVE_FIELDS, TABLE_ORDER, TTT2
from ..ttt2 import motbin, motion
from . import idmaps as M

T7_END, TT_END = M.END_REQ['t7'], M.END_REQ['ttt2']
SEQ0 = 0x800D                       # a cancel direction from here on names an input sequence

# ------------------------------------------------------------------------------------------------ rules
# Tekken 7 requirement ids that are always false in TTT2 (the mode or system does not exist there)
REQ_FALSE = {157: 'rage', 636: 'assist button', 811: 'basic combo', 558: 'story battle', 559: 'story battle no.',
             560: 'customization', 563: 'game mode', 634: 'treasure battle', 765: 'arcade cutscene',
             830: 'power crush absorption', 809: 'assist combo value', 810: 'assist combo', 807: 'assist combo'}
CHAR_IS, CHAR_IS_NOT = {217, 219, 223}, {218}     # "player / opponent is character <roster id>" requirements
# Tekken 7's screw state does not exist in TTT2: its requirement and properties become TTT2's bound. The alignment
# has no evidence for these ids; the pairs are format facts as the community's moveset tools record them (README:
# Acknowledgements)
REQ_OVERRIDE = {615: 467}
PROP_OVERRIDE = {0x8255: 0x8193, 0x8256: 0x8194}
# Tekken 7 properties left out (Tekken 7-only presentation or mechanics, or values not converted yet)
PROP_DROP = {0x828f: 'tiger animation', 0x828e: 'projectile index', 0x81bd: 'power crush',
             0x81be: 'rage art fx', 0x801b: 'rage drive vfx', 0x8233: 'rage drive bg', 0x8234: 'rage drive bg',
             0x8272: 'spend rage', 0x828b: 'game speed', 0x828c: 'slow motion', 0x828d: 'slow motion immunity',
             0x829d: 'HUD', 0x829f: 'subtitles', 0x8243: 'subtitles', 0x82bf: 'assist vfx',
             0x8414: 'assist combo value', 0x842e: 'hand animation (Tekken 7 hand codec not converted)',
             0x842f: 'hand animation', 0x8435: 'camera/item animation id', 0x8049: 'item id', 0x8343: 'attach item',
             0x8344: 'detach item'}
SOUND_PROPS = {0x84c4, 0x84c6}       # value = bank << 24 | n: kept only where the donor uses the same value,
# or a voice of the fighter's own banks (convert/voice.py): shout n (bank 2) and damage voice n (bank 3), numbered
# alike in both games (their SE_KIAI_n / SE_YARARE_n test moves), up to the last number TTT2 has
OWN_VOICE = {2: 0xE, 3: 0xA}
# A win quote: TTT2's win poses play a tone of the fighter's se_Dwi bank with this property (value | tone); Tekken 7
# plays its win quote by the pose's name. The donor's poses stay, with the animation of the quote at their tone.
WIN_QUOTE_PROP, WIN_QUOTE_VALUE = 0x82F9, 0x0E003000
VALUE_KIND = {0x8331: 'reaction', 0x8332: 'reaction', 0x843c: 'throwcam', 0x843d: 'throwcam', 0x820b: 'projectile'}
# Projectiles (Kazumi's tiger). Tekken 7 spawns one with five properties on the same frame: limb 0x820c, offsets
# 0x820d/0x820e/0x820f, then 0x820b = the projectile's index. TTT2 has the same set at 0x8169 (limb; resets the
# offsets), 0x816a/0x816b/0x816c (offset = the value as a signed 16-bit number) and 0x8168 (spawn projectile
# <value>): handlers in its property interpreter (sub_03AE86A0), used in the same order by its balloon and cloche
# items. The alignment has no evidence for these ids (no Heihachi move spawns a projectile).
PROJ_PROPS = {0x820b: 0x8168, 0x820c: 0x8169, 0x820d: 0x816a, 0x820e: 0x816b, 0x820f: 0x816c}
# A projectile row, Tekken 7 (42 x u32) -> TTT2 (34 x u32): (TTT2 field, Tekken 7 field, count). TTT2's fields as
# its projectile code reads them: 0 effect, 1 delay, 2 forward speed, 3 upward speed, 4 hits it can deal, 5 frames
# it lives, 6 shape (0 sphere, 1 cylinder), 7 radius, 8 height, 9 hit level, 14 sound at spawn, 16 sound on hit,
# 18 sound when it runs out, 19 hit conditions, 20 cancels (both table indices, 0 = none), 21 hits the owner's
# team, 22 hits the other team, 23..33 a hit effect (on when 23 != 0 and 26 > 0). Tekken 7's are the same with
# five more fields after the effect and 64-bit links (hit conditions at 24, cancels at 26).
PROJ_FIELDS = [(1, 6, 3), (4, 9, 15), (21, 28, 13)]
PROJ_SOUNDS = (14, 16, 18)
PROJ_EFFECT = 0                 # Tekken 7's effect ids mean nothing in TTT2: none
# the fighter's own moves that are not converted: Rage Arts / Drives, story, customisation, cinematics
DROP_MOVES = r'RageArts|_EX\d?$|^b7_|^vra_|_7CS$|^Story|^FACE'
# Tekken 7 generic moves (also Heihachi's, not in TTT2) converted when a reaction needs them, except these
DROP_T_RE = re.compile(r'Balcony|_RA$|RAtk|RageArt|^vra_|_7CS$|^SE_|^FACE|Story|^b7_')
ANIM_KEY_BYTES = 256                 # animations are matched by a hash of their first bytes


def rev32(v):
    return int('{:032b}'.format(v)[::-1], 2)


def classify(k, h7, donor):
    """Per move of the Tekken 7 fighter: 'G' generic (the donor has it), 'T' Tekken 7 generic (Tekken 7 Heihachi
    has it), 'K' the fighter's own."""
    g = set(donor.move_name(i) for i in range(len(donor.tables['moves'])))
    t = set(h7.move_name(i) for i in range(len(h7.tables['moves'])))
    return ['G' if n in g else ('T' if n in t else 'K') for n in (k.move_name(i) for i in range(len(k.tables['moves'])))]


def _anim_key(buf):
    return hashlib.sha1(buf[:ANIM_KEY_BYTES]).hexdigest()


def anim_index(sources):
    """sources: [(tag, data, MOTA offset)] -> {key: [(tag, index)]}"""
    idx = collections.defaultdict(list)
    for tag, d, o in sources:
        for i, a in enumerate(motion.mota_offsets(d, o)[1]):
            idx[_anim_key(d[o + a:o + a + ANIM_KEY_BYTES])].append((tag, i))
    return idx


class Converter:
    def __init__(self, k, h7, donor, donor_pack, h2, common_motions, maps, usage, newid, d):
        """k, h7: the fighter's and Tekken 7 Heihachi's movesets (tkmvst.read); donor: the donor's motbin
        (motbin.read) and its motion pack; h2: TTT2 Heihachi's motbin; common_motions: data004's common MOTA;
        maps: (requirement map, property map, reaction remap, hitbox remap); usage: idmaps.ttt2_usage;
        newid: the new fighter's motion row; d: the character definition."""
        self.k, self.h7, self.d, self.h2 = k, h7, donor, h2
        self.donor_pack = donor_pack
        self.newid = newid
        self.k_id = k.character_id
        self.defn = d
        self.req_map, self.prop_map, self.react_remap, self.hitbox = maps
        self.usage = usage
        self.stats = collections.Counter()
        self.unmapped = collections.Counter()
        self.T = copy.deepcopy(donor.tables)
        self.strings = bytearray(donor.raw[motbin.BASE:motbin.BASE + donor.table_info['reactions'][0]])
        while self.strings and self.strings[-1] == 0:      # trailing alignment
            self.strings.pop()
        self.strings.append(0)
        self.str_off = {}
        self.dn = {donor.move_name(i): i for i in range(len(donor.tables['moves']))}
        self.kn = {k.move_name(i): i for i in range(len(k.tables['moves']))}
        self.cls = classify(k, h7, donor)
        t7names = set(self.kn) | set(h7.move_name(i) for i in range(len(h7.tables['moves'])))
        h2names = set(h2.move_name(i) for i in range(len(h2.tables['moves'])))
        self.ttt2_only_generic = {n for n in self.dn if n in h2names and n not in t7names}
        self.cache = {}
        self.donor_sound = collections.defaultdict(set)
        for t in ('extra_move_properties', 'move_begin_props', 'move_end_props'):
            for x in donor.tables[t]:
                self.donor_sound[x['id']].add(x['value'])
        self.donor_clips = {v['value'] for v in donor.tables['voiceclips']} - {0xFFFFFFFF}
        self.known_sounds = set(self.donor_clips)
        for pid in (0x82f9, 0x82fb):                 # player / opponent sound
            self.known_sounds |= self.donor_sound[pid]
        self.voice = True               # the fighter has its own voice banks (convert/voice.py)
        # animations already in TTT2: the common motions and the donor's own pack
        o0 = motion.pack_items(donor_pack)[0][0]
        idx = anim_index([('common', common_motions, 0), ('donor', donor_pack, o0)])
        self.anim_src = {off: idx.get(_anim_key(motion.swap_animation(k.animbuf[off:off + k.anim_size[off]], '<')), [])
                         for off in k.anim_offsets}
        self.pack0_count = len(motion.mota_offsets(donor_pack, o0)[1])
        self.new_anims, self.anim_id = [], {}
        self.seq_index = {}
        T = self.T
        for i, s in enumerate(T['input_sequences']):
            key = (s['window'], tuple((x['direction'], x['button'])
                                      for x in T['inputs'][s['inputs']:s['inputs'] + s['amount']]))
            self.seq_index.setdefault(key, i)
        self.extra_index = {}
        for j, e in enumerate(T['cancel_extras']):
            self.extra_index.setdefault(e['value'], j)
        self.drop_moves = re.compile(DROP_MOVES + '|' + d.MOVESET['drop_moves'])

    # --- helpers ----------------------------------------------------------------------------------------
    def string(self, s):
        if s not in self.str_off:
            self.str_off[s] = len(self.strings)
            self.strings += s.encode('latin1') + b'\0'
        return self.str_off[s]

    def add(self, table, row):
        self.T[table].append(row)
        return len(self.T[table]) - 1

    # --- ids --------------------------------------------------------------------------------------------
    def map_req(self, c):
        if c == T7_END:
            return TT_END
        if c in REQ_OVERRIDE:
            return REQ_OVERRIDE[c]
        if c in REQ_FALSE:
            return None
        b, how = (self.req_map if c < 0x8000 else self.prop_map).lookup(c)
        if how in ('observed', 'observed-exception', 'interpolated') and b is not None:
            if b in self.usage['req' if b < 0x8000 else 'prop']:
                return b
            self.stats['requirement id no TTT2 moveset uses -> false'] += 1
            return None
        self.unmapped[('req' if c < 0x8000 else 'req-prop', c)] += 1
        return None

    def map_prop(self, p):
        if p in PROP_OVERRIDE:
            return PROP_OVERRIDE[p]
        if p in PROJ_PROPS:
            return PROJ_PROPS[p]
        if p in PROP_DROP:
            self.stats['property dropped: ' + PROP_DROP[p]] += 1
            return None
        b, how = self.prop_map.lookup(p)
        if how in ('observed', 'observed-exception', 'interpolated') and b is not None:
            return b
        self.unmapped[('prop', p)] += 1
        return None

    def target(self, mid):
        """A Tekken 7 move id (or alias slot) -> the new moveset's move id, or None."""
        if mid is None:
            return None
        if mid >= 0x8000:
            return mid if mid < 0x8000 + 56 else None     # alias slots mean the same in both games
        if mid >= len(self.k.tables['moves']):
            return None
        if mid in self.newidx:
            return self.newidx[mid]
        n = self.k.move_name(mid)
        if n in self.dn:
            return self.dn[n]
        r = self.react_remap.get(n)
        if r and r in self.dn:
            self.stats['target remapped (Tekken 7-only move -> the TTT2 move in its place)'] += 1
            return self.dn[r]
        if self.alloc_ok and self.cls[mid] == 'T' and not DROP_T_RE.search(n):
            idx = len(self.T['moves'])
            self.newidx[mid] = idx
            self.T['moves'].append(self.conv_move(mid))
            self.queue.append(mid)
            self.stats['Tekken 7 generic moves converted (needed by reactions)'] += 1
            return idx
        return None

    # --- lists ------------------------------------------------------------------------------------------
    def conv_reqs(self, i):
        """A Tekken 7 requirement list -> (the new list's index, ok); ok False: the list can never be true."""
        if i is None:
            return None, True
        key = ('req', i)
        if key in self.cache:
            return self.cache[key]
        rows, res = [], None
        for c, p in M.reqs(self.k, i):
            if c in CHAR_IS or c in CHAR_IS_NOT:
                if p == self.k_id:
                    p = self.newid
                elif c in CHAR_IS_NOT:            # "is not <another character>": true
                    self.stats['character requirement "is not X" dropped (true)'] += 1
                    continue
                else:                             # "is <another character>": false
                    self.stats['character requirement "is X" -> false'] += 1
                    res = (None, False)
                    break
            c2 = self.map_req(c)
            if c2 is None:
                res = (None, False)
                break
            if c == 0x81dc:                       # the parameter is a move id
                t = self.target(p)
                if t is None:
                    res = (None, False)
                    break
                p = t
            elif c in (817, 823):                 # parry lists: not converted
                self.stats['parry requirement -> false'] += 1
                res = (None, False)
                break
            rows.append({'condition': c2, 'param': p})
        if res is None:
            rows.append({'condition': TT_END, 'param': 0})
            start = len(self.T['requirements'])
            self.T['requirements'] += rows
            res = (start, True)
        self.cache[key] = res
        return res

    def conv_cancel_list(self, i, table='cancels', end=M.LIST_END):
        """The converted rows of the Tekken 7 cancel list at i (its end row included)."""
        out = []
        nseq = len(self.k.tables['input_sequences'])
        for c in M.cancels(self.k, i, table, end):
            d = dict(direction=c['direction'], button=c['button'], req=None, extradata=None,
                     win_start=c['win_start'], win_end=c['win_end'], start_frame=c['start_frame'],
                     move_id=c['move_id'], option=0)
            if c['direction'] in (M.LIST_END, M.GROUP_END):
                d['req'], _ = self.conv_reqs(c['req'])
                d['extradata'] = self.extradata(c['extradata'])
                if c['direction'] == M.LIST_END:
                    d['move_id'] = self.target(c['move_id']) or 0
                out.append(d)
                break
            d['req'], ok = self.conv_reqs(c['req'])
            if not ok:
                self.stats['cancel dropped: requirement'] += 1
                continue
            if c['direction'] == M.GROUP:
                d['move_id'] = self.conv_group(c['move_id'])
            else:
                if SEQ0 <= c['direction'] < SEQ0 + nseq:
                    d['direction'] = SEQ0 + self.conv_seq(c['direction'] - SEQ0)
                t = self.target(c['move_id'])
                if t is None:
                    self.stats['cancel dropped: target not converted'] += 1
                    continue
                d['move_id'] = t
            d['extradata'] = self.extradata(c['extradata'])
            out.append(d)
            self.stats['cancels converted'] += 1
        return out

    def conv_group(self, gi):
        key = ('group', gi)
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = None
        rows = self.conv_cancel_list(gi, 'group_cancels', M.GROUP_END)
        start = len(self.T['group_cancels'])
        self.T['group_cancels'] += rows
        self.cache[key] = start
        return start

    def conv_seq(self, si):
        key = ('seq', si)
        if key in self.cache:
            return self.cache[key]
        s = self.k.tables['input_sequences'][si]
        rows = [(x['direction'], x['button']) for x in self.k.tables['inputs'][s['inputs']:s['inputs'] + s['amount']]]
        k2 = (min(s['window'], 255), tuple(rows))
        if k2 in self.seq_index:
            idx = self.seq_index[k2]
        else:
            start = len(self.T['inputs'])
            for dr, bt in rows:
                self.T['inputs'].append(dict(direction=dr, button=bt))
            idx = self.add('input_sequences', dict(s_00=0, window=k2[0], amount=len(rows), inputs=start))
            self.seq_index[k2] = idx
        self.cache[key] = idx
        return idx

    def extradata(self, i):
        if i is None:
            return None
        v = self.k.tables['cancel_extras'][i]['value'] & ~0x84000     # Tekken 7-only bits (0x84080 -> 128)
        if v not in self.extra_index:
            self.extra_index[v] = self.add('cancel_extras', {'value': v})
        return self.extra_index[v]

    def conv_value(self, t7id, v):
        kind = VALUE_KIND.get(t7id)
        if kind == 'throwcam':
            return self.conv_throwcam(v)
        if kind == 'reaction':
            return self.conv_reaction(v)
        if kind == 'projectile':
            return self.conv_projectile(v)
        if t7id in SOUND_PROPS and v not in self.donor_sound[self.prop_map.lookup(t7id)[0]] and not self.own_voice(v):
            return None
        return v

    def own_voice(self, v):
        return self.voice and (v & 0xFFFFFF) <= OWN_VOICE.get(v >> 24, -1)

    def conv_voiceclips(self, i):
        """A Tekken 7 voice clip list -> the new list's index (its own voices kept), or None."""
        vals = [v for v in M.voices(self.k, i) if self.own_voice(v) or v in self.donor_clips]
        if not vals:
            return None
        start = len(self.T['voiceclips'])
        self.T['voiceclips'] += [{'value': v} for v in vals] + [{'value': 0xFFFFFFFF}]
        return start

    def conv_xps(self, i):
        if i is None:
            return None
        rows = []
        for f, idv, v in M.xps(self.k, i):
            if idv == 0 and f == 0:
                break
            p = self.map_prop(idv) if idv >= 0x8000 else self.map_req(idv)
            if p is None:
                continue
            v2 = self.conv_value(idv, v)
            if v2 is None:
                self.stats['property dropped: value (sound bank / index)'] += 1
                continue
            rows.append(dict(frame=f, id=p, value=v2))
        if not rows:
            return None
        rows.append(dict(frame=0, id=0, value=0))
        start = len(self.T['extra_move_properties'])
        self.T['extra_move_properties'] += rows
        return start

    def conv_props(self, table, i):
        if i is None:
            return None
        rows = []
        for _, p in self.k.iter_list(table, i, lambda p: p['id'] == T7_END):
            if p['id'] == T7_END:
                break
            pid = self.map_prop(p['id']) if p['id'] >= 0x8000 else self.map_req(p['id'])
            if pid is None:
                continue
            r, ok = self.conv_reqs(p['req'])
            if not ok:
                self.stats['property dropped: requirement'] += 1
                continue
            v2 = self.conv_value(p['id'], p['value'])
            if v2 is None:
                self.stats['property dropped: value (sound bank / index)'] += 1
                continue
            rows.append(dict(req=r if r is not None else 0, id=pid, value=v2))
        if not rows:
            return None
        rows.append(dict(req=0, id=TT_END, value=0))
        start = len(self.T[table])
        self.T[table] += rows
        return start

    def conv_throwcam(self, ti):
        key = ('tc', ti)
        if key not in self.cache:
            t = self.k.tables['throw_cameras'][ti]
            cd = self.add('camera_data', dict(self.k.tables['camera_data'][t['camera_data']]))
            self.cache[key] = self.add('throw_cameras', dict(side=t['side'] & 0xFFFFFFFF, camera_data=cd))
        return self.cache[key]

    def conv_pushback(self, pi):
        if pi is None:
            return None
        key = ('pb', pi)
        if key not in self.cache:
            p = self.k.tables['pushbacks'][pi]
            ex = None
            if p['extradata'] is not None:
                ex = len(self.T['pushback_extras'])
                for q in range(p['loops']):
                    self.T['pushback_extras'].append(dict(self.k.tables['pushback_extras'][p['extradata'] + q]))
            self.cache[key] = self.add('pushbacks', dict(duration=p['duration'], displacement=p['displacement'],
                                                         loops=p['loops'], extradata=ex))
        return self.cache[key]

    def conv_reaction(self, ri):
        key = ('react', ri)
        if key in self.cache:
            return self.cache[key]
        r = self.k.tables['reactions'][ri]
        row = {}
        self.alloc_ok += 1
        for nm, off, fmt, link in TTT2['reactions'][1]:
            if link == 'pushbacks':
                row[nm] = self.conv_pushback(r[nm])
            elif link == 'move':
                t = self.target(r[nm])
                if t is None:
                    self.stats['reaction slot -> fallback'] += 1
                    n = self.k.move_name(r[nm]) if r[nm] < len(self.k.tables['moves']) else r[nm]
                    t = self.similar(n) if isinstance(n, str) else None
                    if t is None:
                        t = self.slot_default[nm]
                row[nm] = t
            else:
                row[nm] = r[nm]
        self.alloc_ok -= 1
        idx = self.add('reactions', row)
        self.cache[key] = idx
        return idx

    def similar(self, n):
        """The donor move whose name shares the longest prefix (7 characters at least) with n."""
        best, bl = None, 6
        for dn_, j in self.dn.items():
            l = 0
            for a, b in zip(n, dn_):
                if a != b:
                    break
                l += 1
            if l > bl or (l == bl and best is not None and len(dn_) < len(self.d.move_name(best))):
                best, bl = j, l
        return best

    def conv_projectile(self, pi):
        """A Tekken 7 projectile index -> the new moveset's projectile index (the row appended), or None."""
        t = self.k.tables['projectiles']
        if not 0 < pi < len(t):
            return None
        key = ('proj', pi)
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = None                    # a cancel that respawns this projectile: not converted
        p = t[pi]
        v = struct.unpack('<42I', p['raw'])
        out = [0] * 34
        out[0] = PROJ_EFFECT
        for to, fr, n in PROJ_FIELDS:
            out[to:to + n] = v[fr:fr + n]
        for f in PROJ_SOUNDS:
            if out[f] and out[f] not in self.known_sounds and not self.own_voice(out[f]):
                out[f] = 0
                self.stats['projectile sound dropped'] += 1
        n0 = len(self.T['hit_conditions'])
        hc = self.conv_hitconds(p['hit_condition'])
        out[19] = hc if hc is not None and len(self.T['hit_conditions']) > n0 else 0
        out[20] = self.conv_proj_cancels(p['cancel'])
        idx = self.add('projectiles', {'raw': struct.pack('>34I', *out)})
        self.cache[key] = idx
        self.stats['projectiles converted'] += 1
        return idx

    def conv_proj_cancels(self, i):
        """A projectile's cancel list -> its new index, 0 if nothing but the end row is left. TTT2 runs it every
        frame of the projectile's life: a row whose window and requirements hold applies its properties (the
        requirement list's ids >= 0x8000) to the owner; with option 0x40 the projectile turns into projectile
        move_id."""
        if i is None:
            return 0
        rows = []
        for c in M.cancels(self.k, i):
            end = c['direction'] == M.LIST_END
            r, ok = self.conv_reqs(c['req'])
            if not ok and not end:
                self.stats['projectile cancel dropped: requirement'] += 1
                continue
            m = 0
            if not end and c['option'] & 0x40:
                m = self.conv_projectile(c['move_id'])
                if m is None:
                    self.stats['projectile cancel dropped: target'] += 1
                    continue
            rows.append(dict(direction=c['direction'], button=c['button'], req=r,
                             extradata=self.extradata(c['extradata']), win_start=c['win_start'],
                             win_end=c['win_end'], start_frame=c['start_frame'], move_id=m,
                             option=c['option'] & 0x40))
            if end:
                break
        if len(rows) < 2:
            return 0
        start = len(self.T['cancels'])
        self.T['cancels'] += rows
        return start

    def conv_hitconds(self, i):
        if i is None:
            return None
        out = []
        t = self.k.tables['hit_conditions']
        j = i
        while j < len(t):
            h = t[j]
            last = not M.reqs(self.k, h['req'])
            r, ok = self.conv_reqs(h['req'])
            if ok:
                if any(c == 615 for c, p in M.reqs(self.k, h['req'])):   # screw -> the donor's bound reactions
                    rx = self.bound_reaction
                else:
                    rx = self.conv_reaction(h['reactions']) if h['reactions'] is not None else None
                out.append(dict(req=r, damage=h['damage'], reactions=rx))
            else:
                self.stats['hit condition entry dropped'] += 1
            if last:
                break
            j += 1
        start = len(self.T['hit_conditions'])
        self.T['hit_conditions'] += out
        return start

    def anim(self, off):
        if off not in self.anim_id:
            hits = self.anim_src.get(off, [])
            com = [h for h in hits if h[0] == 'common']
            own = [h for h in hits if h[0] == 'donor']
            if com:
                aid = 0x8000 | com[0][1]
                self.stats['animations: common'] += 1
            elif own:
                aid = 0x4000 | own[0][1]
                self.stats['animations: in the donor pack'] += 1
            else:
                aid = 0x4000 | (self.pack0_count + len(self.new_anims))
                self.new_anims.append(motion.swap_animation(self.k.animbuf[off:off + self.k.anim_size[off]], '<'))
                self.stats['animations: new'] += 1
            self.anim_id[off] = aid
        return self.anim_id[off]

    # --- moves ------------------------------------------------------------------------------------------
    def conv_move(self, i):
        mv = self.k.tables['moves'][i]
        return dict(name=self.string(self.k.move_name(i)), anim_name=self.string(self.k.anim_name(i)),
                    anim=self.anim(mv['anim']), vuln=mv['vuln'], hitlevel=mv['hitlevel'], cancel=None, cancel2=0,
                    c2_int=0, cancel3=0, c3_int=0, cancel4=0, c4_int=0, transition=0, m_56=mv['m_56'],
                    move_id_hi=0, move_id_lo=0, hit_condition=None, anim_len=0,
                    airborne_start=mv['airborne_start'], airborne_end=mv['airborne_end'],
                    ground_fall=mv['ground_fall'], voiceclip=None, extraprops=None, begin_props=None,
                    end_props=None, bitfield=rev32(mv['bitfield']) & ~(1 << 30),   # Tekken 7 bit 1: no TTT2 meaning
                    hitbox=bytes(self.hitbox.get(x, x) for x in mv['hitbox']), first_active=mv['first_active'],
                    last_active=mv['last_active'], m_a8=mv['m_a8'], distance=mv['distance'])

    def cancel_list(self, i):
        key = ('cl', i)
        if key not in self.cache:
            cl = self.conv_cancel_list(i)
            self.cache[key] = len(self.T['cancels'])
            self.T['cancels'] += cl
        return self.cache[key]

    def run(self):
        k, d = self.k, self.d
        self.alloc_ok = 0
        self.queue = []
        # per reaction slot, the donor's most common move (fallback); the donor's bound reactions (requirement 467)
        self.slot_default = {f: collections.Counter(r[f] for r in d.tables['reactions']).most_common(1)[0][0]
                             for f in REACTION_MOVE_FIELDS}
        bc = collections.Counter(h['reactions'] for h in d.tables['hit_conditions']
                                 if h['reactions'] is not None and any(c == 467 for c, p in M.reqs(d, h['req'])))
        self.bound_reaction = bc.most_common(1)[0][0]
        nd = len(d.tables['moves'])
        keep = [i for i, c in enumerate(self.cls) if c == 'K' and not self.drop_moves.search(k.move_name(i))]
        self.stats['own moves'] = sum(1 for c in self.cls if c == 'K')
        self.stats['own moves converted'] = len(keep)
        self.newidx = {i: nd + n for n, i in enumerate(keep)}
        self.T['moves'] += [self.conv_move(i) for i in keep]
        # alias slots: the donor's, except where it names a donor-specific move (the round start, its stance):
        # there the Tekken 7 fighter's slot, converted. Such a pair are counterparts: the converted move also gets
        # the donor move's cancels into TTT2-only moves (tag out from standing, ...)
        donor_specific = {n for n in self.dn if n not in self.kn and n not in self.ttt2_only_generic}
        self.aliases = list(d.aliases)
        counterpart = {}
        for s_ in range(56):
            if d.move_name(d.aliases[s_]) in donor_specific and k.aliases[s_] in self.newidx:
                self.aliases[s_] = self.newidx[k.aliases[s_]]
                counterpart.setdefault(k.aliases[s_], d.aliases[s_])
        # the round-start move (alias slot 0): Tekken 7's does not convert (its mode checks land on TTT2 ids that
        # need guards: one crashes in practice), so the donor's list is kept with its own targets replaced
        self.rebuild_direct(donor_specific)
        # second pass: the links (every new index is known now)
        for i in keep:
            self.link_move(i, counterpart)
        self.alloc_ok += 1
        while self.queue:
            self.link_move(self.queue.pop(0), counterpart)
        self.alloc_ok -= 1
        self.rebuild_hubs()
        # every move belongs to the new motion row
        for n, row in enumerate(self.T['moves']):
            combined = (self.newid << 16) + n - (self.newid - 1)
            row['move_id_hi'] = combined >> 16 & 0xFFFF
            row['move_id_lo'] = combined & 0xFFFF
        if len(self.T['pushback_extras']) % 2:
            self.T['pushback_extras'].append({'value': 0})
        return self

    def link_move(self, i, counterpart):
        k, d = self.k, self.d
        mv = k.tables['moves'][i]
        row = self.T['moves'][self.newidx[i]]
        if i in counterpart:
            cl = self.merge_donor_extras(self.conv_cancel_list(mv['cancel']),
                                         M.cancels(d, d.tables['moves'][counterpart[i]]['cancel']))
            row['cancel'] = len(self.T['cancels'])
            self.T['cancels'] += cl
        else:
            row['cancel'] = self.cancel_list(mv['cancel'])
        t = self.target(mv['transition'])
        if t is None:
            self.stats['transition -> the standing alias 0x8001'] += 1
            t = 0x8001
        row['transition'] = t
        row['hit_condition'] = self.conv_hitconds(mv['hit_condition'])
        row['extraprops'] = self.conv_xps(mv['extraprops'])
        row['begin_props'] = self.conv_props('move_begin_props', mv['begin_props'])
        row['end_props'] = self.conv_props('move_end_props', mv['end_props'])
        if M.voices(k, mv['voiceclip']):
            row['voiceclip'] = self.conv_voiceclips(mv['voiceclip'])
            self.stats['voice clips kept' if row['voiceclip'] is not None else 'voice clips dropped'] += 1

    def rebuild_hubs(self):
        """Generic moves that lead into the fighter's own moves get its cancel lists plus the donor's cancels into
        TTT2-only moves."""
        k, d = self.k, self.d
        nd = len(d.tables['moves'])
        donor_specific = {n for n in self.dn if n not in self.kn and n not in self.ttt2_only_generic}
        for i, c in enumerate(self.cls):
            if c != 'G':
                continue
            mv = k.tables['moves'][i]
            kc = M.cancels(k, mv['cancel'])
            dj = self.dn[k.move_name(i)]
            dc = M.cancels(d, d.tables['moves'][dj]['cancel'])
            k_hub = any(x['direction'] < 0x8000 and x['move_id'] in self.newidx for x in kc) or \
                any(x['direction'] == M.GROUP for x in kc)
            d_spec = any(x['direction'] < 0x8000 and x['move_id'] < nd and d.move_name(x['move_id']) in donor_specific
                         for x in dc) or any(x['direction'] == M.GROUP for x in dc)
            if not k_hub and not d_spec:
                continue
            cl = self.merge_donor_extras(self.conv_cancel_list(mv['cancel']), dc)
            self.T['moves'][dj]['cancel'] = len(self.T['cancels'])
            self.T['cancels'] += cl
            self.stats['hub moves rebuilt'] += 1

    def merge_donor_extras(self, cl, dc):
        """Insert the donor's cancels into TTT2-only generic moves (the tag system, ...) at their aligned place:
        after the converted cancel that matches the nearest preceding donor cancel (same target name and input)."""
        d = self.d

        def sig_new(x):
            m = x['move_id']
            return (x['direction'], x['button'],
                    d.move_name(m) if m < len(self.T['moves']) and m < len(d.tables['moves']) else m)
        pos = {}
        for p, x in enumerate(cl[:-1]):
            pos.setdefault(sig_new(x), p)
        inserts = collections.defaultdict(list)      # converted position -> donor rows after it (-1: in front)
        anchor = -1

        def tto(m):
            return m < len(d.tables['moves']) and d.move_name(m) in self.ttt2_only_generic
        for x in dc:
            if x['direction'] == M.LIST_END:
                break
            m = x['move_id']
            if x['direction'] == M.GROUP:
                g = [y for y in M.cancels(d, m, 'group_cancels', M.GROUP_END) if y['direction'] != M.GROUP_END]
                gt = [y for y in g if tto(y['move_id'])]
                if g and len(gt) * 2 >= len(g):          # a TTT2-only group (tag out from standing, ...): kept
                    inserts[anchor].append(dict(x))
                    continue
                for y in gt:                             # TTT2-only members of a shared group: as plain cancels
                    y = dict(y)
                    y['option'] = 0
                    inserts[anchor].append(y)
            elif tto(m):
                y = dict(x)
                y['option'] = 0
                inserts[anchor].append(y)
                continue
            s = (x['direction'], x['button'],
                 d.move_name(m) if (x['direction'] != M.GROUP and m < len(d.tables['moves'])) else m)
            if s in pos:
                anchor = pos[s]
        out = list(inserts[-1])
        for p, x in enumerate(cl[:-1]):
            out.append(x)
            out += inserts[p]
        out.append(cl[-1])
        return out

    def rebuild_direct(self, donor_specific):
        """The round-start list (alias slot 0) keeps the donor's targets except its own moves (MOVESET['direct']):
        its stance becomes the fighter's; its intros and win poses stay (their camera animations end the intro and
        the win screen; their sound properties play the fighter's own lines, which sit at the same tones of its
        banks) and play the fighter's animations instead."""
        d = self.d
        dj = d.aliases[0]
        turn = collections.Counter()
        by_tone = {tone: name for name, tone in self.win_tones.items()}

        def quote_tone(j):
            for f, idv, v in M.xps(d, d.tables['moves'][j]['extraprops']):
                if idv == WIN_QUOTE_PROP and v & 0xFFFFF000 == WIN_QUOTE_VALUE:
                    return v & 0xFFF
            return None

        def sub(j):
            name = d.move_name(j)
            for pat, how, theirs in self.defn.MOVESET['direct']:
                if not re.search(pat, name):
                    continue
                own = [n for n in theirs if self.kn.get(n) in self.newidx]
                if not own:
                    break
                if how == 'move':
                    return self.newidx[self.kn[own[0]]]
                pick = by_tone.get(quote_tone(j))
                if pick not in own:
                    pick = own[turn[pat] % len(own)]
                    turn[pat] += 1
                mv = self.k.tables['moves'][self.kn[pick]]
                row = self.T['moves'][j]
                row['anim'] = self.anim(mv['anim'])
                row['anim_name'] = self.string(self.k.anim_name(self.kn[pick]))
                self.stats['donor round-start moves with her animation'] += 1
                return j
            return 0x8001                                # the standing alias
        out = []
        for x in M.cancels(d, d.tables['moves'][dj]['cancel']):
            y = dict(x)
            m = x['move_id']
            if x['direction'] < 0x8000 and m < len(d.tables['moves']) and d.move_name(m) in donor_specific:
                y['move_id'] = sub(m)
            out.append(y)
        self.T['moves'][dj]['cancel'] = len(self.T['cancels'])
        self.T['cancels'] += out

    # --- output -----------------------------------------------------------------------------------------
    def write(self):
        """-> (motbin bytes, motion pack bytes)"""
        hdr, strings, blob, slots = motbin.split(self.d)
        hdr = bytearray(hdr)
        nid = self.newid
        struct.pack_into('>4H', hdr, 0xF8 + 32 * 2, nid - 1, (-(nid - 1)) & 0xFFFF, nid, (-nid) & 0xFFFF)
        struct.pack_into('>56H', hdr, 0x18, *self.aliases)
        struct.pack_into('>56H', hdr, 0x88, *self.aliases)
        name_off = self.string(self.defn.MOVESET['name'])
        old = struct.unpack_from('>4I', hdr, 8)
        mb = motbin.build(hdr, bytes(self.strings), self.T, blob, slots, name_offsets=(name_off,) + old[1:])
        pk = self.donor_pack
        items = [pk[o:o + s] for o, s in motion.pack_items(pk)]
        items[0] = motion.extend_mota(items[0], self.new_anims)
        return mb, motion.build_pack(items)

    def summary(self):
        lines = ['tables: ' + ', '.join('%s %d' % (t, len(self.T[t])) for t in TABLE_ORDER),
                 'new animations: %d (%d bytes)' % (len(self.new_anims), sum(len(a) for a in self.new_anims))]
        lines += ['%s: %d' % kv for kv in sorted(self.stats.items())]
        if self.unmapped:
            lines.append('ids without a TTT2 counterpart (dropped where used): %d' % len(self.unmapped))
        return lines
