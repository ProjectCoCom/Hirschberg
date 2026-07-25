/**
 * React UI component 'Aiproviderspanel'.
 *
 * Responsibilities:
 * Renders the 'Aiproviderspanel' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useCallback, useEffect, useRef, useState, type React } from "react";

type Provider = {
  id: string;
  provider_type: string;
  name: string;
  enabled: boolean;
  daily_limit: number;
};

const PROVIDER_TYPES = [
  "groq", "google", "cloudflare", "openrouter", "ollama", "cerebras",
  "cohere", "mistral", "nvidia_nim", "github_models", "huggingface",
  "sambanova", "fireworks", "nebius", "hyperbolic", "scaleway", "longcat", "deepseek", "custom",
];

const ProviderTypeDropdown = ({ value, onChange, onSelected }: { value: string; onChange: (v: string) => void; onSelected?: () => void }) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = PROVIDER_TYPES.filter((t) => t.includes(search.toLowerCase()));

  const selectItem = (t: string) => {
    onChange(t);
    setOpen(false);
    setSearch("");
    onSelected?.();
  };

  return (
    <div className="apis-custom-dropdown" ref={ref}>
      <button type="button" className="apis-custom-dropdown-trigger" onClick={() => setOpen(!open)}>
        <span>{value.toUpperCase()}</span>
        <span className="apis-custom-dropdown-arrow">▾</span>
      </button>
      {open && (
        <div className="apis-custom-dropdown-panel">
          <input
            className="apis-custom-dropdown-search"
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filtered.length > 0) {
                selectItem(filtered[0]);
              }
            }}
            autoFocus
          />
          <div className="apis-custom-dropdown-list">
            {filtered.map((t) => (
              <button key={t} type="button" className={`apis-custom-dropdown-item${t === value ? " is-active" : ""}`} onClick={() => selectItem(t)}>
                {t.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

type TestPopupProps = {
  providerId: string;
  models: { id: string; name: string }[];
  modelsLoading: boolean;
  selectedModel: string;
  modelSearch: string;
  input: string;
  response: string;
  sending: boolean;
  onModelSearchChange: (v: string) => void;
  onModelSelect: (v: string) => void;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onClose: () => void;
  onOpen: () => void;
};

const TestProviderPopup = (props: TestPopupProps) => {
  useEffect(() => { props.onOpen(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = props.models.filter((m) => m.id.toLowerCase().includes(props.modelSearch.toLowerCase()));

  return (
    <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) props.onClose(); }}>
      <div className="apis-popup apis-popup--wide">
        <header className="apis-popup-header"><h3>Test Provider</h3></header>
        <div className="apis-popup-body">
          <div className="apis-field">
            <label>Model</label>
            <input className="apis-test-model-search" type="text" placeholder="Search models..." value={props.modelSearch} onChange={(e) => props.onModelSearchChange(e.target.value)} />
            <div className="apis-test-model-list">
              {props.modelsLoading && <span className="apis-test-model-loading">Loading models...</span>}
              {!props.modelsLoading && filtered.length === 0 && <span className="apis-test-model-loading">No models found</span>}
              {filtered.map((m) => (
                <button key={m.id} type="button" className={`apis-test-model-item${m.id === props.selectedModel ? " is-active" : ""}`} onClick={() => props.onModelSelect(m.id)}>
                  {m.id}
                </button>
              ))}
            </div>
          </div>
          <div className="apis-field">
            <label>Message</label>
            <input type="text" value={props.input} onChange={(e) => props.onInputChange(e.target.value)} placeholder="Say hello..." onKeyDown={(e) => { if (e.key === "Enter" && props.input) props.onSend(); }} />
          </div>
          {props.response && <pre className={`apis-test-response${props.response.includes("not available") || props.response.includes("Error") || props.response.includes("failed") ? " apis-test-response--error" : ""}`}>{props.response}</pre>}
        </div>
        <footer className="apis-popup-footer">
          <button type="button" onClick={props.onClose}>Close</button>
          <button type="button" className="apis-submit-btn" disabled={props.sending || !props.selectedModel || !props.input} onClick={props.onSend}>
            {props.sending ? "Sending..." : "Send"}
          </button>
        </footer>
      </div>
    </div>
  );
};

export const AiProvidersPanel = ({ onAddRef }: { onAddRef: React.MutableRefObject<() => void> }) => {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [formType, setFormType] = useState("groq");
  const [formName, setFormName] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formBaseUrl, setFormBaseUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const keyInputRef = useRef<HTMLInputElement>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmInput, setConfirmInput] = useState("");
  const [confirmToggleId, setConfirmToggleId] = useState<string | null>(null);
  const [confirmToggleEnabled, setConfirmToggleEnabled] = useState(false);
  const [toggleInput, setToggleInput] = useState("");
  const [testProviderId, setTestProviderId] = useState<string | null>(null);
  const [testModels, setTestModels] = useState<{ id: string; name: string }[]>([]);
  const [testModel, setTestModel] = useState("");
  const [testModelSearch, setTestModelSearch] = useState("");
  const [testModelsLoading, setTestModelsLoading] = useState(false);
  const [testInput, setTestInput] = useState("");
  const [testResponse, setTestResponse] = useState("");
  const [testSending, setTestSending] = useState(false);

  const fetchProviders = useCallback(async () => {
    const res = await fetch("/api/providers");
    if (res.ok) {
      const data = await res.json();
      setProviders(data.providers || []);
    }
  }, []);

  useEffect(() => { void fetchProviders(); }, [fetchProviders]);

  const getNextName = (type: string) => {
    const prefix = type.toUpperCase().replace("_", "-");
    const existing = providers.map((p) => p.name);
    let n = 1;
    while (existing.includes(`${prefix}_${n}`)) n++;
    return `${prefix}_${n}`;
  };

  onAddRef.current = () => { setFormName(getNextName(formType)); setShowForm(true); };

  const handleAdd = async () => {
    if (!formName.trim()) return;
    if (formType === "custom" && !formBaseUrl.trim()) return;
    if (formType !== "custom" && !formKey.trim()) return;
    setLoading(true);
    await fetch("/api/providers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider_type: formType, name: formName, api_key: formKey, base_url: formBaseUrl }),
    });
    setShowForm(false);
    setFormName("");
    setFormKey("");
    setFormBaseUrl("");
    setLoading(false);
    setSuccessMsg(`${formType} key "${formName}" added`);
    setTimeout(() => setSuccessMsg(""), 4000);
    void fetchProviders();
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    await fetch(`/api/providers/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: !enabled }),
    });
    void fetchProviders();
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/providers/${id}`, { method: "DELETE" });
    setConfirmDeleteId(null);
    setConfirmInput("");
    void fetchProviders();
  };

  return (
    <>
      {successMsg && <div className="apis-success">{successMsg}</div>}
      <div className="apis-list">
        {providers.length === 0 && <p className="apis-empty">No AI provider keys configured.</p>}
        {providers.map((p) => (
          <div key={p.id} className="apis-card" data-enabled={p.enabled}>
            <div className="apis-card-header">
              <span className="apis-card-name">{p.name}</span>
              <span className={`apis-card-status ${p.enabled ? "apis-card-status--on" : "apis-card-status--off"}`}>
                {p.enabled ? "active" : "disabled"}
              </span>
            </div>
            <div className="apis-card-details">
              <span>Limit: {p.daily_limit || "unlimited"}/day</span>
            </div>
            <div className="apis-card-actions">
              <button type="button" onClick={() => { fetch(`/api/providers/${p.id}/docs`).then((r) => r.json()).then((d) => { if (d.url) window.open(d.url, "_blank"); }); }}>Docs</button>
              <button type="button" onClick={() => { setTestProviderId(p.id); }}>Test</button>
              <button type="button" onClick={() => { setConfirmToggleId(p.id); setConfirmToggleEnabled(p.enabled); }}>
                {p.enabled ? "Disable" : "Enable"}
              </button>
              <button type="button" className="apis-card-delete" onClick={() => setConfirmDeleteId(p.id)}>Remove</button>
            </div>
          </div>
        ))}
      </div>

      {showForm && (
        <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowForm(false); }}>
          <div className="apis-popup">
            <header className="apis-popup-header"><h3>Add AI Provider</h3></header>
            <div className="apis-popup-body">
              <div className="apis-field">
                <label>Provider Type</label>
                <ProviderTypeDropdown value={formType} onChange={(v) => { setFormType(v); setFormName(getNextName(v)); }} onSelected={() => keyInputRef.current?.focus()} />
              </div>
              <div className="apis-field">
                <label>Name</label>
                <input type="text" value={formName} onChange={(e) => setFormName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") keyInputRef.current?.focus(); }} />
              </div>
              <div className="apis-field">
                <label>API Key{formType === "custom" ? " (optional)" : ""}</label>
                <input ref={keyInputRef} type="password" value={formKey} onChange={(e) => setFormKey(e.target.value)} placeholder={formType === "custom" ? "Optional..." : "Enter key..."} onKeyDown={(e) => { if (e.key === "Enter" && formName && (formKey || formType === "custom")) void handleAdd(); }} />
              </div>
              {formType === "custom" && (
                <div className="apis-field">
                  <label>Base URL (OpenAI-compatible endpoint)</label>
                  <input type="text" value={formBaseUrl} onChange={(e) => setFormBaseUrl(e.target.value)} placeholder="https://api.example.com/v1" onKeyDown={(e) => { if (e.key === "Enter" && formName && formBaseUrl) void handleAdd(); }} />
                </div>
              )}
            </div>
            <footer className="apis-popup-footer">
              <button type="button" onClick={() => setShowForm(false)}>Cancel</button>
              <button type="button" className="apis-submit-btn" disabled={loading || !formName || !formKey} onClick={() => void handleAdd()}>
                {loading ? "Saving..." : "Save"}
              </button>
            </footer>
          </div>
        </div>
      )}

      {confirmDeleteId && (
        <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setConfirmDeleteId(null); setConfirmInput(""); } }}>
          <div className="apis-popup apis-popup--narrow">
            <header className="apis-popup-header"><h3>Remove Provider</h3></header>
            <div className="apis-popup-body">
              <p className="apis-confirm-text">Type "confirm" to remove this key permanently.</p>
              <input className="apis-confirm-input" type="text" value={confirmInput} onChange={(e) => setConfirmInput(e.target.value)} placeholder="confirm" />
            </div>
            <footer className="apis-popup-footer">
              <button type="button" className="apis-popup-cancel" onClick={() => { setConfirmDeleteId(null); setConfirmInput(""); }}>Cancel</button>
              <button type="button" className="apis-submit-btn apis-submit-btn--danger" disabled={confirmInput !== "confirm"} onClick={() => void handleDelete(confirmDeleteId)}>Remove</button>
            </footer>
          </div>
        </div>
      )}

      {confirmToggleId && (
        <div className="apis-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setConfirmToggleId(null); setToggleInput(""); } }}>
          <div className="apis-popup apis-popup--narrow">
            <header className="apis-popup-header"><h3>{confirmToggleEnabled ? "Disable" : "Enable"} Provider</h3></header>
            <div className="apis-popup-body">
              <p className="apis-confirm-text">Type "confirm" to {confirmToggleEnabled ? "disable" : "enable"} this provider.</p>
              <input className="apis-confirm-input" type="text" value={toggleInput} onChange={(e) => setToggleInput(e.target.value)} placeholder="confirm" />
            </div>
            <footer className="apis-popup-footer">
              <button type="button" className="apis-popup-cancel" onClick={() => { setConfirmToggleId(null); setToggleInput(""); }}>Cancel</button>
              <button type="button" className="apis-submit-btn" disabled={toggleInput !== "confirm"} onClick={() => { void handleToggle(confirmToggleId, confirmToggleEnabled); setConfirmToggleId(null); setToggleInput(""); }}>Confirm</button>
            </footer>
          </div>
        </div>
      )}

      {testProviderId && (
        <TestProviderPopup
          providerId={testProviderId}
          models={testModels}
          modelsLoading={testModelsLoading}
          selectedModel={testModel}
          modelSearch={testModelSearch}
          input={testInput}
          response={testResponse}
          sending={testSending}
          onModelSearchChange={setTestModelSearch}
          onModelSelect={setTestModel}
          onInputChange={setTestInput}
          onSend={() => {
            setTestSending(true);
            fetch(`/api/providers/${testProviderId}/test`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ model: testModel, message: testInput }),
            }).then((r) => r.json()).then((d) => setTestResponse(d.response ?? d.error ?? "No response"))
              .catch(() => setTestResponse("Request failed"))
              .finally(() => setTestSending(false));
          }}
          onClose={() => { setTestProviderId(null); setTestModels([]); setTestModel(""); setTestModelSearch(""); setTestInput(""); setTestResponse(""); }}
          onOpen={() => {
            setTestModelsLoading(true);
            fetch(`/api/providers/${testProviderId}/models`).then((r) => r.json())
              .then((d) => { setTestModels(d.models ?? []); if (d.models?.length) setTestModel(d.models[0].id); })
              .catch(() => {}).finally(() => setTestModelsLoading(false));
          }}
        />
      )}
    </>
  );
};
