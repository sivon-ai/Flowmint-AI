/** Flowmint AI TypeScript types — mirrors backend Pydantic schemas */

export interface Product {
  id: string;
  merchant_id: string;
  category_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  sku: string;
  price: number;
  compare_at_price: number | null;
  currency: string;
  status: 'active' | 'draft' | 'archived';
  image_url: string | null;
  attributes: ProductAttribute[];
  inventory: InventoryInfo | null;
  created_at: string;
  updated_at: string;
}

export interface ProductAttribute {
  key: string;
  value: string;
}

export interface InventoryInfo {
  quantity: number;
  reserved: number;
  available: number;
  is_low_stock: boolean;
  is_in_stock: boolean;
}

export interface Order {
  id: string;
  merchant_id: string;
  customer_id: string;
  cart_id: string | null;
  order_number: string;
  status: string;
  subtotal: number;
  tax: number;
  discount: number;
  total: number;
  currency: string;
  shipping_address: Record<string, string> | null;
  items: OrderItem[];
  created_at: string;
}

export interface OrderItem {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: number;
  total: number;
}

export interface Customer {
  id: string;
  merchant_id: string;
  email: string;
  name: string;
  phone: string | null;
  created_at: string;
}

export interface CartResponse {
  id: string;
  merchant_id: string;
  customer_id: string | null;
  status: string;
  items: CartItemResponse[];
  subtotal: number;
  item_count: number;
  created_at: string;
}

export interface CartItemResponse {
  id: string;
  product_id: string;
  product_name: string | null;
  quantity: number;
  unit_price: number;
  line_total: number;
}

export interface User {
  id: string;
  merchant_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
}

export interface ToolCallInfo {
  tool: string;
  parameters: Record<string, any>;
  result?: any;
  status: string;
  latency_ms: number;
}

export interface AgentChatResponse {
  session_id: string;
  trace_id: string;
  agent_name: string;
  response: string;
  structured_data: any;
  tool_calls: ToolCallInfo[];
  latency_ms: number;
}

export interface AgentSessionItem {
  id: string;
  merchant_id: string;
  agent_name: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface AgentMessageItem {
  id: string;
  role: string;
  content: string;
  tool_calls?: ToolCallInfo[];
  metadata_json?: Record<string, any>;
  created_at: string;
}

// ==========================================
// Phase 2B: Revenue Intelligence & Decision Engine Types
// ==========================================

export interface Opportunity {
  id: string;
  merchant_id: string;
  type: string;
  title: string;
  description: string;
  status: 'detected' | 'investigating' | 'proposed' | 'simulating' | 'ready_for_review' | 'resolved' | 'dismissed' | 'expired';
  priority: 'critical' | 'high' | 'medium' | 'low';
  confidence: number;
  estimated_value: number;
  currency: string;
  evidence_json: Record<string, any>;
  affected_entity_type: string;
  affected_entity_ids: string[];
  recommended_action: string;
  detected_at: string;
  expires_at?: string | null;
  resolved_at?: string | null;
  created_at: string;
}

export interface ActionPlan {
  id: string;
  action_id: string;
  merchant_id: string;
  opportunity_id?: string | null;
  action_type: string;
  target: string;
  parameters: Record<string, any>;
  evidence: Record<string, any>;
  recommendation_reason: string;
  estimated_impact?: Record<string, any> | null;
  risk_level: string;
  requires_approval: boolean;
  status: 'proposed' | 'simulating' | 'ready_for_review' | 'deferred' | 'rejected';
  created_at: string;
}

export interface SimulationResult {
  simulation_id?: string;
  simulation_type: string;
  eligible_count: number;
  current_value: number;
  assumed_conversion_rate: number;
  projected_conversions: number;
  projected_revenue: number;
  discount_cost: number;
  projected_margin_impact: number;
  assumptions: Record<string, any>;
  confidence: number;
  disclaimer: string;
}

export interface RevenueOverviewMetrics {
  period: string;
  currency: string;
  total_revenue: number;
  completed_orders: number;
  aov: number;
  checkout_conversion_rate: number;
  cart_abandonment_rate: number;
  revenue_at_risk: number;
  payment_failure_rate: number;
  active_opportunities_count: number;
  inventory_pressure_count: number;
}

