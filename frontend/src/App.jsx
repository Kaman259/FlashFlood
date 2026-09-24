function App() {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-16 text-slate-100">
      <section className="mx-auto max-w-3xl rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl shadow-black/20">
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-400">
          Stage 1
        </p>
        <h1 className="text-4xl font-bold tracking-tight">FlashFlood</h1>
        <p className="mt-3 text-lg text-slate-300">
          Hyperlocal Early-Warning &amp; Resilient Evacuation Support System
        </p>
        <div className="mt-8 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-200">
          Frontend setup is running. Flood-warning logic has not been added yet.
        </div>
        <p className="mt-5 text-sm leading-6 text-slate-400">
          This is an educational prototype. Future warning thresholds and demo data must not be treated as operational flood guidance.
        </p>
      </section>
    </main>
  );
}

export default App;
