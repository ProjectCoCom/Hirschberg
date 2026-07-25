/**
 * React UI component 'Julesaccountspanel'.
 *
 * Responsibilities:
 * Renders the 'Julesaccountspanel' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useCallback, useEffect, useState, type MutableRefObject } from "react";

type JulesAccount = {
  id: string;
  name: string;
  api_key_masked: string;
  plan_tier: string;
  role: "orchestrator" | "worker" | "qa";
  label: string;
  daily_limit: number;
  concurrent_limit: number;
  sessions_today: number;
  enabled: boolean;
};

export const JulesAccountsPanel = ({ onAddRef }: { onAddRef: MutableRefObject<() => void> }) => {
  const [accounts, setAccounts] = useState<JulesAccount[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formPlan, setFormPlan] = useState("free");
  const [formRole, setFormRole] = useState("worker");
  const [formLabel, setFormLabel] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmInput, setConfirmInput] = useState("");

  const fetchAccounts = useCallback(() => {
    fetch("/api/jules/accounts").then((r) => r.json()).then((d) => {
      setAccounts(d.accounts ?? []);
    }).catch(() => {});
  }, []);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  const getNextName = () => {
    const existing = accounts.map((a) => a.name);
    let n = 1;
    while (existing.includes(`JULES_API_${n}`)) n++;
    return `JULES_API_${n}`;
  };

  onAddRef.current = () => { setFormName(getNextName()); setShowForm(true); };

  const handleAdd = () => {
    if (!formName.trim() || !formKey.trim()) return;
    fetch("/api/jules/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: formName.trim(),
        api_key: formKey.trim(),
        plan_tier: formPlan,
        role: formRole,
        label: formLabel.trim()
      }),
    }).then(() => {
      setShowForm(false);
      setFormName("");
      setFormKey("");
      setFormPlan("free");
      setFormRole("worker");
      setFormLabel("");
      setSuccessMsg(`Jules account "${formName}" added`);
      setTimeout(() => setSuccessMsg(""), 4000);
      fetchAccounts();
    }).catch(() => {});
  };

  const handleToggle = (id: string, enabled: boolean) => {
    fetch(`/api/jules/accounts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !enabled }),
    }).then(() => fetchAccounts()).catch(() => {});
  };

  const handleDelete = (id: string) => {
    fetch(`/api/jules/accounts/${id}`, { method: "DELETE" })
      .then(() => { setConfirmDeleteId(null); setConfirmInput(""); fetchAccounts(); })
      .catch(() => {});
  };

  return (
    <>
      {successMsg && <div className="apis-success">{successMsg}</div>}
      <div className="apis-list">
        {accounts.length === 0 && <p className="apis-empty">No Jules accounts configured.</p>}
        {accounts.map((a) => (
          <div key={a.id} className="apis-card" data-enabled={a.enabled}>
            <div className="apis-card-header">
              <span className="apis-card-type">{a.plan_tier.toUpperCase()}</span>
              <span className="apis-card-name">{a.name}</span>
              <span className={`apis-card-status ${a.enabled ? "apis-card-status--on" : "apis-card-status--off"}`}>
                {a.enabled ? "active" : "disabled"}
              </span>
            </div>
            <div className="apis-card-details">
              <span>Role: <strong>{a.role}</strong></span>
              {a.label && <span>Label: <strong>{a.label}</strong></span>}
              <span>Daily: {a.sessions_today}/{a.daily_limit}</span>
              <span>Concurrent: {a.concurrent_limit}</span>
            </div>
            <div className="apis-card-actions">
              <button type="button" onClick={() => handleToggle(a.id, a.enabled)}>
                {a.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" className="apis-card-delete" onClick={() => setConfirmDeleteId(a.id)}>Remove</button>
            </div>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowForm(false); }}>
          <div className="apis-popup">
            <header className="apis-popup-header"><h3>Add Jules Account</h3></header>
            <div className="apis-popup-body">
              <div className="apis-field">
                <label>Account Name</label>
                <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} />
              </div>
              <div className="apis-field">
                <label>API Key</label>
                <input type="password" value={formKey} onChange={(e) => setFormKey(e.target.value)} placeholder="AQ..." />
              </div>
              <div className="apis-field">
                <label>Plan Tier</label>
                <select value={formPlan} onChange={(e) => setFormPlan(e.target.value)}>
                  <option value="free">Free (15/day, 3 concurrent)</option>
                  <option value="pro">Pro (100/day, 15 concurrent)</option>
                  <option value="ultra">Ultra (300/day, 60 concurrent)</option>
                </select>
              </div>
              <div className="apis-field">
                <label>Account Role</label>
                <select value={formRole} onChange={(e) => setFormRole(e.target.value)}>
                  <option value="orchestrator">Orchestrator</option>
                  <option value="worker">Worker</option>
                  <option value="qa">QA</option>
                </select>
              </div>
              <div className="apis-field">
                <label>Label</label>
                <input type="text" value={formLabel} onChange={(e) => setFormLabel(e.target.value)} placeholder="e.g. primary-worker" />
              </div>
            </div>
            <footer className="apis-popup-footer">
              <button type="button" onClick={() => setShowForm(false)}>Cancel</button>
              <button type="button" className="apis-submit-btn" disabled={!formName.trim() || !formKey.trim()} onClick={handleAdd}>Save</button>
            </footer>
          </div>
        </div>
      )}

      {confirmDeleteId && (
        <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setConfirmDeleteId(null); setConfirmInput(""); } }}>
          <div className="apis-popup apis-popup--narrow">
            <header className="apis-popup-header"><h3>Remove Account</h3></header>
            <div className="apis-popup-body">
              <p className="apis-confirm-text">Type "confirm" to remove this account permanently.</p>
              <input className="apis-confirm-input" type="text" value={confirmInput} onChange={(e) => setConfirmInput(e.target.value)} placeholder="confirm" />
            </div>
            <footer className="apis-popup-footer">
              <button type="button" className="apis-popup-cancel" onClick={() => { setConfirmDeleteId(null); setConfirmInput(""); }}>Cancel</button>
              <button type="button" className="apis-submit-btn apis-submit-btn--danger" disabled={confirmInput !== "confirm"} onClick={() => handleDelete(confirmDeleteId)}>Remove</button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
};
