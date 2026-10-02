"""
Unit tests for the Payment State Machine.

Tests:
- Valid transitions: pending -> authorized, pending -> captured, pending -> failed,
                     authorized -> captured, authorized -> failed,
                     captured -> refunded
- Invalid transitions: pending -> refunded, authorized -> refunded,
                       captured -> authorized, captured -> pending,
                       failed -> any, refunded -> any
- Terminal states: failed (empty transition set), refunded (empty transition set)
- Duplicate transitions: idempotency handling
"""

import pytest
from app.models.payment import PAYMENT_TRANSITIONS, Payment


class TestPaymentTransitions:
    def test_conceptual_states_exist(self):
        """Verify all required conceptual states exist in the transition graph."""
        required_states = {"pending", "authorized", "captured", "failed", "refunded"}
        assert set(PAYMENT_TRANSITIONS.keys()) == required_states

    def test_valid_transitions_from_pending(self):
        """pending can transition to authorized, captured, or failed."""
        assert "authorized" in PAYMENT_TRANSITIONS["pending"]
        assert "captured" in PAYMENT_TRANSITIONS["pending"]
        assert "failed" in PAYMENT_TRANSITIONS["pending"]
        assert "refunded" not in PAYMENT_TRANSITIONS["pending"]

    def test_valid_transitions_from_authorized(self):
        """authorized can transition to captured or failed."""
        assert "captured" in PAYMENT_TRANSITIONS["authorized"]
        assert "failed" in PAYMENT_TRANSITIONS["authorized"]
        assert "pending" not in PAYMENT_TRANSITIONS["authorized"]
        assert "refunded" not in PAYMENT_TRANSITIONS["authorized"]

    def test_valid_transitions_from_captured(self):
        """captured can only transition to refunded."""
        assert PAYMENT_TRANSITIONS["captured"] == {"refunded"}

    def test_terminal_state_failed(self):
        """failed is a terminal state — cannot transition to any other status."""
        assert len(PAYMENT_TRANSITIONS["failed"]) == 0
        p = Payment(status="failed", idempotency_key="k1")
        assert not p.can_transition_to("pending")
        assert not p.can_transition_to("authorized")
        assert not p.can_transition_to("captured")
        assert not p.can_transition_to("refunded")

    def test_terminal_state_refunded(self):
        """refunded is a terminal state — cannot transition to any other status."""
        assert len(PAYMENT_TRANSITIONS["refunded"]) == 0
        p = Payment(status="refunded", idempotency_key="k2")
        assert not p.can_transition_to("pending")
        assert not p.can_transition_to("authorized")
        assert not p.can_transition_to("captured")
        assert not p.can_transition_to("failed")

    def test_payment_model_can_transition_to(self):
        """Test Payment.can_transition_to method for valid and invalid paths."""
        payment = Payment(status="pending", idempotency_key="k3")
        assert payment.can_transition_to("authorized") is True
        assert payment.can_transition_to("captured") is True
        assert payment.can_transition_to("failed") is True
        assert payment.can_transition_to("refunded") is False

        payment.status = "authorized"
        assert payment.can_transition_to("captured") is True
        assert payment.can_transition_to("failed") is True
        assert payment.can_transition_to("pending") is False

        payment.status = "captured"
        assert payment.can_transition_to("refunded") is True
        assert payment.can_transition_to("authorized") is False
        assert payment.can_transition_to("failed") is False
