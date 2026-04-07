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

---

## ✨ Features

- 🎰 Real 3-reel slot result tied to the visible outcome
- 💸 Persistent fake-money balance across review sessions
- 📊 Odds and rewards page inside Anki
- 🧮 Configurable EV-driven multiplier solver
- 🧱 Pixel-art slot UI with local bundled assets
- 🔒 No scheduling changes and no note/card field edits

Everything runs locally inside Anki. No CDN, no online dependency, no network
call for the slot UI.

---

## 🧠 What is this?

Every review becomes a gamble.

- You answer your card
- The slot resolves
- You win fake money, win nothing, or lose `$1`
- You feel something

That’s it. That’s the product.

---

## 💸 Rules (very serious business)

- **Again** → you lose `$1`  
  → skill issue

- **Hard** → you earn `$0`  
  → safe, boring, respectable

- **Good** → you spin and earn `$1 × multiplier`  
  → now we’re talking

- **Easy** → you spin and earn `$2 × multiplier`  
  → risky confidence

- **No match** → `x0`  
  → pain

- **Exact pair** → derived pair multiplier  
  → small hope

- **Triple** → derived triple multiplier  
  → the machine acknowledges your existence

---

## 🎯 The Philosophy

Most spins give nothing.  
Some spins give something.  
Rare spins hit.

Like life. But compressed into 300ms.

---

## 🧮 How it works (for nerds)

- Each symbol has a probability based on `slot_faces`
- Pairs and triples are evaluated from a real 3-reel result
- Rarer symbols scale higher than common ones
- Everything is tuned to hit a target expected value

Important:

Rare events are not there to make money.  
They are there to make you feel alive.

---

## ⚙️ Config

Main config lives in `src/anki_slot_machine/config.json`.

```json
{
  "starting_balance": 100,
  "expected_multiplier_target": 1.08,
  "decimal_places": 2,
  "rarity_exponent": 2.2,
  "pair_scale_multiplier": 0.35,
  "triple_scale_multiplier": 12,
  "slot_faces": {
    "SLOT_1": 60,
    "SLOT_2": 22,
    "SLOT_3": 10,
    "SLOT_4": 6,
    "SLOT_5": 2
  }
}
```

Useful intuition:

- `rarity_exponent` → how unfair life is  
- `pair_scale_multiplier` → how much small wins matter  
- `triple_scale_multiplier` → how hard jackpots slap  
- `expected_multiplier_target` → how fast you inflate your ego  

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
- expected value  

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
- `src/anki_slot_machine/config.py` derives the slot solver tables
- `src/anki_slot_machine/state.py` owns local persistence
- `src/anki_slot_machine/ui/` contains Qt dialogs
- `src/anki_slot_machine/web/` contains reviewer CSS and JavaScript

## Development

```bash
make check
make test
make solver
make build
make install
```
