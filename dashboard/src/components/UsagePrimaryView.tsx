/**
 * Summary: React UI component 'Usageprimaryview'.
 *
 * What it does: Renders the 'Usageprimaryview' dashboard interface, manages localized state, and handles user actions.
 *
 * How it fits in: Layout component rendered by parent dashboard containers; interacts with hooks and contexts from 'dashboard/src/app'.
 */



import { useCallback, useEffect, useState } from "react";

type UsageStats = {
  total: { input_tokens: number; output_tokens: number; requests: number };
  today: { input_tokens: number; output_tokens: number; requests: number };
  by_provider: Record<string, { input_tokens: number; output_tokens: number; requests: number }>;
  by_model: Record<string, { input_tokens: number; output_tokens: number; requests: number }>;
  daily: { date: string; input_tokens: number; output_tokens: number; requests: number }[];
  recent: { provider: string; model: string; input: number; output: number; at: string }[];
};

// Equivalent market rates per million tokens even for free-tier providers
const PRICING: Record<string, { input: number; output: number }> = {
  nvidia_nim: { input: 0.60, output: 0.60 },
  deepseek: { input: 0.27, output: 1.10 },
  openrouter: { input: 0.50, output: 1.50 },
  google: { input: 0.075, output: 0.30 },
  groq: { input: 0.05, output: 0.08 },
  github_models: { input: 0.30, output: 0.60 },
  custom: { input: 0.50, output: 1.50 },
};

function estimateCost(byProvider: Record<string, { input_tokens: number; output_tokens: number }>): number {
  let total = 0;
  for (const [provider, data] of Object.entries(byProvider)) {
    const pricing = PRICING[provider] ?? { input: 0.50, output: 1.50 };
    total += (data.input_tokens / 1_000_000) * pricing.input;
    total += (data.output_tokens / 1_000_000) * pricing.output;
  }
  return total;
}

const StatCard = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
  <div className="usage-stat-card">
    <span className="usage-stat-label">{label}</span>
    <span className="usage-stat-value">{value}</span>
    {sub && <span className="usage-stat-sub">{sub}</span>}
  </div>
);

const DailyLineGraph = ({ daily }: { daily: UsageStats["daily"] }) => {
  if (daily.length === 0) return <p className="usage-empty">No daily data yet</p>;

  const w = 500, h = 200, pad = 30;
  const maxVal = Math.max(...daily.map((d) => d.input_tokens + d.output_tokens), 1);
  const stepX = (w - pad * 2) / Math.max(daily.length - 1, 1);

  const inputPoints = daily.map((d, i) => `${pad + i * stepX},${h - pad - ((d.input_tokens / maxVal) * (h - pad * 2))}`).join(" ");
  const outputPoints = daily.map((d, i) => `${pad + i * stepX},${h - pad - ((d.output_tokens / maxVal) * (h - pad * 2))}`).join(" ");
  const totalPoints = daily.map((d, i) => `${pad + i * stepX},${h - pad - (((d.input_tokens + d.output_tokens) / maxVal) * (h - pad * 2))}`).join(" ");

  return (
    <div className="usage-graph-container">
      <svg viewBox={`0 0 ${w} ${h}`} className="usage-svg-graph" preserveAspectRatio="xMidYMax meet">
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#2b2f36" strokeWidth="1" />
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="#2b2f36" strokeWidth="1" />
        <polyline points={totalPoints} fill="none" stroke="#4a5568" strokeWidth="1.5" strokeDasharray="4 2" />
        <polyline points={inputPoints} fill="none" stroke="#00e5ff" strokeWidth="2" />
        <polyline points={outputPoints} fill="none" stroke="#a855f7" strokeWidth="2" />
        {daily.map((d, i) => (
          <text key={d.date} x={pad + i * stepX} y={h - 6} textAnchor="middle" fill="#e6e8ec" fontSize="8">{d.date.slice(5)}</text>
        ))}
        <text x={pad - 4} y={pad + 4} textAnchor="end" fill="#e6e8ec" fontSize="7">{maxVal.toLocaleString()}</text>
        <text x={pad - 4} y={h - pad} textAnchor="end" fill="#e6e8ec" fontSize="7">0</text>
      </svg>
      <div className="usage-graph-legend">
        <span className="usage-legend-input">Input</span>
        <span className="usage-legend-output">Output</span>
        <span className="usage-legend-total">Total</span>
      </div>
    </div>
  );
};



export const UsagePrimaryView = () => {
  const [stats, setStats] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(() => {
    setLoading(true);
    fetch("/api/usage/stats")
      .then((r) => r.json())
      .then((d) => {
        const empty = { input_tokens: 0, output_tokens: 0, requests: 0 };
        setStats({
          total: d.total ?? empty,
          today: d.today ?? empty,
          by_provider: d.by_provider ?? {},
          by_model: d.by_model ?? {},
          daily: d.daily ?? [],
          recent: d.recent ?? [],
        });
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  if (loading && !stats) {
    return <section className="usage-view"><div className="usage-loading">Loading usage data...</div></section>;
  }

  if (!stats) {
    return <section className="usage-view"><div className="usage-loading">No usage data available yet. Start chatting to track tokens.</div></section>;
  }

  const totalCost = estimateCost(stats.by_provider);

  return (
    <section className="usage-view" aria-label="Usage analytics">
      <header className="usage-header">
        <h2>Token Usage Analytics</h2>
        <button type="button" className="usage-refresh-btn" onClick={fetchStats}>Refresh</button>
      </header>

      <div className="usage-stats-grid">
        <StatCard label="Total Tokens" value={(stats.total.input_tokens + stats.total.output_tokens).toLocaleString()} sub={`${stats.total.requests} requests`} />
        <StatCard label="Input Tokens" value={stats.total.input_tokens.toLocaleString()} sub="prompts + context" />
        <StatCard label="Output Tokens" value={stats.total.output_tokens.toLocaleString()} sub="AI responses" />
        <StatCard label="Today" value={`${stats.today.requests}`} sub={`${(stats.today.input_tokens + stats.today.output_tokens).toLocaleString()} tokens today`} />
        <StatCard label="Est. Cost" value={`$${totalCost.toFixed(4)}`} sub="equivalent market rate" />
      </div>

      <div className="usage-sections-row">
        <div className="usage-section">
          <h3>Daily (7 Days)</h3>
          <DailyLineGraph daily={stats.daily} />
        </div>

        <div className="usage-section">
          <h3>By Provider</h3>
          <div className="usage-breakdown-list">
            {Object.entries(stats.by_provider).map(([name, data]) => {
              const pricing = PRICING[name] ?? { input: 0.50, output: 1.50 };
              const cost = (data.input_tokens / 1_000_000) * pricing.input + (data.output_tokens / 1_000_000) * pricing.output;
              return (
                <div key={name} className="usage-breakdown-row">
                  <span className="usage-breakdown-name">{name.replace("_", " ").toUpperCase()}</span>
                  <span className="usage-breakdown-tokens">{(data.input_tokens + data.output_tokens).toLocaleString()} tok</span>
                  <span className="usage-breakdown-cost">${cost.toFixed(4)}</span>
                  <span className="usage-breakdown-reqs">{data.requests} req</span>
                </div>
              );
            })}
            {Object.keys(stats.by_provider).length === 0 && <p className="usage-empty">No data yet</p>}
          </div>
        </div>

        <div className="usage-section">
          <h3>By Model</h3>
          <div className="usage-breakdown-list">
            {Object.entries(stats.by_model).map(([name, data]) => (
              <div key={name} className="usage-breakdown-row">
                <span className="usage-breakdown-name">{name}</span>
                <span className="usage-breakdown-tokens">{(data.input_tokens + data.output_tokens).toLocaleString()} tok</span>
                <span className="usage-breakdown-reqs">{data.requests} req</span>
              </div>
            ))}
            {Object.keys(stats.by_model).length === 0 && <p className="usage-empty">No data yet</p>}
          </div>
        </div>

        <div className="usage-section">
          <h3>Cost Breakdown</h3>
          <div className="usage-breakdown-list">
            {Object.entries(stats.by_provider).map(([name, data]) => {
              const pricing = PRICING[name] ?? { input: 0.50, output: 1.50 };
              const inputCost = (data.input_tokens / 1_000_000) * pricing.input;
              const outputCost = (data.output_tokens / 1_000_000) * pricing.output;
              return (
                <div key={name} className="usage-cost-row">
                  <span className="usage-breakdown-name">{name.replace("_", " ").toUpperCase()}</span>
                  <div className="usage-cost-detail">
                    <span>In: ${inputCost.toFixed(4)} ({pricing.input}/M)</span>
                    <span>Out: ${outputCost.toFixed(4)} ({pricing.output}/M)</span>
                  </div>
                </div>
              );
            })}
            {Object.keys(stats.by_provider).length === 0 && <p className="usage-empty">No cost data yet</p>}
          </div>
        </div>
      </div>
    </section>
  );
};
