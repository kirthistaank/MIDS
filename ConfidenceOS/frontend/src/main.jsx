import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";
import Landing from "./Landing.jsx";

// Simple client-side routing — no react-router needed
const path = window.location.pathname;

createRoot(document.getElementById("root")).render(
  <StrictMode>
    {path === "/app" ? <App /> : <Landing />}
  </StrictMode>
);