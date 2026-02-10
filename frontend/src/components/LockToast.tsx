/**
 * LockToast — PR-LOCK-OPS-01
 *
 * Lightweight toast notifications for lock operations.
 * Auto-dismisses after 3 seconds. Renders as fixed overlay.
 */

import React, { useEffect } from "react";
import { CheckCircle, XCircle, Info, X } from "lucide-react";
import { useLockStore, type LockToastMessage } from "../store/lockStore";

// =============================================================================
// Single Toast Item
// =============================================================================

const TOAST_DURATION_MS = 3000;

const TOAST_STYLES: Record<
  LockToastMessage["type"],
  { icon: React.ElementType; bg: string; border: string; text: string }
> = {
  success: {
    icon: CheckCircle,
    bg: "bg-green-900/90",
    border: "border-green-700/50",
    text: "text-green-300",
  },
  error: {
    icon: XCircle,
    bg: "bg-red-900/90",
    border: "border-red-700/50",
    text: "text-red-300",
  },
  info: {
    icon: Info,
    bg: "bg-blue-900/90",
    border: "border-blue-700/50",
    text: "text-blue-300",
  },
};

interface ToastItemProps {
  toast: LockToastMessage;
  onDismiss: (id: string) => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ toast, onDismiss }) => {
  const style = TOAST_STYLES[toast.type];
  const Icon = style.icon;

  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), TOAST_DURATION_MS);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg border shadow-lg
        backdrop-blur-sm animate-in slide-in-from-right
        ${style.bg} ${style.border}
      `}
    >
      <Icon size={14} className={style.text} />
      <span className={`text-xs font-medium ${style.text}`}>
        {toast.message}
      </span>
      <button
        onClick={() => onDismiss(toast.id)}
        className="ml-1 p-0.5 rounded hover:bg-white/10 transition-colors"
      >
        <X size={10} className="text-gray-400" />
      </button>
    </div>
  );
};

// =============================================================================
// Toast Container — renders all active toasts
// =============================================================================

export const LockToastContainer: React.FC = () => {
  const toasts = useLockStore((s) => s.toasts);
  const dismissToast = useLockStore((s) => s.dismissToast);

  if (toasts.length === 0) return null;

  // Only show latest 3 toasts
  const visible = toasts.slice(-3);

  return (
    <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-auto">
      {visible.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={dismissToast} />
      ))}
    </div>
  );
};

export default LockToastContainer;
