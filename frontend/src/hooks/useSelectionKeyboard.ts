/**
 * useSelectionKeyboard Hook
 *
 * Handles keyboard shortcuts for selection management:
 * - Escape: Clear current selection
 */

import { useEffect } from "react";
import { useSelectionStore } from "../store/selectionStore";

export function useSelectionKeyboard(): void {
  const clearSelection = useSelectionStore((state) => state.clearSelection);
  const hasSelection = useSelectionStore(
    (state) => state.selectedType !== null
  );

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Escape key clears selection
      if (event.key === "Escape" && hasSelection) {
        // Don't clear if user is typing in an input
        const target = event.target as HTMLElement;
        if (
          target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable
        ) {
          return;
        }

        event.preventDefault();
        clearSelection();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection, hasSelection]);
}

export default useSelectionKeyboard;
