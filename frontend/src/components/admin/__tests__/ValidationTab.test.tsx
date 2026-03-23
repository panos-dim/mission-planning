import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ValidationTab from '../ValidationTab'

const { listE2ETestCatalogMock, runE2ETestsMock } = vi.hoisted(() => ({
  listE2ETestCatalogMock: vi.fn(),
  runE2ETestsMock: vi.fn(),
}))

vi.mock('../../../api/e2eValidation', () => ({
  listE2ETestCatalog: listE2ETestCatalogMock,
  runE2ETests: runE2ETestsMock,
}))

describe('ValidationTab', () => {
  beforeEach(() => {
    listE2ETestCatalogMock.mockReset()
    runE2ETestsMock.mockReset()
    listE2ETestCatalogMock.mockResolvedValue({
      suites: [],
      input_profiles: [],
    })
  })

  it('renders the active E2E validation review surface only', async () => {
    render(<ValidationTab />)

    expect(await screen.findByText('E2E Validation Review')).toBeInTheDocument()
    expect(screen.queryByText('Workflow Validation')).not.toBeInTheDocument()
    expect(listE2ETestCatalogMock).toHaveBeenCalledTimes(1)
  })
})
