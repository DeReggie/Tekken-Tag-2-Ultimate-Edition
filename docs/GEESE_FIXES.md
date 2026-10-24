# Geese special cancels

Geese explicitly opts into meter-free EX, MAX cancels and supers, as requested.
Normal commands remain separate from the original two-button EX commands.
Rage Arts and Deadly Rave's Rage restrictions are unchanged.

The source audit found 34 moves with T7's special input buffer:

- 16 normal/command-normal sources: standing 1/2, f+1, crouching and while-standing attacks,
  FC d/f+1 and the exported back-turned punch/kick variants. Exact internal names are
  `_NORMAL_CANCELS` in `characters/geese.py`; no cancellation is invented for other strings.
- Four MAX-cancel-only sources: `My_rp02F`, `My_lk00F`, `My_4lplk`, `My_lkrp00B`.
- `My_WPF` into its normal/EX Shippu Ken follow-ups.
- Ten Fudou Ken/Jaei Ken stages into supers, retaining their hit/block confirmation.
- Three Reppuu Ken stages into supers, retaining T7's non-contact cancellation rule.

Special targets cover Reppuu Ken and Double Reppuu Ken, Hishou Nichirin Zan,
Fudou Ken and its existing follow-ups, Jaei Ken, jumping and f+1+2 Shippu Ken,
their EX versions, MAX cancel, Raigou Reppuu Ken and Raging Storm.
The exported f+1/f+3 buffer follow-ups are also retained where present.

The repair uses separate native words for motion capture and hit/block confirmation,
resets both at move entry, preserves dispatch start timing and command priority,
and applies the same eight-frame late allowance and minimum 24-frame motion window
used for Eliza. Longer original super-motion windows remain longer. Ordinary strings
remain available while the special buffer is empty. Unsupported additional capture or
dispatch guards fail conversion rather than being silently discarded.

Validation against the locally exported T7 moveset and regenerated pack checked all
34 source moves, 928 original dispatch rows, 760 original capture rows, preserved
normal follow-ups and 17 standalone normal/EX/super target moves. Unit regressions
cover MAX opt-in isolation, special-to-super contact gating, unknown guard rejection
and normal-string priority. This is source/pack validation; gameplay confirmation is
still required, including hit, block, whiff, jump, MAX-cancel and super-cancel behavior.

Rebuild Geese from the updated source before testing. Source changes do not update
an existing pack automatically. No game assets or generated packs are committed.
