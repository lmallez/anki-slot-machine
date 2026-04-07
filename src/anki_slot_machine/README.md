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

Example:

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

---

## 🧪 Tuning knobs

- `rarity_exponent` → how unfair life is  
- `pair_scale_multiplier` → how much small wins matter  
- `triple_scale_multiplier` → how hard jackpots slap  
- `expected_multiplier_target` → how fast you inflate your ego  

---

## 📊 Odds & Rewards

Tools → Slot Machine → Show Odds and Rewards

Includes:

- real probabilities  
- actual multipliers  
- expected value  

---

## 💾 Persistence

Your fake wealth is stored locally.

Yes, it survives restarts.  
No, you cannot cash it out.  

---

## ⚠️ Disclaimer

- This is not gambling  
- This is not productive  
- This is barely educational  

But it might make you review more cards.

---

## 🏁 Final note

If you ever find yourself thinking:

"one more card, I can hit the jackpot"

It’s working.
