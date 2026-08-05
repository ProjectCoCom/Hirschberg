/**
 * Summary: React UI component 'Searchabledropdown'.
 *
 * What it does: Renders the 'Searchabledropdown' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import { memo, useState } from "react";

type Props = {
  items: { id: string; label: string }[];
  selected: string;
  onSelect: (id: string) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  disabled?: boolean;
  displayValue?: string;
};

export const SearchableDropdown = memo(({
  items,
  selected,
  onSelect,
  placeholder = "Select...",
  searchPlaceholder = "Search...",
  disabled,
  displayValue,
}: Props) => {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = items.filter((i) => i.label.toLowerCase().includes(search.toLowerCase()));
  const label = displayValue ?? items.find((i) => i.id === selected)?.label ?? placeholder;

  return (
    <div className="chat-model-dropdown">
      <button
        type="button"
        className="chat-model-dropdown-trigger"
        onClick={() => { if (!disabled) setOpen((o) => !o); }}
        disabled={disabled}
      >
        {label}
        <span className="chat-model-dropdown-arrow">▾</span>
      </button>
      {open && (
        <div className="chat-model-dropdown-panel">
          <input
            className="chat-model-dropdown-search"
            type="text"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
          <div className="chat-model-dropdown-list">
            {filtered.map((item) => (
              <button
                key={item.id}
                type="button"
                className={`chat-model-dropdown-item${item.id === selected ? " is-active" : ""}`}
                onClick={() => {
                  onSelect(item.id);
                  setOpen(false);
                  setSearch("");
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});
