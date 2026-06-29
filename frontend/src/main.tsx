import React from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

function App() {
  return (
    <main className="app-shell">
      <section className="workspace">
        <p className="eyebrow">Local-first scientific RAG</p>
        <h1>Private Scientific RAG</h1>
        <p>
          Foundation shell is ready. Mockups will define the research workbench before the
          production UI is filled in.
        </p>
        <div className="status-grid" aria-label="Foundation status">
          <div>
            <span>Frontend</span>
            <strong>React/Vite</strong>
          </div>
          <div>
            <span>Backend</span>
            <strong>FastAPI</strong>
          </div>
          <div>
            <span>Vector Store</span>
            <strong>Qdrant</strong>
          </div>
        </div>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
