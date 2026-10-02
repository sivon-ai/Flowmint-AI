"""
Flowmint AI — Failure Recovery & Safe State Machine (Phase 4).

Guarantees:
1. No duplicate financial side effects.
2. Failed operations are completely observable and audited.
3. Retries are strictly idempotent.
4. Ambiguous or unknown states always fail closed.
5. Never assume success after a timeout.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FailureType(str, enum.Enum):
    LLM_TIMEOUT = "llm_timeout"
    LLM_UNAVAILABLE = "llm_unavailable"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_FAILURE = "tool_failure"
    DB_FAILURE = "db_failure"
    REDIS_FAILURE = "redis_failure"
    EXTERNAL_API_FAILURE = "external_api_failure"
    DUPLICATE_EXECUTION = "duplicate_execution"
    DUPLICATE_WEBHOOK = "duplicate_webhook"
    DUPLICATE_EVENT = "duplicate_event"
    EXPIRED_APPROVAL = "expired_approval"
    EXECUTION_RETRY = "execution_retry"
    PARTIAL_FAILURE = "partial_failure"


class RecoveryAction(str, enum.Enum):
    FAIL_CLOSED = "fail_closed"
    RETURN_CACHED_IDEMPOTENT = "return_cached_idempotent"
    RECORD_AUDIT_AND_ALERT = "record_audit_and_alert"
    SAFE_RETRY = "safe_retry"


@dataclass
class FailureState:
    failure_type: FailureType
    operation: str
    resource_id: str | None
    error_message: str
    recovery_action: RecoveryAction
    side_effects_prevented: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)


class FailureRecoveryService:
    """
    Enforces fail-closed rules and guarantees no unverified side effects.
    """

    @staticmethod
    def handle_llm_timeout(operation: str, trace_id: str | None = None) -> FailureState:
        logger.error(f"[FAIL-CLOSED] LLM timeout during {operation}, trace={trace_id}")
        return FailureState(
            failure_type=FailureType.LLM_TIMEOUT,
            operation=operation,
            resource_id=trace_id,
            error_message="LLM provider timed out after max latency threshold. Request aborted safely.",
            recovery_action=RecoveryAction.FAIL_CLOSED,
            side_effects_prevented=True,
            metadata={"fail_closed": True, "trace_id": trace_id},
        )

    @staticmethod
    def handle_tool_failure(tool_name: str, error: Exception, parameters: dict[str, Any]) -> FailureState:
        logger.error(f"[FAIL-CLOSED] Tool {tool_name} failed: {error}")
        return FailureState(
            failure_type=FailureType.TOOL_FAILURE,
            operation=f"tool_execution:{tool_name}",
            resource_id=tool_name,
            error_message=str(error),
            recovery_action=RecoveryAction.FAIL_CLOSED,
            side_effects_prevented=True,
            metadata={"parameters": parameters},
        )

    @staticmethod
    def handle_expired_approval(action_id: str, expired_at: datetime) -> FailureState:
        logger.warning(f"[FAIL-CLOSED] Attempted execution with expired approval {action_id}")
        return FailureState(
            failure_type=FailureType.EXPIRED_APPROVAL,
            operation="action_execution",
            resource_id=action_id,
            error_message=f"Approval for action {action_id} expired at {expired_at.isoformat()}.",
            recovery_action=RecoveryAction.FAIL_CLOSED,
            side_effects_prevented=True,
            metadata={"expired_at": expired_at.isoformat()},
        )

    @staticmethod
    def handle_duplicate_execution(action_id: str, idempotency_key: str, existing_result: dict[str, Any]) -> FailureState:
        logger.info(f"[IDEMPOTENT] Duplicate execution detected for key={idempotency_key}")
        return FailureState(
            failure_type=FailureType.DUPLICATE_EXECUTION,
            operation="action_execution",
            resource_id=action_id,
            error_message="Action already executed. Returning idempotent cached result.",
            recovery_action=RecoveryAction.RETURN_CACHED_IDEMPOTENT,
            side_effects_prevented=True,
            metadata={"existing_result": existing_result, "idempotency_key": idempotency_key},
        )
