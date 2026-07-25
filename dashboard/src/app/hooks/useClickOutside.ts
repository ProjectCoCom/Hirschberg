/**
 * Custom React hook 'Useclickoutside'.
 *
 * Responsibilities:
 * Abstracts state management, data polling, or backend API actions for 'Useclickoutside' into a reusable hook.
 *
 * Coupling:
 * Consumed by React UI components inside the 'dashboard/src/components' component tree.
 */


import { type RefObject, useEffect } from "react";

export const useClickOutside = (
  ref: RefObject<HTMLElement | null>,
  isActive: boolean,
  onDismiss: () => void,
) => {
  useEffect(() => {
    if (!isActive) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onDismiss();
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismiss();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [ref, isActive, onDismiss]);
};
