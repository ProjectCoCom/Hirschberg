/**
 * React UI component 'Julesprimaryview'.
 *
 * Responsibilities:
 * Renders the 'Julesprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useCallback, useEffect, useState } from "react";

type JulesAccount = {
  id: string;
  name: string;
  api_key_masked: string;
  plan_tier: string;
  daily_limit: number;
  concurrent_limit: number;
  sessions_today: number;
  enabled: boolean;
};

export const JulesPrimaryView = () => {
  const [accounts, setAccounts] = useState<JulesAccount[]>([]);
  const [showAddPopup, setShowAddPopup] = useState(false);
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formPlan, setFormPlan] = useState("free");
  const [successMsg, setSuccessMsg] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
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

  const handleAdd = useCallback(() => {
    if (!formName.trim() || !formKey.trim()) return;
    fetch("/api/jules/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: formName.trim(), api_key: formKey.trim(), plan_tier: formPlan }),
    }).then(() => {
      setShowAddPopup(false);
      setFormName("");
      setFormKey("");
      setFormPlan("free");
      setSuccessMsg(`Jules account "${formName}" added`);
      setTimeout(() => setSuccessMsg(""), 4000);
      fetchAccounts();
    }).catch(() => {});
  }, [formName, formKey, formPlan, fetchAccounts]);

  const handleToggle = useCallback((id: string, enabled: boolean) => {
    fetch(`/api/jules/accounts/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !enabled }),
    }).then(() => fetchAccounts()).catch(() => {});
  }, [fetchAccounts]);

  const handleDelete = useCallback((id: string) => {
    fetch(`/api/jules/accounts/${id}`, { method: "DELETE" })
      .then(() => { setConfirmDelete(null); setConfirmInput(""); fetchAccounts(); })
      .catch(() => {});
  }, [fetchAccounts]);

  return (
    <section className="jules-view" aria-label="Jules accounts view">
      <div className="jules-content">
        <header className="jules-header">
          <h2 className="jules-title">Jules Accounts</h2>
          <button type="button" className="jules-add-btn" onClick={() => { setFormName(getNextName()); setShowAddPopup(true); }}>+ Add Account</button>
        </header>
        {successMsg && <div className="jules-success">{successMsg}</div>}
        <div className="jules-list">
          {accounts.length === 0 && <p className="jules-empty">No Jules accounts configured. Add one to start orchestrating.</p>}
          {accounts.map((a) => (
            <div key={a.id} className={`jules-card${a.enabled ? "" : " jules-card--disabled"}`}>
              <div className="jules-card-header">
                <span className="jules-card-name">{a.name}</span>
                <span className={`jules-card-plan jules-card-plan--${a.plan_tier}`}>{a.plan_tier.toUpperCase()}</span>
              </div>
              <div className="jules-card-body">
                <div className="jules-card-row"><span className="jules-card-label">Key:</span><span className="jules-card-value">{a.api_key_masked}</span></div>
                <div className="jules-card-row"><span className="jules-card-label">Daily:</span><span className="jules-card-value">{a.sessions_today}/{a.daily_limit}</span></div>
                <div className="jules-card-row"><span className="jules-card-label">Concurrent:</span><span className="jules-card-value">{a.concurrent_limit}</span></div>
              </div>
              <div className="jules-card-actions">
                <button type="button" className={`jules-toggle-btn${a.enabled ? " jules-toggle-btn--on" : ""}`} onClick={() => handleToggle(a.id, a.enabled)}>
                  {a.enabled ? "Enabled" : "Disabled"}
                </button>
                <button type="button" className="jules-delete-btn" onClick={() => setConfirmDelete(a.id)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showAddPopup && (
        <div className="jules-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowAddPopup(false); }}>
          <div className="jules-popup">
            <h3 className="jules-popup-title">Add Jules Account</h3>
            <div className="jules-popup-field">
              <label>Account Name</label>
              <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="e.g. Main Ultra" />
            </div>
            <div className="jules-popup-field">
              <label>API Key</label>
              <input type="password" value={formKey} onChange={(e) => setFormKey(e.target.value)} placeholder="AQ..." />
            </div>
            <div className="jules-popup-field">
              <label>Plan Tier</label>
              <select value={formPlan} onChange={(e) => setFormPlan(e.target.value)}>
                <option value="free">Free (15/day, 3 concurrent)</option>
                <option value="pro">Pro (100/day, 15 concurrent)</option>
                <option value="ultra">Ultra (300/day, 60 concurrent)</option>
              </select>
            </div>
            <div className="jules-popup-footer">
              <button type="button" onClick={() => setShowAddPopup(false)}>Cancel</button>
              <button type="button" className="jules-popup-save" onClick={handleAdd} disabled={!formName.trim() || !formKey.trim()}>Save</button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div className="jules-popup-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setConfirmDelete(null); setConfirmInput(""); } }}>
          <div className="jules-popup jules-popup--narrow">
            <h3 className="jules-popup-title">Remove Account</h3>
            <p className="jules-confirm-text">Type "confirm" to remove this account permanently.</p>
            <input className="jules-confirm-input" type="text" value={confirmInput} onChange={(e) => setConfirmInput(e.target.value)} placeholder="confirm" />
            <div className="jules-popup-footer">
              <button type="button" onClick={() => { setConfirmDelete(null); setConfirmInput(""); }}>Cancel</button>
              <button type="button" className="jules-popup-save jules-popup-save--danger" disabled={confirmInput !== "confirm"} onClick={() => handleDelete(confirmDelete)}>Remove</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
