# 🎰 Anki Slot Machine

[![CI](https://github.com/lmallez/anki-slot-machine/actions/workflows/ci.yml/badge.svg)](https://github.com/lmallez/anki-slot-machine/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

> Warning
> This add-on is still in testing.
> Expect balance tweaks, UI changes, and rough edges.
> Use it at your own risk.
> I am not responsible for resets, lost progress, broken profiles, deck issues, or other unexpected Anki problems while it is still in beta.

Turn your suffering into fake money.

This add-on adds a completely unnecessary, slightly addictive, and emotionally manipulative slot machine on top of Anki.

It does **not** improve your memory.  
It does **not** change scheduling, intervals, cards, or notes.  
It **does** make you want to press "Good" just one more time.

![Anki Slot Machine screenshot](docs/images/anki-slot-machine.jpeg)

---

## ✨ Features

- 🎰 Real slot-machine style spin that feels tied to the result
- 🎞️ Faster reel animation with a clean slowdown at the end
- 💸 Persistent fake-money balance across review sessions
- 📈 Live terminal-style stats window with a PnL chart, tape feed, and quant sidebar
- 📊 Odds and rewards page inside Anki
- 📁 File-based slot profile with reel faces and pair/triple payouts
- 🧱 Pixel-art slot UI with local bundled assets
- 🔒 No scheduling changes and no note/card field edits

Everything runs locally inside Anki. No CDN, no online dependency, no network
call for the slot UI.

---

## 🧠 What is this?

Every review becomes a gamble.

- You answer your card
- The slot resolves
- You win fake money, win nothing, or burn money on `Again`
- You feel something

That’s it. That’s the product.

---

## 💸 Rules (very serious business)

- **Hard**, **Good**, and **Easy** → run the slot and multiply their payout (`0.5`, `1`, and `1.5` by default)  
  → fake finance begins

- **Again** → `0` by default, so no spin and no reward  
  → but if you believe learning should involve suffering, you can make it negative in the config

- **No match** → `x0`  
  → pain

- **Exact pair** → profile pair multiplier  
  → small hope

- **Triple** → profile triple multiplier  
  → the machine acknowledges your existence

---

## 🎯 The Philosophy

Most spins give nothing.  
Some spins give something.  
Rare spins hit.

Like life. But compressed into 300ms.

---

## 🧮 How it works (for nerds)

- The add-on loads one slot profile JSON file
- That file defines reel faces, pair multipliers, and triple multipliers
- Reel probabilities come directly from the configured face counts
- The backend builds a real reel strip from those faces and keeps reel position state
- Visible reel symbols are derived from real backend stop positions
- The reel strip is mixed into a stable order so the visible 3x3 window feels less clumpy without changing the configured probabilities
- Pairs and triples are evaluated from the real backend reel result
- The odds page computes the real distribution from that profile

Important:

The machine is not solving the economy for you anymore.  
It just runs the profile you give it.

---

## Short Changelog

- `v0.0.8` Configurable rewards, cleaner odds, and lag fixes.
- `v0.0.7` One-slot default, collapsed controls, configurable spin triggering, and lighter DOM usage.
- `v0.0.6` Real reel rotation, smoother reel visuals, better timing, and no replayed spins on restore.
- `v0.0.5` Multi-slot support with one shared bankroll and quick slot controls.
- `v0.0.4` Stats window, better history tracking, and stronger layout/state handling.
- `v0.0.3` Draggable, resizable slot window with saved layout.
- `v0.0.2` Slot profiles, undo support, and spun-loss `Again` behavior.
- `v0.0.1` Initial playable slot-machine add-on release.

---

## ⚙️ Config

Main config lives in `src/anki_slot_machine/config.json`.

```json
{
  "starting_balance": 100,
  "decimal_places": 2,
  "spin_animation_duration_ms": 500,
  "spin_trigger_every_n": 1,
  "spin_trigger_chance": 1.0,
  "answer_base_values": {
    "again": 0.0,
    "hard": 0.5,
    "good": 1.0,
    "easy": 1.5
  },
  "slot_profile_path": "slot_profiles/base.json"
}
```

A slot profile looks like this:

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

Useful intuition:

- `faces` → how often each symbol shows up on one reel  
- `pair_multipliers` → what an exact pair pays  
- `triple_multipliers` → what a triple pays  
- `spin_animation_duration_ms` → total reel animation budget, capped at `750`  
- `spin_trigger_every_n` → run a spin check every `n` `Good` / `Easy` reviews  
- `spin_trigger_chance` → chance that the spin actually happens at that check  
- `answer_base_values` → signed per-answer base values, configurable in JSON  
- `slot_profile_path` → which profile file the add-on loads  

More detail is documented in `src/anki_slot_machine/config.md`.

---

## 🚀 Installation

This project is still in beta.

If you are testing it locally:

```bash
make install
```

Or install the built `.ankiaddon` archive manually from the `dist/` folder after
running:

```bash
make build
```

---

## 📊 Odds & Rewards

Tools → Slot Machine → Show Odds and Rewards

Includes:

- real probabilities  
- actual multipliers  
- expected payout per spin  

The add-on menu also includes:

- `Show Stats`
- `Reset Balance and Stats`

---

## 💾 Persistence

Your fake wealth is stored locally.

Yes, it survives restarts.  
No, you cannot cash it out.  

Runtime state is stored separately from Anki card data, so the add-on does not
modify scheduling, note fields, or card content.

---

## ⚠️ Disclaimer

- This is not gambling  
- This is not productive  
- This is barely educational  

But it might make you review more cards.

---

## Repo Structure

The repo uses a lightweight `src/<package>` layout:

- `src/anki_slot_machine/addon.py` registers the add-on once
- `src/anki_slot_machine/reviewer.py` wires Anki reviewer hooks and the JS bridge
- `src/anki_slot_machine/service.py` coordinates config, state, and review application
- `src/anki_slot_machine/game.py` contains slot and payout logic
- `src/anki_slot_machine/config.py` loads the slot profile and computes the odds summary
- `src/anki_slot_machine/state.py` owns local persistence
- `src/anki_slot_machine/ui/` contains Qt dialogs
- `src/anki_slot_machine/web/` contains reviewer CSS and JavaScript
- `src/anki_slot_machine/slot_profiles/` contains packaged slot definitions

## Development

```bash
make install-dev
make lint
make check
make test
make real-slot-report
make build
make install
```
