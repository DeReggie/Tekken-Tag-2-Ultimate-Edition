# Gameplay bug tracker

Branch: `codex/all-local-changes`.

These are player reports, not yet confirmed diagnoses. Work through one issue at a time in the order below. For each, record the exact internal move and input route, source-vs-installed evidence, minimal change, validation, installed files/backups, and whether gameplay confirmation is still needed. A passing build or metadata test alone does not make a gameplay issue resolved. Preserve all existing costumes and unrelated fixes.

The repeated Noctis u/f+1 report is consolidated. Related reaction/projectile reports remain individually tracked until a common cause is demonstrated. Earlier reports of missing moves may already be addressed in source or installed packs; verify both before changing anything.

## Queue

| ID | Fighter | Report | Status |
|---|---|---|---|
| NEG-01 | Negan | 1,2: second hit does not connect | False positive — closed at user request |
| NEG-02 | Negan | 4,2: second hit does not connect | Fixed — confirmed by player |
| NEG-03 | Negan | 1,4,2: final hit does not connect | Fixed — confirmed by player |
| NEG-04 | Negan | INT 4 fails mid-combo | Open |
| NEG-05 | Negan | Hit effects should be red | Open |
| NEG-06 | Negan | d/b+1+2 counter-hit reaction is broken; resembles Noctis u/f+1 problem | CH crumple correction installed; needs gameplay check |
| NEG-07 | Negan | qcf+1 knife is not visible | Open |
| NEG-08 | Negan | Missing sidestep 2 | Open |
| NOC-01 | Noctis | u/f+1 counter-hit reaction is broken (reported twice) | Same CH crumple correction installed; needs gameplay check |
| NOC-02 | Noctis | f+2 deals unscaled combo damage | Open |
| KUN-01 | Kunimitsu II | f+2 deals unscaled combo damage | Open |
| TAG-01 | Noctis / Kunimitsu II | Dagger attacks fail during Tag Assault; inspect each fighter separately | Open |
| FAH-01 | Fahkumram | f,f+1+2 does not hit a grounded opponent | Open |
| FAH-02 | Fahkumram | Missing sidestep 4 | Open |
| FAH-03 | Fahkumram | b+1 hitbox unreliable in combos | Open |
| FAH-04 | Fahkumram | d/f+1 hitbox sometimes fails, e.g. after d/f+2,3 launch | Open |
| LID-01 | Lidia | Cat Foot Stance II (b+3+4) 4,4 has an incorrect hit reaction | Open |
| LID-02 | Lidia (provisional attribution) | qcf+2,2,b,f,f+1+2: last-hit animation is wrong; confirm fighter/notation | Needs clarification |
| LID-03 | Lidia | Missing full-crouch d/f+3 | Open |
| LID-04 | Lidia | Missing sidestep 2 | Open |
| LID-05 | Lidia | Missing sidestep 4 | Open |
| NOC-03 | Noctis | Sword hit effects and impact sounds wrong, e.g. 2,2,2,2 | Open |
| NOC-04 | Noctis | 2,2 fails in combos when opponent was launched on their back | Open |
| NOC-05 | Noctis | Freezes airborne on block instead of teleporting forward: f+2, 2,2,b+2, d/f+1,2 | Open |
| NOC-06 | Noctis | Airborne 2,2,2 stops after its first hit in combos | Open |
| NOC-07 | Noctis | u/f+3 plays only its first kick rather than the full animation | Open |
| NOC-08 | Noctis | Emoman unexpectedly launches; establish exact input and expected reaction | Open |
| NOC-09 | Noctis | Missing b+2,1+2 follow-up | Open |
| NOC-10 | Noctis | d/f+4,2 fails against female characters at the wall | Open |
| NOC-11 | Noctis | Emoman does not work as a wall combo | Open |
| NOC-12 | Noctis | WS 1,2 second-hit hitbox unreliable, especially at tip range | Open |
| NOC-13 | Noctis | Missing sidestep 2 | Open |
| KAZ-01 | Kazumi | 3,2 should Bound | Open |
| KAZ-02 | Kazumi | f,f+2 tiger is not visible | Open |
| GIG-01 | Gigas | f+1+2 counter-hit reaction breaks at the wall | Open |
| GIG-02 | Gigas | Missing d/b+1 crouch jab | Open |
| GIG-03 | Gigas | Missing full-crouch 1,2 | Open |
| GIG-04 | Gigas | Missing full-crouch d+3 | Open |
| GIG-05 | Gigas | Missing full-crouch d/f+2 | Open |
| SYS-01 | General | Game becomes extremely slow after hours; reboot resolves it. Memory leak is a hypothesis, not a diagnosis. | Open |
| SYS-03 | General | Grounded counter-hit Screw launches consume Bound (e.g. Geese standing 4) | Fixed — Geese standing 4 confirmed by player |
| SYS-02 | General | Fighters keep running indefinitely after starting a run. Referenced video was not attached in this message. | Open |
| ELZ-01 | Eliza | Tag Assault b+4 can enter Glide, but attacks out of Glide fail | Open — entry works; follow-ups fail; native trace prepared |
| GEE-01 | Geese (carry-over) | Special cancels fail when entering as Tag Assault partner; Akuma works | Open |

## Investigation log

### NEG-01 — Negan 1,2

Status: False positive — closed at user request. The player reports that 1,2 usually connects and only sometimes misses.

The weapon-animation pair change was an unconfirmed candidate, not an established diagnosis. Reverted that source change and its candidate regression test, and restored all 11 installed Negan files from their verified original backups. No executable rebuild is required; restart the game to reload the restored pack if it was already running.

NEG-02 and NEG-03 remain open independently; no common cause has been confirmed.

## Carry-over validation

Geese grounded scaling and f+1+2 airborne float changes are installed but still need player confirmation. Akuma and Geese were rebuilt after source consolidation; other installed packs were preserved. Do not assume all 17 installed packs match the newest consolidated source until each is audited/rebuilt as appropriate.

### Geese f+1+2 → d+4 airborne pickup — reopened

Player confirmed the previous float-only change still did not allow the pickup. Installed `My_WPF` retains the native float but now returns to neutral at frame 44 rather than 52 (`recovery_trim: 8`). d+4 (`My_t_srk00`) first becomes active at frame 17. This candidate shortens recovery on hit, block and whiff; attack startup, active frames, damage, reactions and existing special cancels are preserved. Source override and installed moveset updated; no executable rebuild required. Binary round-trip validation and all 10 move-override tests passed. Restart and gameplay confirmation required; not marked resolved.

### SYS-03 — Grounded counter-hit Screw launches consume Bound

Geese standing 4 (`My_rk00`) has a distinct grounded CH reaction `sDw_screwL`, separate from its airborne requirement-467 Bound entry. Converted grounded Screw reactions retained T7 property 0x8255 as TTT2 property 0x8193, spending Bound when starting the juggle. The shared converter now removes only 0x8193 from the six grounded `sDw_screw{L,R,LL,LR,RL,RR}` reaction variants. Airborne Screw/Bound reactions and all hit conditions remain intact. Property lists are copied to preserve other users of shared data.

Applied the same correction to 13 affected installed packs, preserving attack data, cancels, animations, costumes and all other tables. Backups and binary round-trip checks completed; 2,210 other installed files hash-verified unchanged. Restart required, no executable rebuild. Test CH standing 4 into a combo ending in a known Bound attack; the later Bound should remain available. Gameplay confirmation pending.

Player confirmed SYS-03: Geese CH standing 4 now preserves the subsequent Bound. Other affected routes share the corrected reactions but have not all been individually tested.

### Eliza — special cancels absent from installed pack

Player reported all cancels failing. Compared with the pre-Screw-fix backup: cancel/requirement tables were identical, so SYS-03 did not overwrite them. Source retained all Eliza fixes, but the preserved installed pack lacked buffered-special capture/dispatch routes. Rebuilt Eliza from consolidated source and installed only `elz.moveset` and `elz.motion`, with backups. Verified all 16 configured special-cancel sources have capture and dispatch rows; all base move names retained, eight costumes and pack metadata unchanged, CH Screw correction retained, 2,221 other files unchanged. Six obsolete Bound Tag Assault twin/exit moves disappear consistently with the existing three `bounds: False` source settings. Twelve special-cancel tests and three local-customization tests passed. Restart required; gameplay confirmation pending.

Eliza special cancels: player confirmed working after the rebuilt pack was installed.

### NEG-02 / NEG-03 — confirmed string misses

Player confirms both 4,2 and 1,4,2 consistently miss the final hit. Both routes reach `Na_rkrp` (1,4 uses `Na_lprk` then cancels into it). Source and installed active frame 26, damage 20 and reaction choices agree; follow-up is present. No weapon-pair change has been reintroduced. Collision cause remains under investigation.

### NEG-02 / NEG-03 — bat-tip collision candidate installed

Player clarified the last swing animates but passes through the opponent. The finisher uses T7 point 0x72, previously approximated as 70 cm along the scaled bat axis (664.65 mm from the grip). The actual T7 model tip bone `ATH_R_weapon001_top` is 873.54 mm from the grip and already exists as native point 71 (T7 0x70). Scoped `Na_rkrp` override extends only the second collision capsule to that actual tip: installed hitbox `48004808` → `48004708`. Inner point, timing, damage, reactions and cancel tables are unchanged by this override. Source override saved, installed moveset backed up, binary round-trip verified. This is a candidate, not a confirmed diagnosis or resolved issue. Restart and test both strings.

### NEG-06 / NOC-01 — retain the two-stage CH crumple

Verified actual inputs: Negan d/b+1+2 is `Na_1lrp`; Noctis u/f+1 is `Mz_9LP` (not the generic jump jab). Both T7 grounded reactions select `sDm_nkdoBxC` on CH, transitioning at frame 24 into `sDm_nkd2BxC`. The installed packs instead selected `ym_y01L`, a normal stagger. Alignment-derived reaction remapping had replaced the crumple. Shared converter now retains these two T7 states when no native counterpart exists, preserving their animation and follow-up while leaving other mappings intact.

Regenerated and installed Negan and Noctis gameplay moveset/motion files, retaining all old base move names, valid animation references, and the prior grounded Screw/Bound fix. Costumes, metadata, effects, voices and other fighters were hash-verified unchanged (2,219 other files). Added regression coverage for both crumple stages, native-counterpart priority and unchanged unrelated remaps. 225 tests run with one skipped and no failures (launcher tests excluded after their previously observed subprocess timeout). No executable rebuild; restart required. Gameplay confirmation pending for both CH reactions. NEG-04 (INT 4 mid-combo) remains open separately.

### ELZ-01 — Moon Glide follow-ups during Tag Assault

Player confirms ordinary special cancels work, but b+4 into Glide during Tag Assault cannot perform any attacks from Glide. Installed `Vp_dash_C`, `Vp_dash_EX` and `Vp_dash_EX2` all retain five attack input rows, but their hitlevel is 0. Working Kunimitsu SET uses hitlevel flag 0x200000 to retain an empty state's assist continuation. Opted in these three non-attacking Glide states to the same flag, guarded against active attacks or a nonzero low hit level. This is a candidate based on the working stance convention; gameplay confirmation is required.

Changed only those three hitlevel fields in the installed Eliza moveset. All cancel/input/requirement tables, timing, damage, animations and other tables are unchanged; 2,222 other files hash-verified unchanged, including costumes, other packs and the executable. Source override retained for future rebuilds, backup saved and binary round-trip verified. Twelve move-override tests passed, including new empty-state preservation and attacking-state rejection coverage. Restart required; no executable rebuild or reimport needed for this installation. Test Tag Assault → Eliza b+4 → Glide → 1, 2, 3, 4 or 1+2, then verify ordinary Glide still works.

### Player test update — Negan confirmed, Eliza flag candidate reverted

Player reports Negan's moves are fixed after the prior batch. NEG-02 and NEG-03 are marked confirmed; Noctis CH still requires its own confirmation. Eliza's Glide hitlevel candidate instead prevented entry, so restored the exact pre-candidate moveset from its hash-verified backup and removed the candidate source option/helper/tests. Prior restored special cancels and other fighter fixes remain intact. ELZ-01 remains open: before the candidate, b+4 could enter Glide but no attacks followed. The assumption that Kunimitsu's stance flag transfers directly to Eliza was disproved in gameplay. Trace the actual b+4 entry and assist cancel gate before any replacement change.

### ELZ-01 — f+3+4 route verified; transition-only candidate

Player confirms using f+3+4 after b+4. The installed command and b+4 capture rows accept that input (buffer code 21) and b+4 dispatches into `Vp_dash_EX`. The reverted flag candidate is not reintroduced: all three Glide states retain hitlevel 0. Instead, an explicitly scoped special-stance-cancel option changes only b+4's two automatic `Vp_dash_EX` dispatch rows from normal attack/string mode 0x182 to native empty-stance mode 0x80, as used by Kunimitsu's working held-forward SET transition. This remains a candidate; the native mode comparison does not prove the cause of the lockout.

Original f+3+4 capture, contact latch gates, windows, damage, all five Glide attacks and other special cancels are preserved. Source configuration and converter guard reject applying this mode to an attacking target. Installed only the Eliza moveset with a verified backup and binary round-trip validation. 227 tests run, one skipped, no failures (launcher tests excluded). Restart and test Tag Assault b+4 → f+3+4 → Glide attack, as well as the same route outside Tag Assault. No executable rebuild needed. Negan's previously confirmed fixes remain installed.

### ELZ-01 — entry-mode candidate ineffective; native diagnostics installed

Player confirms b+4 → f+3+4 enters Glide but still cannot attack. Reverted the two entry-mode rows and their source option/converter/test changes to the prior verified pack. Neither failed flag nor ineffective entry-mode experiment remains active. Native input-gate investigation identifies `sub_03F51E70` as the input eligibility check and `sub_0414E7E4` as the cancel selector. Added opt-in `TTT2_TRACE_ELIZA_ASSIST=1` logging around their original decisions and the physics move transitions, limited to Eliza b+4/Glide. Hooks preserve native results and do not change eligibility, timing, state or input. Ordinary launches keep logging disabled.

Diagnostic executable built and synchronized to both established launch paths. Title, damage scaling, character import and outfit menu CTests passed (4/4). Baseline Eliza moveset restored by SHA-256; confirmed Negan fixes and other packs untouched. A logged normal b+4 → f+3+4 → Glide attack followed by the same route during Tag Assault is needed to distinguish rejected input, missing cancel evaluation and assist exit. No new gameplay candidate installed; issue remains unresolved.


### Eliza / Kunimitsu assist control comparison

Player confirms the failing recorded Glide attempt was during Tag Assault with 3 pressed. The native gate received synthesized inactive-partner tag-out input `03FE0100`, unlike the successful ordinary Glide 3. Installed Kunimitsu II retains the existing f+4~F fix: frame-1 held-forward capture, mode 0x80, and SET non-hit continuation flag 0x200000. SET attack rows still use normal 0x182. Eliza's buffered special entry differs, and earlier separate mode/flag experiments remain reverted. Extended opt-in assist tracing to Kunimitsu f+4/SET and the native inactive-controller routing boundary, recording raw masks and ownership/assist state without modifying native behavior. Rebuilt and synchronized both executable paths; four relevant CTests pass. Character packs untouched. Gameplay fix remains unresolved pending a matching SET versus Glide trace.


### Eliza Glide assist controller routing candidate

The 16:58:52 trace confirms `Vp_dash_EX` has assist=1, owner=0, human control=0, and raw controller activity, yet native inactive routing replaces every input with synthesized TAG (`03FE0100`). Added a scoped runtime exception at `sub_03F53238`: only Eliza, only the three exact Glide states, only active Tag Assault with human control, and only frames 1–24 (the existing Glide attack-input window) use native active-controller decoding `sub_03F52F20`. All other states and frames retain the original inactive handler, including normal assist exit after the window. No masks copied, move IDs invented, or moveset flags changed. This candidate addresses the observed discarded input directly; gameplay confirmation remains required. Kunimitsu and other characters are unaffected.
