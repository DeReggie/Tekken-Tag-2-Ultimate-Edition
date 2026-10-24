# Fahkumram alternate outfits: implementation and reproduction guide

**Roster-wide update:** the current source supports all 17 imported fighters. See `IMPORTED_PRESET_OUTFITS.md` for the current 14-entry menu limit, 32-bit private registry namespace, blueprint accessories and chain support. Earlier trial limits and numeric log examples in this document are historical.

**Kazumi extension:** the current source also builds nine Kazumi presets with tiger compatibility checks. See `KAZUMI_PRESETS.md`. Numeric log examples below describe the original successful Fahkumram trial; registry IDs can change when more outfit packs are loaded.

This documents the working in-game costume-menu implementation tested on October 23, 2026. It is intended for someone extending the importer and runtime to another imported fighter.

**The essential rule: keep the fighter's gameplay identity, but give the appearance recipe the selected outfit's body code.** Changing the fighter ID made Fahkumram invisible. Keeping his ID while allowing the native loader to substitute his base body made every selection look like Default. Both the identity and the appearance handoff must be handled correctly.

## What is confirmed

- The native CHANGE COSTUME menu displays all seven Fahkumram preset previews.
- Default renders in a match.
- The sixth preset, Royal (purple clothing and shoulder armor), now loads and renders in a match; the user confirmed this.
- The successful trace shows the recipe retaining fighter ID 74 while reading `fkf.xml`, `fkf.bon`, `fkf.nud`, `fkf.mop`, and `fkf.nut`.
- The focused Python suite passed 78 tests during development. The runtime compiled and passed startup checks.

All seven bodies were generated and structurally checked. That does **not** mean every outfit, mirror match, team position, effect, or animation has been playtested. Those remain part of the checklist below.

The working executable and packs are currently an isolated trial. This feature has not been installed into the normal game or added to the existing PR by this work.

## 1. Source changes to carry over

These are the outfit-specific files. Paths are relative to the repository root:

| File | Purpose |
| --- | --- |
| `tools/characters/ttt2char/characters/fahkumram.py` | Ordered `PRESETS` definition. |
| `tools/characters/ttt2char/convert/outfits.py` | Discover each full preset, convert bodies, relocate textures, build previews and supporting files. New file. |
| `tools/characters/ttt2char/importer.py` | Build optional outfits and pass their codes to the pack writer. |
| `tools/characters/ttt2char/pack.py` | Optional `outfits` metadata, preserving behavior for ordinary packs. |
| `runtime/src/title/roster.cpp` | Read/validate packs, register bodies, expose chooser entries, retain selection, hand appearance to the native loader. |
| `runtime/src/title/outfit_menu.h` | Chooser confirmation and loader-cache rules with compile-time checks. New file. |
| `tools/characters/tests/test_outfits.py` | Preset discovery, gameplay preservation, texture relocation, and metadata tests. New file. |
| `docs/FAHKUMRAM_PRESETS.md` | This implementation guide. |

A plain `git diff HEAD` in the development checkout also includes earlier gameplay customizations. It omits the contents of new untracked files. Do not treat that whole diff as the outfit-only change.

The accompanying `fahk-preset-menu.patch` compares these files against the original local source as it existed during this work, including new files. It is **not** guaranteed to apply unchanged to an arbitrary upstream revision. In your own checkout, inspect and check it before applying:

```bash
git status --short
git apply --check /path/to/fahk-preset-menu.patch
git apply /path/to/fahk-preset-menu.patch
```

If the check fails, port the changes by file and function rather than forcing the patch. Preserve existing customizations.

## 2. Define and discover the presets

Fahkumram's base code is `nsc`; his T7 set directory is `NSC`:

```python
PRESETS = (
    ('DefaultCos1P', 'Default'),
    ('DefaultCos2P', 'Default 2P'),
    ('1P_c1', 'Default alternate'),
    ('Champ', 'Champion'),
    ('Champ_silver', 'Champion silver'),
    ('trad_royal', 'Royal'),
    ('trad_royal_c1', 'Royal alternate'),
)
```

The first value is the actual asset suffix; the second is a development label. Menu selection is by the corresponding picture. The trial does not add these English labels to the game's menu.

For example, Royal is:

```text
/Game/Character/Item/Sets/NSC/CS_NSC_trad_royal
```

Discover another fighter's actual set assets instead of guessing their spelling. From the source checkout, this read-only script lists candidate set packages from your own T7 installation:

```bash
python3 - <<'PY'
import os
import sys
sys.path.insert(0, 'tools/characters')
from ttt2char.tekken7.pak import Paks

folder = os.path.expanduser('~/.local/share/Steam/steamapps/common/TEKKEN 7')
paks = Paks(os.path.join(folder, 'TekkenGame', 'Content', 'Paks'))
# Change this to the other fighter's set directory.
prefix = 'TekkenGame/Content/Character/Item/Sets/NSC/'.lower()
for entry in sorted(paks.index.values(), key=lambda e: e.path.lower()):
    if entry.path.lower().startswith(prefix) and entry.path.lower().endswith('.uasset'):
        print(entry.path)
PY
```

A set being present is only discovery evidence. Check that it is a usable full preset and that its dependencies and preview can be read.

## 3. Convert a full body for each preset

`outfits.definition()` copies the base fighter's uppercase configuration into a temporary definition. It calls:

```python
model.costume_items(paks, costume_path, follow=True)
```

Following dependencies matters: a preset may reference other item definitions. Collect every `SkeletalMeshAnim` item, deduplicate its skeletal-mesh path case-insensitively, and classify it by its asset folder:

| T7 folder | Conversion tag |
| --- | --- |
| `Face` | `fac` |
| `Lower` | `bdl` |
| `Upper` | `bdu` |
| `Hair` | `har` |
| `Face_Hair` | `fah` |
| `Head` | `hed` |

Keep the base definition's merge order where possible, then append newly discovered parts. Unknown categories fail explicitly, rather than silently omitting clothing.

The temporary definition retains the base `CODE`, material rules, skeleton/weapon configuration, and gameplay rules. Replace its `TEKKEN7` model inputs with the chosen preset's parts. Do not keep `costume_2p`: each preset's colors are baked into its own body, rather than treating it as a second color layer of Default.

Run the existing `model.convert()` for each definition. **Keep the base mesh naming convention.** The working trial did not require renaming `nsc_*` meshes to the alias prefix.

Each outfit supplies:

```text
<alias>.nud      model
<alias>.nut      textures
<alias>.bon      skeleton
<alias>.xml      body item/effect definitions
<alias>.mop      spring/static attachment support
```

The XML is the base fighter's generated XML. Runtime supplies matching effect aliases. Preserve required static weapon/OPT bones in the MOP; Fahkumram's custom hitbox attachment must survive every costume.

The trial started with a private copy of the installed pack and added appearance files, preserving its existing moveset and motion files. The normal full importer also regenerates gameplay from the source configuration, so use the checkout containing your intended gameplay fixes.

## 4. Give bodies and previews distinct texture IDs

Fahkumram's body aliases are `fka` through `fkg`; Kazumi uses `kza` through `kzi`. They are appearance codes, not extra roster fighters.

The current body-texture allocation (expanded from the original stride of eight for Kazumi) is:

```python
first = 0x10500000 + (slot * 16 + preset_index) * 0x1000
```

For each owned texture, map its old GIDX to a new ID and update **both**:

1. The GIDX in the NUT texture container.
2. Every corresponding texture reference in NUD materials.

Leave external/shared texture references unchanged. Remove each texture's cached `ext` field before serializing the NUT, so the writer regenerates the GIDX extension. Merely editing the decoded `gidx` field can leave the old serialized ID behind.

Build each matching preview with `art.costume_previews()`. Fahk's `DefaultCos1P` and `DefaultCos2P` use preview suffixes `01` and `02`; the other presets currently use uppercased suffixes. This naming shortcut must be checked for every additional fighter.

Relocate preview IDs too. The current preview adjustment is:

```python
texture['gidx'] += 128 + slot * 16 + preset_index
texture.pop('ext', None)
```

Combine the previews, in preset order, into `art/costumes.nut`. Keep the NUT texture count, alias list, and chooser order identical. Check texture/vertex budgets and ID collisions when extending the allocation scheme.

## 5. Write optional pack metadata

Fahkumram's `character.ini` gains:

```ini
outfits = fka fkb fkc fkd fke fkf fkg
```

Keep the base `nsc.*` files as the fallback body and the only moveset/motion source. Do not make duplicate fighter packs for the costumes.

`importer.py` runs `outfits.build()` only when a fighter defines `PRESETS`. `pack.character_ini()` and `pack.write()` accept optional outfit codes. Existing packs without the field retain their previous behavior.

Runtime validates three-letter lowercase, unique aliases different from the base code, all five required files per alias, and an `NTP3` preview count matching the list. An invalid list falls back to the ordinary body.

## 6. Register aliases and preserve the native menu

In `roster.cpp`:

- Serve alias body files through the archive overlay using the donor's corresponding archive flags.
- Register each alias's file keys in the native key registry.
- Share the base fighter's part-pack keys, gameplay motion row, and effects; serve effect files under the alias code too.
- Add chara-master entries for alias lookup. Reserve separate registry IDs without creating roster cells.
- Repeat the donor's first native equipment entry for the preset count. The picture/body choice is separate from the native equipment style.

The current registry ID pool is **192 through 207: sixteen IDs total**, not eight for each fighter. Fahk uses seven and Kazumi uses nine, filling the pool. The earlier IDs 336–342 exceeded byte-sized identity fields and were replaced. Do not extend this by assigning arbitrary larger IDs.

The native function `sub_033E265C` handles both opening the costume menu and confirming a choice. Only normalize the native style to `1` at the two confirmed chooser return addresses:

```text
0x033E3B30
0x033E3BDC
```

These addresses are specific to this supported guest executable. Forcing style `1` on every call bypasses CHANGE COSTUME and immediately selects the fighter.

Capture the original one-based menu choice before normalization. `sub_033E2530` saves its zero-based outfit index by side/member, with the side and member captured before calling the native function. Native loader slots use:

```text
slot = side + 2 * member
```

## 7. The critical loading fix

The working path uses two different identities for different purposes:

| Value | Royal in this installation | Purpose |
| --- | --- | --- |
| Base gameplay ID | `74` | Fahkumram's actual player/cache identity. Derived from his installed slot. |
| Outfit registry ID | `197` | Find the `fkf` appearance entry. Never substitute it for the real player's identity. |
| Selected body code | `fkf` | Resolve Royal's actual body files. |
| Gameplay motion row | `74` | Base fighter's animations/moves. Derived from the installed slot mapping. |

Do not hardcode those numeric examples for another installation or fighter.

### Load request: `sub_044BE1EC`

Resolve the picked outfit for the native player slot. Record its registry body in `g_outfit_bodies[slot]` and issue the existing added-fighter proxy load using the selected body code. Restore the normal code-table entry and the player's base ID afterward. Ordinary fighter loads clear that slot's pending outfit body.

The native loader cache compares fighter records, not outfit codes. When a completed slot requests a different body code for the same record, invalidate its cached current record using the native empty-record sentinel `139`. Do not do this while a load is pending.

### Code lookup: `sub_0209506C`

Let the native chara-master lookup find the alias. For a recognized active outfit, replace only the returned tuple's ID with the base fighter ID. Keep its row and strings. This lets the command parser index its cache under the actual fighter identity.

This alone was insufficient: a later native lookup reconstructs the appearance recipe from the base fighter's master entry and loses the outfit code.

### Recipe initialization: `sub_02091898`

Read the recipe's native player-slot index at `recipe + 20`. Use the explicit `g_outfit_bodies[slot]` handoff to recover the selected alias, rather than expecting the incoming tuple to still contain it.

Make a private 72-byte tuple copy and supply:

```text
tuple + 0   base fighter ID
tuple + 4   base gameplay motion row
tuple + 8   selected outfit name string
tuple + 40  selected outfit code string
```

Assign the strings with the native string helper; do not replace string objects with raw pointers. Call the original initializer with the private tuple. Leave the shared master entry unchanged.

**The resulting recipe at `recipe + 24` must retain the base fighter ID.** In the successful Royal test it is `74`, while the strings request `fkf`.

This is the combination that worked. Using registry ID `197` in that recipe made the character invisible. Keeping base ID `74` but allowing both strings to become `nsc` loaded Default regardless of menu choice.

## 8. Rebuild and import safely

Use a source checkout containing the complete feature, including new files. Build the matching runtime; the original executable does not understand this pack extension.

For an already configured checkout with generated EU v16 code and dependencies:

```bash
cmake --build build --target ttt2
```

For initial build setup, follow the repository README. Native addresses and structures in this implementation must be rechecked for a different guest revision.

Use a **fresh private copy of the full installed character directory** for the trial. Keeping existing pack slots and `shared/` together avoids changing other fighters' slot assignments. Example, run once from your feature checkout; choose an unused output directory:

```bash
mkdir -p "$HOME/ttt2-outfit-test"
cp -a "$HOME/.local/share/ttt2/characters" "$HOME/ttt2-outfit-test/characters"

python3 tools/characters/import_character.py fahkumram \
  --tekken7 "$HOME/.local/share/Steam/steamapps/common/TEKKEN 7" \
  --movesets "$HOME/.local/share/ttt2/tekken7/movesets" \
  --game "$HOME/Games/TekkenTag2/game" \
  --out "$HOME/ttt2-outfit-test/characters"
```

The importer requires the player's game assets and a usable T7 moveset dump. This command performs a full fighter import; it is not an appearance-only overlay operation.

Then launch the matching runtime with the private packs and a separate save directory:

```bash
TTT2_CHARACTERS="$HOME/ttt2-outfit-test/characters" \
TTT2_SAVE_DIR="$HOME/ttt2-outfit-test/save" \
TTT2_TRACE_ROSTER=1 \
./build/ttt2 "$HOME/Games/TekkenTag2/game" \
  2>&1 | tee "$HOME/ttt2-outfit-test/playtest.log"
```

Fully close and reopen the process after replacing its executable or model files.

## 9. Generalize for another fighter

The runtime machinery is reusable, but the current converter is **Fahkumram-specific** in several places. Adding `PRESETS` alone is not enough.

1. **Set root:** the builder now derives the set root from `TEKKEN7_CODE.upper()`. Check that convention for another fighter; use explicit full paths if it differs.
2. **Alias allocation:** `outfits.codes()` currently supports `nsc` and `kzm`; it rejects other base codes. Assign globally unique lowercase three-letter aliases and check them against all fighter and outfit codes. Keep them stable across rebuilds.
3. **Registry capacity:** redesign/expand the sixteen-entry runtime identity pool after checking every affected native representation. Fahkumram and Kazumi together fill the current pool. Do not simply reuse Fahk's IDs or aliases.
4. **Preset count:** runtime currently accepts at most nine per pack; texture namespaces reserve sixteen positions per fighter. Nine plus five native customization rows fit the existing chooser storage. More presets require coordinated changes, including preview allocation and menu limits.
5. **Preview names:** verify real art assets. Replace Fahk's suffix shortcut with explicit per-preset preview references if needed.
6. **Mesh categories and attachments:** add mappings only after checking skeleton parenting and material behavior. The fallback for a new mesh tag assumes a head attachment; it is not appropriate for every accessory.
7. **Animated attachments:** the builder now supports Kazumi's `TIGER`, including matching bone indices/bind transforms and generating MOP entries. Fighters with nonempty `CHAINS` remain rejected; implement proper preset-specific conversion before enabling them. Do not remove the guard to hide missing cloth, chains, animals, or weapons.
8. **Skeleton/weapon compatibility:** verify the base pack's weapon-point metadata against every generated BON. If bone indices differ, a shared base weapon registry may require an extension or consistent skeleton layout.
9. **Encrypted assets:** this trial did not implement Geese/Noctis preset support. Their source assets need the existing decrypted-file capture path as applicable.
10. **Test one fighter at a time:** begin with a visibly different preset, then test all color variants and multi-fighter combinations.

## 10. Verification and troubleshooting

Run the focused tests from the repository root:

```bash
python3 - <<'PY'
import unittest
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for name in ('test_outfits.py', 'test_packs.py', 'test_formats.py',
             'test_model.py', 'test_weapons.py'):
    suite.addTests(loader.discover('tools/characters/tests', pattern=name))
result = unittest.TextTestRunner().run(suite)
raise SystemExit(not result.wasSuccessful())
PY
```

Inspect the model/texture references, disjoint texture IDs, preview counts, required files, weapon attachment registry, and budget limits. If adding appearance files to an existing pack, compare hashes of its moveset and motion files before/after.

Then playtest:

- All previews, especially their order relative to the loaded bodies.
- A distinctly different preset from a fresh launch.
- Changing outfits between matches without restarting.
- Both sides and both tag-team positions.
- A mirror match with different outfits, plus repeated matches.
- Intro/win animations, hit effects, tag actions, special attachments and customized attacks.
- A normal pack without outfit metadata, and incomplete outfit data falling back safely.

With `TTT2_TRACE_ROSTER=1`, a successful Royal selection in this trial produced:

```text
costume chooser built 7 entries for nsc
confirmed menu entry 6 for nsc
slot 0 model fkf: accepted=1 pending=1 ...
slot 0 body recipe fkf (registry 197), incoming fighter 74, stored fighter 74
read body file fkf.xml
read body file fkf.bon
read body file fkf.nud
read body file fkf.mop
read body file fkf.nut
```

The added file-read observer logs each recognized file once per process. It is disabled when `TTT2_INPUT_SCRIPT` needs the same archive observer. A completed load alone does not prove rendering; check the actual match.

| Symptom | Check |
| --- | --- |
| CHANGE COSTUME immediately selects the fighter | Style normalization must occur only at native chooser confirmations. |
| Menu freezes/retries endlessly | Registry IDs, native identity width, pending/current record state, and alias lookup. |
| Correct preview, Default in match | Slot choice survived, but recipe name/code may have reverted to the base code. |
| Invisible fighter | Recipe/player identity agreement first; then actual file reads, model/skeleton data and texture references. |
| Previous costume sticks after changing it | Record-only loader cache needs invalidation on a completed body-code change. |
| Wrong colors or textures | NUD references and serialized NUT GIDX must agree; check overlapping ID ranges. |
| Only a static/weapon/cloth part is missing | Skeleton OPT metadata, MOP, animated attachments and preset dependencies. |

## Local reference artifacts from this session

These paths identify the tested implementation on this machine; they are not required directory names for another developer:

- Source: `work/fahk-outfits/` under the conversation workspace.
- Launcher: `outputs/run-fahk-outfits.sh`.
- Candidate: `outputs/fahk-preset-trial/ttt2-outfits`.
- Private pack: `outputs/fahk-preset-trial/characters/nsc/`.
- Log: `outputs/fahk-preset-trial/playtest.log`.
- Feature patch: `outputs/fahk-preset-menu.patch`.
- Preset inventory: `outputs/T7-Preset-Outfit-Inventory.json`.

The first trial alias, `fka`, currently uses byte-identical original installed body files from a controlled diagnostic. The other presets use converted assets; Royal is confirmed working. A clean full import builds all seven through `outfits.build()`, so recheck Default after removing that diagnostic substitution.

Share source changes and this guide. Generate personal model/texture packs locally from the player's own games; do not include the game's converted assets or executable in the source patch.
