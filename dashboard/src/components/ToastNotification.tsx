/**
 * React UI component 'Toastnotification'.
 *
 * Responsibilities:
 * Renders the 'Toastnotification' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useEffect } from "react";

export type Toast = {
  id: string;
  message: string;
  type: "success" | "error" | "info";
};

type Props = {
  toasts: Toast[];
  onDismiss: (id: string) => void;
};

const TYPE_COLORS = {
  success: "#25d366",
  error: "#ef4444",
  info: "#00e5ff",
};

export const ToastNotification = ({ toasts, onDismiss }: Props) => {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

const ToastItem = ({ toast, onDismiss }: { toast: Toast; onDismiss: (id: string) => void }) => {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 5000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div className="toast-item" style={{ borderLeftColor: TYPE_COLORS[toast.type] }}>
      <span className="toast-message">{toast.message}</span>
      <button type="button" className="toast-close" onClick={() => onDismiss(toast.id)}>x</button>
    </div>
  );
};
