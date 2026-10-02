"""
Flowmint AI — Agent Permission System (Phase 3).

Enforces strictly bounded permissions per agent.
Wildcard permissions are prohibited.
Agents can only propose actions or invoke read tools within their granted capabilities.
"""

from __future__ import annotations

import enum
from typing import Set


class AgentCapability(str, enum.Enum):
    # Read capabilities
    READ_PRODUCTS = "read:products"
    READ_INVENTORY = "read:inventory"
    READ_CATEGORIES = "read:categories"
    READ_ANALYTICS = "read:analytics"
    READ_ORDERS = "read:orders"
    READ_PAYMENTS = "read:payments"
    READ_RECOVERY = "read:recovery"
    READ_COMMERCE_AFFINITIES = "read:commerce_affinities"

    # Proposal capabilities (Non-mutating ActionPlan creation)
    PROPOSE_BUNDLE = "propose:bundle"
    PROPOSE_OFFER = "propose:offer"
    PROPOSE_RECOVERY = "propose:recovery"
    PROPOSE_PAYMENT_RETRY = "propose:payment_retry"

    # Execution capabilities (Restricted ONLY to ActionExecutionService)
    EXECUTE_CAMPAIGN_DRAFT = "execute:campaign_draft"
    EXECUTE_OFFER = "execute:offer"
    EXECUTE_RECOVERY_CAMPAIGN = "execute:recovery_campaign"


# Explicit, non-wildcard capability grants
AGENT_CAPABILITIES: dict[str, Set[AgentCapability]] = {
    "buyer_agent": {
        AgentCapability.READ_PRODUCTS,
        AgentCapability.READ_INVENTORY,
        AgentCapability.READ_CATEGORIES,
    },
    "analytics_agent": {
        AgentCapability.READ_ANALYTICS,
        AgentCapability.READ_ORDERS,
        AgentCapability.READ_PAYMENTS,
        AgentCapability.READ_PRODUCTS,
    },
    "growth_agent": {
        AgentCapability.READ_PRODUCTS,
        AgentCapability.READ_ORDERS,
        AgentCapability.READ_INVENTORY,
        AgentCapability.READ_COMMERCE_AFFINITIES,
        AgentCapability.PROPOSE_BUNDLE,
        AgentCapability.PROPOSE_OFFER,
    },
    "recovery_agent": {
        AgentCapability.READ_RECOVERY,
        AgentCapability.READ_ORDERS,
        AgentCapability.READ_PAYMENTS,
        AgentCapability.PROPOSE_RECOVERY,
        AgentCapability.PROPOSE_PAYMENT_RETRY,
    },
}

# Mapping from ActionPlan action_type to required capability
ACTION_TYPE_REQUIRED_CAPABILITY: dict[str, AgentCapability] = {
    "cross_sell_bundle": AgentCapability.PROPOSE_BUNDLE,
    "promotional_offer": AgentCapability.PROPOSE_OFFER,
    "abandoned_cart_recovery": AgentCapability.PROPOSE_RECOVERY,
    "payment_retry_nudge": AgentCapability.PROPOSE_PAYMENT_RETRY,
}


def validate_agent_permission(agent_name: str, required_capability: AgentCapability) -> bool:
    """
    Validates whether the named agent has been explicitly granted the required capability.
    Wildcards and unknown agents are denied.
    """
    capabilities = AGENT_CAPABILITIES.get(agent_name.lower())
    if not capabilities:
        return False
    return required_capability in capabilities


def validate_agent_can_propose_action(agent_name: str, action_type: str) -> tuple[bool, str]:
    """
    Verifies that the agent has the permission to propose the given action type.
    """
    req_cap = ACTION_TYPE_REQUIRED_CAPABILITY.get(action_type)
    if not req_cap:
        return False, f"Unknown action type: '{action_type}'"

    allowed = validate_agent_permission(agent_name, req_cap)
    if not allowed:
        return (
            False,
            f"Agent '{agent_name}' lacks explicit permission '{req_cap.value}' to propose '{action_type}'",
        )
    return True, "Permission verified"
