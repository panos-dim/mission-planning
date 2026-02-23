/**
 * Format a numeric value to exactly 1 decimal place.
 * Returns "–" for null/undefined/NaN.
 * Used for off-nadir angles (PR-UI-028).
 */
export function fmt1(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '–'
  return parseFloat(n.toFixed(1)).toString()
}

/**
 * Format a numeric value to exactly 2 decimal places.
 * Returns "–" for null/undefined/NaN.
 * Integer counts and IDs should NOT use this helper.
 */
export function fmt2(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '–'
  return parseFloat(n.toFixed(2)).toString()
}
