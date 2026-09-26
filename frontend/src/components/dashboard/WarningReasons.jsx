export default function WarningReasons({ risk, unavailableReason }) {
  return (
    <div>
      <p className="section-label">Why this warning</p>

      {risk?.reasons?.length ? (
        <ol className="mt-3 divide-y divide-slate-800 border border-slate-800">
          {risk.reasons.map((reason, index) => (
            <li
              key={`${reason}-${index}`}
              className="grid grid-cols-[2.5rem_1fr] text-sm leading-6 text-slate-300"
            >
              <span className="border-r border-slate-800 bg-slate-950/50 px-3 py-3 text-center text-xs font-bold text-slate-500">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="px-4 py-3">{reason}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="mt-3 text-sm leading-6 text-slate-400">
          {unavailableReason || "Warning reasons are not available."}
        </p>
      )}

      <div className="mt-4 border-l-4 border-sky-500 bg-slate-950/55 px-4 py-3">
        <p className="section-label text-sky-300">Recommended action</p>
        <p className="mt-2 text-sm font-semibold leading-6 text-slate-100">
          {risk?.recommended_action ?? "DATA UNAVAILABLE"}
        </p>
      </div>
    </div>
  );
}