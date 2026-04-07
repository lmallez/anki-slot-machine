# Anki Slot Machine

This add-on adds a fake-money reward layer on top of the reviewer. It never
changes Anki scheduling, intervals, or note data.

## Config keys

- `starting_balance`: first balance for a fresh profile state file.
- `expected_multiplier_target`: target average slot multiplier over many spins.
- `decimal_places`: how many decimals are used for balances, payouts, and
  derived multipliers.
- `rarity_exponent`: how aggressively rarity turns into reward weight. Higher
  values compress common hits and push more reward into rare ones.
- `pair_scale_multiplier`: one global strength control for all exact pairs.
- `triple_scale_multiplier`: how much more strongly triples scale than pairs.
- `slot_faces`: the only probability input. More faces means a symbol appears
  more often on each reel.

## Reward rules

- `Again`: lose `$1`.
- `Hard`: earn `$0` with no spin.
- `Good`: spin the slot and earn `$1 x multiplier`.
- `Easy`: spin the slot and earn `$2 x multiplier`.
- A no-match spin uses `x0`.
- An exact pair uses the derived double multiplier for that symbol.
- A triple uses the derived triple multiplier for that symbol.

## How the solver works

- Reel probabilities come only from `slot_faces`.
- For each symbol:
  - `p = faces / total_faces`
  - `P(double) = 3 * p^2 * (1 - p)`
  - `P(triple) = p^3`
- Symbol rarity is converted to a score with `(-log(p)) ^ rarity_exponent`.
- The add-on solves one scale value from the target expected multiplier.
- Double and triple multipliers are then derived automatically:
  - `double = 1 + score * a * pair_scale_multiplier`
  - `triple = 1 + score * a * triple_scale_multiplier`
- Multipliers are rounded to `decimal_places`, then the achieved EV is
  recomputed and shown in the odds dialog.

## Odds and rewards page

Tools -> Slot Machine -> Show Odds and Rewards shows:

- target expected multiplier
- achieved expected multiplier after rounding
- configured rarity exponent, pair scale, and triple scale
- per-symbol reel probability
- per-symbol double multiplier
- per-symbol triple multiplier
- expected `Good` and `Easy` payouts

## Persistence

Runtime progress is stored in `user_files/slot_machine_state.json` inside the
installed add-on folder so config edits stay separate from balance and stats.
