/**
 * Frontend JavaScript/TypeScript module 'Formattimestamp'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Formattimestamp'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


export const formatTimestamp = (value: string | null) => {
  if (!value) {
    return "--";
  }

  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Date(parsed).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};
