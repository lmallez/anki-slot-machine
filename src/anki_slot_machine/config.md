# Anki Slot Machine

This add-on adds a fake-money reward layer on top of the reviewer. It never
changes Anki scheduling, intervals, or note data.

## Config keys

- `starting_balance`: first balance for a fresh profile state file.
- `decimal_places`: how many decimals are used for balances, payouts, and
  displayed multipliers.
- `slot_profile_path`: path to the slot profile JSON file, relative to the
  add-on root unless you provide an absolute path.

## Slot profile format

The profile file is the source of truth for the slot:

```json
{
  "name": "base",
  "faces": {
    "SLOT_1": 35,
    "SLOT_2": 25,
    "SLOT_3": 20,
    "SLOT_4": 12,
    "SLOT_5": 8
  },
  "pair_multipliers": {
    "SLOT_1": 0.75,
    "SLOT_2": 0.95,
    "SLOT_3": 1.15,
    "SLOT_4": 2.20,
    "SLOT_5": 4.50
  },
  "triple_multipliers": {
    "SLOT_1": 2.50,
    "SLOT_2": 7.00,
    "SLOT_3": 15.00,
    "SLOT_4": 60.00,
    "SLOT_5": 300.00
  }
}
```

- `faces`: how many times each symbol appears on a reel strip.
- `pair_multipliers`: reward for an exact pair of that symbol.
- `triple_multipliers`: reward for a triple of that symbol.

## Reward rules

- `Again`: lose `$1`.
- `Hard`: earn `$0` with no spin.
- `Good`: spin the slot and earn `$1 x multiplier`.
- `Easy`: spin the slot and earn `$2 x multiplier`.
- A no-match spin uses `x0`.
- An exact pair uses the profile pair multiplier for that symbol.
- A triple uses the profile triple multiplier for that symbol.

## How probabilities work

- The slot is a real 3-reel model with 3 independent draws.
- Reel probabilities come only from `faces`.
- For each symbol:
  - `p = faces / total_faces`
  - `P(pair) = 3 * p^2 * (1 - p)`
  - `P(triple) = p^3`
- The odds dialog computes the expected multiplier from the loaded profile. It
  does not solve or rebalance anything for you.

## Odds and rewards page

Tools -> Slot Machine -> Show Odds and Rewards shows:

- the loaded slot profile
- no-match, pair, and triple rates
- per-symbol reel probability
- per-symbol pair multiplier
- per-symbol triple multiplier
- expected `Good` and `Easy` payouts

## Persistence

Runtime progress is stored in `user_files/slot_machine_state.json` inside the
installed add-on folder so config edits stay separate from balance and stats.
