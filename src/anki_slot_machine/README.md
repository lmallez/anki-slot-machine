# 🎰 Anki Slot Machine

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

![Anki Slot Machine screenshot](https://raw.githubusercontent.com/lmallez/anki-slot-machine/main/docs/images/anki-slot-machine.jpeg)

---

## ✨ Features

- 🎰 Real 3-reel slot result tied to the visible outcome
- 🎰 Multiple independent slot windows can spin at once
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

- **Again** → the slot runs and removes money instead of adding it  
  → same machine, bad outcome

- **Hard** → you earn `$0`  
  → safe, boring, respectable

- **Good** → you spin and earn `$1 × multiplier`  
  → now we’re talking

- **Easy** → you spin and earn `$2 × multiplier`  
  → risky confidence

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

- The add-on loads one or more slot profile JSON files
- Each visible machine uses its own profile
- All machines share one bankroll, one streak, and one stats feed
- Reel probabilities come from the face counts
- Pairs and triples are evaluated from a real 3-reel result
- The odds page computes both per-machine odds and aggregate expected payout

Important:

The machine is not solving the economy for you anymore.  
It just runs the profiles you give it.

---

## Short Changelog

- `v0.0.5` Multi-slot support with one shared bankroll and quick slot controls.
- `v0.0.4` Stats window, better history tracking, and stronger layout/state handling.
- `v0.0.3` Draggable, resizable slot window with saved layout.
- `v0.0.2` Slot profiles, undo support, and spun-loss `Again` behavior.
- `v0.0.1` Initial playable slot-machine add-on release.

---

## ⚙️ Config

```json
{
  "starting_balance": 100,
  "decimal_places": 2,
  "slot_profile_path": "slot_profiles/base.json",
  "machines": [
    {
      "key": "base",
      "label": "Base"
    },
    {
      "key": "second_window",
      "label": "Second Window"
    }
  ]
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
- `slot_profile_path` → which shared profile every machine window loads  
- `machines` → which machine windows appear on screen  

---

## 📊 Odds & Rewards

Tools → Slot Machine → Show Odds and Rewards

Includes:

- aggregate expected payout across all active machines  
- real probabilities  
- actual multipliers  
- expected payout per machine spin  

The add-on menu also includes:

- `Show Stats`
- `Reset Balance and Stats`

---

## 💾 Persistence

Your fake wealth is stored locally.

Yes, it survives restarts.  
No, you cannot cash it out.  

Runtime state is stored separately from Anki card data, so the add-on does not
modify scheduling, note fields, or card content. All machines share the same
saved bankroll and stats history.

---

## ⚠️ Disclaimer

- This is not gambling  
- This is not productive  
- This is barely educational  

But it might make you review more cards.

---

## 🏁 Final Note

If you ever find yourself thinking:

"one more card, I can hit the jackpot"

It’s working.
