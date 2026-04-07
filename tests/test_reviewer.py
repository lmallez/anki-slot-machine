from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_support import install_stubs

stubs = install_stubs()

from anki_slot_machine import reviewer

reviewer.mw = stubs.mw


class ReviewerHookTests(unittest.TestCase):
    def make_reviewer(self, button_count: int = 4):
        web = SimpleNamespace(eval=Mock())
        fake_col = SimpleNamespace(
            sched=SimpleNamespace(answerButtons=lambda _card: button_count)
        )
        fake_mw = SimpleNamespace(col=fake_col)

        class FakeReviewer(stubs.reviewer_class):
            pass

        instance = FakeReviewer()
        instance.web = web
        instance.mw = fake_mw
        instance.card = SimpleNamespace(id=123)
        instance.answerCard = Mock()
        return instance

    def test_web_assets_are_injected_once(self) -> None:
        content = SimpleNamespace(css=[], js=[])
        context = self.make_reviewer()
        reviewer.on_webview_will_set_content(content, context)
        reviewer.on_webview_will_set_content(content, context)
        self.assertEqual(len(content.css), 1)
        self.assertEqual(len(content.js), 1)

    def test_duck_typed_reviewer_context_is_supported(self) -> None:
        content = SimpleNamespace(css=[], js=[])
        context = SimpleNamespace(web=SimpleNamespace(), card=SimpleNamespace(id=1))
        reviewer.on_webview_will_set_content(content, context)
        self.assertEqual(len(content.css), 1)
        self.assertEqual(len(content.js), 1)

    def test_non_prefixed_messages_are_ignored(self) -> None:
        context = self.make_reviewer()
        result = reviewer.on_webview_did_receive_js_message((False, None), "noop", context)
        self.assertEqual(result, (False, None))

    def test_prefixed_messages_update_the_panel_only(self) -> None:
        context = self.make_reviewer()
        fake_service = SimpleNamespace(
            set_bet=Mock(return_value={"balance": "125.00", "fixed_bet_amount": "1.00"}),
        )
        with patch.object(reviewer, "get_service", return_value=fake_service):
            handled, payload = reviewer.on_webview_did_receive_js_message(
                (False, None), "anki-slot-machine:set-bet:5", context
            )

        self.assertTrue(handled)
        self.assertIsNone(payload)
        fake_service.set_bet.assert_called_once_with("5")
        script = context.web.eval.call_args[0][0]
        self.assertIn("syncState", script)
        self.assertIn('"balance": "125.00"', script)

    def test_already_handled_filter_state_is_preserved(self) -> None:
        context = self.make_reviewer()
        result = reviewer.on_webview_did_receive_js_message(
            (True, "existing"), "anki-slot-machine:set-bet:5", context
        )
        self.assertEqual(result, (True, "existing"))

    def test_answer_hook_uses_existing_anki_rating_without_answering_again(self) -> None:
        context = self.make_reviewer(button_count=2)
        card = SimpleNamespace(id=456)
        fake_service = SimpleNamespace(apply_review=Mock())

        with patch.object(reviewer, "get_service", return_value=fake_service):
            reviewer.on_reviewer_did_answer_card(context, card, 2)

        fake_service.apply_review.assert_called_once_with(
            card_id=456, ease=2, button_count=2
        )
        context.answerCard.assert_not_called()

    def test_state_did_undo_restores_slot_state_after_review_undo(self) -> None:
        fake_service = SimpleNamespace(undo_last_review=Mock(return_value=True))

        with (
            patch.object(reviewer, "get_service", return_value=fake_service),
            patch.object(reviewer, "refresh_active_reviewer") as refresh_active_reviewer,
        ):
            reviewer.on_state_did_undo(
                SimpleNamespace(changes=SimpleNamespace(study_queues=True))
            )

        fake_service.undo_last_review.assert_called_once_with()
        refresh_active_reviewer.assert_called_once_with()

    def test_state_did_undo_ignores_non_review_undo(self) -> None:
        fake_service = SimpleNamespace(undo_last_review=Mock(return_value=True))

        with (
            patch.object(reviewer, "get_service", return_value=fake_service),
            patch.object(reviewer, "refresh_active_reviewer") as refresh_active_reviewer,
        ):
            reviewer.on_state_did_undo(
                SimpleNamespace(changes=SimpleNamespace(study_queues=False))
            )

        fake_service.undo_last_review.assert_not_called()
        refresh_active_reviewer.assert_not_called()

    def test_refresh_pushes_serialized_state_to_webview(self) -> None:
        context = self.make_reviewer()
        stubs.mw.reviewer = context
        fake_service = SimpleNamespace(
            snapshot=Mock(return_value={"balance": "99.00", "fixed_bet_amount": "1.00"})
        )

        with patch.object(reviewer, "get_service", return_value=fake_service):
            reviewer.refresh_active_reviewer()

        fake_service.snapshot.assert_called_once()
        script = context.web.eval.call_args[0][0]
        payload = script.split("syncState(", 1)[1].rsplit(");", 1)[0]
        self.assertEqual(json.loads(payload), {"balance": "99.00", "fixed_bet_amount": "1.00"})


if __name__ == "__main__":
    unittest.main()
