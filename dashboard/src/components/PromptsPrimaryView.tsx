/**
 * React UI component 'Promptsprimaryview'.
 *
 * Responsibilities:
 * Renders the 'Promptsprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { type ReactNode, useCallback, useEffect, useState } from "react";

import { usePromptLibrary } from "../app/hooks/usePromptLibrary";
import { SidebarPromptsList } from "./SidebarPromptsList";
import { type PromptCategory, type TemplateOption, TEMPLATES, textToXml } from "./prompt-templates";
import { ActionButton } from "./ui/ActionButton";
import { MarkdownContent } from "./ui/MarkdownContent";

type PromptsPrimaryViewProps = {
  enabled: boolean;
  onSidebarContent?: (content: ReactNode) => void;
};

export const PromptsPrimaryView = ({ enabled, onSidebarContent }: PromptsPrimaryViewProps) => {
  const {
    prompts,
    selectedPromptName,
    selectedPromptDetail: selectedPrompt,
    isLoadingPrompts,
    isLoadingDetail,
    isEditing,
    editDraft,
    errorMessage,
    refreshPrompts,
    selectPrompt: selectPromptLibraryItem,
    deletePrompt: deletePromptLibraryItem,
    startEditing: onStartEditing,
    cancelEditing: onCancelEditing,
    setEditDraft: onSetEditDraft,
    submitEdit: onSubmitEdit,
  } = usePromptLibrary({ enabled });

  const [showXml, setShowXml] = useState(false);
  const [showTemplatePopup, setShowTemplatePopup] = useState(false);
  const [newPromptMode, setNewPromptMode] = useState(false);
  const [newCategory, setNewCategory] = useState<PromptCategory>("general");
  const [newName, setNewName] = useState("");
  const [newContent, setNewContent] = useState("");
  const [newXmlContent, setNewXmlContent] = useState("");
  const [newSaving, setNewSaving] = useState(false);
  const [showDiscardPopup, setShowDiscardPopup] = useState(false);
  const [pendingSelectName, setPendingSelectName] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmInput, setConfirmInput] = useState("");

  const onDelete = useCallback(() => {
    if (selectedPromptName) return deletePromptLibraryItem(selectedPromptName);
    return Promise.resolve(false);
  }, [selectedPromptName, deletePromptLibraryItem]);

  const onRefresh = refreshPrompts;

  const handleSelectTemplate = (template: TemplateOption) => {
    setNewCategory(template.category);
    setNewName("");
    setNewContent(template.starter);
    setNewXmlContent(textToXml("untitled", template.starter || "[your instructions here]", template.category));
    setShowTemplatePopup(false);
    setNewPromptMode(true);
  };

  const handleSaveNewPrompt = useCallback(async () => {
    const contentToSave = showXml ? newXmlContent : newContent;
    if (!newName.trim() || !contentToSave.trim()) return;
    setNewSaving(true);
    try {
      const res = await fetch("/api/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newName.trim(),
          content: contentToSave.trim(),
          source: "user",
          category: newCategory,
          is_xml: showXml,
        }),
      });
      if (res.ok) {
        setNewPromptMode(false);
        setNewName("");
        setNewContent("");
        setNewXmlContent("");
        void onRefresh();
      }
    } finally {
      setNewSaving(false);
    }
  }, [newName, newContent, newXmlContent, newCategory, showXml, onRefresh]);

  const hasUnsavedContent = newPromptMode && (newName.trim() !== "" || newContent.trim() !== "" || newXmlContent.trim() !== "");

  const handleSidebarSelect = (name: string) => {
    if (hasUnsavedContent) {
      setPendingSelectName(name);
      setShowDiscardPopup(true);
    } else {
      setNewPromptMode(false);
      selectPromptLibraryItem(name);
    }
  };

  const confirmDiscard = () => {
    setNewPromptMode(false);
    setNewName("");
    setNewContent("");
    setNewXmlContent("");
    setShowDiscardPopup(false);
    if (pendingSelectName) {
      selectPromptLibraryItem(pendingSelectName);
      setPendingSelectName(null);
    }
  };

  const sidebarContent = (
    <SidebarPromptsList
      prompts={prompts}
      selectedPromptName={selectedPromptName}
      isLoadingPrompts={isLoadingPrompts}
      onSelectPrompt={handleSidebarSelect}
      onRefresh={() => { void refreshPrompts(); }}
      onNewPrompt={() => { setShowTemplatePopup(true); }}
    />
  );

  useEffect(() => {
    onSidebarContent?.(sidebarContent);
    return () => onSidebarContent?.(null);
  }, [prompts, selectedPromptName, isLoadingPrompts, newPromptMode]); // eslint-disable-line react-hooks/exhaustive-deps

  const promptCategory: PromptCategory = selectedPrompt?.source === "user" ? "skill" : "general";

  const isSystemPrompt = selectedPrompt?.source === "system";

  const [resetting, setResetting] = useState(false);

  const handleReset = useCallback(async () => {
    if (!selectedPromptName) return;
    setResetting(true);
    try {
      const res = await fetch(`/api/prompts/system/${selectedPromptName}/reset`, { method: "POST" });
      if (res.ok) {
        selectPromptLibraryItem(selectedPromptName);
        void onRefresh();
      }
    } finally {
      setResetting(false);
    }
  }, [selectedPromptName, selectPromptLibraryItem, onRefresh]);

  return (
    <section className="prompts-view" aria-label="Prompts primary view">
      {showTemplatePopup && (
        <div className="prompts-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowTemplatePopup(false); }}>
          <div className="prompts-template-popup">
            <header className="prompts-template-popup-header">
              <h3>New Prompt</h3>
              <button type="button" className="prompts-popup-close" onClick={() => setShowTemplatePopup(false)}>X</button>
            </header>
            <div className="prompts-template-popup-body">
              <div className="prompts-template-group">
                <h4 className="prompts-template-group-title">General Prompts</h4>
                <p className="prompts-template-group-desc">Broad tasks like reviews, analysis, and refactoring</p>
                {TEMPLATES.filter((t) => t.category === "general").map((t) => (
                  <button key={t.id} type="button" className="prompts-template-item" onClick={() => handleSelectTemplate(t)}>
                    <span className="prompts-template-item-label">{t.label}</span>
                    <span className="prompts-template-item-desc">{t.description}</span>
                  </button>
                ))}
              </div>
              <div className="prompts-template-group">
                <h4 className="prompts-template-group-title">Skill Prompts</h4>
                <p className="prompts-template-group-desc">Specific skills with scope isolation and quality gates</p>
                {TEMPLATES.filter((t) => t.category === "skill").map((t) => (
                  <button key={t.id} type="button" className="prompts-template-item" onClick={() => handleSelectTemplate(t)}>
                    <span className="prompts-template-item-label">{t.label}</span>
                    <span className="prompts-template-item-desc">{t.description}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {newPromptMode && (
        <div className="prompts-create-form">
          <header className="prompts-terminal-header">
            <button type="button" className="prompts-terminal-back" onClick={() => setNewPromptMode(false)}>Back</button>
            <span className="prompts-terminal-label">
              <strong>{newCategory === "skill" ? "New Skill" : "New Prompt"}</strong>
            </span>
            <button
              type="button"
              className={`prompts-toggle-btn prompts-toggle-btn--yellow${showXml ? " prompts-toggle-btn--active" : ""}`}
              onClick={() => {
                if (!showXml) setNewXmlContent(textToXml(newName || "untitled", newContent || "[your instructions here]", newCategory));
                setShowXml((v) => !v);
              }}
            >
              {showXml ? "Text" : "XML"}
            </button>
            <button
              type="button"
              className="prompts-toggle-btn prompts-toggle-btn--yellow"
              onClick={() => {
                const text = showXml ? newXmlContent : textToXml(newName || "untitled", newContent || "[your instructions here]", newCategory);
                void navigator.clipboard.writeText(text);
              }}
            >
              Copy
            </button>
          </header>
          <div className="prompts-create-body">
            <label className="prompts-create-field">
              <span>Name</span>
              <input
                className="prompts-create-input"
                placeholder="e.g. security-audit, add-feature"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
            </label>
            {showXml ? (
              <label className="prompts-create-field">
                <span>XML (sent to AI)</span>
                <textarea
                  className="prompts-create-textarea prompts-create-textarea--xml"
                  value={newXmlContent}
                  onChange={(e) => setNewXmlContent(e.target.value)}
                  rows={14}
                  spellCheck={false}
                />
              </label>
            ) : (
              <label className="prompts-create-field">
                <span>Instructions</span>
                <textarea
                  className="prompts-create-textarea"
                  placeholder="Write your instructions in plain text..."
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  rows={14}
                  spellCheck={false}
                />
              </label>
            )}
            <div className="prompts-create-actions">
              <button type="button" className="prompts-create-cancel" onClick={() => setNewPromptMode(false)}>Cancel</button>
              <button
                type="button"
                className="prompts-create-save"
                disabled={newSaving || !newName.trim() || !newContent.trim()}
                onClick={() => void handleSaveNewPrompt()}
              >
                {newSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div className="prompts-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setConfirmDelete(false); setConfirmInput(""); } }}>
          <div className="prompts-template-popup" style={{ maxWidth: 360 }}>
            <header className="prompts-template-popup-header">
              <h3>Delete Prompt</h3>
              <button type="button" className="prompts-popup-close" onClick={() => { setConfirmDelete(false); setConfirmInput(""); }}>X</button>
            </header>
            <div className="prompts-template-popup-body" style={{ padding: "1rem" }}>
              <p style={{ color: "#a9b0ba", fontSize: "0.78rem", margin: "0 0 0.8rem" }}>
                Type <strong style={{ color: "#ff6b6b" }}>confirm</strong> to delete "{selectedPromptName}"
              </p>
              <input
                className="prompts-create-input"
                value={confirmInput}
                onChange={(e) => setConfirmInput(e.target.value)}
                placeholder="confirm"
                autoFocus
              />
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.8rem", justifyContent: "flex-end" }}>
                <button type="button" className="prompts-create-cancel" onClick={() => { setConfirmDelete(false); setConfirmInput(""); }}>Cancel</button>
                <button
                  type="button"
                  className="prompts-create-save"
                  style={{ background: "#7c3aed" }}
                  disabled={confirmInput !== "confirm"}
                  onClick={() => { void onDelete(); setConfirmDelete(false); setConfirmInput(""); }}
                >
                  Remove
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showDiscardPopup && (
        <div className="prompts-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) { setShowDiscardPopup(false); setPendingSelectName(null); } }}>
          <div className="prompts-template-popup" style={{ maxWidth: 360 }}>
            <header className="prompts-template-popup-header">
              <h3>Discard Changes?</h3>
              <button type="button" className="prompts-popup-close" onClick={() => { setShowDiscardPopup(false); setPendingSelectName(null); }}>X</button>
            </header>
            <div className="prompts-template-popup-body" style={{ padding: "1rem" }}>
              <p style={{ color: "#a9b0ba", fontSize: "0.78rem", margin: "0 0 0.8rem" }}>
                You have unsaved changes. Discard and switch to another prompt?
              </p>
              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                <button type="button" className="prompts-create-cancel" onClick={() => { setShowDiscardPopup(false); setPendingSelectName(null); }}>Keep Editing</button>
                <button type="button" className="prompts-create-save" style={{ background: "#c53030" }} onClick={confirmDiscard}>Discard</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {!newPromptMode && !showTemplatePopup && (
        <>
          {errorMessage ? <p className="prompts-error">{errorMessage}</p> : null}
          {isLoadingDetail ? (
            <p className="prompts-empty">Loading prompt...</p>
          ) : selectedPrompt ? (
            <div className="prompts-detail">
              <header className="prompts-detail-header">
                <div className="prompts-detail-header-left">
                  <h3 className="prompts-detail-name">{selectedPrompt.name}</h3>
                  <span className="prompts-detail-source-badge" data-source={selectedPrompt.source}>
                    {selectedPrompt.source === "user" ? "Custom" : selectedPrompt.source === "system" ? "System" : "Skill"}
                  </span>
                  <button
                    type="button"
                    className={`prompts-toggle-btn prompts-toggle-btn--yellow${showXml ? " prompts-toggle-btn--active" : ""}`}
                    onClick={() => setShowXml((v) => !v)}
                  >
                    {showXml ? "Text" : "XML"}
                  </button>
                  <button
                    type="button"
                    className="prompts-toggle-btn prompts-toggle-btn--yellow"
                    onClick={() => {
                      const text = showXml
                        ? textToXml(selectedPrompt.name, selectedPrompt.content, promptCategory)
                        : selectedPrompt.content;
                      void navigator.clipboard.writeText(text);
                    }}
                  >
                    Copy
                  </button>
                </div>
                <div className="prompts-detail-header-actions">
                  {isEditing ? (
                    <>
                      <ActionButton onClick={() => { void onSubmitEdit(); }}>Save</ActionButton>
                      <ActionButton onClick={onCancelEditing}>Cancel</ActionButton>
                    </>
                  ) : (
                    <>
                      <ActionButton onClick={() => {
                        setShowXml(false);
                        onStartEditing();
                      }}>Edit</ActionButton>
                      {isSystemPrompt ? (
                        <ActionButton onClick={() => void handleReset()}>
                          {resetting ? "Resetting..." : "Reset"}
                        </ActionButton>
                      ) : (
                        <ActionButton onClick={() => setConfirmDelete(true)}>Delete</ActionButton>
                      )}
                    </>
                  )}
                </div>
              </header>
              {isEditing ? (
                <textarea
                  className={`prompts-edit-area${showXml ? " prompts-edit-area--xml" : ""}`}
                  value={editDraft}
                  onChange={(e) => { onSetEditDraft(e.target.value); }}
                  spellCheck={false}
                />
              ) : (
                <div className="prompts-content">
                  {showXml ? (
                    <textarea
                      className="prompts-edit-area prompts-edit-area--xml"
                      value={textToXml(selectedPrompt.name, selectedPrompt.content, promptCategory)}
                      readOnly
                    />
                  ) : (
                    <MarkdownContent content={selectedPrompt.content} />
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="prompts-empty-state">
              <p className="prompts-empty">Select a prompt from the sidebar, or create a new one.</p>
            </div>
          )}
        </>
      )}
    </section>
  );
};
