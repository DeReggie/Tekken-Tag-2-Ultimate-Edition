# Kazumi preset outfits

**Roster-wide update:** the current source supports all 17 imported fighters. See `IMPORTED_PRESET_OUTFITS.md` for the current 14-entry menu limit, 32-bit private registry namespace, blueprint accessories and chain support. Earlier trial limits and numeric log examples in this document are historical.

This extends the working Fahkumram outfit implementation to Kazumi. The first trial is isolated from the installed game and from the previously working Fahkumram trial.

## Preset order

| Menu entry | Source suffix | Body code |
| --- | --- | --- |
| 1 | DefaultCos1P | kza |
| 2 | DefaultCos2P | kzb |
| 3 | 1p_c2 | kzc |
| 4 | dancer | kzd |
| 5 | dancer_silver | kze |
| 6 | dougi | kzf |
| 7 | lycoris | kzg |
| 8 | lycoris_c1 | kzh |
| 9 | taisyo_roman | kzi |

The sets come from `/Game/Character/Item/Sets/KZM/CS_KZM_<suffix>` in the player's T7 installation. Each has a matching preview asset. These labels describe the source; the native menu uses pictures.

## Changes from Fahkumram

- `kazumi.py` defines all nine presets.
- `outfits.py` derives the set root from `TEKKEN7_CODE`, assigns distinct `kza`–`kzi` aliases, supports `Full_Body` meshes with a body parent, and preserves the base tiger configuration.
- The tiger is converted into every outfit by the existing model converter. Every outfit is checked against the base skeleton for identical tiger bone indices, names, parents, and bind transforms. Its 49 OPT bones use the existing shared tiger animation channels.
- Each outfit's MOP includes the tiger's no-spring entries, built using the same path as the ordinary Kazumi importer. Hanging-chain fighters remain unsupported by the preset builder.
- The normal importer passes the generated base BON as the reference for these checks. An appearance-only trial passes the installed BON and retains the installed moveset and motion bytes.
- Model and preview namespaces reserve 16 positions per fighter, allowing the ninth preset without overlapping the following fighter's allocation. The existing working Fahkumram trial pack is kept unchanged; its actual IDs must be checked for collisions when combined with the new Kazumi pack.
- Runtime accepts nine presets per pack. Nine native preset rows plus the five native customization rows fit the chooser's entry storage; the hook then hides the unsupported customization rows. A compile-time assertion checks that storage boundary.
- The private registry identity pool is 192–207, enough for Kazumi's nine and Fahkumram's seven. Those are appearance lookup identities, not player IDs. Further fighters need more capacity and native representation checks.
- The successful Fahkumram loading rule remains: normalize alias lookup to the base gameplay ID, then initialize the per-player recipe with that base ID and the chosen appearance's name/code strings.

## Reproduction

Use the matching modified runtime and importer, including new files. The feature is not supplied by an unmodified upstream build.

For a fresh private copy of the installed character packs, use the commands in `FAHKUMRAM_PRESETS.md`, changing the import fighter argument to `kazumi`. Build the runtime with `cmake --build build --target ttt2`. Keep existing pack slots and `shared/` intact. Do not combine partial files from different imports.

The trial's `build-outfits.py` is an appearance-only builder: it caches converted bodies, validates the tiger skeletons, builds the nine alias bodies/previews, and adds `outfits` metadata to a private copy of the installed Kazumi pack. It does not regenerate gameplay. Its absolute paths are local to this machine.

## Validation

Automated conversion/format checks do not establish visual correctness. Playtest all nine pictures and bodies, both sides/team positions, and repeated outfit changes. Check tiger attacks, tiger intro/win poses, fly stance during Tag Assault, normal effects, and a tag team with Fahkumram in an alternate outfit. Also recheck Fahkumram's known-working purple outfit in the combined runtime.

In a successful match load, `TTT2_TRACE_ROSTER=1` should show the selected `kz*` body recipe retaining Kazumi's base player ID, followed by reads of that alias's XML/BON/NUD/MOP/NUT. The exact IDs/rows depend on installed pack slots; never hardcode Fahkumram's numeric examples for Kazumi.

The private save, executable, and packs are trial data. Share source changes and docs, not converted game assets.
