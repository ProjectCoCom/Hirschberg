/**
 * Frontend JavaScript/TypeScript module 'Main'.
 *
 * Responsibilities:
 * Provides application-level UI helper functions, adapters, or configurations for 'Main'.
 *
 * Coupling:
 * Used to build or bundle the React dashboard application.
 */


import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Root container '#root' was not found.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
