# Slot Profiles

These JSON files are packaged presets for the slot machine.

- `base.json`: the default v1 profile used by the add-on.
- `liberty_bell.json`: triples-only style profile with dead pairs.
- `liberty_bell_pair.json`: classic-feeling profile where any exact pair pays a flat `x1`.

Each profile file uses the same shape:

```json
{
  "name": "profile_name",
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

The add-on config points all reviewer windows at one shared profile through
`slot_profile_path`. The `machines` list only controls how many windows appear
and what each window is called.
