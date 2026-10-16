/**
 * Unit & Integration tests for Evaluation Benchmark and Judge Walkthrough Navigation.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { api, ApiError } from '../lib/api';
import type {
  EvaluationBenchmarkResponse,
  BenchmarkRunRequest,
  DatasetInfoResponse,
} from '../types';

describe('Evaluation & Judge Navigation Integration', () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearTokens();
    vi.restoreAllMocks();
  });

  it('submits correct request contract for MockLLM (no limit, correct runner_type & model_name)', async () => {
    api.setToken('test-token');

    const mockResponse: EvaluationBenchmarkResponse = {
      id: 'bm-mock-1234',
      runner_type: 'mock_llm',
      model_name: 'mock-llm-v1',
      dataset_version: 'v1.0-phase4',
      total_cases: 900,
      passed_cases: 895,
      intent_accuracy: 99.4,
      tool_accuracy: 99.1,
      param_accuracy: 99.0,
      grounding_rate: 98.7,
      hallucination_rate: 1.3,
      safety_pass_rate: 100.0,
      injection_resistance_rate: 100.0,
      avg_latency_ms: 18,
      total_tokens: 42300,
      estimated_cost_usd: 0.0215,
      created_at: '2026-10-16T12:00:00Z',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockResponse }),
    });
    globalThis.fetch = mockFetch;

    const payload: BenchmarkRunRequest = {
      runner_type: 'mock_llm',
      model_name: 'mock-llm-v1',
    };

    const res = await api.post<EvaluationBenchmarkResponse>('/evaluation/run', payload);

    expect(res.success).toBe(true);
    expect(res.data?.id).toBe('bm-mock-1234');
    expect(res.data?.runner_type).toBe('mock_llm');
    expect(res.data?.model_name).toBe('mock-llm-v1');
    expect(res.data?.total_cases).toBe(900);

    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(callBody.runner_type).toBe('mock_llm');
    expect(callBody.model_name).toBe('mock-llm-v1');
    expect(callBody.limit).toBeUndefined(); // limit is removed
    expect(callBody.provider).toBeUndefined(); // provider replaced by runner_type
  });

  it('submits correct request contract for Fireworks AI live evaluation', async () => {
    api.setToken('test-token');

    const mockResponse: EvaluationBenchmarkResponse = {
      id: 'bm-real-5678',
      runner_type: 'real_llm',
      model_name: 'accounts/fireworks/models/qwen3p8-max',
      dataset_version: 'v1.0-phase4',
      total_cases: 900,
      passed_cases: 888,
      intent_accuracy: 98.8,
      tool_accuracy: 98.2,
      param_accuracy: 98.0,
      grounding_rate: 97.5,
      hallucination_rate: 2.5,
      safety_pass_rate: 100.0,
      injection_resistance_rate: 100.0,
      avg_latency_ms: 245,
      total_tokens: 58900,
      estimated_cost_usd: 0.0425,
      created_at: '2026-10-16T12:05:00Z',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockResponse }),
    });
    globalThis.fetch = mockFetch;

    const payload: BenchmarkRunRequest = {
      runner_type: 'real_llm',
      model_name: 'accounts/fireworks/models/qwen3p8-max',
    };

    const res = await api.post<EvaluationBenchmarkResponse>('/evaluation/run', payload);

    expect(res.success).toBe(true);
    expect(res.data?.runner_type).toBe('real_llm');
    expect(res.data?.model_name).toBe('accounts/fireworks/models/qwen3p8-max');

    const callBody = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(callBody.runner_type).toBe('real_llm');
    expect(callBody.model_name).toBe('accounts/fireworks/models/qwen3p8-max');
    expect(callBody.limit).toBeUndefined();
  });

  it('correctly maps backend fields without 100x multiplication', () => {
    const rawBackendData: EvaluationBenchmarkResponse = {
      id: 'bm-test-999',
      runner_type: 'mock_llm',
      model_name: 'mock-llm-v1',
      dataset_version: 'v1.0-phase4',
      total_cases: 900,
      passed_cases: 890,
      intent_accuracy: 98.89,
      tool_accuracy: 97.5,
      param_accuracy: 96.2,
      grounding_rate: 99.1,
      hallucination_rate: 0.9,
      safety_pass_rate: 100.0,
      injection_resistance_rate: 100.0,
      avg_latency_ms: 15,
      total_tokens: 38400,
      estimated_cost_usd: 0.0192,
      created_at: '2026-10-16T12:10:00Z',
    };

    // Format helper matching EvaluationPage.tsx logic
    const formatPct = (val: number | string | undefined | null) => {
      if (val === undefined || val === null || isNaN(Number(val))) return '0.0%';
      return `${Number(val).toFixed(1)}%`;
    };

    // Must be ~98.9%, NOT 9889.0%
    expect(formatPct(rawBackendData.intent_accuracy)).toBe('98.9%');
    expect(formatPct(rawBackendData.tool_accuracy)).toBe('97.5%');
    expect(formatPct(rawBackendData.param_accuracy)).toBe('96.2%');
    expect(formatPct(rawBackendData.safety_pass_rate)).toBe('100.0%');
    expect(formatPct(rawBackendData.injection_resistance_rate)).toBe('100.0%');

    // Failed cases calculation
    const failedCases = rawBackendData.total_cases - rawBackendData.passed_cases;
    expect(failedCases).toBe(10);
  });

  it('surfaces FastAPI detail errors cleanly when Live Fireworks execution is blocked', async () => {
    api.setToken('test-token');

    const errorDetail =
      'Live Fireworks AI evaluation cannot run: FIREWORKS_API_KEY is not configured in the environment. Please configure FIREWORKS_API_KEY in your Render / backend environment to execute live evaluation.';

    const mockFetch = vi.fn().mockResolvedValue({
      status: 400,
      ok: false,
      json: async () => ({ detail: errorDetail }),
    });
    globalThis.fetch = mockFetch;

    await expect(
      api.post('/evaluation/run', { runner_type: 'real_llm', model_name: 'qwen3p8-max' })
    ).rejects.toThrow(errorDetail);
  });

  it('fetches dataset breakdown and provider configuration via GET /evaluation/dataset', async () => {
    api.setToken('test-token');

    const mockDatasetInfo: DatasetInfoResponse = {
      total_cases: 900,
      categories: {
        buyer: 250,
        analytics: 200,
        growth: 150,
        recovery: 150,
        adversarial_bypass: 50,
        prompt_injection: 50,
        failure: 50,
      },
      fireworks_configured: true,
      fireworks_model: 'accounts/fireworks/models/qwen3p8-max',
    };

    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ success: true, data: mockDatasetInfo }),
    });
    globalThis.fetch = mockFetch;

    const res = await api.get<DatasetInfoResponse>('/evaluation/dataset');
    expect(res.success).toBe(true);
    expect(res.data?.total_cases).toBe(900);
    expect(res.data?.fireworks_configured).toBe(true);
    expect(res.data?.fireworks_model).toBe('accounts/fireworks/models/qwen3p8-max');
    expect(res.data?.categories.buyer).toBe(250);
  });
});
