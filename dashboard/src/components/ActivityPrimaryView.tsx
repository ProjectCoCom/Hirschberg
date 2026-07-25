/**
 * React UI component 'Activityprimaryview'.
 *
 * Responsibilities:
 * Renders the 'Activityprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * Coupling:
 * Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */


import { useEffect, useState, type ComponentProps } from "react";

import { GitHubPrimaryView } from "./GitHubPrimaryView";
import { UsageBarChart } from "./UsageHeatmap";

type ActivityPrimaryViewProps = {
  usageChartProps: ComponentProps<typeof UsageBarChart>;
  githubPrimaryViewProps: ComponentProps<typeof GitHubPrimaryView>;
};

export const ActivityPrimaryView = ({
  usageChartProps,
  githubPrimaryViewProps,
}: ActivityPrimaryViewProps) => {
  const [hasGithubKey, setHasGithubKey] = useState(true);

  useEffect(() => {
    fetch("/api/settings/status").then((r) => {
      if (!r.ok) { setHasGithubKey(true); return null; }
      return r.json();
    }).then((d) => {
      if (!d) return;
      const ghClassic = d.github_token?.status === "active";
      const ghFg = d.github_fg_token?.status === "active";
      setHasGithubKey(ghClassic || ghFg);
    }).catch(() => setHasGithubKey(true));
  }, []);

  return (
    <section className="activity-view" aria-label="Activity primary view" style={{ position: "relative" }}>
      {!hasGithubKey && (
        <div className="apis-setup-overlay">
          <div className="apis-setup-card">
            <h3>GitHub API Key Required</h3>
            <p>Configure your GitHub token in Settings to view activity data, commits, and repository stats.</p>
            <button type="button" className="apis-setup-btn" onClick={() => { window.dispatchEvent(new CustomEvent("navigate", { detail: 8 })); }}>
              Go to Settings
            </button>
          </div>
        </div>
      )}
      <UsageBarChart {...usageChartProps} />
      <GitHubPrimaryView {...githubPrimaryViewProps} />
    </section>
  );
};
