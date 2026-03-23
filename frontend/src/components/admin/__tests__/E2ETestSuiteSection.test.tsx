import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import E2ETestSuiteSection from '../E2ETestSuiteSection'

const { listE2ETestCatalogMock, runE2ETestsMock } = vi.hoisted(() => ({
  listE2ETestCatalogMock: vi.fn(),
  runE2ETestsMock: vi.fn(),
}))

vi.mock('../../../api/e2eValidation', () => ({
  listE2ETestCatalog: listE2ETestCatalogMock,
  runE2ETests: runE2ETestsMock,
}))

const catalogResponse = {
  suites: [
    {
      name: 'ScenarioFlowSuite',
      description: 'Scenario mission flow coverage.',
      suite_type: 'scenario',
      suite_label: 'Complex scenario E2E',
      input_profile_ids: ['baseline_profile'],
      tests: [{ name: 'test_story', description: 'Covers the scenario flow.' }],
    },
    {
      name: 'ApiProtectionSuite',
      description: 'API protections and backend safety checks.',
      suite_type: 'api',
      suite_label: 'API and backend-specific validation',
      input_profile_ids: ['baseline_profile'],
      tests: [{ name: 'test_api_guard', description: 'Covers conflict protections.' }],
    },
  ],
  input_profiles: [
    {
      id: 'baseline_profile',
      title: 'Baseline profile',
      summary: 'Canonical reviewer baseline.',
      satellites: [
        {
          name: 'SAT-1',
          tle_line1: '1 00000U 00000A 26064.28789825  .00007988  00000+0  63127-3 0  9993',
          tle_line2: '2 00000  97.7436 181.4786 0000928 206.1630 153.9547 15.00931401 38499',
        },
      ],
      targets: [{ name: 'Athens', latitude: 37.9838, longitude: 23.7275 }],
      time_windows: [
        {
          label: 'Canonical review window',
          start_time: '2026-03-08T00:00:00Z',
          end_time: '2026-03-11T00:00:00Z',
        },
      ],
      notes: ['Used for repeatable admin review.'],
    },
  ],
}

const selectedReport = {
  success: true,
  summary: {
    passed: 1,
    failed: 0,
    skipped: 0,
    total: 1,
    duration_s: 1.2,
  },
  test_classes: [
    {
      name: 'ApiProtectionSuite',
      description: null,
      suite_type: 'api',
      suite_label: null,
      input_profile_ids: [],
      passed: 1,
      failed: 0,
      skipped: 0,
      tests: [
        {
          name: 'test_api_guard',
          outcome: 'passed',
          duration_s: 0.12,
          description: null,
          message: null,
        },
      ],
    },
  ],
  run_id: 'run_selected',
  timestamp: '2026-03-08T12:00:00Z',
  error: null,
}

describe('E2ETestSuiteSection', () => {
  beforeEach(() => {
    listE2ETestCatalogMock.mockReset()
    runE2ETestsMock.mockReset()
    listE2ETestCatalogMock.mockResolvedValue(catalogResponse)
  })

  it('renders catalog metadata and canonical review inputs', async () => {
    render(<E2ETestSuiteSection />)

    expect(await screen.findByText('ScenarioFlowSuite')).toBeInTheDocument()
    expect(screen.getByText('ApiProtectionSuite')).toBeInTheDocument()
    expect(screen.getAllByText('Baseline profile').length).toBeGreaterThan(0)
    expect(screen.getByText('Athens')).toBeInTheDocument()
    expect(screen.getByText('2 suites')).toBeInTheDocument()
  })

  it('runs selected suites and enriches the report with catalog descriptions', async () => {
    const user = userEvent.setup()
    runE2ETestsMock.mockResolvedValue(selectedReport)

    render(<E2ETestSuiteSection />)

    expect(await screen.findByText('ScenarioFlowSuite')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /run selected suites/i }))
    await user.click(screen.getByLabelText('Select ApiProtectionSuite'))
    await user.click(screen.getByRole('button', { name: /^run selected$/i }))

    await waitFor(() => expect(runE2ETestsMock).toHaveBeenCalledWith(['ApiProtectionSuite']))
    expect(screen.getAllByText('API protections and backend safety checks.').length).toBeGreaterThan(
      0,
    )
    expect(screen.getByText('Run ID: run_selected')).toBeInTheDocument()
  })

  it('shows a friendly message when the backend reports a validation run is already active', async () => {
    const user = userEvent.setup()
    runE2ETestsMock.mockRejectedValue({ status: 429 })

    render(<E2ETestSuiteSection />)

    expect(await screen.findByText('ScenarioFlowSuite')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /run all tests/i }))

    expect(
      await screen.findByText('A test run is already in progress. Please wait and try again.'),
    ).toBeInTheDocument()
  })
})
