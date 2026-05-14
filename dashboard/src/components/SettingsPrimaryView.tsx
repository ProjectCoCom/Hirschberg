import { useCallback, useEffect, useState } from "react";

type SettingsPrimaryViewProps = {
  isRuntimeStatusStripVisible: boolean;
  isMonitorVisible: boolean;
  onRuntimeStatusStripVisibilityChange: (visible: boolean) => void;
  onMonitorVisibilityChange: (visible: boolean) => void;
};

type AppSettings = {
  github_token: string;
  github_fg_token: string;
  supabase_url: string;
  supabase_key: string;
  encryption_key_status: string;
  database_mode: "local" | "supabase" | "hybrid";
};

type CreateKeyGuide = {
  keyLabel: string;
  url: string;
  steps: string[];
  note?: string;
};

const KEY_CREATION_GUIDES: Record<string, CreateKeyGuide> = {
  github_fg_token: {
    keyLabel: "GitHub Fine-Grained Token",
    url: "https://github.com/settings/personal-access-tokens/new",
    steps: [
      'In "Token name", enter: JAT-AI',
      'Expiration: select "No expiration" or "90 days"',
      'Repository access: choose "All repositories" or select specific repos',
      'Under "Repository permissions", set these to "Read and Write":',
      '  \u2022 Contents \u2014 for reading/writing code',
      '  \u2022 Pull Requests \u2014 for creating/merging PRs',
      '  \u2022 Issues \u2014 for managing issues',
      '  \u2022 Workflows \u2014 for updating GitHub Actions',
      '  \u2022 Metadata \u2014 Read-only (auto-granted)',
      'Click "Generate token", then copy the value and paste it here',
    ],
  },
  github_token: {
    keyLabel: "GitHub Classic Token",
    url: "https://github.com/settings/tokens/new",
    steps: [
      'In "Note" field, enter: JAT-AI',
      'Expiration: select "No expiration" or a duration you prefer',
      'Under "Select scopes", check these:',
      '  \u2022 repo (Full control of private repositories)',
      '  \u2022 workflow (Update GitHub Action files)',
      '  \u2022 read:org (Read organization membership)',
      '  \u2022 read:user (Read user profile data)',
      'Scroll down and click "Generate token"',
      'Copy the generated token and paste it here',
    ],
    note: "Classic tokens support org SSO. If your org enforces SSO, you'll need to enable it after creation.",
  },
  supabase_url: {
    keyLabel: "Supabase Project URL",
    url: "https://supabase.com/dashboard/project/_/settings/api",
    steps: [
      'Go to your Supabase project dashboard',
      'Navigate to Settings > API in the left sidebar',
      'Under "Project URL", copy the URL shown at the top of the page',
      'Paste that value into the Supabase URL field in JAT-AI',
    ],
  },
  supabase_key: {
    keyLabel: "Supabase Service Role Key",
    url: "https://supabase.com/dashboard/project/_/settings/api",
    steps: [
      'Go to your Supabase project dashboard',
      'Navigate to Settings > API in the left sidebar',
      'Under "Project API keys", find the "service_role" key',
      'Copy the service_role key value',
      'Paste that value into the Supabase Key field in JAT-AI',
    ],
    note: "Use the service_role key here, not the anon/public key. The service_role key has full admin access and must stay server-side.",
  },
};

export const SettingsPrimaryView = (_props: SettingsPrimaryViewProps) => {
  const [settings, setSettings] = useState<AppSettings>({
    github_token: "", github_fg_token: "",
    supabase_url: "", supabase_key: "",
    encryption_key_status: "", database_mode: "local",
  });
  const [original, setOriginal] = useState<AppSettings | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [showRegenPopup, setShowRegenPopup] = useState(false);
  const [regenInput, setRegenInput] = useState("");
  const [regenerating, setRegenerating] = useState(false);
  const [showDbConfirm, setShowDbConfirm] = useState(false);
  const [pendingDbMode, setPendingDbMode] = useState<"local" | "supabase" | "hybrid" | null>(null);
  const [dbConfirmInput, setDbConfirmInput] = useState("");
  const [keyStatus, setKeyStatus] = useState<Record<string, { status: string; error?: string; user?: string }>>({});
  const [errorPopup, setErrorPopup] = useState<string | null>(null);
  const [createKeyPopup, setCreateKeyPopup] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/settings")
      .then((r) => r.json())
      .then((d) => { setSettings(d); setOriginal(d); setLoaded(true); })
      .catch(() => setLoaded(true));
    fetch("/api/settings/status")
      .then((r) => r.json())
      .then((d) => setKeyStatus(d))
      .catch(() => {});
  }, []);

  const hasChanges = original && JSON.stringify(settings) !== JSON.stringify(original);

  const handleSave = useCallback(() => {
    setSaving(true);
    fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    })
      .then(() => { setTimeout(() => window.location.reload(), 1000); })
      .catch(() => setSaving(false));
  }, [settings]);

  const handleCancel = () => {
    if (original) setSettings(original);
    setEditing(false);
  };

  const handleRegenerate = useCallback(() => {
    setRegenerating(true);
    fetch("/api/settings/regenerate-key", { method: "POST" })
      .then(() => {
        setShowRegenPopup(false);
        setRegenInput("");
        setSettings((s) => ({ ...s, encryption_key_status: "configured" }));
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      })
      .catch(() => {})
      .finally(() => setRegenerating(false));
  }, []);

  const updateField = (field: keyof AppSettings, value: string) => {
    setSettings((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <section className="settings-view" aria-label="Settings primary view">
      <section className="settings-panel">
        <header className="settings-panel-header">
          <h2>Database Mode</h2>
          <p>Choose where data is stored.</p>
        </header>
        <div className="settings-db-modes">
          {(["local", "supabase", "hybrid"] as const).map((m) => (
            <button key={m} type="button" className={`settings-db-btn${settings.database_mode === m ? " settings-db-btn--active" : ""}`} onClick={() => {
              if (m !== settings.database_mode) { setPendingDbMode(m); setShowDbConfirm(true); }
            }}>
              {m.toUpperCase()}
            </button>
          ))}
        </div>
        <p className="settings-db-desc">
          {settings.database_mode === "local" && "All data stored in local SQLite (./data/jat.db). No network needed."}
          {settings.database_mode === "supabase" && "All data stored in Supabase. Requires URL and key below."}
          {settings.database_mode === "hybrid" && "Reads from local SQLite, writes to both. Background sync to Supabase."}
        </p>
      </section>

      <section className="settings-panel">
        <header className="settings-panel-header">
          <h2>Connection Keys</h2>
          <p>API keys for external services.</p>
          {!editing && <button type="button" className="settings-edit-btn" onClick={() => setEditing(true)}>Edit</button>}
        </header>
        <div className="settings-fields">
          <SettingsFieldWithStatus label="GitHub Classic Token (ghp_...)" value={settings.github_token} onChange={(v) => updateField("github_token", v)} placeholder="ghp_xxxxxxxxxxxx" type="password" disabled={!editing} loaded={loaded} status={keyStatus.github_token} onErrorClick={(err) => setErrorPopup(err)} onCreateNew={() => setCreateKeyPopup("github_token")} />
          <SettingsFieldWithStatus label="GitHub Fine-Grained Token (github_pat_...)" value={settings.github_fg_token} onChange={(v) => updateField("github_fg_token", v)} placeholder="github_pat_xxxxxxxxxxxx" type="password" disabled={!editing} loaded={loaded} status={keyStatus.github_fg_token} onErrorClick={(err) => setErrorPopup(err)} onCreateNew={() => setCreateKeyPopup("github_fg_token")} />
          <SettingsFieldWithStatus label="Supabase URL" value={settings.supabase_url} onChange={(v) => updateField("supabase_url", v)} placeholder="https://xxxxx.supabase.co" disabled={!editing} loaded={loaded} status={keyStatus.supabase_url} onErrorClick={(err) => setErrorPopup(err)} onCreateNew={() => setCreateKeyPopup("supabase_url")} />
          <SettingsFieldWithStatus label="Supabase Key (service_role)" value={settings.supabase_key} onChange={(v) => updateField("supabase_key", v)} placeholder="eyJhbGciOi..." type="password" disabled={!editing} loaded={loaded} status={keyStatus.supabase_key} onErrorClick={(err) => setErrorPopup(err)} onCreateNew={() => setCreateKeyPopup("supabase_key")} />
        </div>
      </section>

      {editing && (
        <div className="settings-save-row">
          <button type="button" className="settings-cancel-btn" onClick={handleCancel}>Cancel</button>
          <button type="button" className="settings-save-btn" onClick={handleSave} disabled={saving || !hasChanges}>
            {saving ? "Saving..." : "Save Settings"}
          </button>
          {saved && <span className="settings-saved-pill">Saved</span>}
        </div>
      )}
      {!editing && saved && <span className="settings-saved-pill">Saved</span>}

      <section className="settings-panel">
        <header className="settings-panel-header">
          <h2>Encryption</h2>
          <p>Used to encrypt all stored API keys. Auto-generated on first run.</p>
        </header>
        <div className="settings-encryption-row">
          <span className="settings-encryption-status">
            Status: {settings.encryption_key_status === "configured" ? "Active" : "Not configured (will auto-generate on save)"}
          </span>
          <button type="button" className="settings-regen-btn" onClick={() => setShowRegenPopup(true)}>
            Regenerate Key
          </button>
        </div>
      </section>

      {showRegenPopup && (
        <div className="settings-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setShowRegenPopup(false); setRegenInput(""); } }}>
          <div className="settings-popup">
            <h3 className="settings-popup-title">Regenerate Encryption Key</h3>
            <p className="settings-popup-warning">
              This will generate a new encryption key. All existing encrypted API keys
              (providers, Jules accounts) will become unreadable. You will need to
              re-add all API keys after regeneration.
            </p>
            <p className="settings-popup-confirm-text">Type "yes regenerate key" to confirm:</p>
            <input className="settings-popup-input" type="text" value={regenInput} onChange={(e) => setRegenInput(e.target.value)} placeholder="yes regenerate key" />
            <div className="settings-popup-footer">
              <button type="button" onClick={() => { setShowRegenPopup(false); setRegenInput(""); }}>Cancel</button>
              <button type="button" className="settings-popup-danger" disabled={regenInput !== "yes regenerate key" || regenerating} onClick={handleRegenerate}>
                {regenerating ? "Regenerating..." : "Confirm Regenerate"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showDbConfirm && pendingDbMode && (
        <div className="settings-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setShowDbConfirm(false); setDbConfirmInput(""); setPendingDbMode(null); } }}>
          <div className="settings-popup">
            <h3 className="settings-popup-title">Switch Database Mode</h3>
            <p className="settings-popup-warning">
              Switching to "{pendingDbMode}" mode will update the database configuration
              and require an app restart. Existing data in the current mode will remain
              but won't be accessible until you switch back.
            </p>
            <p className="settings-popup-confirm-text">Type "confirm" to proceed:</p>
            <input className="settings-popup-input" type="text" value={dbConfirmInput} onChange={(e) => setDbConfirmInput(e.target.value)} placeholder="confirm" />
            <div className="settings-popup-footer">
              <button type="button" onClick={() => { setShowDbConfirm(false); setDbConfirmInput(""); setPendingDbMode(null); }}>Cancel</button>
              <button type="button" className="settings-popup-danger" disabled={dbConfirmInput !== "confirm"} onClick={() => {
                setSettings((s) => ({ ...s, database_mode: pendingDbMode }));
                setShowDbConfirm(false); setDbConfirmInput(""); setPendingDbMode(null); setEditing(true);
              }}>Confirm Switch</button>
            </div>
          </div>
        </div>
      )}

      {errorPopup && (
        <div className="settings-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setErrorPopup(null); }}>
          <div className="settings-popup">
            <h3 className="settings-popup-title">Connection Error</h3>
            <p className="settings-popup-warning">{errorPopup}</p>
            <div className="settings-popup-footer">
              <button type="button" onClick={() => setErrorPopup(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {createKeyPopup && KEY_CREATION_GUIDES[createKeyPopup] && (() => {
        const guide = KEY_CREATION_GUIDES[createKeyPopup]!;
        return (
          <div className="settings-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setCreateKeyPopup(null); }}>
            <div className="settings-popup settings-popup--help">
              <h3 className="settings-popup-title settings-popup-title--help">Create {guide.keyLabel}</h3>
              <p className="settings-help-desc">
                Open the link below, create your token, then paste it back here.
              </p>
              <a
                href={guide.url}
                target="_blank"
                rel="noopener noreferrer"
                className="settings-help-url"
              >
                Open {guide.keyLabel} Page &rarr;
              </a>
              <div className="settings-help-steps">
                <span className="settings-help-steps-label">Step-by-step:</span>
                <ol className="settings-help-list">
                  {guide.steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </div>
              {guide.note && (
                <p className="settings-help-note">{guide.note}</p>
              )}
              <div className="settings-popup-footer">
                <button type="button" onClick={() => setCreateKeyPopup(null)}>Close</button>
              </div>
            </div>
          </div>
        );
      })()}

      <ResetSection />
    </section>
  );
};

const RESET_TARGETS = [
  { id: "ai_providers", label: "AI Provider Keys", desc: "All stored API keys for AI providers" },
  { id: "jules_accounts", label: "Jules Accounts", desc: "All Jules API keys and account data" },
  { id: "github_tokens", label: "GitHub Tokens", desc: "Classic and fine-grained GitHub tokens from .env" },
  { id: "env_keys", label: "All .env Keys", desc: "Wipes all .env values except ENCRYPTION_KEY" },
  { id: "conversations", label: "Chat Conversations", desc: "All chat history and messages" },
  { id: "custom_prompts", label: "Custom Prompts", desc: "User-created prompts (keeps built-in skills)" },
  { id: "system_prompt_overrides", label: "System Prompt Edits", desc: "Restores all system prompts to defaults" },
  { id: "agent_tasks", label: "Agent Tasks & Activities", desc: "All task history and session activities" },
  { id: "workflows", label: "Workflows", desc: "All saved workflow definitions" },
  { id: "context_messages", label: "Context Messages", desc: "Cross-session context data" },
  { id: "merge_queue", label: "Merge Queue", desc: "Pending merge operations" },
];

const ResetSection = () => {
  const [showPopup, setShowPopup] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmInput, setConfirmInput] = useState("");
  const [resetting, setResetting] = useState(false);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const handleReset = () => {
    setResetting(true);
    fetch("/api/settings/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ targets: [...selected] }),
    })
      .then(() => { window.location.reload(); })
      .catch(() => setResetting(false));
  };

  const closePopup = () => {
    setShowPopup(false);
    setSelected(new Set());
    setConfirmInput("");
  };

  return (
    <>
      <section className="settings-panel">
        <header className="settings-panel-header">
          <h2>Reset</h2>
          <p>Clear stored data. System prompts and built-in skills are preserved.</p>
        </header>
        <div>
          <button type="button" className="settings-reset-btn" onClick={() => setShowPopup(true)}>
            Reset Data...
          </button>
        </div>
      </section>

      {showPopup && (
        <div className="settings-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) closePopup(); }}>
          <div className="settings-popup settings-popup--wide">
            <h3 className="settings-popup-title">Reset Data</h3>
            <p className="settings-popup-warning">
              Select what you want to clear. Built-in skills and system prompts are never deleted.
            </p>
            <label className="settings-reset-select-all">
              <input type="checkbox" checked={selected.size === RESET_TARGETS.length} onChange={() => {
                if (selected.size === RESET_TARGETS.length) setSelected(new Set());
                else setSelected(new Set(RESET_TARGETS.map((t) => t.id)));
              }} />
              <span>Select All</span>
            </label>
            <div className="settings-reset-list">
              {RESET_TARGETS.map((t) => (
                <label key={t.id} className="settings-reset-item">
                  <input type="checkbox" checked={selected.has(t.id)} onChange={() => toggle(t.id)} />
                  <div>
                    <span className="settings-reset-item-label">{t.label}</span>
                    <span className="settings-reset-item-desc">{t.desc}</span>
                  </div>
                </label>
              ))}
            </div>
            {selected.size > 0 && (
              <>
                <p className="settings-popup-confirm-text">
                  Type "yes reset these" to confirm clearing {selected.size} item{selected.size > 1 ? "s" : ""}:
                </p>
                <input className="settings-popup-input" type="text" value={confirmInput} onChange={(e) => setConfirmInput(e.target.value)} placeholder="yes reset these" />
              </>
            )}
            <div className="settings-popup-footer">
              <button type="button" onClick={closePopup}>Cancel</button>
              <button type="button" className="settings-popup-danger" disabled={selected.size === 0 || confirmInput !== "yes reset these" || resetting} onClick={handleReset}>
                {resetting ? "Resetting..." : "Confirm Reset"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const SettingsField = ({ label, value, onChange, placeholder, type = "text", disabled, loaded }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string; disabled: boolean; loaded: boolean;
}) => (
  <div className="settings-field">
    <label className="settings-field-label">{label}</label>
    <input
      className="settings-field-input"
      type={type}
      value={loaded ? value : ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      disabled={disabled || !loaded}
    />
  </div>
);

const SettingsFieldWithStatus = ({ label, value, onChange, placeholder, type = "text", disabled, loaded, status, onErrorClick, onCreateNew }: {
  label: string; value: string; onChange: (v: string) => void; placeholder: string; type?: string; disabled: boolean; loaded: boolean;
  status?: { status: string; error?: string; user?: string }; onErrorClick: (err: string) => void;
  onCreateNew?: () => void;
}) => (
  <div className="settings-field">
    <div className="settings-field-label-row">
      <label className="settings-field-label">{label}</label>
      {status?.status === "active" && <span className="settings-status-badge settings-status-badge--active">Active{status.user ? ` (${status.user})` : ""}</span>}
      {status?.status === "error" && <button type="button" className="settings-status-badge settings-status-badge--error" onClick={() => onErrorClick(status.error ?? "Unknown error")}>Error</button>}
      {status?.status === "not_configured" && <span className="settings-status-badge settings-status-badge--none">Not set</span>}
    </div>
    <div className="settings-input-row">
      <input
        className="settings-field-input"
        type={type}
        value={loaded ? value : ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled || !loaded}
      />
      {(status?.status === "missing" || status?.status === "not_configured" || (!value && loaded)) && onCreateNew ? (
        <button type="button" className="settings-create-btn" onClick={onCreateNew}>
          + Create New
        </button>
      ) : null}
    </div>
  </div>
);
