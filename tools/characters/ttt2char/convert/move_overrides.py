"""Opt-in gameplay edits applied before generating Tag Assault twins."""
from . import tagsystem as TS


def apply(c):
    for name, damage in c.defn.MOVESET.get('damage', {}).items():
        if type(damage) is not int or not 0 <= damage <= 255:
            raise ValueError('damage must be an integer from 0 to 255: ' + name)
        move = c.T['moves'][c.newidx[c.kn[name]]]
        hits = [dict(hit, damage=damage) for hit in TS.hits(c.T, move['hit_condition'])]
        if not hits:
            raise ValueError('no hit conditions for damage override: ' + name)
        move['hit_condition'] = TS.write(c.T, 'hit_conditions', hits)
        c.stats['explicit move damage overrides'] += 1
    for name, bound in c.defn.MOVESET.get('bounds', {}).items():
        move = c.T['moves'][c.newidx[c.kn[name]]]
        hits = [dict(h) for h in TS.hits(c.T, move['hit_condition'])]
        if bound:
            # One bound per juggle; preserve all ground and post-bound reactions.
            hits = [h for h in hits if not TS.has(c.T, h['req'], TS.BOUND)]
            damage = next((h['damage'] for h in hits if TS.has(c.T, h['req'], TS.AIR)), hits[-1]['damage'])
            hits.insert(0, dict(req=c.bound_req, damage=damage, reactions=c.bound_reaction))
        else:
            hits = [h for h in hits if not TS.has(c.T, h['req'], TS.BOUND)]
            for h in hits:
                if TS.has(c.T, h['req'], TS.AIR) and TS.same_reaction(c.T, h['reactions'], c.bound_reaction):
                    h['reactions'] = c.after_bound_reaction
        move['hit_condition'] = TS.write(c.T, 'hit_conditions', hits)
        c.stats['explicit bound enabled' if bound else 'explicit bound removed'] += 1

    for name, locations in c.defn.MOVESET.get('hitboxes', {}).items():
        c.T['moves'][c.newidx[c.kn[name]]]['hitbox'] = bytes(c.hit_location(x) for x in locations)
    for name, template in c.defn.MOVESET.get('air_reactions', {}).items():
        # Use a native airborne reaction, not a vertical offset on every hit.
        reference = getattr(c, 'air_reaction_reference', c.d)
        if isinstance(template, tuple):
            row, template = template
            reference = c.air_reaction_references[row]
        names = c.dn if reference is c.d else {reference.move_name(i): i for i in range(len(reference.tables['moves']))}
        donor = reference.tables['moves'][names[template]]
        native = [h for h in TS.hits(reference.tables, donor['hit_condition'])
                  if TS.has(reference.tables, h['req'], TS.AIR)]
        if len(native) != 1:
            raise ValueError('no unique native airborne reaction: ' + template)
        row = dict(reference.tables['reactions'][native[0]['reactions']])
        if reference is not c.d:
            from ..movesets import TTT2
            for field, _, _, link in TTT2['reactions'][1]:
                if link == 'move':
                    row[field] = c.dn[reference.move_name(reference.resolve_alias(row[field]))]
                elif link == 'pushbacks':
                    push = dict(reference.tables['pushbacks'][row[field]])
                    extras = push['extradata']
                    if extras is not None:
                        push['extradata'] = len(c.T['pushback_extras'])
                        c.T['pushback_extras'].extend(dict(x) for x in
                            reference.tables['pushback_extras'][extras:extras + push['loops']])
                    row[field] = c.add('pushbacks', push)
        reaction = c.add('reactions', row)
        move = c.T['moves'][c.newidx[c.kn[name]]]
        hits = [dict(h) for h in TS.hits(c.T, move['hit_condition'])]
        changed = 0
        for hit in hits:
            if TS.has(c.T, hit['req'], TS.AIR) and not TS.has(c.T, hit['req'], TS.BOUND):
                hit['reactions'] = reaction
                changed += 1
        if not changed:
            raise ValueError('no airborne hit condition: ' + name)
        move['hit_condition'] = TS.write(c.T, 'hit_conditions', hits)
        c.stats['airborne reactions replaced from native template'] += changed
    for source, target in c.defn.MOVESET.get('buffered_stance_transitions', {}).items():
        buffered_stance_transition(c, source, target)

    for source, target in c.defn.MOVESET.get('stance_transitions', {}).items():
        move = c.T['moves'][c.newidx[c.kn[source]]]
        rows = [dict(row) for row in TS.cancels(c.T, move['cancel'])]
        index = c.newidx[c.kn[target]]
        reference = c.stance_reference
        entry_name, state_name = c.defn.MOVESET['stance_reference'][1:]
        names = {reference.move_name(i): i for i in range(len(reference.tables['moves']))}
        entry = reference.tables['moves'][names[entry_name]]
        native_state = reference.tables['moves'][names[state_name]]
        from . import idmaps as M
        native = next(row for row in M.cancels(reference, entry['cancel'])
                      if row['direction'] == 64 and row['button'] == 0
                      and reference.resolve_alias(row['move_id']) == names[state_name])
        value = reference.tables['cancel_extras'][native['extradata']]['value']
        extra = c.extra_index.get(value)
        if extra is None:
            extra = c.add('cancel_extras', dict(value=value))
            c.extra_index[value] = extra
        # Retain SET's other flags; match the native stance's bit 0x20.
        stance = c.T['moves'][index]
        stance['bitfield'] = (stance['bitfield'] & ~0x20) | (native_state['bitfield'] & 0x20)
        matches = 0
        for row in rows:
            if row['move_id'] == index and row['direction'] == 64 and row['button'] == 0:
                row['extradata'] = extra
                matches += 1
        if matches != 1:
            raise ValueError('no unique forward stance transition: ' + source)
        move['cancel'] = TS.write(c.T, 'cancels', rows)

    for name in c.defn.MOVESET.get('direct_buffered_strings', ()):
        direct_buffered_string(c, name)
    normalize_buffered_strings(c)


def direct_buffered_string(c, name):
    """Expose a buffered follow-up as a native direct input, retaining its gates."""
    variable = c.map_req(352)
    setter = c.map_req(0x80a6)
    if variable is None or setter is None:
        raise ValueError('no mapped string buffer')
    move = c.T['moves'][c.newidx[c.kn[name]]]
    rows = [dict(row) for row in TS.cancels(c.T, move['cancel'])]
    captures = {}
    for i, row in enumerate(rows):
        if row['button'] == 0:
            continue
        req = TS.reqs(c.T, row['req'])
        codes = [v for pid, v in req if pid == setter]
        if codes:
            captures[i] = codes[0]
    made, consumed = {}, set()
    for i, row in enumerate(rows):
        req = TS.reqs(c.T, row['req'])
        code = next((v for pid, v in req if pid == variable and v != 0), None)
        if row['button'] or code is None:
            continue
        for capture, value in captures.items():
            if value != code:
                continue
            rest = [(a, b) for a, b in req if a != variable]
            rq = len(c.T['requirements'])
            c.T['requirements'] += [dict(condition=a, param=b) for a, b in rest]
            c.add('requirements', dict(condition=TS.TT_END, param=0))
            inp = rows[capture]
            made.setdefault(capture, []).append(dict(row, direction=inp['direction'], button=inp['button'], req=rq,
                             win_start=inp['win_start'], win_end=inp['win_end']))
            consumed.update((i, capture))
    if not made:
        raise ValueError('no buffered follow-ups in ' + name)
    out = []
    for i, row in enumerate(rows):
        out.extend(made.get(i, ()))
        if i not in consumed:
            out.append(row)
    move['cancel'] = TS.write(c.T, 'cancels', out)
    c.stats['buffered string follow-ups made direct'] += sum(map(len, made.values()))


def buffered_stance_transition(c, source, target):
    """Candidate for a ground stance's late directional entry during an assist.

    Accept held forward before its transition frame, keeping the animation start
    and final input frame. Kazumi's working FLY uses mode 0x80 and the non-hit
    hitlevel flag 0x200000. Apply that flag only to this opted-in empty-hit state;
    do not copy FLY's airborne frames or alter the attack's active frames.
    """
    move = c.T['moves'][c.newidx[c.kn[source]]]
    index = c.newidx[c.kn[target]]
    state = c.T['moves'][index]
    if state['first_active'] or state['last_active'] or state['hitlevel'] & 0xffff:
        raise ValueError('stance continuation target is an attack: ' + target)
    extra = c.extra_index.get(0x80)
    if extra is None:
        extra = c.add('cancel_extras', dict(value=0x80))
        c.extra_index[0x80] = extra
    rows = [dict(row) for row in TS.cancels(c.T, move['cancel'])]
    matches = 0
    for row in rows:
        if row['move_id'] == index and row['direction'] == 64 and row['button'] == 0:
            row['win_start'] = 1
            row['extradata'] = extra
            matches += 1
    if matches != 1:
        raise ValueError('no unique forward stance transition: ' + source)
    state['hitlevel'] |= 0x200000
    move['cancel'] = TS.write(c.T, 'cancels', rows)
    c.stats['buffered stance continuation candidates'] += 1


def normalize_buffered_strings(c):
    """Convert only simple two-stage input buffers, across the imported roster.

    A capture may only test that the buffer is empty and set one code. Every
    capture must have a dispatch; complex captures and partial conversions are
    left intact. These neutral-target capture cancels are not actual attacks,
    but expose an extra cancel to TTT2's assist bookkeeping.
    """
    variable, setter = c.map_req(352), c.map_req(0x80a6)
    if variable is None or setter is None:
        return
    for name, original in c.kn.items():
        if original not in c.newidx:
            continue
        move = c.T['moves'][c.newidx[original]]
        rows = TS.cancels(c.T, move['cancel'])
        captures = []
        safe = True
        for row in rows:
            req = TS.reqs(c.T, row['req'])
            setters = [b for a, b in req if a == setter]
            if not setters:
                continue
            if (not row['button'] or len(setters) != 1 or setters[0] == 0 or
                    any((a, b) not in ((variable, 0), (setter, setters[0]), (0, 0)) for a, b in req)):
                safe = False
                break
            captures.append(setters[0])
        if not safe or not captures:
            continue
        dispatch = {b for row in rows if row['direction'] == 0 and row['button'] == 0
                    for a, b in TS.reqs(c.T, row['req']) if a == variable and b != 0}
        if not set(captures) <= dispatch:
            continue
        direct_buffered_string(c, name)
