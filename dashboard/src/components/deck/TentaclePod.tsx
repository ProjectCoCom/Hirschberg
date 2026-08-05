/**
 * Summary: React UI component 'Tentaclepod'.
 *
 * What it does: Renders the 'Tentaclepod' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { DeckAvailableSkill, DeckTentacleSummary } from "@octogent/core";
import { OctopusGlyph } from "../EmptyOctopus";
import type { OctopusVisuals } from "./octopusVisuals";

// ─── Status styling ──────────────────────────────────────────────────────────

export const STATUS_LABELS: Record<DeckTentacleSummary["status"], string> = {
  idle: "idle",
  active: "active",
  blocked: "blocked",
  "needs-review": "review",
};

// ─── TodoList ────────────────────────────────────────────────────────────────

export const TodoList = ({
  items,
  tentacleId,
  onToggle,
}: {
  items: { text: string; done: boolean }[];
  tentacleId: string;
  onToggle?: ((tentacleId: string, itemIndex: number, done: boolean) => void) | undefined;
}) => {
  let lastDoneIndex = -1;
  for (let idx = items.length - 1; idx >= 0; idx--) {
    if (items[idx]?.done) {
      lastDoneIndex = idx;
      break;
    }
  }
  const scrollRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ block: "start" });
  }, []);

  return (
    <ul className="deck-pod-todos">
      {items.map((item, i) => (
        <li
          key={item.text}
          ref={i === lastDoneIndex ? scrollRef : undefined}
          className={`deck-pod-todo-item${item.done ? " deck-pod-todo-item--done" : ""}`}
        >
          <input
            type="checkbox"
            checked={item.done}
            className="deck-pod-todo-checkbox"
            onChange={() => onToggle?.(tentacleId, i, !item.done)}
          />
          <span className="deck-pod-todo-text">{item.text}</span>
        </li>
      ))}
    </ul>
  );
};

// ─── TentaclePod ─────────────────────────────────────────────────────────────

export type TentaclePodProps = {
  tentacle: DeckTentacleSummary;
  visuals: OctopusVisuals;
  isFocused: boolean;
  activeFileName?: string | undefined;
  onVaultFileClick?: (fileName: string) => void;
  onVaultBrowse?: () => void;
  onClose?: () => void;
  onTodoToggle?: (tentacleId: string, itemIndex: number, done: boolean) => void;
  availableSkills: DeckAvailableSkill[];
  isSavingSkills?: boolean | undefined;
  onSaveSuggestedSkills?:
    | ((tentacleId: string, suggestedSkills: string[]) => Promise<boolean>)
    | undefined;
};

export const TentaclePod = ({
  tentacle,
  visuals,
  isFocused,
  activeFileName,
  onVaultFileClick,
  onVaultBrowse,
  onClose,
  onTodoToggle,
  availableSkills,
  isSavingSkills,
  onSaveSuggestedSkills,
}: TentaclePodProps) => {
  const progressPct =
    tentacle.todoTotal > 0 ? Math.round((tentacle.todoDone / tentacle.todoTotal) * 100) : 0;
  const [isEditingSkills, setIsEditingSkills] = useState(false);
  const [draftSkills, setDraftSkills] = useState<string[]>(tentacle.suggestedSkills);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    setDraftSkills(tentacle.suggestedSkills);
  }, [tentacle.suggestedSkills]);

  const availableSkillNames = availableSkills.map((skill) => skill.name);
  const skillNames = [...new Set([...availableSkillNames, ...draftSkills])].sort((a, b) =>
    a.localeCompare(b),
  );

  const toggleSkill = (skillName: string) => {
    setDraftSkills((current) =>
      current.includes(skillName)
        ? current.filter((skill) => skill !== skillName)
        : [...current, skillName].sort((a, b) => a.localeCompare(b)),
    );
  };

  const handleSaveSkills = async () => {
    const saved = await onSaveSuggestedSkills?.(tentacle.tentacleId, draftSkills);
    if (saved) {
      setIsEditingSkills(false);
    }
  };

  return (
    <article
      className={`deck-pod${isFocused ? " deck-pod--focused" : ""}`}
      data-status={tentacle.status}
      style={{ borderColor: "var(--accent-primary)" }}
    >
      <header className="deck-pod-header">
        {isFocused && (
          <button type="button" className="deck-pod-btn deck-pod-btn--secondary" onClick={onClose}>
            ← Back
          </button>
        )}
        <button type="button" className="deck-pod-btn">
          Spawn
        </button>
        <button
          type="button"
          className="deck-pod-btn"
          onClick={() => {
            setDraftSkills(tentacle.suggestedSkills);
            setIsEditingSkills((current) => !current);
          }}
        >
          Skills
        </button>
        <button type="button" className="deck-pod-btn" onClick={() => onVaultBrowse?.()}>
          Vault
        </button>
        <button
          type="button"
          className="deck-pod-btn deck-pod-btn--expand"
          onClick={(e) => { e.stopPropagation(); setIsExpanded(true); }}
          aria-label="Expand on canvas"
        >
          <svg className="deck-pod-btn-icon" viewBox="0 0 16 16" aria-hidden="true">
            <path
              d="M2 2h5M2 2v5M14 14h-5M14 14v-5M14 2h-5M14 2v5M2 14h5M2 14v-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </header>

      <div className="deck-pod-body">
        <span className={`deck-pod-status deck-pod-status--${tentacle.status}`}>
          {STATUS_LABELS[tentacle.status]}
        </span>
        <div className="deck-pod-identity">
          <div className="deck-pod-octopus-col">
            <div className="deck-pod-octopus">
              <OctopusGlyph
                color={visuals.color}
                animation={visuals.animation}
                expression={visuals.expression}
                accessory={visuals.accessory}
                {...(visuals.hairColor ? { hairColor: visuals.hairColor } : {})}
                scale={5}
              />
            </div>
          </div>
          <div className="deck-pod-identity-text">
            <span className="deck-pod-name">{tentacle.displayName}</span>
            <span className="deck-pod-description">{tentacle.description}</span>
          </div>
        </div>

        <div className="deck-pod-details">
          {isEditingSkills && (
            <div className="deck-pod-skills-editor">
              {skillNames.length === 0 ? (
                <span className="deck-pod-skills-empty">No Claude Code skills found.</span>
              ) : (
                <div className="deck-pod-skills-options">
                  {skillNames.map((skillName) => {
                    const skill = availableSkills.find((entry) => entry.name === skillName);
                    return (
                      <label key={skillName} className="deck-pod-skill-option">
                        <input
                          type="checkbox"
                          checked={draftSkills.includes(skillName)}
                          onChange={() => toggleSkill(skillName)}
                        />
                        <span className="deck-pod-skill-copy">
                          <span className="deck-pod-skill-name">{skillName}</span>
                          {skill?.description && (
                            <span className="deck-pod-skill-desc">{skill.description}</span>
                          )}
                          {!skill && (
                            <span className="deck-pod-skill-desc">
                              Stored on this tentacle, but not available right now.
                            </span>
                          )}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
              <div className="deck-pod-skills-actions">
                <button
                  type="button"
                  className="deck-pod-btn deck-pod-btn--secondary"
                  onClick={() => {
                    setDraftSkills(tentacle.suggestedSkills);
                    setIsEditingSkills(false);
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="deck-pod-btn"
                  disabled={Boolean(isSavingSkills)}
                  onClick={() => void handleSaveSkills()}
                >
                  {isSavingSkills ? "Saving..." : "Save Skills"}
                </button>
              </div>
            </div>
          )}

          {tentacle.todoTotal > 0 && (
            <div className="deck-pod-progress">
              <div className="deck-pod-progress-bar">
                <div
                  className="deck-pod-progress-fill"
                  style={{ width: `${progressPct}%`, backgroundColor: visuals.color }}
                />
              </div>
              <span
                className="deck-pod-progress-label"
                style={{ backgroundColor: `${visuals.color}22`, color: visuals.color }}
              >
                {tentacle.todoDone}/{tentacle.todoTotal} done
              </span>
            </div>
          )}

          {tentacle.todoItems.length > 0 && (
            <TodoList
              items={tentacle.todoItems}
              tentacleId={tentacle.tentacleId}
              onToggle={onTodoToggle}
            />
          )}

          {tentacle.suggestedSkills.length > 0 && (
            <div className="deck-pod-vault">
              <span className="deck-pod-vault-label">skills</span>
              <div className="deck-pod-vault-files">
                {tentacle.suggestedSkills.map((skill) => (
                  <span key={skill} className="deck-pod-vault-file">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {tentacle.vaultFiles.length > 0 && (
            <div className="deck-pod-vault">
              <span className="deck-pod-vault-label">vault</span>
              <div className="deck-pod-vault-files">
                {tentacle.vaultFiles.map((file) => (
                  <button
                    key={file}
                    type="button"
                    className="deck-pod-vault-file"
                    aria-current={activeFileName === file ? "true" : undefined}
                    onClick={(e) => {
                      e.stopPropagation();
                      onVaultFileClick?.(file);
                    }}
                  >
                    {file}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {isExpanded && createPortal(
        <div className="deck-pod-overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setIsExpanded(false); }}>
          <div className="deck-pod-popup" onClick={(e) => e.stopPropagation()}>
            <header className="deck-pod-popup-header">
              <div className="deck-pod-popup-identity">
                <div className="deck-pod-octopus" style={{ width: 64, height: 64 }}>
                  <OctopusGlyph
                    color={visuals.color}
                    animation={visuals.animation}
                    expression={visuals.expression}
                    accessory={visuals.accessory}
                    {...(visuals.hairColor ? { hairColor: visuals.hairColor } : {})}
                    scale={4}
                  />
                </div>
                <div>
                  <h2 className="deck-pod-popup-title">{tentacle.displayName}</h2>
                  <p className="deck-pod-popup-desc">{tentacle.description}</p>
                  <span className={`deck-pod-status deck-pod-status--${tentacle.status}`}>
                    {STATUS_LABELS[tentacle.status]}
                  </span>
                </div>
              </div>
              <button
                type="button"
                className="deck-pod-popup-close"
                onClick={() => setIsExpanded(false)}
                aria-label="Close"
              >
                X
              </button>
            </header>

            <div className="deck-pod-popup-body">
              {tentacle.todoItems.filter((t) => !t.done).length > 0 && (
                <div className="deck-pod-popup-section">
                  <h3 className="deck-pod-popup-section-title">
                    Agents Working ({tentacle.todoItems.filter((t) => !t.done).length})
                  </h3>
                  <ul className="deck-pod-popup-agents">
                    {tentacle.todoItems.filter((t) => !t.done).map((item) => (
                      <li key={item.text} className="deck-pod-popup-agent">
                        <span className="deck-pod-popup-agent-dot" style={{ backgroundColor: visuals.color }} />
                        <span className="deck-pod-popup-agent-label">{item.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {tentacle.todoTotal > 0 && (
                <div className="deck-pod-popup-section">
                  <h3 className="deck-pod-popup-section-title">
                    Progress ({tentacle.todoDone}/{tentacle.todoTotal})
                  </h3>
                  <div className="deck-pod-progress-bar" style={{ height: 8 }}>
                    <div
                      className="deck-pod-progress-fill"
                      style={{ width: `${progressPct}%`, backgroundColor: visuals.color }}
                    />
                  </div>
                  <TodoList
                    items={tentacle.todoItems}
                    tentacleId={tentacle.tentacleId}
                    onToggle={onTodoToggle}
                  />
                </div>
              )}

              {tentacle.suggestedSkills.length > 0 && (
                <div className="deck-pod-popup-section">
                  <h3 className="deck-pod-popup-section-title">Skills</h3>
                  <div className="deck-pod-vault-files">
                    {tentacle.suggestedSkills.map((skill) => (
                      <span key={skill} className="deck-pod-vault-file">{skill}</span>
                    ))}
                  </div>
                </div>
              )}

              {tentacle.vaultFiles.length > 0 && (
                <div className="deck-pod-popup-section">
                  <h3 className="deck-pod-popup-section-title">Vault</h3>
                  <div className="deck-pod-vault-files">
                    {tentacle.vaultFiles.map((file) => (
                      <button
                        key={file}
                        type="button"
                        className="deck-pod-vault-file"
                        onClick={() => onVaultFileClick?.(file)}
                      >
                        {file}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <footer className="deck-pod-popup-footer">
              <button type="button" className="deck-pod-btn" onClick={() => onVaultBrowse?.()}>
                Browse Vault
              </button>
              <button
                type="button"
                className="deck-pod-btn deck-pod-btn--danger"
                onClick={() => onClose?.()}
              >
                Delete Repo
              </button>
            </footer>
          </div>
        </div>,
        document.body,
      )}
    </article>
  );
};
