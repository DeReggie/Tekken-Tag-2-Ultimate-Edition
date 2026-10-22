"""Tekken 7 movesets dumped in the background: the importer's .tkmvst files without the player doing anything.

Tekken 7's data files are encrypted; a fighter's moveset is readable only once the game has loaded it, so the game
has to run, and it runs where nobody sees or hears it, and with nothing pressed:
* Proton runs it inside gamescope's headless backend (no window, no output) with its sound sent to a silent sink of
  its own (Tekken 7 does not start without an audio device);
* t7helper.exe (tools/characters/t7helper, built with MinGW) runs next to it in its Wine prefix: it asks Steam, as
  the game does, which DLC the player owns (only owned fighters are dumped), and it calls the game's own loader for
  each fighter while the game sits on its start-up screens: the function that loads a fighter's files by its code
  (the game's background tasks read and decrypt them), then the game's two functions that turn the moveset and the
  command list into the form it uses; the helper knows those functions and checks their first bytes before calling
  any (another build of the game is refused, not crashed), and takes no address from outside;
* the dumper reads the result from the game's memory (memdump.py) and writes .tkmvst files.
Some fighters' files the game keeps encrypted in its paks (Geese Howard's and Noctis's costumes, Noctis's voice bank):
the helper has the game read them with its own file reader (the one its loading uses), which hands them over decoded,
and they are saved under their pak paths in a folder of their own (FILES) that the importer reads them from.
No menu, key or screen is involved, so the player's key bindings, settings, language or pop-ups do not matter.
Nothing is written into the game's files, its saves or its prefix (but the helper's copy at C:\\t7helper.exe).

Written for this project (no third-party code).
"""
import os
import re
import secrets
import shutil
import socket
import subprocess
import time

from . import memdump
from .pak import plain

APP_ID = 389730
GAME_COMM = 'TekkenGame-Win6'                 # the game's Linux process name (15 characters)
SINK = 'ttt2_tekken7_silent'
STEAMWORKS = 'Engine/Binaries/ThirdParty/Steamworks/Steamv132/Win64/steam_api64.dll'
HEIHACHI = 8                                    # every import needs his moveset (the id maps)
BATCH = 4                                       # fighters loaded at once
LOAD_TIMEOUT = 90                               # seconds a batch may take
# Tekken 7's DLC fighters: their roster ids and the Steam app ids of the DLC that has them (Steam's public lists)
DLC = {36: 592370, 43: 592373, 44: 592374, 45: 878460, 46: 878461, 47: 878462, 48: 878463, 49: 878464, 50: 878465,
       51: 1114561, 52: 1162600, 53: 1162601, 54: 1236500, 55: 1289451, 56: 1289453}
RECORD_MOVELIST = 0x68                          # a fighter record's command list: written last, once all is loaded
COMMON_ANIMATIONS = 0x38
# the encrypted files as the game reads them (pak paths below it)
FILES = os.path.join(os.path.expanduser('~/.local/share'), 'ttt2', 'tekken7', 'files')
FILE_BATCH = 64                                 # files the game reads at once (the helper takes up to 256) ...
FILE_BATCH_BYTES = 96 << 20                     # ... and their size together, in the game's memory meanwhile


class DumpError(Exception):
    pass


# ---------------------------------------------------------------- finding the game

class Tekken7:
    def __init__(self, steam, game, prefix, proton):
        self.steam, self.game, self.prefix, self.proton = steam, game, prefix, proton


def _libraries(steam):
    out = [steam]
    vdf = os.path.join(steam, 'steamapps', 'libraryfolders.vdf')
    if os.path.isfile(vdf):
        out += re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='replace').read())
    return list(dict.fromkeys(out))


def find_tekken7():
    """Tekken 7's install, its Proton prefix and the Proton it uses, through Steam's files."""
    steam = next((p for p in (os.path.expanduser('~/.local/share/Steam'), os.path.expanduser('~/.steam/steam'))
                  if os.path.isdir(p)), None)
    if steam is None:
        raise DumpError('Steam is not installed (no ~/.local/share/Steam)')
    for lib in _libraries(steam):
        acf = os.path.join(lib, 'steamapps', 'appmanifest_%d.acf' % APP_ID)
        if not os.path.isfile(acf):
            continue
        m = re.search(r'"installdir"\s+"([^"]+)"', open(acf, encoding='utf-8', errors='replace').read())
        game = os.path.join(lib, 'steamapps', 'common', m.group(1) if m else 'TEKKEN 7')
        prefix = os.path.join(lib, 'steamapps', 'compatdata', str(APP_ID))
        info = os.path.join(prefix, 'config_info')
        if not os.path.isdir(os.path.join(prefix, 'pfx')) or not os.path.isfile(info):
            raise DumpError('Tekken 7 has not run with Proton yet: start it once from Steam, then try again')
        lines = open(info, encoding='utf-8', errors='replace').read().splitlines()
        proton = next((l.split('/files/')[0] for l in lines if '/files/' in l), None)
        if not proton or not os.path.isfile(os.path.join(proton, 'proton')):
            raise DumpError('the Proton Tekken 7 last ran with is gone; start the game once from Steam')
        return Tekken7(steam, game, prefix, proton)
    raise DumpError('Tekken 7 is not installed in any Steam library')


def _running(comm):
    for pid in os.listdir('/proc'):
        if pid.isdigit():
            try:
                with open('/proc/%s/comm' % pid) as f:
                    if f.read().strip() == comm:
                        return int(pid)
            except OSError:
                pass
    return None


def steam_running():
    return _running('steam') is not None


HELPER_SOURCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 't7helper', 't7helper.c')


def build_helper(cache):
    """t7helper.exe, built with MinGW into `cache` when its source is newer."""
    exe = os.path.join(cache, 't7helper.exe')
    src = os.path.normpath(HELPER_SOURCE)
    if os.path.isfile(exe) and os.path.getmtime(exe) >= os.path.getmtime(src):
        return exe
    gcc = shutil.which('x86_64-w64-mingw32-gcc')
    if gcc is None:
        raise DumpError('building the helper needs MinGW (x86_64-w64-mingw32-gcc; Arch: mingw-w64-gcc, '
                        'Debian/Ubuntu: gcc-mingw-w64-x86-64)')
    os.makedirs(cache, exist_ok=True)
    subprocess.run([gcc, '-O2', '-mwindows', '-o', exe, src, '-lws2_32'], check=True)
    return exe


# ---------------------------------------------------------------- the helper

class Helper:
    """A connection to t7helper.exe (serve <port> <secret>)."""

    def __init__(self, port, secret, timeout=90):
        end = time.time() + timeout
        while True:
            try:
                self.s = socket.create_connection(('127.0.0.1', port), timeout=5)
                break
            except OSError:
                if time.time() > end:
                    raise DumpError('the helper did not start')
                time.sleep(0.5)
        self.s.settimeout(180)
        self.buf = b''
        self.send(secret)

    def _fill(self):
        c = self.s.recv(1 << 20)
        if not c:
            raise DumpError('the helper stopped')
        self.buf += c

    def _line(self):
        while b'\n' not in self.buf:
            self._fill()
        line, self.buf = self.buf.split(b'\n', 1)
        return line.decode('latin1').rstrip('\r')

    def _exact(self, n):
        while len(self.buf) < n:
            self._fill()
        d, self.buf = self.buf[:n], self.buf[n:]
        return d

    def send(self, line):
        self.s.sendall((line + '\n').encode())

    def _answer(self, line):
        self.send(line)
        answer = self._line()
        if answer.startswith('error'):
            raise DumpError(answer[6:])
        return answer

    def dlc(self, dll):
        self.send('dlc ' + dll)
        out = []
        while True:
            line = self._line()
            if line == 'end':
                return out
            if line.startswith('error'):
                raise DumpError(line[6:])
            a, owned, name = line.split(' ', 2)
            out.append((int(a), owned == '1', name))

    def attach(self):
        return self._answer('attach')

    def ready(self):
        return self._answer('ready') == '1'

    def common(self):
        return int(self._answer('common'), 16)

    def load(self, fighter):
        """-> (record, the game's code of the fighter)."""
        record, code = self._answer('load %d' % fighter).split()
        return int(record, 16), code

    def fixup(self, record, common):
        moveset, movelist = self._answer('fixup %x %x' % (record, common)).split()
        return int(moveset, 16), int(movelist, 16)

    def read(self, address, size):
        self.send('read %x %d' % (address, size))
        line = self._line()
        if not line.startswith('data '):
            raise DumpError('helper: ' + line)
        return self._exact(int(line.split()[1]))

    def u64(self, address):
        return int.from_bytes(self.read(address, 8).ljust(8, b'\0'), 'little')

    def files(self, paths):
        """The game's files (pak paths, 'TekkenGame/Content/...') as the game reads them: [bytes, or None where the
        game could not read one], in order."""
        for p in paths:
            self._answer('want ../../../' + p)
        self.send('fetch')
        out = []
        while True:
            line = self._line()
            if line == 'end':
                return out
            if line.startswith('error'):
                raise DumpError(line[6:])
            _, ok, n = line.split()
            d = self._exact(int(n))
            out.append(d if ok == '1' else None)

    def quit(self):
        try:
            self.send('quit')
            self.s.close()
        except OSError:
            pass


# ---------------------------------------------------------------- the hidden session

INSIDE = r'''#!/bin/sh
# Run by gamescope (headless); the session lasts as long as this script.
if [ "$WITH_GAME" = 1 ]; then
  ( cd "$T7DIR" && PULSE_SINK="$SINK" "$PROTON" run "$T7DIR/TEKKEN 7.exe" > "$RUN/game.log" 2>&1 ) &
  i=0
  while [ $i -lt 360 ]; do
    for f in /proc/[0-9]*/comm; do [ "$(cat "$f" 2>/dev/null)" = "TekkenGame-Win6" ] && { p=${f#/proc/}; echo ${p%/comm} > "$RUN/game.pid"; }; done
    [ -s "$RUN/game.pid" ] && break
    i=$((i + 1)); sleep 0.5
  done
  [ -s "$RUN/game.pid" ] || exit 1
  # (without the game's app id: Steam would count the helper as the game)
  env -u SteamAppId -u SteamGameId -u STEAM_COMPAT_APP_ID "$PROTON" run 'C:\t7helper.exe' serve "$PORT" "$SECRET" > "$RUN/helper.log" 2>&1 &
  while kill -0 "$(cat "$RUN/game.pid")" 2>/dev/null; do sleep 1; done
  exit 0
fi
exec "$PROTON" run 'C:\t7helper.exe' serve "$PORT" "$SECRET" > "$RUN/helper.log" 2>&1
'''


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Session:
    """Tekken 7's prefix inside gamescope's headless backend: the helper alone, or the game and the helper."""

    def __init__(self, t7, helper_exe, run, with_game):
        self.t7, self.run = t7, run
        os.makedirs(run, exist_ok=True)
        if os.path.exists(os.path.join(run, 'game.pid')):
            os.remove(os.path.join(run, 'game.pid'))
        shutil.copyfile(helper_exe, os.path.join(t7.prefix, 'pfx', 'drive_c', 't7helper.exe'))
        self.sink_module = None
        if with_game:
            sinks = subprocess.run(['pactl', 'list', 'short', 'sinks'], capture_output=True, text=True).stdout
            if SINK not in sinks:
                r = subprocess.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=' + SINK,
                                    'sink_properties=device.description="Tekken 7 (silent, ttt2)"'],
                                   capture_output=True, text=True)
                self.sink_module = r.stdout.strip() or None
        inside = os.path.join(run, 'inside.sh')
        with open(inside, 'w') as f:
            f.write(INSIDE)
        os.chmod(inside, 0o755)
        self.port, self.secret = _free_port(), secrets.token_hex(16)
        env = dict(os.environ, STEAM_COMPAT_CLIENT_INSTALL_PATH=t7.steam, STEAM_COMPAT_DATA_PATH=t7.prefix,
                   SteamAppId=str(APP_ID), SteamGameId=str(APP_ID), STEAM_COMPAT_APP_ID=str(APP_ID),
                   PROTON=os.path.join(t7.proton, 'proton'), T7DIR=t7.game, RUN=run, SINK=SINK, PORT=str(self.port),
                   SECRET=self.secret, WITH_GAME='1' if with_game else '0')
        self.gamescope = subprocess.Popen(
            ['gamescope', '--backend', 'headless', '-W', '1280', '-H', '720', '-w', '1280', '-h', '720', '-r', '60',
             '--', inside], env=env, stdout=open(os.path.join(run, 'gamescope.log'), 'w'), stderr=subprocess.STDOUT)
        self.helper = None

    def wait_game(self, timeout=240):
        end = time.time() + timeout
        while time.time() < end:
            p = os.path.join(self.run, 'game.pid')
            if os.path.isfile(p) and open(p).read().strip():
                return int(open(p).read())
            if self.gamescope.poll() is not None:
                raise DumpError('the hidden session ended (see %s)' % self.run)
            time.sleep(0.5)
        raise DumpError('Tekken 7 did not start within %d s' % timeout)

    def connect(self):
        self.helper = Helper(self.port, self.secret)
        return self.helper

    def close(self):
        if self.helper:
            self.helper.quit()
        wineserver = os.path.join(self.t7.proton, 'files', 'bin', 'wineserver')
        subprocess.run([wineserver, '-k'], env=dict(os.environ, WINEPREFIX=os.path.join(self.t7.prefix, 'pfx')),
                       capture_output=True)
        time.sleep(1)
        if self.gamescope.poll() is None:
            self.gamescope.terminate()
            try:
                self.gamescope.wait(10)
            except subprocess.TimeoutExpired:
                self.gamescope.kill()
        if self.sink_module:
            subprocess.run(['pactl', 'unload-module', self.sink_module], capture_output=True)


# ---------------------------------------------------------------- the encrypted files

def encrypted_files(paks, code):
    """The pak entries of a fighter (its Tekken 7 code in the path) that the game keeps encrypted."""
    code = code.lower()
    return [e for k, e in sorted(paks.index.items()) if code in k and paks.encrypted(e)]


def unsaved_files(paks, code):
    """The fighter's encrypted entries not in paks.saved yet."""
    out = []
    for e in encrypted_files(paks, code):
        p = paks.saved_path(e)
        if not p or not os.path.isfile(p) or os.path.getsize(p) != e.usize:
            out.append(e)
    return out


def _save_files(h, paks, entries):
    """Has the game read the entries (in batches) and saves them below paks.saved."""
    k = 0
    while k < len(entries):
        batch, size = [], 0
        while k < len(entries) and len(batch) < FILE_BATCH and (not batch or size + entries[k].usize <= FILE_BATCH_BYTES):
            batch.append(entries[k])
            size += entries[k].usize
            k += 1
        for e, d in zip(batch, h.files([e.path for e in batch])):
            if d is None or len(d) != e.usize or not plain(e.path, d):
                raise DumpError('Tekken 7 did not read %s' % e.path)
            path = paks.saved_path(e)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + '.part', 'wb') as f:
                f.write(d)
            os.replace(path + '.part', path)


# ---------------------------------------------------------------- dumping

def owned_dlc(t7, helper_exe, run):
    """{DLC app id: owned} as the game asks Steam."""
    s = Session(t7, helper_exe, run, False)
    try:
        h = s.connect()
        return {a: owned for a, owned, _ in h.dlc('Z:' + os.path.join(t7.game, STEAMWORKS))}
    finally:
        s.close()


def unowned(fighters, cache=None):
    """{roster id: reason} of the fighters (roster ids) whose DLC the player's Steam account does not own, as Steam
    tells the game (Steam must be running). Base-game fighters are always owned."""
    dlc = [fid for fid in fighters if fid in DLC]
    if not dlc:
        return {}
    if not steam_running():
        raise DumpError('Steam is not running: start it, then try again (it tells which fighters you own)')
    cache = cache or os.path.join(os.path.expanduser('~/.cache'), 'ttt2', 'tekken7')
    owned = owned_dlc(find_tekken7(), build_helper(cache), os.path.join(cache, 'run'))
    return {fid: 'its DLC is not owned' for fid in dlc if not owned.get(DLC[fid], False)}


def _until(what, condition, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return
        time.sleep(0.5)
    raise DumpError(what)


def dump(fighters, out, log=print, cache=None, files=None, paks=None):
    """Dumps the fighters ({roster id: (Tekken 7 code, name)}) into `out` as T7_<name>.tkmvst; Heihachi too (when
    there are any). files: {roster id: (name, [pak entries])}: also saves those encrypted files (from unsaved_files)
    of the fighters, as the game reads them, below paks.saved. -> ({id: path} dumped, {id: reason} skipped)."""
    if not steam_running():
        raise DumpError('Steam is not running: start it, then try again (Tekken 7 needs it)')
    if _running(GAME_COMM):
        raise DumpError('Tekken 7 is running: close it first')
    cache = cache or os.path.join(os.path.expanduser('~/.cache'), 'ttt2', 'tekken7')
    run = os.path.join(cache, 'run')
    t7 = find_tekken7()
    helper_exe = build_helper(cache)
    os.makedirs(out, exist_ok=True)
    log('Tekken 7: %s (Proton: %s)' % (t7.game, os.path.basename(t7.proton)))
    owned = owned_dlc(t7, helper_exe, run)
    names = dict(fighters)
    if names:
        names.setdefault(HEIHACHI, ('hei', 'Heihachi'))
    files = {fid: v for fid, v in (files or {}).items() if v[1]}
    skipped = {}
    for fid in list(names) + list(files):
        if fid in DLC and not owned.get(DLC[fid], False):
            skipped[fid] = 'its DLC is not owned'
    wanted = [fid for fid in names if fid not in skipped]
    files = {fid: v for fid, v in files.items() if fid not in skipped}
    dumped = {}
    if not wanted and not files:
        return dumped, skipped
    log('Starting Tekken 7 in the background (no window, no sound) ...')
    s = Session(t7, helper_exe, run, True)
    try:
        s.wait_game()
        h = s.connect()
        end = time.time() + 60
        while True:                                      # (the game's code may not be mapped at once)
            try:
                h.attach()
                break
            except DumpError:
                if time.time() > end:
                    raise
                time.sleep(1)
        _until('Tekken 7 did not get ready', h.ready, 120)
        for fid, (name, entries) in files.items():
            log('  %s: %d encrypted files (%d MB), as the game reads them'
                % (name, len(entries), sum(e.usize for e in entries) >> 20))
            _save_files(h, paks, entries)
        if wanted:
            common = h.common()
            _until('the shared animations did not load', lambda: h.u64(common + COMMON_ANIMATIONS), LOAD_TIMEOUT)
        for k in range(0, len(wanted), BATCH):
            batch = {}
            for fid in wanted[k:k + BATCH]:
                try:
                    batch[fid] = h.load(fid)
                except DumpError as e:
                    skipped[fid] = str(e)
            end = time.time() + LOAD_TIMEOUT
            pending = dict(batch)
            while pending and time.time() < end:
                for fid, (record, code) in list(pending.items()):
                    if not h.u64(record + RECORD_MOVELIST):
                        continue
                    del pending[fid]
                    moveset, movelist = h.fixup(record, common)
                    blocks = memdump.read_moveset(h.read, moveset, movelist)
                    path = os.path.join(out, 'T7_%s.tkmvst' % names[fid][1].replace(' ', '_'))
                    memdump.write_tkmvst(path, blocks, fid, names[fid][1])
                    dumped[fid] = path
                    log('  %s' % names[fid][1])
                time.sleep(0.5)
            for fid in pending:
                skipped[fid] = 'it did not load'
    finally:
        s.close()
    return dumped, skipped
