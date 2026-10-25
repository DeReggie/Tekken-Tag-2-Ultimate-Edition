## Second autonomous batch — 2026-10-24

Noctis b+2 follow-ups restored with scoped attack-to-throw/contact gates; airborne f+2 delayed damage inherits native juggle scaling once. Installed and rebuilt; 4/4 targeted CTests, 229 Python tests (one skipped, launcher excluded). Gameplay confirmation pending. Prior Noctis fixes and 2,222 other character files verified preserved.

# Consolidated gameplay bug list

Updated 2026-10-25. Branch: `codex/all-local-changes`. Merges the full pasted chat report, all visible screenshot rows, and earlier tracked work. Repeated reports are combined; distinct moves, symptoms and test routes remain separate. Existing IDs are preserved.

## Status rules

- **Open / Untriaged:** a reported issue, not a verified diagnosis.
- **Reported resolved:** the screenshot says Resolved; current installed behavior was not independently rechecked for this inventory.
- **Installed / Partial:** a change exists, but the full reported behavior still needs gameplay confirmation.
- **Fixed — confirmed:** the player confirmed the relevant behavior. Later conversation evidence takes precedence over stale screenshot statuses.
- **False positive:** closed at the player’s request; not queued for another fix.
- **Requested behavior change:** design request rather than an established defect.

The screenshot still marks universal CH Screw consumption Open, but the player subsequently confirmed Geese CH 4 preserves Bound. That specific confirmation is retained; universal airborne double-Bound accounting remains separate. Eliza ordinary cancels are confirmed working; her full Tag Assault Glide 3,3 now works, while main-character follow-along is a newly confirmed regression (ELZ-07). Gigas’s broad resolved screenshot row does not specifically name FC d/f+2, so that route needs verification before calling it confirmed.

Input notation: `+` means simultaneous buttons; commas mean a sequence; `~F` means hold/transition forward; CH = counter hit; FC = full crouch; WS = while standing; WR = while running; BT = back-turned; SET/INT = named stances.

## Items needing clarification

- LID-02: the fighter and exact `qcf+2,2,b,f,f+1+2` notation are provisional.
- NOC-14 / ELZ-03: later text names Noctis **d/b+2 CH**, while the original shared crumple report names **u/f+1 CH**. Do not silently treat them as one move.
- NOC-08 / NOC-11 / NOC-16: confirm the exact “emoman” input and test launch reaction, wall combo and Bound behavior separately.
- ELZ-04: screenshot says generic missing hitboxes are resolved, but does not identify whether qcb+2 was included.
- Suggested Noctis d/b+2 reaction references for Claudio/Katarina are reporter proposals, not verified implementation instructions.

## General

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| SYS-01 | Game becomes extremely slow after hours; reboot resolves it. Memory leak is a hypothesis, not a diagnosis. | Open | Earlier tracker; repeated in full text where applicable |
| SYS-03 | Grounded counter-hit Screw launches consume Bound (e.g. Geese standing 4) | Fixed — Geese CH 4 confirmed; other affected routes need individual checks | Earlier gameplay confirmation + screenshot (screenshot still says Open) |
| SYS-02 | Fighters keep running indefinitely after starting a run. Referenced video was not attached in this message. | Correction installed — automated validation passed; gameplay check pending | Earlier tracker; repeated in full text where applicable |
| TAG-02 | Female characters always perform Jun’s b+4,2 during Tag Assault | Open | Screenshot |
| SYS-04 | Remove wall bounce from everyone | Requested behavior change — not a confirmed defect | Screenshot |
| TAG-03 | Male characters always perform Lars’s b+1+2 during Tag Assault | Open | Screenshot |
| SYS-05 | Converted T7 Screw attacks prevent a later Bound, whereas native Tag 2 Bound attacks permit two Bounds | Open — distinguish airborne Screw/Bound accounting from fixed grounded CH Screw launches | Screenshot |
| SYS-06 | Wall flip-over behavior is missing; example Shaheen b+4 at a low wall slump | Open | Screenshot |
| SYS-07 | Preserve complete costumes and prior fixes across both PRs and subsequent rebuilds | Consolidated branch and costume restoration completed; ongoing preservation requirement | Earlier conversation / existing tracker and manifest |

## Shared: Noctis / Kunimitsu II

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| TAG-01 | Dagger attacks fail during Tag Assault; inspect each fighter separately | Open | Earlier tracker; repeated in full text where applicable |
| TAG-04 | Imported characters lose Tag Assault participation when entering stances; investigate shared assist lifetime and stance continuation | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |

## Negan

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| NEG-01 | 1,2: second hit does not connect | False positive — closed at user request | Earlier tracker; repeated in full text where applicable |
| NEG-02 | 4,2: second hit does not connect | Fixed — confirmed by player | Earlier tracker; repeated in full text where applicable |
| NEG-03 | 1,4,2: final hit does not connect | Fixed — confirmed by player | Earlier tracker; repeated in full text where applicable |
| NEG-04 | INT 4 fails mid-combo | Open | Earlier tracker; repeated in full text where applicable |
| NEG-05 | Hit effects should be red | Open | Earlier tracker; repeated in full text where applicable |
| NEG-06 | d/b+1+2 counter-hit reaction is broken; resembles Noctis u/f+1 problem | CH crumple correction installed; needs gameplay check | Earlier tracker; repeated in full text where applicable |
| NEG-07 | qcf+1 knife is not visible | Open | Earlier tracker; repeated in full text where applicable |
| NEG-08 | Missing sidestep 2 | Open — installed sidestep input routes present; gameplay reproduction needed | Earlier tracker; repeated in full text where applicable |
| NEG-09 | d/f+4,2 second-hit hitbox is inconsistent | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |
| NEG-10 | Leaves Tag Assault when transitioning into INT stance, e.g. after d/f+4,2 | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |

## Noctis

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| NOC-01 | u/f+1 counter-hit reaction is broken (reported twice) | Same CH crumple correction installed; needs gameplay check | Earlier tracker; repeated in full text where applicable |
| NOC-02 | f+2 deals unscaled combo damage | Correction installed — automated checks passed; gameplay check pending | Earlier tracker; repeated in full text where applicable |
| NOC-03 | Sword impact effects and sounds are incorrect (e.g. 2,2,2,2); 2,2 effects appear in the wrong location | Open | Full text + screenshot “2,2 effects are in the wrong spot” |
| NOC-04 | 2,2 fails in combos when opponent was launched on their back | Open | Full text + screenshot “2,2 (second hit) hitbox issues” |
| NOC-05 | Freezes airborne on block instead of teleporting forward: f+2, 2,2,b+2, d/f+1,2 | Working — player confirmed 2026-10-25; no warp change applied | Earlier tracker; repeated in full text where applicable |
| NOC-06 | Airborne 2,2,2 stops after its first hit in combos | Previous candidate failed — revised native latches installed; gameplay retest pending | Earlier tracker; repeated in full text where applicable |
| NOC-07 | u/f+3 plays only its first kick rather than the full animation | Correction installed — automated validation passed; gameplay check pending | Earlier tracker; repeated in full text where applicable |
| NOC-08 | Emoman unexpectedly launches; establish exact input and expected reaction | Player reports airborne launch issue fixed — 2026-10-25 | Earlier tracker; repeated in full text where applicable |
| NOC-09 | Missing b+2,1+2 follow-up | Correction installed — source follow-up routes restored; gameplay check pending | Earlier tracker; repeated in full text where applicable |
| NOC-10 | d/f+4,2 fails against female characters at the wall | Open | Full text + screenshot “Missing SS2, DF4,2 hitbox issues” |
| NOC-11 | Emoman does not work as a wall combo | Airborne finisher reaction reported fixed; specific wall-combo check pending | Earlier tracker; repeated in full text where applicable |
| NOC-12 | WS 1,2 second-hit hitbox unreliable, especially at tip range | Open | Earlier tracker; repeated in full text where applicable |
| NOC-13 | Missing sidestep 2 | Move available — earlier missing-input report superseded by NOC-17 hitbox report | Earlier tracker; repeated in full text where applicable |
| NOC-14 | d/b+2 counter-hit animation is referenced as broken; confirm whether distinct from u/f+1 report | Reference identified — d/b+2 CH is distinct from u/f+1; no new change to reference | Full text, comparison in Eliza stance 4 report |
| NOC-15 | 1+2 should not Bound | Non-Bound verified in live pack 2026-10-25; retained through rebuild | Screenshot |
| NOC-16 | Emoman should not Bound | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| NOC-17 | Sidestep 2 hitbox is unreliable; distinct from the earlier missing-input report | Open — source timing/collision points inspected; gameplay contact check pending | BH59 report supplied 2026-10-25 |
| NOC-18 | WS 2,2 final hit should instantly Screw an airborne opponent without consuming Bound, like Eliza CH standing 4 | Requested correction installed — source airborne Screw retained without Bound; gameplay check pending | Direct user request 2026-10-25 |

## Kunimitsu II

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| KUN-01 | f+2 deals unscaled combo damage | Open | Earlier tracker; repeated in full text where applicable |
| KUN-02 | Missing weapons | Visible weapon meshes installed for default + 9 presets; model validation passed, visual check pending | Screenshot |
| KUN-03 | SET 1,2,3 should Bound | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| KUN-04 | u/f+3+4 has no hitbox | Open | Screenshot |
| KUN-05 | f+4~F → SET continuation during Tag Assault | Existing fix retained and installed metadata verified; user recalls this as fixed | Earlier conversation / existing tracker and manifest |
| KUN-06 | Missing crouch jab / dickjab; exact input not supplied | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |
| KUN-07 | SET stance slides underneath airborne opponents during combos | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |

## Fahkumram

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| FAH-01 | f,f+1+2 does not hit a grounded opponent | Open | Earlier tracker; repeated in full text where applicable |
| FAH-02 | Missing sidestep 4 | Open — installed sidestep input routes present; gameplay reproduction needed | Earlier tracker; repeated in full text where applicable |
| FAH-03 | b+1 hitbox unreliable in combos | Open | Earlier tracker; repeated in full text where applicable |
| FAH-04 | d/f+1 hitbox sometimes fails, e.g. after d/f+2,3 launch | Open | Earlier tracker; repeated in full text where applicable |
| FAH-05 | Previously missing d+4 | Reported resolved — screenshot; not independently rechecked | Screenshot |
| FAH-06 | Previously missing WR 3 | Reported resolved — screenshot; not independently rechecked | Screenshot |

## Lidia

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| LID-01 | Cat Foot Stance II (b+3+4) 4,4 has an incorrect hit reaction | Open | Earlier tracker; repeated in full text where applicable |
| LID-02 | qcf+2,2,b,f,f+1+2: last-hit animation is wrong; confirm fighter/notation | Needs clarification | Earlier tracker; repeated in full text where applicable |
| LID-03 | Missing full-crouch d/f+3 | Open | Earlier tracker; repeated in full text where applicable |
| LID-04 | Missing sidestep 2 | Open — installed sidestep input routes present; gameplay reproduction needed | Earlier tracker; repeated in full text where applicable |
| LID-05 | Missing sidestep 4 | Open — installed sidestep input routes present; gameplay reproduction needed | Earlier tracker; repeated in full text where applicable |

## Kazumi

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| KAZ-01 | 3,2 should Bound | Correction installed — automated validation passed; gameplay check pending | Earlier tracker; repeated in full text where applicable |
| KAZ-02 | f,f+2 tiger is not visible | Open — base f,f+2 and Rage follow-up distinguished | Earlier tracker; repeated in full text where applicable |

## Gigas

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| GIG-01 | f+1+2 counter-hit reaction breaks at the wall | Open | Earlier tracker; repeated in full text where applicable |
| GIG-02 | Missing d/b+1 crouch jab | Reported resolved — screenshot; verify installed behavior | Full text + screenshot “Missing dickjab and full crouch” (broad resolution; FC d/f+2 not individually named) |
| GIG-03 | Missing full-crouch 1,2 | Reported resolved — screenshot; verify installed behavior | Full text + screenshot “Missing dickjab and full crouch” (broad resolution; FC d/f+2 not individually named) |
| GIG-04 | Missing full-crouch d+3 | Reported resolved — screenshot; verify installed behavior | Full text + screenshot “Missing dickjab and full crouch” (broad resolution; FC d/f+2 not individually named) |
| GIG-05 | Missing full-crouch d/f+2 | Reported resolved — screenshot; verify installed behavior | Full text + screenshot “Missing dickjab and full crouch” (broad resolution; FC d/f+2 not individually named) |

## Master Raven

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| MRV-01 | b+2,4,2 fails during Tag Assault: disappears airborne and does not perform the move | Open | Full pasted report |
| MRV-02 | BT f+2,4,2 has the same Tag Assault disappearance/failure | Open | Full pasted report |
| MRV-03 | d/b+4 counter-hit behavior is broken; exact symptom needs reproduction | Open | Full pasted report |
| MRV-04 | u/b+1,2 should Bound | Correction installed — automated validation passed; gameplay check pending | Full pasted report |
| MRV-05 | qcf+4 has no hitbox | Open | Full pasted report |

## Leroy

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| LER-01 | d/b+2 hitbox is unreliable against grounded opponents | Open | Full pasted report |
| LER-02 | Sugar is missing (2+3) | Open | Full pasted report |
| LER-03 | d/f+2,1+2 does not launch high enough to combo | Open | Full pasted report |
| LER-04 | qcf+2 fails in combos, including after orbital | Open | Full pasted report |
| LER-05 | Missing sidestep 4 | Open | Full pasted report |
| LER-06 | Cane is missing (d/f+2+3) | Open | Full pasted report |
| LER-07 | b+2 parry is missing or does not activate | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |

## Eliza

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| ELZ-01 | Tag Assault b+4 → f+3+4 → Glide attack/string continuation | Partial confirmation — full Glide 3,3 confirmed working; 3,4 not yet confirmed | Latest player test: full b+4 → Glide → 3,3 works; follow-along regression tracked separately as ELZ-07 |
| ELZ-02 | qcb+2 does not hit grounded opponents | Open | Full pasted report |
| ELZ-03 | Stance 4 has a broken reaction, described as the same problem as Noctis d/b+2 CH | Correction installed — automated validation passed; gameplay check pending | Full pasted report |
| ELZ-04 | General missing hitboxes; exact affected moves unspecified | Reported resolved — screenshot; relationship to qcb+2 unconfirmed | Screenshot |
| ELZ-05 | Ordinary special cancels were broken | Fixed — confirmed by player; screenshot also says Resolved | Screenshot |
| ELZ-06 | EX divekick consumes Bound | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| ELZ-07 | During Tag Assault b+4 → Glide → 3,3, the main character cannot move or follow along, leaving them too far behind to continue the combo; expected automatic follow-along during extended assist stance/string sequences | Movement input restored while retaining working Glide 3,3; automatic follow-along check pending | Latest player test; preserve working full Glide 3,3 while correcting main-character follow-along |

## Akuma

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| AKU-01 | Cannot initiate Tag Assault out of d/f+1,2 | Open | Screenshot |
| AKU-02 | Missing f,f+2:1 | Existing hit-latched follow-up restoration retained in rebuilt pack; gameplay check pending | Screenshot |
| AKU-03 | f+1+2 should Bound | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| AKU-04 | All meter actions should be free, matching Eliza | Restored in consolidated branch/build — no fresh audit in this list | Earlier conversation / existing tracker and manifest |

## Claudio

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| CLA-01 | Sidestep 4 CH behavior is missing; reporter suggests Noctis d/b+2 as reaction reference | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| CLA-02 | Starburst does not exist / is unavailable | Open | Screenshot |
| CLA-03 | Missing d+1,2 | Open | Screenshot |
| CLA-04 | d/b+2,1 is available only from crouch, not standing | Open | Screenshot |

## Katarina

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| KAT-01 | FC d/f+4 has a bad CH reaction; reporter suggests Noctis d/b+2 reference | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| KAT-02 | d/f+3+4 has a bad CH reaction; same proposed reference | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| KAT-03 | Hopkick can cause two Bounds | Open | Screenshot |
| KAT-04 | d/f+3,3 second hit has a strange effect | Open | Screenshot |
| KAT-05 | d/b+3 also needs inspection for a strange effect | Open — symptom not specified beyond comparison | Screenshot |
| KAT-06 | b+4,1+2 should Bound | Correction installed — automated validation passed; gameplay check pending | Screenshot |
| KAT-07 | f,f+2,4 looks visually wrong | Open — exact animation/effect symptom needs reproduction | Screenshot |
| KAT-08 | d+2 → Harrier 1 is inconsistent in combos; slides through the opponent | Open | Screenshot |
| KAT-09 | d/f+1 → 3,3,3,3 does not work at the wall | Open | Screenshot |

## Shaheen

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| SHA-01 | Stance 4,1 is broken on counter hit | Open | Screenshot |

## Josie

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| JOS-01 | f+3+4 has unnatural forward momentum | Open | Screenshot |

## Lucky Chloe

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| LCH-01 | f+4,4 second hit does not connect, e.g. against Fahkumram | Untriaged — screenshot status blank | Screenshot |
| LCH-02 | Sometimes performs standing moves while back-turned | Untriaged — screenshot status blank | Screenshot |
| LCH-03 | After d/b+3+4 → 2, gets standing 2 instead of back-turned 2 | Untriaged — may reproduce LCH-02; retained as a concrete route | Screenshot |
| LCH-04 | d/f+1 connects unreliably in combos, including after a Cali Roll combo | Open — newly reported; investigation pending | BH59 report supplied 2026-10-25 |

## Geese

| ID | Report / requested behavior | Current status | Source / notes |
|---|---|---|---|
| GEE-01 | Special cancels fail when entering as Tag Assault partner; Akuma works | Open | Earlier tracker; repeated in full text where applicable |
| GEE-02 | Grounded strings / combo damage scaling is excessive | Correction installed — needs gameplay confirmation | Earlier conversation / existing tracker and manifest |
| GEE-03 | f+1+2 should allow d+4 pickup against an airborne opponent | Float and recovery correction installed — needs gameplay confirmation | Earlier conversation / existing tracker and manifest |
| GEE-04 | CD+2 should Bound on the final hit of the two-hit move | Implemented — retained from earlier work; no fresh audit in this list | Earlier conversation / existing tracker and manifest |

## Reports merged on 2026-10-25

Added eight distinct reports. Master Raven, Leroy’s earlier six reports, Eliza qcb+2 and Glide 4 overlap existing entries; their statuses are preserved. The repeated text is not treated as a fresh test disproving an installed correction. TAG-04 tracks the shared stance/assist lifetime issue; NEG-10 retains its concrete Negan reproduction. Noctis SS2 hitbox and missing SS2 input remain separate reports.

## Scope and history

This inventory contains **110 tracked entries**. A combined report may have been split into independently testable moves; this is not a count of confirmed defects. Conversation chatter and the speculative memory-leak diagnosis are excluded as separate bugs. The long-session slowdown report keeps the memory-leak theory explicitly unproven.

An autonomous implementation batch now covers 16 tracked entries, with gameplay verification still pending. See `autonomous-fix-report.md` and `autonomous-bug-audit.md` alongside this document. Existing investigation history remains in the repository tracker.

---

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


### Eliza Glide 3 string continuation and main-controller handoff

Player confirms the routing exception enables the first Glide 3, but not 3,3 / 3,4, and the main fighter becomes controllable too soon. Installed metadata identifies `Vp_6rklk` as the first Glide 3: direct 3 and 4 follow-up rows accept input frames 1–18 and enter `Vp_66lklk` / `Vp_6rklkrk` at frame 18. The previous exception covered only the empty Glide state, so it stopped at that first kick.

A latched Tag Assault Glide session now follows precisely these string states, including `Vp_66lklk_H` on hit. Native active decoding remains available to the assist through the string; the shared controller decodes neutral buttons/directions for the main fighter meanwhile. The session ends on leaving this graph, interruption/tag-out, or the existing neutral recovery endpoint: first kick 46, 3,3 58, its hit state 54, 3,4 50. It can only begin during human-controlled Eliza Tag Assault Glide, so normal strings and other fighters cannot start it. No attack timing, hitbox, damage, pack or costume edits. This extends the user-confirmed partial fix; full gameplay verification is pending.


### ELZ-01 confirmation / ELZ-07 follow-along regression

Player confirms full Tag Assault b+4 → Glide → 3,3 now works. Do not revert that successful continuation. Glide 3,4 has not been individually confirmed. Player reports the main fighter cannot move at all during the sequence and stays too far behind for the follow-up; expected behavior is to follow along with extended Tag Assault stance/string movement. Added separate open regression ELZ-07. This turn only updates documentation; no new gameplay candidate installed.


### Autonomous batch — 16 tracked entries

## Installed changes

| Entries | Change | What to test |
|---|---|---|
| CLA-01, ELZ-03, KAT-01, KAT-02 | CH-only Noctis d/b+2 knockdown family for Claudio SS4, Eliza Glide 4, Katarina FC d/f+4 and d/f+3+4. Use mirrored right variant for Claudio/Eliza where their exports lack the left variant. Normal-hit, airborne, block, damage and other reaction fields verified unchanged. | CH each move; compare normal hit separately. |
| KAZ-01 | Kazumi 3,2 final hit now has gated Bound. | Launch → 3,2; later Bound remains unavailable after it. |
| MRV-04 | Master Raven u/b+1,2 final hit now has gated Bound. | Airborne u/b+1,2. |
| KUN-03 | Kunimitsu SET 1,2,3 final hit now has gated Bound. | Airborne SET 1,2,3. |
| KAT-06 | Katarina b+4,1+2 final hit now has gated Bound. | Airborne b+4,1+2, including its alternate entry. |
| AKU-03 | Akuma f+1+2 now has gated Bound. | Airborne f+1+2; verify free-meter actions/cancels remain intact. |
| NOC-15, NOC-16 | Noctis 1+2 and both d+4,1,1+2 Maelstrom/emoman finisher variants no longer Bound. | Juggle and wall routes, including clean/easy finisher. Launch/wall reports remain separate pending results. |
| ELZ-06 | Eliza grounded/airborne EX Dark Cannon landing follow-ups no longer Bound. | EX divekick → later known Bound move. |
| NOC-07 | Restored u/f+3 second-kick on-hit transition with original window/entry timing. | Normal hit, CH, block and whiff; verify no second kick is granted without a hit. |
| SYS-02 | Restored 51 native running tackle/body-check collision exits across 17 imported fighters, learned from donor movesets. Kept fighter-specific running attacks and tag inputs. | Long run toward opponent; verify collision ends the run, plus back-input stopping and WR attacks. Native roster data is unchanged. |
| KUN-02 | Enabled the two sword meshes that were explicitly hidden by source settings. Rebuilt default + all 9 presets; 10 models validated with both weapons and unchanged skeletons. | Weapons visible and correctly posed, costumes still available. |
| ELZ-07 | Replaced full-pad neutralization of main fighter with filtering only the four native attack-button masks during Eliza’s latched Glide sequence. Kept movement/analog state and the confirmed full 3,3 route. | Tag Assault b+4 → Glide → 3,3 and 3,4; main movement/automatic follow-along and combo pickup. Automatic follow-along is not yet gameplay-confirmed. |

## Validation and preservation

- Converter regression suite: **227 tests run, one skipped, no failures**. Launcher tests excluded because of their previously observed subprocess timeout.
- Runtime build passed; title, damage scaling, character import and outfit-menu CTests passed **4/4**.
- All 17 staged movesets round-trip through the binary writer; owned animation references fit their corresponding motion packs.
- Shared-table tests cover CH-only preservation, on-hit gating/timing, native running requirements and idempotence.
- Installation uses per-file backups and hash checks. Character metadata, costume selectors and all files outside the explicit install allowlist are preserved. Exact counts/hashes are in `autonomous-gameplay-validation.json`.

## Remaining investigation

The companion `autonomous-bug-audit.md` retains all 101 entries with per-entry findings/decisions. A 17-fighter source-versus-installed cancel-link audit is available as JSON. That scan includes intentional story/Rage/assist-combo omissions and is not a list of confirmed defects.

Concrete leads include Noctis Warp-Strike’s flat victim-state damage property (25 damage outside ordinary hit scaling), lost Noctis b+2 hit-confirm paths with unmapped requirements, and Kazumi’s existing tiger model/animation path whose hit-confirm entry needs further work. Several “missing sidestep” inputs are already present in installed data, so no duplicate inputs were added. Kunimitsu u/f+3+4 has no base hitbox in T7 either: it is an input state for 2/4 follow-ups. Other collision, visual, audio and long-session performance reports remain open where metadata did not establish a safe correction.

## Launch and rollback

Restart the game using the normal launch command. Both executable launch paths are synchronized. No manual rebuild or character reimport is required for this installation.

Backups: `work/bugs/autonomous-before/` in this workspace. The runtime executable backup is `work/bugs/autonomous-before/executable`; changed character files preserve their pack-relative paths. Source changes remain on the consolidated local branch.


### Noctis targeted batch — 2026-10-25

Restored airborne 2,2,2 continuations with native contact and opponent-airborne gates; unsupported T7 value-store dispatches had been dropped and their input captures converted to neutral cancels. Preserved source input windows and animation entry frames; backward-jump variant unchanged.

For d+4,1,1+2 clean/easy finishers only, retain source airborne downward slams instead of approximate Heihachi rebounds. Shared reaction caches and grounded reactions preserved. Every existing move name/Tag Assault variant retained; comparison of all existing hit metadata finds changes only on these two finishers. Separate grounded launch report still needs exact hit/condition.

Player confirms warp works on d/f+1,2, f+2, 2,2,b+2 and WS 3,2; closed the earlier freeze report without changing warp behavior. Neutral 1+2 verified non-Bound and retained.

232 Python tests ran, one skipped, no failures (launcher module excluded); 4/4 targeted CTests passed. Round-trip, animation references and earlier fixes verified. Installed only mrz.moveset/mrz.motion with backups; 2,221 other character files hash-verified unchanged. Restart only, no reimport or executable rebuild. New candidates await gameplay checks; hitbox and sword sound/effect reports remain open.


### Noctis gameplay feedback and WS 2,2 — 2026-10-25

Player confirms airborne 2,2,2 still stops after its first hit; prior direct-input candidate superseded by independent native input/contact latches. Capture input without leaving the move, latch successful hit 47 plus opponent airborne 457 during source active window, dispatch at source timing using both stored words, reset both on entry. Native action-only 0x2800 and follow-up 0x182 modes match existing working hit-latched/string fixes. New gameplay retest pending.

Player clarified the d+4,1,1+2 launch issue was airborne and says it looks fixed. Retained that correction; wall-combo reproduction remains separate.

NOC-18: WS 2,2 is Mz_s_trp00 → Mz_s_trp01. Final hit now uses private source airborne Screw victim states without property 0x8193; ordinary airborne gate replaces Bound gate and generated Bound tag twins are absent. Grounded/CH reactions, damage and active frames unchanged. Every other existing hit/reaction row verified unchanged, including the d+4,1,1+2 fix and neutral 1+2 non-Bound setting.

232 Python tests ran (one skipped; launcher excluded), no failures; 4/4 targeted CTests passed. Round-trip and animation references passed. Installed mrz.moveset/mrz.motion only, with backups and 2,221 other character files hash-verified unchanged. Restart only; no executable rebuild/reimport.
