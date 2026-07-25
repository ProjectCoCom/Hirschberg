/**
 * Custom React hook 'Useconsolekeyboardshortcuts'.
 *
 * Responsibilities:
 * Abstracts state management, data polling, or backend API actions for 'Useconsolekeyboardshortcuts' into a reusable hook.
 *
 * Coupling:
 * Consumed by React UI components inside the 'dashboard/src/components' component tree.
 */


import { useEffect } from "react";

import type { PrimaryNavIndex } from "../constants";
import { isEditableEventTarget, parsePrimaryNavKey } from "../hotkeys";

type UseConsoleKeyboardShortcutsOptions = {
  setActivePrimaryNav: (index: PrimaryNavIndex) => void;
};

export const useConsoleKeyboardShortcuts = ({
  setActivePrimaryNav,
}: UseConsoleKeyboardShortcutsOptions) => {
  useEffect(() => {
    const handleWindowKeyDown = (event: globalThis.KeyboardEvent) => {
      if (isEditableEventTarget(event.target)) {
        return;
      }

      const nextPrimaryNav = parsePrimaryNavKey(event.key);
      if (nextPrimaryNav !== null) {
        setActivePrimaryNav(nextPrimaryNav);
        event.preventDefault();
      }
    };

    window.addEventListener("keydown", handleWindowKeyDown);
    return () => {
      window.removeEventListener("keydown", handleWindowKeyDown);
    };
  }, [setActivePrimaryNav]);
};
