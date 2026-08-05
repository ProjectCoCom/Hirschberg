/**
 * Summary: React UI component 'Runtimestatusstrip'.
 *
 * What it does: Renders the 'Runtimestatusstrip' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import { useEffect, useMemo, useRef, useState } from "react";

import { GITHUB_SPARKLINE_HEIGHT, GITHUB_SPARKLINE_WIDTH } from "../app/constants";
import type { UsageChartData } from "../app/hooks/useUsageHeatmapPolling";
import type { ClaudeUsageSnapshot } from "../app/types";
import { OctopusGlyph } from "./EmptyOctopus";

type RuntimeStatusStripProps = {
  sparklinePoints: string;
  usageData: UsageChartData | null;
  claudeUsage: ClaudeUsageSnapshot | null;
  isRefreshingClaudeUsage?: boolean;
  onRefreshClaudeUsage?: () => void;
};

const MINI_USAGE_WIDTH = 160;
const MINI_USAGE_HEIGHT = 28;
const MINI_BAR_GAP = 1;

type MiniBar = { x: number; y: number; width: number; height: number };

const buildUsageBars = (data: UsageChartData): MiniBar[] => {
  const days = Array.isArray(data.days) ? data.days.slice(-30) : [];
  if (days.length === 0) return [];

  const totals = days.map((day) => (typeof day.totalTokens === "number" ? day.totalTokens : 0));
  const max = Math.max(...totals, 1);
  const barSlot = MINI_USAGE_WIDTH / days.length;
  const barWidth = Math.max(1, barSlot - MINI_BAR_GAP);

  return days.map((day, index) => {
    const totalTokens = typeof day.totalTokens === "number" ? day.totalTokens : 0;
    const h = Math.max(0.5, (totalTokens / max) * (MINI_USAGE_HEIGHT - 2));
    return {
      x: index * barSlot,
      y: MINI_USAGE_HEIGHT - h,
      width: barWidth,
      height: h,
    };
  });
};

const pct = (value: number | null | undefined, loading?: boolean): string => {
  if (loading) return "···";
  return value == null ? "NA" : `${Math.round(value)}`;
};

const usageState = (
  claudeUsage: ClaudeUsageSnapshot | null,
): {
  label: string;
  loading: boolean;
  sessionPercent: number | null | undefined;
  sessionDisplay: string;
  weekPercent: number | null | undefined;
  weekDisplay: string;
  message?: string;
} => {
  if (claudeUsage === null) {
    return {
      label: "Daily",
      loading: true,
      sessionPercent: 0,
      sessionDisplay: "...",
      weekPercent: 0,
      weekDisplay: "...",
    };
  }

  const used = claudeUsage.extraUsageCostUsed ?? 0;
  const limit = claudeUsage.extraUsageCostLimit ?? 300;
  const label = "Daily";

  if (claudeUsage.status === "ok") {
    return {
      label,
      loading: false,
      sessionPercent: claudeUsage.primaryUsedPercent,
      sessionDisplay: `${used}/${limit}`,
      weekPercent: claudeUsage.secondaryUsedPercent,
      weekDisplay: `${claudeUsage.secondaryUsedPercent ?? 0}`,
    };
  }

  return {
    label,
    loading: false,
    sessionPercent: null,
    sessionDisplay: "NA",
    weekPercent: null,
    weekDisplay: "NA",
    message: claudeUsage.message ?? "Jules usage unavailable",
  };
};

const UsageRail = ({
  label,
  percent,
  loading,
  title,
  displayValue,
}: {
  label: string;
  percent: number | null | undefined;
  loading?: boolean;
  title?: string;
  displayValue?: string;
}) => {
  const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null);

  const showTooltip = (clientX: number, clientY: number) => {
    if (!title) return;
    setTooltip({ x: clientX, y: clientY });
  };

  return (
    <div
      className="console-status-usage-row"
      data-has-tooltip={title ? "true" : undefined}
      tabIndex={title ? 0 : -1}
      onMouseEnter={(event) => showTooltip(event.clientX, event.clientY)}
      onMouseMove={(event) => showTooltip(event.clientX, event.clientY)}
      onMouseLeave={() => setTooltip(null)}
      onBlur={() => setTooltip(null)}
      onFocus={(event) => {
        if (!title) return;
        const rect = event.currentTarget.getBoundingClientRect();
        setTooltip({ x: rect.left + 24, y: rect.bottom + 8 });
      }}
    >
      <span className="console-status-usage-row-meta">
        <span className="console-status-usage-row-label">{label}</span>
        <span className="console-status-usage-row-value">{displayValue || pct(percent, loading)}</span>
      </span>
      <span className="console-status-usage-rail">
        <span
          className="console-status-usage-rail-fill"
          style={{ width: `${Math.min(100, percent ?? 0)}%` }}
        />
      </span>
      {title && tooltip ? (
        <span
          className="console-status-usage-tooltip"
          style={{
            left: `${Math.max(8, tooltip.x - 260)}px`,
            top: `${Math.min(window.innerHeight - 80, tooltip.y + 14)}px`,
          }}
        >
          {title}
        </span>
      ) : null}
    </div>
  );
};

export const RuntimeStatusStrip = ({
  sparklinePoints,
  usageData,
  claudeUsage,
  isRefreshingClaudeUsage = false,
  onRefreshClaudeUsage,
}: RuntimeStatusStripProps) => {
  const usageBars = useMemo(() => (usageData ? buildUsageBars(usageData) : []), [usageData]);
  const claudeUsageState = usageState(claudeUsage);
  const [showRefreshSpin, setShowRefreshSpin] = useState(false);
  const refreshStartedAtRef = useRef<number | null>(null);
  const refreshHideTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (refreshHideTimerRef.current !== null) {
        window.clearTimeout(refreshHideTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (isRefreshingClaudeUsage) {
      if (refreshHideTimerRef.current !== null) {
        window.clearTimeout(refreshHideTimerRef.current);
        refreshHideTimerRef.current = null;
      }
      refreshStartedAtRef.current = Date.now();
      setShowRefreshSpin(true);
      return;
    }

    if (refreshStartedAtRef.current === null) {
      setShowRefreshSpin(false);
      return;
    }

    const elapsedMs = Date.now() - refreshStartedAtRef.current;
    const remainingMs = Math.max(0, 450 - elapsedMs);
    refreshHideTimerRef.current = window.setTimeout(() => {
      setShowRefreshSpin(false);
      refreshStartedAtRef.current = null;
      refreshHideTimerRef.current = null;
    }, remainingMs);
  }, [isRefreshingClaudeUsage]);

  return (
    <section className="console-status-strip" aria-label="Runtime status strip">
      <div className="console-status-main">
        <OctopusGlyph
          className="console-status-octopus-icon"
          animation="sway"
          expression="normal"
          scale={2}
          color="#7c3aed"
        />
        <span className="console-status-brand">JAT-AI</span>
      </div>
      <div className="console-status-claude-usage" aria-label="Claude usage limits">
        {onRefreshClaudeUsage && (
          <button
            type="button"
            className="console-status-claude-usage-refresh"
            onClick={onRefreshClaudeUsage}
            aria-label="Refresh Claude usage"
            title="Refresh Claude usage"
            data-refreshing={showRefreshSpin ? "true" : "false"}
          >
            ↻
          </button>
        )}
        <span className="console-status-claude-usage-title">
          JULES
          <br />
          USAGE
        </span>
        <div className="console-status-claude-usage-bars">
          <UsageRail
            label={claudeUsageState.label}
            percent={claudeUsageState.sessionPercent}
            loading={claudeUsageState.loading}
            displayValue={claudeUsageState.sessionDisplay}
            {...(claudeUsageState.message ? { title: claudeUsageState.message } : {})}
          />
          <UsageRail
            label="Accounts"
            percent={claudeUsageState.weekPercent}
            loading={claudeUsageState.loading}
            displayValue={claudeUsageState.weekDisplay}
            {...(claudeUsageState.message ? { title: claudeUsageState.message } : {})}
          />
        </div>
      </div>
    </section>
  );
};
