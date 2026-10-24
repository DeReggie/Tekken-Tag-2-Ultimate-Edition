# Gameplay bug tracker

Branch: `codex/all-local-changes`.

These are player reports, not yet confirmed diagnoses. Work through one issue at a time in the order below. For each, record the exact internal move and input route, source-vs-installed evidence, minimal change, validation, installed files/backups, and whether gameplay confirmation is still needed. A passing build or metadata test alone does not make a gameplay issue resolved. Preserve all existing costumes and unrelated fixes.

The repeated Noctis u/f+1 report is consolidated. Related reaction/projectile reports remain individually tracked until a common cause is demonstrated. Earlier reports of missing moves may already be addressed in source or installed packs; verify both before changing anything.

## Queue

| ID | Fighter | Report | Status |
|---|---|---|---|
| NEG-01 | Negan | 1,2: second hit does not connect | False positive — closed at user request |
| NEG-02 | Negan | 4,2: second hit does not connect | Open |
| NEG-03 | Negan | 1,4,2: final hit does not connect | Open |
| NEG-04 | Negan | INT 4 fails mid-combo | Open |
| NEG-05 | Negan | Hit effects should be red | Open |
| NEG-06 | Negan | d/b+1+2 counter-hit reaction is broken; resembles Noctis u/f+1 problem | Open |
| NEG-07 | Negan | qcf+1 knife is not visible | Open |
| NEG-08 | Negan | Missing sidestep 2 | Open |
| NOC-01 | Noctis | u/f+1 counter-hit reaction is broken (reported twice) | Open |
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
| SYS-02 | General | Fighters keep running indefinitely after starting a run. Referenced video was not attached in this message. | Open |
| GEE-01 | Geese (carry-over) | Special cancels fail when entering as Tag Assault partner; Akuma works | Open |

## Investigation log

### NEG-01 — Negan 1,2

Status: False positive — closed at user request. The player reports that 1,2 usually connects and only sometimes misses.

The weapon-animation pair change was an unconfirmed candidate, not an established diagnosis. Reverted that source change and its candidate regression test, and restored all 11 installed Negan files from their verified original backups. No executable rebuild is required; restart the game to reload the restored pack if it was already running.

NEG-02 and NEG-03 remain open independently; no common cause has been confirmed.

## Carry-over validation

Geese grounded scaling and f+1+2 airborne float changes are installed but still need player confirmation. Akuma and Geese were rebuilt after source consolidation; other installed packs were preserved. Do not assume all 17 installed packs match the newest consolidated source until each is audited/rebuilt as appropriate.
