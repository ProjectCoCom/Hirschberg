/**
 * React UI component 'Apisprimaryview'.
 *
 * Responsibilities:
 * Renders the 'Apisprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useRef, useState } from "react";
import { AiProvidersPanel } from "./apis/AiProvidersPanel";
import { JulesAccountsPanel } from "./apis/JulesAccountsPanel";

export const ApisPrimaryView = () => {
  const [mode, setMode] = useState<"providers" | "jules">("providers");
  const addRef = useRef<() => void>(() => {});

  return (
    <section className="apis-view" aria-label="APIs primary view">
      <div className="apis-content">
        <header className="apis-header">
          <h2 className="apis-title">API Keys</h2>
          <div className="apis-mode-toggle">
            <button
              type="button"
              className={`apis-mode-btn${mode === "providers" ? " apis-mode-btn--active" : ""}`}
              onClick={() => setMode("providers")}
            >
              AI Providers
            </button>
            <button
              type="button"
              className={`apis-mode-btn${mode === "jules" ? " apis-mode-btn--active" : ""}`}
              onClick={() => setMode("jules")}
            >
              Jules Accounts
            </button>
          </div>
          <button type="button" className="apis-add-btn" onClick={() => addRef.current()}>
            {mode === "providers" ? "+ Add Provider" : "+ Add Jules Account"}
          </button>
        </header>
        {mode === "providers" ? <AiProvidersPanel onAddRef={addRef} /> : <JulesAccountsPanel onAddRef={addRef} />}
      </div>
    </section>
  );
};
