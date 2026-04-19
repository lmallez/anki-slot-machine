from __future__ import annotations

import unittest
from unittest.mock import patch

from test_support import install_stubs


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        install_stubs()

    def test_build_settings_config_preserves_other_values(self) -> None:
        from anki_slot_machine.ui.settings_dialog import build_settings_config

        updated = build_settings_config(
            {
                "starting_balance": 250,
                "roll_cost": 1,
                "spin_trigger_chance": 0.25,
                "answer_base_values": {
                    "again": 0,
                    "hard": 0.5,
                    "good": 1,
                    "easy": 1.5,
                },
                "machines": [{"key": "main", "label": "Slot 1"}],
            },
            roll_cost=1.5,
            answer_base_values={
                "again": -1.0,
                "hard": 0.25,
                "good": 2.0,
                "easy": 3.0,
            },
            spin_trigger_every_n=3,
            stealth_mode_enabled=True,
        )

        self.assertEqual(updated["starting_balance"], 250)
        self.assertEqual(updated["roll_cost"], 1.5)
        self.assertEqual(updated["machines"], [{"key": "main", "label": "Slot 1"}])
        self.assertNotIn("spin_trigger_chance", updated)
        self.assertEqual(updated["spin_trigger_every_n"], 3)
        self.assertTrue(updated["stealth_mode_enabled"])
        self.assertEqual(
            updated["answer_base_values"],
            {
                "again": -1.0,
                "hard": 0.25,
                "good": 2.0,
                "easy": 3.0,
            },
        )

    def test_dialog_loads_current_config_values(self) -> None:
        from anki_slot_machine.ui.settings_dialog import SlotMachineSettingsDialog

        raw_config = {
            "starting_balance": 100,
            "decimal_places": 2,
            "roll_cost": 1.25,
            "spin_trigger_every_n": 4,
            "stealth_mode_enabled": True,
            "answer_base_values": {
                "again": -1.0,
                "hard": 0.25,
                "good": 1.75,
                "easy": 2.5,
            },
        }

        with patch(
            "anki_slot_machine.ui.settings_dialog.addon_config",
            return_value=raw_config,
        ):
            dialog = SlotMachineSettingsDialog()

        self.assertEqual(dialog.roll_cost_input.value(), 1.25)
        self.assertEqual(dialog.again_input.value(), -1.0)
        self.assertEqual(dialog.hard_input.value(), 0.25)
        self.assertEqual(dialog.good_input.value(), 1.75)
        self.assertEqual(dialog.easy_input.value(), 2.5)
        self.assertEqual(dialog.spin_trigger_every_n_input.value(), 4)
        self.assertTrue(dialog.stealth_mode_enabled_input.isChecked())

    def test_save_writes_config_and_refreshes_reviewer(self) -> None:
        from anki_slot_machine.ui.settings_dialog import SlotMachineSettingsDialog

        raw_config = {
            "starting_balance": 100,
            "decimal_places": 2,
            "roll_cost": 1.0,
            "spin_trigger_every_n": 1,
            "stealth_mode_enabled": False,
            "answer_base_values": {
                "again": 0.0,
                "hard": 0.5,
                "good": 1.0,
                "easy": 1.5,
            },
        }

        with patch(
            "anki_slot_machine.ui.settings_dialog.addon_config",
            return_value=raw_config,
        ), patch(
            "anki_slot_machine.ui.settings_dialog.write_addon_config"
        ) as write_config, patch(
            "anki_slot_machine.reviewer.refresh_active_reviewer"
        ) as refresh_reviewer:
            dialog = SlotMachineSettingsDialog()
            dialog.roll_cost_input.setValue(2.0)
            dialog.good_input.setValue(2.25)
            dialog.easy_input.setValue(3.5)
            dialog.spin_trigger_every_n_input.setValue(5)
            dialog.stealth_mode_enabled_input.setChecked(True)

            dialog.save()

        write_config.assert_called_once()
        saved_config = write_config.call_args.args[0]
        self.assertEqual(saved_config["roll_cost"], 2.0)
        self.assertEqual(saved_config["answer_base_values"]["good"], 2.25)
        self.assertEqual(saved_config["answer_base_values"]["easy"], 3.5)
        self.assertNotIn("spin_trigger_chance", saved_config)
        self.assertEqual(saved_config["spin_trigger_every_n"], 5)
        self.assertTrue(saved_config["stealth_mode_enabled"])
        refresh_reviewer.assert_called_once_with(suppress_animation=True)


if __name__ == "__main__":
    unittest.main()
