/**
 * Frontend JavaScript/TypeScript module 'Githubmetrics'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Githubmetrics'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import { GITHUB_COMMIT_SERIES_LENGTH } from "./constants";
import type { GitHubCommitPoint, GitHubCommitSparkPoint, GitHubRepoSummarySnapshot } from "./types";

export const formatGitHubCommitHoverLabel = (point: GitHubCommitPoint) => {
  if (point.date.startsWith("n/a-")) {
    return point.count === 1 ? "No date · 1 commit" : `No date · ${point.count} commits`;
  }

  return point.count === 1 ? `${point.date} · 1 commit` : `${point.date} · ${point.count} commits`;
};

export const buildGitHubStatusPill = (summary: GitHubRepoSummarySnapshot | null) => {
  if (!summary) {
    return "GitHub loading";
  }

  if (summary.status === "ok") {
    return "GitHub live";
  }

  if (summary.status === "unavailable") {
    return "GitHub unavailable";
  }

  return "GitHub error";
};

export const buildGitHubCommitSeries = (summary: GitHubRepoSummarySnapshot | null) => {
  const fallbackSeries = Array.from({ length: GITHUB_COMMIT_SERIES_LENGTH }, (_, index) => ({
    date: `n/a-${index}`,
    count: 0,
  }));

  if (!summary?.commitsPerDay || summary.commitsPerDay.length === 0) {
    return fallbackSeries;
  }

  const sorted = [...summary.commitsPerDay]
    .sort((left, right) => left.date.localeCompare(right.date))
    .slice(-GITHUB_COMMIT_SERIES_LENGTH);

  return sorted;
};

export const buildGitHubCommitSparkPoints = (
  series: GitHubCommitPoint[],
  width: number,
  height: number,
): GitHubCommitSparkPoint[] => {
  const values = series.map((point) => point.count);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = Math.max(1, maxValue - minValue);
  const padY = 12;
  const padLeft = 40;
  const padRight = 10;
  const usableWidth = width - padLeft - padRight;

  return series.map((point, index) => {
    const x = padLeft + (index / Math.max(1, series.length - 1)) * usableWidth;
    const y = padY + (height - 2 * padY) - ((point.count - minValue) / valueRange) * (height - 2 * padY);
    return {
      date: point.date,
      count: point.count,
      x,
      y,
    };
  });
};

export const buildGitHubSparkPolylinePoints = (series: GitHubCommitSparkPoint[]) =>
  series.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");

export const buildGitHubCommitCount = (series: GitHubCommitPoint[]) =>
  series.reduce((total, point) => total + point.count, 0);
