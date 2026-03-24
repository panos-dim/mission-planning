import type { AddedEntry, ChangeLog, DroppedEntry, RepairDiff } from '../api/scheduleApi'

function collectHiddenMovedPairIds(changeLog?: ChangeLog): {
  hiddenAddedIds: Set<string>
  hiddenDroppedIds: Set<string>
} {
  const hiddenAddedIds = new Set<string>()
  const hiddenDroppedIds = new Set<string>()

  if (!changeLog?.moved?.length) {
    return { hiddenAddedIds, hiddenDroppedIds }
  }

  const movedSourceIds = new Set(changeLog.moved.map((entry) => entry.acquisition_id))
  const droppedById = new Map(changeLog.dropped.map((entry) => [entry.acquisition_id, entry]))

  for (const movedId of movedSourceIds) {
    hiddenDroppedIds.add(movedId)

    const droppedEntry = droppedById.get(movedId)
    for (const addedId of droppedEntry?.replaced_by ?? []) {
      hiddenAddedIds.add(addedId)
    }
  }

  for (const entry of changeLog.added) {
    if ((entry.replaces ?? []).some((replacedId) => movedSourceIds.has(replacedId))) {
      hiddenAddedIds.add(entry.acquisition_id)
    }
  }

  return { hiddenAddedIds, hiddenDroppedIds }
}

function filterAddedEntries(entries: AddedEntry[], hiddenAddedIds: Set<string>): AddedEntry[] {
  if (hiddenAddedIds.size === 0) return entries
  return entries.filter((entry) => !hiddenAddedIds.has(entry.acquisition_id))
}

function filterDroppedEntries(
  entries: DroppedEntry[],
  hiddenDroppedIds: Set<string>,
): DroppedEntry[] {
  if (hiddenDroppedIds.size === 0) return entries
  return entries.filter((entry) => !hiddenDroppedIds.has(entry.acquisition_id))
}

export function normalizeRepairDiffForDisplay(repairDiff: RepairDiff): RepairDiff {
  const changeLog = repairDiff.change_log
  if (!changeLog?.moved?.length) {
    return repairDiff
  }

  const { hiddenAddedIds, hiddenDroppedIds } = collectHiddenMovedPairIds(changeLog)
  if (hiddenAddedIds.size === 0 && hiddenDroppedIds.size === 0) {
    return repairDiff
  }

  const visibleAddedEntries = filterAddedEntries(changeLog.added ?? [], hiddenAddedIds)
  const visibleDroppedEntries = filterDroppedEntries(changeLog.dropped ?? [], hiddenDroppedIds)
  const visibleAddedIds = new Set(visibleAddedEntries.map((entry) => entry.acquisition_id))
  const visibleDroppedIds = new Set(visibleDroppedEntries.map((entry) => entry.acquisition_id))

  return {
    ...repairDiff,
    added: repairDiff.added.filter((id) => visibleAddedIds.has(id)),
    dropped: repairDiff.dropped.filter((id) => visibleDroppedIds.has(id)),
    reason_summary: {
      ...repairDiff.reason_summary,
      dropped: (repairDiff.reason_summary?.dropped ?? []).filter((entry) =>
        visibleDroppedIds.has(entry.id),
      ),
    },
    change_log: {
      ...changeLog,
      added: visibleAddedEntries,
      dropped: visibleDroppedEntries,
    },
  }
}

export function getRepairDisplayCounts(repairDiff: RepairDiff): {
  kept: number
  added: number
  dropped: number
  moved: number
  totalChanges: number
} {
  const normalized = normalizeRepairDiffForDisplay(repairDiff)
  const added = normalized.change_log?.added?.length ?? normalized.added.length
  const dropped = normalized.change_log?.dropped?.length ?? normalized.dropped.length
  const moved = normalized.change_log?.moved?.length ?? normalized.moved.length
  const kept = normalized.kept.length

  return {
    kept,
    added,
    dropped,
    moved,
    totalChanges: added + dropped + moved,
  }
}
