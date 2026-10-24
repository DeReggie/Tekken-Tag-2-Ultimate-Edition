"""Character opt-ins for special inputs and native tag-launch exits."""
from . import idmaps as M
from ..ttt2 import motion

SEQ0 = 0x800D


def apply(c):
    rules = c.defn.MOVESET
    for source, targets in rules.get('special_cancels', {}).items():
        i = c.kn[source]
        rows = M.cancels(c.k, c.k.tables['moves'][i]['cancel'])
        # T7's input-only rows store the chosen special in 0x80c5; automatic
        # contact rows test it with 346. TTT2 has no equivalent buffer.
        inputs = {}
        for row in rows:
            req = M.reqs(c.k, row['req'])
            if (346, 0) in req and SEQ0 <= row['direction'] < SEQ0 + len(c.k.tables['input_sequences']):
                for pid, value in req:
                    if pid == 0x80c5:
                        inputs.setdefault(value, []).append(row)
        # A direct TTT2 input uses the native normal/string input mode.
        # T7's automatic special-dispatch extra retains an additional 0x800.
        direct_extra = c.extra_index.get(0x182)
        if direct_extra is None:
            direct_extra = c.add('cancel_extras', dict(value=0x182))
            c.extra_index[0x182] = direct_extra
        added, seen = [], set()
        for row in rows:
            req = M.reqs(c.k, row['req'])
            target = c.k.resolve_alias(row['move_id']) if row['direction'] != M.GROUP else None
            if target is None or c.k.move_name(target) not in targets:
                continue
            # Keep meter-dependent EX branches out of this replacement.
            if any(pid == 629 for pid, _ in req):
                continue
            codes = [v for pid, v in req if pid == 346 and v != 0]
            if not any(pid in (49, 50) for pid, _ in req):
                continue
            for code in codes:
                for inp in inputs.get(code, []):
                    for contact in (46, 47):       # native block / hit tests
                        key = (inp['direction'], target, contact)
                        if key in seen:
                            continue
                        seen.add(key)
                        rq = c.add('requirements', dict(condition=contact, param=0))
                        c.add('requirements', dict(condition=M.END_REQ['ttt2'], param=0))
                        added.append(dict(direction=SEQ0 + c.conv_seq(inp['direction'] - SEQ0),
                                          button=inp['button'], req=rq, extradata=direct_extra,
                                          win_start=inp['win_start'], win_end=inp['win_end'],
                                          start_frame=1, move_id=c.newidx[target], option=0))
        if not added:
            raise ValueError('no special cancels found for ' + source)
        move = c.T['moves'][c.newidx[i]]
        body = list(c.T['cancels'][move['cancel']:])
        end = next(j for j, row in enumerate(body) if row['direction'] == M.LIST_END)
        move['cancel'] = len(c.T['cancels'])
        c.T['cancels'] += added + body[:end + 1]
        c.stats['special input cancels restored'] += len(added)

    exit_id = electric_exit(c) if rules.get('electric_tag_exit') else None
    for source, template in rules.get('tag_launchers', {}).items():
        donor = c.d.tables['moves'][c.dn[template]]
        rows = [row for row in M.cancels(c.d, donor['cancel'])
                if M.reqs(c.d, row['req']) == [(47, 0), (481, 0)]]
        if len(rows) != 1:
            raise ValueError('no unique tag launcher template: ' + template)
        move = c.T['moves'][c.newidx[c.kn[source]]]
        # Electric's native startup/early-recovery tag window ends eight frames
        # after its last active frame (He_shoryu_S: 12 -> 20).
        electric = c.h2.tables['moves'][next(i for i in range(len(c.h2.tables['moves']))
                                           if c.h2.move_name(i) == 'He_shoryu_S')]
        native = next(row for row in M.cancels(c.h2, electric['cancel'])
                      if M.reqs(c.h2, row['req']) == [(47, 0), (481, 0)])
        tag = dict(rows[0], win_end=move['last_active'] + native['win_end'] - electric['last_active'])
        if source in rules.get('tag_launcher_air_only', ()):
            req = M.reqs(c.d, rows[0]['req']) + [(466, 0)]
            tag['req'] = len(c.T['requirements'])
            c.T['requirements'] += [dict(condition=a, param=b) for a, b in req]
            c.add('requirements', dict(condition=M.END_REQ['ttt2'], param=0))
        if exit_id is not None:
            tag['move_id'] = exit_id
        # The native exit, its animation, requirements and extra (188) all
        # already belong to the donor. Insert before automatic follow-ups.
        body = list(c.T['cancels'][move['cancel']:])
        end = next(j for j, row in enumerate(body) if row['direction'] == M.LIST_END)
        move['cancel'] = len(c.T['cancels'])
        c.T['cancels'] += [tag] + body[:end + 1]
        c.stats['tag launcher cancels added'] += 1


def electric_exit(c):
    """Copy the Electric's native exit and animation, translating table links."""
    h = c.h2
    src = next(m for i, m in enumerate(h.tables['moves']) if h.move_name(i) == 'He_shoryu_SChg')
    def requirements(index):
        start = len(c.T['requirements'])
        c.T['requirements'] += [dict(condition=a, param=b) for a, b in M.reqs(h, index)]
        c.add('requirements', dict(condition=M.END_REQ['ttt2'], param=0))
        return start
    def target(i):
        return i if i >= 0x8000 else c.dn[h.move_name(i)]
    row = dict(src)
    row['name'] = c.string(c.defn.MOVESET.get('tag_exit_name', 'Akuma_DP_TagExit'))
    pack = c.electric_pack
    off, size = motion.pack_items(pack)[0]
    _, offsets = motion.mota_offsets(pack, off)
    index = src['anim'] & 0x3fff
    start = offsets[index]
    stop = min((x for x in offsets if x > start), default=size)
    row['anim'] = 0x4000 | (c.pack0_count + len(c.new_anims))
    c.new_anims.append(pack[off + start:off + stop])
    row['hit_condition'] = c.d.tables['moves'][c.dn['La_StormgearChg']]['hit_condition']
    row['cancel'] = len(c.T['cancels'])
    for cancel in M.cancels(h, src['cancel']):
        value = h.tables['cancel_extras'][cancel['extradata']]['value']
        extra = c.extra_index.get(value)
        if extra is None:
            extra = c.add('cancel_extras', dict(value=value))
            c.extra_index[value] = extra
        c.T['cancels'].append(dict(cancel, req=requirements(cancel['req']),
                                   extradata=extra, move_id=target(cancel['move_id'])))
    row['transition'] = target(src['transition'])
    row['extraprops'] = len(c.T['extra_move_properties'])
    index = src['extraprops']
    while index is not None:
        p = h.tables['extra_move_properties'][index]
        c.T['extra_move_properties'].append(dict(p))
        if p['id'] == 0:
            break
        index += 1
    row['anim_name'] = c.string('amkz_shonige_change(DVD)')
    return c.add('moves', row)
