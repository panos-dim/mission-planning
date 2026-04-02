import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import MissionParameters from '../MissionParameters'

vi.mock('../DateTimePicker', () => ({
  default: () => <div data-testid="datetime-picker" />,
}))

vi.mock('../TimeOfDayPicker', () => ({
  default: ({
    id,
    value,
    onChange,
  }: {
    id: string
    value?: string | null
    onChange: (value: string | null) => void
  }) => (
    <input
      id={id}
      value={value ?? ''}
      onChange={(event) => onChange(event.target.value || null)}
    />
  ),
}))

vi.mock('../../hooks/queries', () => ({
  useSarModes: () => ({ data: { modes: {} } }),
}))

const baseParameters = {
  startTime: '2026-04-02T10:29',
  endTime: '2026-04-03T10:29',
  missionType: 'imaging' as const,
  elevationMask: 45,
  pointingAngle: 45,
  imagingType: 'optical' as const,
}

describe('MissionParameters', () => {
  it('renders a compact UTC acquisition window without helper copy or timezone input', () => {
    render(
      <MissionParameters
        parameters={{
          ...baseParameters,
          acquisitionTimeWindow: {
            enabled: true,
            start_time: '15:00',
            end_time: '17:00',
            timezone: 'UTC',
            reference: 'off_nadir_time',
          },
        }}
        onChange={vi.fn()}
      />,
    )

    expect(screen.getByText('Acquisition Window (UTC)')).toBeInTheDocument()
    expect(screen.queryByText(/Only opportunities whose off-nadir time falls/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText('From')).toBeInTheDocument()
    expect(screen.getByLabelText('To')).toBeInTheDocument()
    expect(screen.queryByText('Timezone')).not.toBeInTheDocument()
  })

  it('keeps UTC semantics when enabling and editing the acquisition window', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()

    const { rerender, container } = render(
      <MissionParameters
        parameters={{
          ...baseParameters,
          acquisitionTimeWindow: {
            enabled: false,
            start_time: null,
            end_time: null,
            timezone: 'UTC',
            reference: 'off_nadir_time',
          },
        }}
        onChange={onChange}
      />,
    )

    const visualCheckbox = container.querySelector('input[type="checkbox"] + span')
    expect(visualCheckbox).not.toBeNull()

    await user.click(visualCheckbox as HTMLElement)

    expect(onChange).toHaveBeenCalledWith({
      acquisitionTimeWindow: {
        enabled: true,
        start_time: null,
        end_time: null,
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })

    onChange.mockClear()

    rerender(
      <MissionParameters
        parameters={{
          ...baseParameters,
          acquisitionTimeWindow: {
            enabled: true,
            start_time: null,
            end_time: null,
            timezone: 'UTC',
            reference: 'off_nadir_time',
          },
        }}
        onChange={onChange}
      />,
    )

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '15:00' } })

    expect(onChange).toHaveBeenCalledWith({
      acquisitionTimeWindow: {
        enabled: true,
        start_time: '15:00',
        end_time: null,
        timezone: 'UTC',
        reference: 'off_nadir_time',
      },
    })
  })
})
