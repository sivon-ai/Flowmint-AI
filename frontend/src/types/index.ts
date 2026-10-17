/** Flowmint AI TypeScript types — mirrors backend Pydantic schemas */

export interface ShopifySyncResult {
  success: boolean;
  status: 'pushed' | 'skipped_local_product' | 'permission_denied' | 'failed' | 'conflict';
  message: string;
  external_product_id?: string | null;
  errors?: string[];
  reconciled?: boolean;
}

export interface ProductUpdateRequest {
  name?: string;
  sku?: string;
  description?: string;
  price?: number;
  compare_at_price?: number | null;
  inventory_quantity?: number;
  status?: 'active' | 'draft' | 'archived';
  image_url?: string;
  sync_to_shopify?: boolean;
}

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
  is_shopify_connected?: boolean;
  external_product_id?: string | null;
  shopify_sync_result?: ShopifySyncResult | null;
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

export interface ProductImportRow {
  row_index: number;
  name: string;
  sku: string;
  price: number | null;
  compare_at_price: number | null;
  stock: number;
  description: string | null;
  category_name: string | null;
  status: string;
  validation_status: 'valid' | 'duplicate' | 'invalid' | 'file_duplicate';
  validation_errors: string[];
  is_existing: boolean;
  existing_product_id: string | null;
}

export interface ProductImportSummary {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  file_duplicate_rows: number;
  existing_skus_found: string[];
}

export interface ProductImportParseResponse {
  file_name: string;
  file_size: number;
  format: string;
  sheets: string[];
  selected_sheet: string | null;
  headers: string[];
  column_mapping: Record<string, string>;
  summary: ProductImportSummary;
  rows: ProductImportRow[];
  warnings: string[];
}

export interface ProductImportConfirmRow {
  name: string;
  sku: string;
  price: number;
  compare_at_price?: number | null;
  stock: number;
  description?: string | null;
  category_name?: string | null;
  status: string;
}

export interface ProductImportConfirmRequest {
  duplicate_resolution: 'skip' | 'update';
  rows: ProductImportConfirmRow[];
}

export interface ProductImportResult {
  imported_count: number;
  updated_count: number;
  skipped_count: number;
  failed_count: number;
  errors: string[];
}

export interface Customer {
  id: string;
  merchant_id: string;
  email: string;
  name: string;
  phone: string | null;
  metadata_json?: Record<string, any> | null;
  order_count: number;
  total_spent: number;
  created_at: string;
  updated_at?: string | null;
}

export interface CustomerCreateRequest {
  name: string;
  email: string;
  phone?: string | null;
  metadata?: Record<string, any> | null;
}

export interface CustomerUpdateRequest {
  name?: string;
  email?: string;
  phone?: string | null;
  metadata?: Record<string, any> | null;
}

export interface CustomerPurchaseSummary {
  total_orders: number;
  total_spent: number;
  last_order_date: string | null;
  average_order_value: number;
}

export interface CustomerOrdersResponse {
  customer_id: string;
  summary: CustomerPurchaseSummary;
  orders: Order[];
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
  onboarding_completed?: boolean;
}

export interface StoreConnection {
  id: string;
  merchant_id: string;
  provider: 'shopify' | 'woocommerce' | 'custom';
  store_url: string;
  store_name: string | null;
  external_store_id: string | null;
  status: 'connected' | 'needs_configuration' | 'syncing' | 'synced' | 'error' | 'disconnected';
  scopes: string | null;
  sync_status: 'idle' | 'running' | 'completed' | 'failed';
  last_sync_at: string | null;
  sync_summary: {
    products?: number;
    customers?: number;
    orders?: number;
    inventory?: number;
  } | null;
  last_error: string | null;
  disconnected_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface OnboardingStatus {
  onboarding_completed: boolean;
  onboarding_step: 'connect_store' | 'payment_setup' | 'completed';
  store_connected: boolean;
  store_mode: 'shopify' | 'woocommerce' | 'custom' | 'manual' | null;
  setup_mode?: 'shopify' | 'woocommerce' | 'custom' | 'manual' | 'unconfigured' | null;
  active_store: StoreConnection | null;
  payment_mode: string | null;
  razorpay_mode: 'test' | 'live';
  razorpay_configured: boolean;
}

export interface PaymentConfig {
  payment_mode: string;
  razorpay_mode: 'test' | 'live';
  razorpay_key_id: string | null;
  razorpay_configured: boolean;
  webhook_url: string;
}

export interface PaymentConfigUpdateRequest {
  payment_mode: 'store_native' | 'razorpay_reconciliation' | 'razorpay_hosted' | 'later' | string;
  razorpay_key_id?: string;
  razorpay_key_secret?: string;
  razorpay_webhook_secret?: string;
  razorpay_mode?: 'test' | 'live';
}

export interface StoreSyncStatus {
  connection_id: string;
  sync_status: 'idle' | 'running' | 'completed' | 'failed';
  last_sync_at: string | null;
  sync_summary: Record<string, number>;
  records_processed: number;
  records_failed: number;
  last_error: string | null;
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
  status: 'proposed' | 'validating' | 'simulating' | 'ready_for_review' | 'pending_approval' | 'auto_approved' | 'policy_rejected' | 'executing' | 'completed' | 'failed' | 'deferred' | 'rejected' | 'expired';
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

// ==========================================
// Phase 3: Safety, Governance, Policy & Audit Types
// ==========================================

export interface Approval {
  id: string;
  merchant_id: string;
  action_plan_id: string;
  requested_by: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  reason: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';
  expires_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_reason?: string | null;
  policy_snapshot: Record<string, any>;
  action_plan?: ActionPlan | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLog {
  id: string;
  merchant_id: string;
  event_id: string;
  actor_type: string;
  actor_id: string;
  action_id?: string | null;
  agent?: string | null;
  event_type: string;
  previous_status?: string | null;
  new_status?: string | null;
  reason: string;
  policy_results?: Record<string, any> | null;
  approval_result?: Record<string, any> | null;
  execution_result?: Record<string, any> | null;
  trace_id?: string | null;
  created_at: string;
}

export interface MerchantPolicy {
  id: string;
  merchant_id: string;
  max_discount_percentage: number;
  max_campaign_budget: number;
  high_value_threshold: number;
  contact_cooldown_hours: number;
  require_approval_all_actions: boolean;
  auto_approval_max_risk: string;
  allowed_action_types: string[];
  restricted_product_ids: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PolicyRuleResult {
  rule: string;
  passed: boolean;
  severity: string;
  reason: string;
  evidence: Record<string, any>;
}

export interface PolicyEvaluationResult {
  allowed: boolean;
  requires_approval: boolean;
  risk_level: string;
  reasons: string[];
  rule_results: PolicyRuleResult[];
  evidence_snapshot: Record<string, any>;
}

export interface EvaluationBenchmarkResponse {
  id: string;
  runner_type: 'mock_llm' | 'real_llm' | string;
  model_name: string;
  dataset_version: string;
  total_cases: number;
  passed_cases: number;
  intent_accuracy: number | string;
  tool_accuracy: number | string;
  param_accuracy: number | string;
  grounding_rate: number | string;
  hallucination_rate: number | string;
  safety_pass_rate: number | string;
  injection_resistance_rate: number | string;
  avg_latency_ms: number;
  total_tokens: number;
  estimated_cost_usd: number | string;
  results_breakdown?: {
    category_breakdown?: Record<string, { total: number; passed: number }>;
    summary?: {
      total: number;
      passed: number;
      cost_usd: number;
      avg_latency_ms: number;
    };
  };
  created_at?: string;
}

export interface BenchmarkRunRequest {
  runner_type: 'mock_llm' | 'real_llm';
  model_name?: string | null;
}

export interface DatasetInfoResponse {
  total_cases: number;
  categories: Record<string, number>;
  fireworks_configured?: boolean;
  fireworks_model?: string;
}

