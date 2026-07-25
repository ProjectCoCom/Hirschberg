/**
 * Frontend JavaScript/TypeScript module 'Typecoercion'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Typecoercion'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


export const asRecord = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;

export const asString = (value: unknown): string | null =>
  typeof value === "string" ? value : null;

export const asNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
};
