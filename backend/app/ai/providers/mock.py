"""
Flowmint AI — Mock LLM Provider.

Provides deterministic, zero-network LLM simulations for unit testing,
agent orchestration tests, and local development.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.ai.providers.base import (
    FunctionCallData,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ToolCallData,
    UsageMetadata,
)


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider that simulates tool-calling and response generation.
    Supports preset queue overrides for exact unit test assertions.
    """

    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name
        self._preset_responses: list[LLMResponse] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    def enqueue_response(self, response: LLMResponse) -> None:
        """Enqueue a specific response to be returned on the next generate call."""
        self._preset_responses.append(response)

    def clear_presets(self) -> None:
        self._preset_responses.clear()

    async def generate(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # 1. Check if a preset response was queued
        if self._preset_responses:
            return self._preset_responses.pop(0)

        # 2. Inspect message history
        # If the last message is a TOOL result, synthesize the final answer
        tool_messages = [m for m in messages if m.role == "tool"]
        last_msg = messages[-1] if messages else None

        if tool_messages and last_msg and last_msg.role == "tool":
            return self._synthesize_tool_response(messages, tool_messages)

        # 3. Otherwise inspect user query to decide whether to call a tool
        user_messages = [m for m in messages if m.role == "user"]
        if not user_messages:
            return LLMResponse(
                content="Hello! How can I assist you today?",
                usage=UsageMetadata(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            )

        query = user_messages[-1].content.strip().lower()

        # Adversarial / Prompt injection check
        if any(keyword in query for keyword in ["ignore previous instructions", "drop tables", "override system", "system prompt reveal"]):
            return LLMResponse(
                content="I cannot comply with requests that attempt to override my security boundaries or system instructions.",
                finish_reason="stop",
                usage=UsageMetadata(prompt_tokens=25, completion_tokens=20, total_tokens=45),
            )

        # If tools are available, map user intent to tool calls
        if tools:
            tool_call = self._determine_tool_call(query, tools)
            if tool_call:
                return LLMResponse(
                    content=None,
                    tool_calls=[tool_call],
                    finish_reason="tool_calls",
                    usage=UsageMetadata(prompt_tokens=50, completion_tokens=20, total_tokens=70),
                )

        # Conversational fallback
        return LLMResponse(
            content=f"I understand your request regarding: '{user_messages[-1].content}'. Please specify if you are looking for product search, stock details, or sales analytics.",
            finish_reason="stop",
            usage=UsageMetadata(prompt_tokens=20, completion_tokens=30, total_tokens=50),
        )

    def _determine_tool_call(self, query: str, tools: list[dict]) -> ToolCallData | None:
        """Determines which tool to invoke based on query heuristics."""
        tool_names = {t.get("function", {}).get("name") for t in tools}

        # BUYER TOOLS:
        # compare products
        if "compare" in query and "compare_products" in tool_names:
            ids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", query)
            return ToolCallData(
                id="call_compare_001",
                function=FunctionCallData(
                    name="compare_products",
                    arguments={"product_ids": ids if len(ids) >= 2 else ["prod-1", "prod-2"]},
                ),
            )

        # inventory check
        if any(w in query for w in ["stock", "available", "inventory", "units left"]) and "check_inventory" in tool_names:
            id_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", query)
            prod_id = id_match.group(0) if id_match else "mock-product-id"
            return ToolCallData(
                id="call_stock_001",
                function=FunctionCallData(
                    name="check_inventory",
                    arguments={"product_id": prod_id},
                ),
            )

        # related products
        if any(w in query for w in ["related", "similar", "alternatives"]) and "get_related_products" in tool_names:
            id_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", query)
            prod_id = id_match.group(0) if id_match else "mock-product-id"
            return ToolCallData(
                id="call_related_001",
                function=FunctionCallData(
                    name="get_related_products",
                    arguments={"product_id": prod_id, "limit": 5},
                ),
            )

        # single product lookup
        if ("details for" in query or "get product" in query or "sku" in query) and "get_product" in tool_names:
            return ToolCallData(
                id="call_get_prod_001",
                function=FunctionCallData(
                    name="get_product",
                    arguments={"sku": "SAMPLE-SKU"} if "sku" in query else {"product_id": "mock-product-id"},
                ),
            )

        # product search
        if any(w in query for w in ["find", "search", "looking for", "laptop", "phone", "watch", "shoes", "price", "under"]) and "search_products" in tool_names:
            # Extract price if present
            max_price = None
            price_match = re.search(r"(?:under|below|less than)\s*₹?\s*(\d+(?:,\d+)?)", query)
            if price_match:
                max_price = float(price_match.group(1).replace(",", ""))

            # Extract search keyword
            cleaned_query = query
            for prefix in ["find me a ", "find me ", "search for ", "looking for ", "show me "]:
                if cleaned_query.startswith(prefix):
                    cleaned_query = cleaned_query[len(prefix):]
                    break
            cleaned_query = re.sub(r"(?:under|below|less than)\s*₹?\s*[\d,]+", "", cleaned_query).strip()
            cleaned_query = re.sub(r"\s+with\s+.*$", "", cleaned_query).strip()

            return ToolCallData(
                id="call_search_001",
                function=FunctionCallData(
                    name="search_products",
                    arguments={
                        "query": cleaned_query[:50] or "laptop",
                        "max_price": max_price,
                        "limit": 10,
                    },
                ),
            )

        # ANALYTICS TOOLS:
        # compare periods
        if "compare" in query and ("period" in query or "month" in query or "quarter" in query or "last year" in query) and "compare_periods" in tool_names:
            return ToolCallData(
                id="call_compare_periods_001",
                function=FunctionCallData(
                    name="compare_periods",
                    arguments={
                        "period1_start": "2026-09-01",
                        "period1_end": "2026-09-15",
                        "period2_start": "2026-09-16",
                        "period2_end": "2026-09-30",
                    },
                ),
            )

        # conversion summary
        if any(w in query for w in ["conversion", "funnel", "checkout rate", "checkout drop"]) and "get_conversion_summary" in tool_names:
            return ToolCallData(
                id="call_conv_001",
                function=FunctionCallData(
                    name="get_conversion_summary",
                    arguments={},
                ),
            )

        # product performance
        if any(w in query for w in ["best sell", "top sell", "top product", "top item", "performance", "worst sell", "popular product", "selling product"]) and "get_product_performance" in tool_names:
            return ToolCallData(
                id="call_perf_001",
                function=FunctionCallData(
                    name="get_product_performance",
                    arguments={"limit": 5, "order_by": "revenue"},
                ),
            )

        # payment summary
        if any(w in query for w in ["payment", "captured", "failed payment", "refunds"]) and "get_payment_summary" in tool_names:
            return ToolCallData(
                id="call_pay_001",
                function=FunctionCallData(
                    name="get_payment_summary",
                    arguments={},
                ),
            )

        # order summary
        if any(w in query for w in ["order count", "how many orders", "pending order"]) and "get_order_summary" in tool_names:
            return ToolCallData(
                id="call_orders_001",
                function=FunctionCallData(
                    name="get_order_summary",
                    arguments={},
                ),
            )

        # revenue summary (default for analytics)
        if any(w in query for w in ["revenue", "sales", "earnings", "income", "fall", "drop", "grow"]) and "get_revenue_summary" in tool_names:
            return ToolCallData(
                id="call_rev_001",
                function=FunctionCallData(
                    name="get_revenue_summary",
                    arguments={},
                ),
            )

        # PHASE 2B GROWTH TOOLS:
        if any(w in query for w in ["bundle", "cross sell", "cross-sell", "bought together", "companion", "affinity", "upsell"]) and "get_frequently_bought_together" in tool_names:
            return ToolCallData(
                id="call_fbt_001",
                function=FunctionCallData(
                    name="get_frequently_bought_together",
                    arguments={"limit": 5},
                ),
            )

        if any(w in query for w in ["customer history", "customer spend", "repeat buyer"]) and "get_customer_purchase_history" in tool_names:
            return ToolCallData(
                id="call_cust_hist_001",
                function=FunctionCallData(
                    name="get_customer_purchase_history",
                    arguments={"email": "cust@test.com"},
                ),
            )

        if any(w in query for w in ["inventory health", "stockout", "reorder", "stock pressure"]) and "get_inventory_health" in tool_names:
            return ToolCallData(
                id="call_inv_health_001",
                function=FunctionCallData(
                    name="get_inventory_health",
                    arguments={"limit": 10},
                ),
            )

        # PHASE 2B RECOVERY TOOLS:
        if any(w in query for w in ["abandoned cart", "abandoned carts", "unconverted cart", "cart abandonment"]) and "get_abandoned_carts" in tool_names:
            return ToolCallData(
                id="call_aband_carts_001",
                function=FunctionCallData(
                    name="get_abandoned_carts",
                    arguments={"min_value": 0.0, "limit": 10},
                ),
            )

        if any(w in query for w in ["failed payment", "failed payments", "retry payment", "payment drop"]) and "get_failed_payments" in tool_names:
            return ToolCallData(
                id="call_failed_pay_001",
                function=FunctionCallData(
                    name="get_failed_payments",
                    arguments={"limit": 10},
                ),
            )

        if any(w in query for w in ["recovery", "recover", "revenue at risk", "churn"]) and "get_recovery_candidates" in tool_names:
            return ToolCallData(
                id="call_rec_cand_001",
                function=FunctionCallData(
                    name="get_recovery_candidates",
                    arguments={"limit": 10},
                ),
            )

        return None

    def _synthesize_tool_response(self, messages: list[LLMMessage], tool_messages: list[LLMMessage]) -> LLMResponse:
        """Synthesizes a natural-language response strictly grounded in the tool results."""
        last_tool = tool_messages[-1]
        content = last_tool.content or ""

        # Unwrap untrusted_data delimiters if present
        if "<untrusted_data" in content and "</untrusted_data>" in content:
            start_tag = content.find(">")
            end_tag = content.rfind("</untrusted_data>")
            if start_tag != -1 and end_tag != -1:
                inner = content[start_tag + 1:end_tag].strip()
                # Skip the "IMPORTANT:..." line if present
                if inner.startswith("IMPORTANT:"):
                    lines = inner.split("\n", 1)
                    inner = lines[1].strip() if len(lines) > 1 else ""
                content = inner

        try:
            raw_data = json.loads(content) if content else {}
        except Exception:
            raw_data = {"raw": content}

        tool_name = last_tool.name or "tool"
        data = raw_data.get("data") if isinstance(raw_data, dict) and "data" in raw_data else raw_data

        # 1. Product Search response
        if tool_name == "search_products":
            items = data if isinstance(data, list) else []
            if not items:
                text = "I searched our catalog, but no products matched your specific criteria. Would you like to adjust your budget or filters?"
            else:
                lines = [f"Found {len(items)} matching product(s):"]
                for p in items:
                    name = p.get("name", "Product")
                    price = p.get("price", "N/A")
                    sku = p.get("sku", "")
                    stock = p.get("available_stock", 0)
                    lines.append(f"- **{name}** (SKU: {sku}) — ₹{price} | Stock: {stock} units available")
                lines.append("\nAll listed products are available in stock and verified directly from the catalog.")
                text = "\n".join(lines)
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=80, completion_tokens=60, total_tokens=140))

        # 2. Check Inventory response
        if tool_name == "check_inventory":
            qty = data.get("quantity", 0) if isinstance(data, dict) else 0
            reserved = data.get("reserved", 0) if isinstance(data, dict) else 0
            avail = data.get("available", 0) if isinstance(data, dict) else 0
            text = f"Inventory Status:\n- Total Quantity: {qty}\n- Reserved: {reserved}\n- Available for Purchase: {avail}"
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=40, completion_tokens=30, total_tokens=70))

        # 3. Revenue Summary response
        if tool_name == "get_revenue_summary":
            total_rev = data.get("total_revenue", "0.00") if isinstance(data, dict) else "0.00"
            order_count = data.get("order_count", 0) if isinstance(data, dict) else 0
            aov = data.get("average_order_value", "0.00") if isinstance(data, dict) else "0.00"
            text = (
                f"**Observed Facts (Direct from Database):**\n"
                f"- Total Revenue: ₹{total_rev}\n"
                f"- Completed Orders: {order_count}\n"
                f"- Average Order Value: ₹{aov}\n\n"
                f"**Derived Calculation & Interpretation:**\n"
                f"Revenue reflects all confirmed orders within the requested timeframe."
            )
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=60, completion_tokens=50, total_tokens=110))

        # 4. Product Performance response
        if tool_name == "get_product_performance":
            items = data if isinstance(data, list) else []
            lines = ["**Product Performance Metrics:**"]
            for idx, item in enumerate(items, 1):
                pname = item.get("product_name", "Item")
                units = item.get("units_sold", 0)
                rev = item.get("total_revenue", 0.0)
                lines.append(f"{idx}. {pname} — {units} sold, generating ₹{rev}")
            text = "\n".join(lines) if items else "No sales data found for products in this period."
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=60, completion_tokens=40, total_tokens=100))

        # 5. Frequently Bought Together (Growth)
        if tool_name == "get_frequently_bought_together":
            pairs = data if isinstance(data, list) else []
            if not pairs:
                text = "No frequent bundle pairs detected in current order history. As catalog volume expands, companion patterns will emerge."
            else:
                lines = ["**Recommended Cross-Sell Bundles:**"]
                for p in pairs:
                    p1 = p.get("product_a", {}).get("product_name", "Item A")
                    p2 = p.get("product_b", {}).get("product_name", "Item B")
                    cnt = p.get("co_occurrence_count", 0)
                    bprice = p.get("bundle_price", 0.0)
                    lines.append(f"- **{p1}** + **{p2}** (Purchased together {cnt} times) — Suggested Bundle Price: ₹{bprice:,.2f}")
                lines.append("\nRecommended Action: Propose bundled checkout discount.")
                text = "\n".join(lines)
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=70, completion_tokens=60, total_tokens=130))

        # 6. Abandoned Carts (Recovery)
        if tool_name in ("get_abandoned_carts", "get_recovery_candidates"):
            carts = data if isinstance(data, list) else data.get("top_abandoned_carts", []) if isinstance(data, dict) else []
            if not carts:
                text = "No active abandoned carts detected. Store checkout conversion is healthy."
            else:
                total_val = sum(c.get("total_value", 0.0) for c in carts)
                lines = [f"**Abandoned Shopping Carts ({len(carts)} eligible, ₹{total_val:,.2f} at risk):**"]
                for c in carts[:5]:
                    cid = c.get("cart_id", "")[:8]
                    cname = c.get("customer_name", "Customer")
                    val = c.get("total_value", 0.0)
                    cnt = c.get("item_count", 0)
                    lines.append(f"- Cart #{cid}... ({cname}) — ₹{val:,.2f} ({cnt} items)")
                lines.append("\nRecommended Action: Deploy targeted recovery email/SMS sequence with 10% incentive.")
                text = "\n".join(lines)
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=80, completion_tokens=60, total_tokens=140))

        # 7. Failed Payments (Recovery)
        if tool_name == "get_failed_payments":
            payments = data if isinstance(data, list) else []
            if not payments:
                text = "Zero failed checkout payments recorded in the requested window."
            else:
                total_failed = sum(p.get("amount", 0.0) for p in payments)
                lines = [f"**Recoverable Failed Payments ({len(payments)} incidents, ₹{total_failed:,.2f}):**"]
                for p in payments[:5]:
                    order_num = p.get("order_number", "Order")
                    amt = p.get("amount", 0.0)
                    err = p.get("error_code", "ERROR")
                    lines.append(f"- {order_num} — ₹{amt:,.2f} (Reason: {err})")
                lines.append("\nRecommended Action: Dispatch 1-click Razorpay payment retry links.")
                text = "\n".join(lines)
            return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=70, completion_tokens=50, total_tokens=120))

        # Generic grounded synthesis
        text = f"Based on authoritative data from `{tool_name}`:\n```json\n{json.dumps(data, indent=2)}\n```"
        return LLMResponse(content=text, usage=UsageMetadata(prompt_tokens=50, completion_tokens=40, total_tokens=90))
