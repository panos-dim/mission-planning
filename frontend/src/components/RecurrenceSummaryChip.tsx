import { Repeat2 } from 'lucide-react'

interface RecurrenceSummaryChipProps {
  summary?: string | null
  className?: string
}

export default function RecurrenceSummaryChip({
  summary,
  className = '',
}: RecurrenceSummaryChipProps): JSX.Element | null {
  if (!summary) {
    return null
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-blue-500/30 bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-200 ${className}`.trim()}
      title={summary}
    >
      <Repeat2 className="h-3 w-3" />
      <span className="truncate">{summary}</span>
    </span>
  )
}
