# Built-in preset outfits for the imported roster

The combined trial contains 137 preset bodies across all 17 imported fighters. This extends the user-tested Fahkumram/Kazumi in-game costume implementation. All models and textures are generated from the player's own installed games.

## Roster

| Fighter | Presets |
| --- | ---: |
| Kazumi | 9 |
| Lucky Chloe | 10 |
| Eliza | 8 |
| Claudio | 9 |
| Akuma | 7 |
| Gigas | 9 |
| Josie | 10 |
| Katarina | 10 |
| Master Raven | 7 |
| Shaheen | 9 |
| Fahkumram | 7 |
| Leroy | 7 |
| Lidia | 7 |
| Kunimitsu II | 9 |
| Negan | 4 |
| Geese | 7 |
| Noctis | 8 |

Each definition contains an ordered `PRESETS` list. Default 1P and 2P appear first. Labels describe source assets; menu selection uses the corresponding pictures. Kunimitsu's `hoodie_off` set has no separate T7 slot image, so `PRESET_PREVIEWS` explicitly reuses `HOODIE` while still loading the distinct hood-down body.

## Runtime invariants

The successful loading rule is unchanged: **keep the base fighter's ID and motion row, but use the selected outfit's name/code strings in its per-player appearance recipe**. See `FAHKUMRAM_PRESETS.md` for the original investigation and function-level handoff.

The full roster requires more registry keys than fit in the old 192–207 pool. Alias keys now live in a separate **32-bit chara-master map namespace starting at `0x10000`**, with room for 128 × 14 entries. Native registration stores that key as a u32. These keys are not selectable fighter IDs and must never enter byte-sized player/side fields.

`sub_0209506C` normalizes an alias lookup to its base fighter ID before the command parser consumes it. `sub_02091898` also writes the base ID into the actual recipe, supplying the alias only through its strings. This is why wider private map keys work here while the early Fahkumram prototype's unnormalized IDs caused failures. In-game testing verified the expanded-registry runtime renders the Kazumi/Fahkumram alternate outfits. The recipe hook also requires the incoming fighter ID to match the remembered outfit owner: returning to the main menu reuses a player slot for fighter 60 without another loader call. Applying the previous fighter's outfit there caused a black screen; the identity guard fixes that transition, verified in game.

The native chooser has 14 entry slots. Its customization-row loop stops at total count 14 (`033E379C`); it does not always append all five rows. Thus ten preset rows plus four temporary customization rows fit, and the existing hook hides those unsupported customization rows. The preset pack limit is 14, checked in Python and runtime, with a compile-time storage check.

## Conversion and attachments

`convert/outfits.py` derives set roots from `TEKKEN7_CODE`, rather than the output pack code. This distinction matters for Kunimitsu: source `KNM`, output `kmi`.

Full-body, full-head, glasses, hair accessories, lower accessories, and extra meshes are supported in addition to ordinary face/upper/lower/hair parts. Meshes keep the base fighter's naming convention. Matching body parents are used for body/accessory parts rather than assigning every new part to the head.

Wearable blueprints are expanded through their component mesh references. This is necessary for Chloe's tail and Katarina's glasses. Static components keep their costume item offsets; synthetic items are passed through the model converter as `PRESET_ITEMS` so those additions are not lost when it reads costume metadata again.

Hair/tail `CHAINS`, `HIDE`, and `COVERED` rules are copied and filtered against the parts, bones, and materials actually present in each preset. Removing a mask or changing hairstyle must not leave rules referencing absent geometry. Existing valid chain rules still use the normal draping/extra-bone converter. MOP files include the generated chain entries, Kazumi's tiger entries, and static weapon entries as applicable.

Kazumi's tiger bone indices, parent relationships, and bind transforms are checked against the base skeleton. Weapon registries are likewise checked against the base pack for every weapon fighter, retaining the shared gameplay's hit-point and summon bindings.

Body texture allocation uses:

```python
0x10500000 + (fighter_slot * 16 + preset_index) * 0x1000
```

Every owned NUT GIDX and matching NUD material reference is relocated together. Cached NUT extensions are removed before serialization. Preview texture IDs are also relocated. All packs in the combined trial use the current allocation; do not mix old-stride outfit packs without checking collisions.

Alias codes are assigned from the stable `CHARACTERS` order, using `o` plus a fighter letter and preset letter. Fahkumram's `fka`–`fkg` and Kazumi's `kza`–`kzi` codes are retained. Runtime rejects aliases colliding with native or imported fighter codes. Adding a new fighter requires checking alias stability and uniqueness.

Geese and Noctis use the existing `Paks(saved=...)` decrypted-file fallback. Their readable saved assets were present for this build. A different installation must capture any encrypted files that are missing; owning the T7 pak files alone may not supply readable content.

## Building

Use the matching source changes, including new files, then build the runtime:

```bash
cmake --build build --target ttt2
```

The normal importer now generates optional outfit packs for every supported fighter:

```bash
python3 tools/characters/import_character.py --all \
  --game /path/to/TTT2/game \
  --tekken7 /path/to/TEKKEN\ 7 \
  --out /path/to/private/character-packs
```

That command is a **full import**, including gameplay regeneration. Use the source configuration containing your intended move changes, and preserve pack slot assignments/shared resources by starting with a private copy of existing packs.

For this session, the appearance-only `outputs/all-preset-trial/build-all.py` instead reads snapshots in `original-packs/`, converts/caches each preset, then adds only appearance files and outfit metadata to private copies. It checks base moveset/motion bytes before swapping in each finished pack. Its absolute paths are specific to this workspace. The installed game and the earlier working trials are unchanged.

## Verification

Automated checks cover all 137 models, finite vertex/bone data, texture references and unique namespaces, preview counts, MOP entries, tiger/weapon bindings, and preservation of base assets/gameplay. The focused suite passes 84 checks. Native startup must resolve every alias back to the expected base fighter ID and motion row.

These checks do not establish every outfit's visual correctness or gameplay behavior. Test visible outfit changes for every fighter, all ten-entry menus, both sides/team positions, changing costumes between matches, mirror matches, hair/tails, masks/glasses, weapon summons/throws, tiger actions, intros/wins, effects and Tag Assault stance transitions.

Enable `TTT2_TRACE_ROSTER=1` to capture selection, loader state, recipe identity, and actual body-file reads. Alias recipe strings should match the chosen outfit, while the stored fighter ID remains the base player's. Close the process fully before switching trial launchers.

Local trial artifacts:

- `outputs/run-all-outfits.sh`: combined trial launcher.
- `outputs/all-preset-trial/audit.json`: model/texture/attachment audit for each preset.
- `outputs/all-preset-trial/startup.log`: native registry checks.
- `outputs/all-preset-trial/playtest.log`: interactive test log.
- `outputs/All-Character-Outfit-Previews.md`: numbered preview sheets.
- `outputs/all-imported-fighter-outfits.patch`: source-only changes against the original local source snapshot.

Share source and documentation; generate personal packs from the player's own games. Converted game assets and executables are not part of the source patch.
