/**
 * React UI component 'Sidebarpromptslist'.
 *
 * Responsibilities:
 * Renders the 'Sidebarpromptslist' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useEffect, useMemo, useState } from "react";

import type { PromptLibraryEntry } from "../app/types";

type SidebarPromptsListProps = {
  prompts: PromptLibraryEntry[];
  selectedPromptName: string | null;
  isLoadingPrompts: boolean;
  onSelectPrompt: (name: string) => void;
  onRefresh: () => void;
  onNewPrompt: () => void;
};

type SystemPromptEntry = { name: string; content: string };

export const SidebarPromptsList = ({
  prompts,
  selectedPromptName,
  isLoadingPrompts,
  onSelectPrompt,
  onRefresh,
  onNewPrompt,
}: SidebarPromptsListProps) => {
  const [search, setSearch] = useState("");
  const [systemOpen, setSystemOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [customOpen, setCustomOpen] = useState(false);
  const [systemPrompts, setSystemPrompts] = useState<SystemPromptEntry[]>([]);

  useEffect(() => {
    fetch("/api/prompts/system")
      .then((r) => r.json())
      .then((data) => setSystemPrompts(data.prompts ?? []))
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return prompts;
    const q = search.toLowerCase();
    return prompts.filter((p) => p.name.toLowerCase().includes(q));
  }, [prompts, search]);

  const filteredSystem = useMemo(() => {
    if (!search.trim()) return systemPrompts;
    const q = search.toLowerCase();
    return systemPrompts.filter((p) => p.name.toLowerCase().includes(q));
  }, [systemPrompts, search]);

  const builtinPrompts = useMemo(() => filtered.filter((p) => p.source === "builtin"), [filtered]);
  const userPrompts = useMemo(() => filtered.filter((p) => p.source === "user"), [filtered]);

  return (
    <div className="sidebar-prompts">
      <div className="sidebar-prompts-toolbar">
        <button type="button" className="sidebar-prompts-new-btn" onClick={onNewPrompt}>
          + New Prompt
        </button>
        <button type="button" className="sidebar-prompts-refresh-btn" onClick={onRefresh} disabled={isLoadingPrompts} aria-label="Refresh prompts">
          R
        </button>
      </div>

      <input className="sidebar-prompts-search" type="text" placeholder="Search prompts..." value={search} onChange={(e) => setSearch(e.target.value)} />

      {isLoadingPrompts && prompts.length === 0 ? (
        <p className="sidebar-prompts-empty">Loading...</p>
      ) : filtered.length === 0 && filteredSystem.length === 0 ? (
        <p className="sidebar-prompts-empty">{search ? "No matches" : "No prompts yet"}</p>
      ) : (
        <div className="sidebar-prompts-list">
          {filteredSystem.length > 0 && (
            <div className="sidebar-prompts-group">
              <button type="button" className="sidebar-prompts-group-toggle" onClick={() => setSystemOpen((o) => !o)}>
                <span className="sidebar-prompts-group-name">System ({filteredSystem.length})</span>
                <span className={`sidebar-prompts-arrow${systemOpen ? " is-open" : ""}`}>▶</span>
              </button>
              {systemOpen && filteredSystem.map((p) => (
                <button key={p.name} type="button" className="sidebar-prompts-item" data-active={selectedPromptName === p.name ? "true" : undefined} onClick={() => onSelectPrompt(p.name)}>
                  {p.name}
                </button>
              ))}
            </div>
          )}

          {builtinPrompts.length > 0 && (
            <div className="sidebar-prompts-group">
              <button type="button" className="sidebar-prompts-group-toggle" onClick={() => setSkillsOpen((o) => !o)}>
                <span className="sidebar-prompts-group-name">Skills ({builtinPrompts.length})</span>
                <span className={`sidebar-prompts-arrow${skillsOpen ? " is-open" : ""}`}>▶</span>
              </button>
              {skillsOpen && builtinPrompts.map((p) => (
                <button key={p.name} type="button" className="sidebar-prompts-item" data-active={selectedPromptName === p.name ? "true" : undefined} onClick={() => onSelectPrompt(p.name)}>
                  {p.name}
                </button>
              ))}
            </div>
          )}

          {userPrompts.length > 0 && (
            <div className="sidebar-prompts-group">
              <button type="button" className="sidebar-prompts-group-toggle" onClick={() => setCustomOpen((o) => !o)}>
                <span className="sidebar-prompts-group-name">Custom Prompts ({userPrompts.length})</span>
                <span className={`sidebar-prompts-arrow${customOpen ? " is-open" : ""}`}>▶</span>
              </button>
              {customOpen && userPrompts.map((p) => (
                <button key={p.name} type="button" className="sidebar-prompts-item" data-active={selectedPromptName === p.name ? "true" : undefined} onClick={() => onSelectPrompt(p.name)}>
                  {p.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
