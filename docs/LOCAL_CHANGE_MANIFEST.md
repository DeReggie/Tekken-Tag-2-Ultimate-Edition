# Consolidated local changes

Branch: `codex/all-local-changes`. Nothing has been pushed.

The branch includes the exact fetched GitHub heads of PR #8
(`36ed4c5877441e2c312953fa5fe77e0f28ef5fb0`) and PR #10
(`385fb97c405757531856ab4286267007dc60e1c1`) as ancestors.
A recovery commit preserves the main checkout's previously uncommitted files.

## Preserved working changes

- Preset costume importer, menu, body selection and lifecycle support for all
  17 imported fighters, including the Katarina face repair.
- Four-orientation grounded back recovery, shared/generic attack retention,
  owner-character requirement folding, sidestep/input coverage, weapon mapping,
  and normal/string buffer restoration from PR #8 and the later normal-move fixes.
- Akuma's normal/string/special cancels, three custom Bounds, two startup trims,
  d/f+2,1 recovery trim, and restored meter-free EX/supers/Focus routes recovered
  from the earlier local `fahk-outfits` source.
- Eliza's free-meter special routes, hitbox, jump/divekick and missing normal
  input repairs, Bound removals and Moon Glide tag-launch choice.
- Fahkumram's f+3 string, running 3/d+4, Bound/reaction/hitbox choices and shared
  hellsweep elbow airborne tag cancel; Kunimitsu's f+4~F SET assist continuation;
  Noctis's string/weapon corrections and custom Bound choices.
- Move-editing tools, backups, dry runs and selected-fighter rebuilding.
- Geese's 34 buffered special/super sources, free EX/MAX choices, final-hit CD+2
  Bound override, and airborne-only f+1+2 float using native Jinpachi u+4.

Geese's special-route change had been reverted in PR #8's final head even
though the local installed pack retained it. It is explicitly restored here,
with this chat's newer move overrides kept. Earlier intentionally reverted
Eliza b+4 stance experiments are not re-enabled.

## Geese grounded scaling

The local T7 executable selects Geese (character 43) at VA `0x1407166FA`
and calls the grounded curve at `0x1406FBE60`. Its jump table at
`0x1406FBEB4` yields percentages 100, 100, 80, 70, 60, 50, 40, 30, 20,
10 for counter values 0 through 9, with 10 thereafter.

The runtime adds that rule to Geese's normal grounded damage result, using
TTT2's existing side combo counter and its existing reset logic. Native air,
downed and non-standard damage paths remain in charge of those cases. It
scales this hit's four damage channels and the training percentage together.
Standalone damage remains unchanged. This is implemented and unit-tested;
matching the live combo counter timing and gameplay still needs player testing.

## Outstanding gameplay report

Geese's normal-to-special transition fails when he is the Tag Assault partner,
while Akuma's works. This has not yet been confirmed fixed. The restored full
Geese pack can be tested, and `TTT2_TRACE_SPECIAL_CANCELS=1` logs motion capture,
contact latching and dispatch checks for a precise reproduction. Do not report
this issue as resolved merely because source/pack tests pass.

## Rebuilding without losing local work

Build from this branch. A source change alone does not change installed packs.
Rebuild affected fighters from these definitions and validate their generated
moveset/motion pair together. Preserve installed outfit/art/voice files when
installing a gameplay-only update. Keep the two launch executables synchronized:
`build/ttt2` and the copy in `~/Games/TekkenTag2/`.

Checks: current PR ancestry, all 17 preset definition counts, free-meter and
move-choice integration tests, the full character suite, native outfit menu,
scaling and title tests, and regenerated pack move/animation/metadata audits.
Game files and generated packs are not committed.

- Grounded counter-hit Screw launch reactions preserve the juggle Bound allowance; airborne Bound conversions remain unchanged. Shared conversion and 13 affected installed packs updated.

- Eliza gameplay pack rebuilt from consolidated source after discovering the preserved installed pack lacked special-cancel fixes. All 16 configured source routes verified in the rebuilt pack; all eight costume assets preserved. Gameplay confirmation pending.

- Negan 4,2 / 1,4,2 share a scoped actual-bat-tip collision candidate; gameplay confirmation pending.
- Shared CH crumple conversion preserves `sDm_nkdoBxC` and `sDm_nkd2BxC` instead of remapping them to a normal stagger. Negan and Noctis gameplay packs regenerated and installed; player testing pending.
- Eliza restored cancels confirmed working by the player.
