/**
 * E2E Test Suite API Client
 *
 * Provides access to the E2E test runner endpoint.
 * Used by admin panel ValidationTab for running/viewing E2E scheduling tests.
 */

import { apiClient } from './client'

export interface E2ETestResult {
  name: string
  outcome: 'passed' | 'failed' | 'skipped' | 'error' | string
  duration_s: number
  message: string | null
}

export interface E2ETestClass {
  name: string
  passed: number
  failed: number
  skipped: number
  tests: E2ETestResult[]
}

export interface E2ESummary {
  passed: number
  failed: number
  skipped: number
  total: number
  duration_s: number
}

export interface E2ERunReport {
  success: boolean
  summary: E2ESummary
  test_classes: E2ETestClass[]
  run_id: string
  timestamp: string
  error: string | null
}

interface E2ERunRequest {
  test_classes?: string[]
}

/**
 * Run E2E scheduling tests via the backend subprocess runner.
 * Returns structured results grouped by test class.
 *
 * @param testClasses - Optional list of test class names to filter. Omit to run all.
 */
export async function runE2ETests(testClasses?: string[]): Promise<E2ERunReport> {
  const body: E2ERunRequest = {}
  if (testClasses && testClasses.length > 0) {
    body.test_classes = testClasses
  }
  return apiClient.post<E2ERunReport>('/api/v1/validate/e2e', body, {
    timeout: 360_000, // 6 minutes — tests take ~55s, plus margin
  })
}
