"""A Tekken 7 fighter's voice -> the added fighter's four TTT2 sound banks.

Each bank is the donor's (`se_Chr_<donor>`, `se_Dwi_<donor>`, `rm_Dst_<donor>`, `rm_Dwi_<donor>`) with every tone's
audio replaced by
one of the Tekken 7 fighter's clips of the same kind, so the banks keep the layout the title expects of the donor:
  se_Chr: shouts (`atck`/`atk` short, medium, long), damage voices (`dmg`), KO screams (`ko`, `die`), special shouts
          (`org`, `itm`), the announcer calling the fighter's name (`syvo_name`)
  se_Dwi: win quotes;  rm_Dst: intro lines;  rm_Dwi: the long win quote one win pose streams
The Tekken 7 clips are Wwise events of its voice bank `AkBankVoice<CODE>.bnk` named `<code>_atk_s01`, `_dmg_m02`,
`_ko01`, `_org03`, `<prefix>_s00` (intros), `<prefix>_w00` (wins); the announcer's call is `syvo_name_<code>` in
`AkBankBattle.bnk`. Events are found by name (Wwise ids are hashes of the names).

The select screen's announcer calls are tones of one shared bank, se_Slt_StartChar: a link tone
`sel_syvo_name_<code>` per fighter plays its audio tones `lnk_sel_syvo_name_<code>[_Copy]`. name_call() appends the
added fighter's three (the runtime gives its select id the link tone's sound).
"""
import re
import struct

import numpy as np

from ..tekken7.wwise import Bank as WwiseBank, decode_wem
from ..ttt2 import dsp
from ..ttt2.nus3bank import Bank, wave

VOICE_BANK = 'TekkenGame/Content/WwiseAudio/Windows/AkBankVoice%s.bnk'
BATTLE_BANK = 'TekkenGame/Content/WwiseAudio/Windows/AkBankBattle.bnk'
# the bank ids the added fighter's banks get in the sound project (BINF): free ones in TTT2's
PROJECT_IDS = {'se_Chr': 409, 'se_Dwi': 457, 'rm_Dst': 458, 'rm_Dwi': 462}
# sample rates tried in turn: the first that keeps a bank no bigger than the donor's (the title's sound memory is
# sized for its own banks)
RATES = (48000, 32000, 24000)


def tone_kind(name):
    """A donor tone's kind: (category, size) with category atk, dmg, ko, org, name, or None."""
    n = name.lower()
    if 'syvo_name' in n:
        return ('name', None)
    m = re.search(r'_(?:atck|atk)_?([sml])?\d', n)
    if m:
        return ('atk', m.group(1))
    if re.search(r'_(?:dmg_)?(?:ko|die)_?\d', n):
        return ('ko', None)
    m = re.search(r'_dmg_?([sml])?\d', n)
    if m:
        return ('dmg', m.group(1))
    if re.search(r'_org_?\d|itm_|_\d\d$', n):
        return ('org', None)
    return (None, None)


class Clips:
    """The Tekken 7 fighter's clips by kind: {(category, size): [(event name, rate, int16 [channels, samples])]}."""

    def __init__(self, paks, code, prefix):
        self.bank = WwiseBank(paks.read(VOICE_BANK % code.upper()))
        self.kinds = {}
        c = code.lower()
        for cat in ('atk', 'dmg'):
            for size in 'sml':
                self._collect((cat, size), ['%s_%s_%s%02d' % (c, cat, size, k) for k in range(1, 21)])
        self._collect(('ko', None), ['%s_ko%02d' % (c, k) for k in range(1, 11)])
        self._collect(('org', None), ['%s_org%02d' % (c, k) for k in range(1, 21)])
        self._collect(('intro', None), ['%s_s%02d' % (prefix, k) for k in range(0, 20)])
        self._collect(('win', None), ['%s_w%02d' % (prefix, k) for k in range(0, 20)])
        try:
            battle = WwiseBank(paks.read(BATTLE_BANK))
            name = 'syvo_name_%s' % c
            if battle.has_event(name):
                media = battle.event_media(name)
                if media:
                    rate, a = decode_wem(battle.media[media[0]])
                    self.kinds[('name', None)] = [(name, rate, a)]
        except (KeyError, OSError, ValueError):
            pass

    def _collect(self, kind, names):
        out = []
        for n in names:
            if not self.bank.has_event(n):
                continue
            media = self.bank.event_media(n)
            if media:
                rate, a = decode_wem(self.bank.media[media[0]])
                out.append((n, rate, a))
        if out:
            self.kinds[kind] = out

    def pick(self, kind, counter):
        """The next clip of a kind (round robin), falling back to the nearest size."""
        cat, size = kind
        order = [size] + [s for s in ('m', 's', 'l', None) if s != size] if cat in ('atk', 'dmg') else [size]
        for s in order:
            lst = self.kinds.get((cat, s))
            if lst:
                k = counter.get((cat, s), 0)
                counter[(cat, s)] = k + 1
                return lst[k % len(lst)]
        return None


def _resample(a, rate, to):
    if rate == to:
        return a
    n = int(round(a.shape[1] * to / rate))
    x = np.linspace(0, a.shape[1] - 1, n)
    return np.stack([np.interp(x, np.arange(a.shape[1]), ch).round().astype(np.int16) for ch in a])


def _fit(a, channels):
    """int16 [channels, samples] with the wanted channel count (mixing down or duplicating)."""
    if a.shape[0] == channels:
        return a
    if channels == 1:
        return a.astype(np.int32).mean(0, keepdims=True).round().astype(np.int16)
    return np.repeat(a[:1], channels, 0)


def _audio(original, clip, channels, to, side=None):
    """Audio bytes in the tone's own container (IDSP or WAVE) -> (bytes, rate, channels, samples). side: 'L' or 'R'
    for a tone that plays one channel of a stereo pair."""
    _, rate, a = clip
    if side is not None and a.shape[0] == 2:
        a = a[1:2] if side == 'R' else a[0:1]
    a = _fit(_resample(a, rate, to), channels)
    if original[:4] == b'IDSP':
        return dsp.idsp(list(a), to), to, channels, a.shape[1]
    return wave(list(a), to), to, channels, a.shape[1]


def build(clips, donor_banks, code):
    """donor_banks: {'se_Chr': bytes, 'se_Dwi': bytes, 'rm_Dst': bytes, 'rm_Dwi': bytes} -> ({file name: bytes},
    report lines, win quotes {Tekken 7 event name: the se_Dwi tone that plays it (moves play win quotes by tone)}).
    The banks take clips in turn from one round of each kind (rm_Dwi gets a win quote se_Dwi has not)."""
    out, report, wins = {}, [], {}
    counter = {}
    for which, data in donor_banks.items():
        for rate in RATES:
            start = dict(counter)
            written, used, placed = _build_one(which, data, clips, code, rate, start)
            if len(written) <= len(data) * 1.02:
                break
        counter = start
        out['%s_%s.nus3bank' % (which, code)] = written
        if which == 'se_Dwi':
            wins = placed
        report.append('%s_%s: %d tones of her own, %d Hz, %d KB (the donor\'s %d KB)'
                      % (which, code, len(used), rate, len(written) // 1024, len(data) // 1024))
    return out, report, wins


def _build_one(which, data, clips, code, to, counter):
    """The donor's bank `which` with the clips at sample rate `to` -> (bytes, the tones replaced, {clip name: the
    tone that plays it}). A link tone's tones (a stereo pair `..R`/`..L`, or variants) get one clip together. counter:
    how many clips of each kind earlier banks took (advanced here)."""
    bank = Bank(data)
    used, placed = [], {}

    def kind_of(name):
        if which == 'se_Chr':
            return tone_kind(name)
        return ('intro', None) if which == 'rm_Dst' else ('win', None)

    def put(i, clip, side=None):
        _, channels, _ = bank.format(i)
        audio, rate, ch, n = _audio(bank.audio[i], clip, channels, to, side)
        bank.replace(i, audio, rate, ch, n)
        used.append('%s<-%s' % (bank.name(i), clip[0]))

    done = set()
    for i in range(len(bank.tones)):
        name = bank.name(i)
        links = bank.links(i) if name and not bank.has_audio(i) else []
        if not links or kind_of(name)[0] is None:
            continue
        clip = clips.pick(kind_of(name), counter)
        if clip is None:
            continue
        for _, k in links:
            side = bank.name(k)[-1] if bank.name(k)[-1] in 'LR' else None
            put(k, clip, side)
            done.add(k)
        placed.setdefault(clip[0], i)
    for i in range(len(bank.tones)):
        name = bank.name(i)
        if i in done or not name or not bank.has_audio(i) or not bank.audio[i] or kind_of(name)[0] is None:
            continue
        clip = clips.pick(kind_of(name), counter)
        if clip is None:
            continue
        put(i, clip)
        placed.setdefault(clip[0], i)
    bank.rename('%s_%s' % (which, code), PROJECT_IDS[which])
    return bank.write(), used, placed


SELECT_BANK = 'se_Slt_StartChar.nus3bank'


def name_call(clips, data, donor, code):
    """The select screen's announcer bank with the fighter's name call added (a copy of the donor's link tone and
    its audio tones with the fighter's name) -> bytes, or None without a name clip."""
    clip = clips.kinds.get(('name', None))
    if not clip:
        return None
    bank = Bank(data)
    names = {bank.name(i): i for i in range(len(bank.tones))}
    link = names.get('sel_syvo_name_%s' % donor)
    if link is None or not bank.links(link):
        return None
    entry = bank.renamed(link, 'sel_syvo_name_%s' % code)
    for offset, k in bank.links(link):
        rate, channels, _ = bank.format(k)
        audio, rate, ch, n = _audio(bank.audio[k], clip[0], channels, rate)
        new = bank.append(bank.renamed(k, bank.name(k).replace('_' + donor, '_' + code)), audio=audio)
        bank.replace(new, audio, rate, ch, n)
        struct.pack_into('<I', entry, offset, new)
    bank.append(entry)
    return bank.write()
