import useBrowserLocation, {
  LOCATION_STATES,
} from "../../hooks/useBrowserLocation.js";

const STATUS_LABELS = Object.freeze({
  [LOCATION_STATES.NOT_CHECKED]: "LOCATION NOT CHECKED",
  [LOCATION_STATES.CHECKING]: "CHECKING LOCATION...",
  [LOCATION_STATES.INSIDE_AFFECTED_AREA]:
    "INSIDE PROTOTYPE AFFECTED AREA",
  [LOCATION_STATES.OUTSIDE_AFFECTED_AREA]:
    "OUTSIDE PROTOTYPE AFFECTED AREA",
  [LOCATION_STATES.PERMISSION_DENIED]:
    "LOCATION PERMISSION DENIED",
  [LOCATION_STATES.POSITION_UNAVAILABLE]: "LOCATION UNAVAILABLE",
  [LOCATION_STATES.REQUEST_TIMEOUT]: "LOCATION REQUEST TIMED OUT",
  [LOCATION_STATES.GEOLOCATION_UNSUPPORTED]:
    "GEOLOCATION NOT SUPPORTED",
});

export default function LocationStatus() {
  const { status, checking, checkLocation } = useBrowserLocation();

  const statusLabel =
    STATUS_LABELS[status] ?? STATUS_LABELS[LOCATION_STATES.POSITION_UNAVAILABLE];

  return (
    <section
      className="panel location-status-shell"
      aria-labelledby="location-status-title"
    >
      <div className="panel-header">
        <div>
          <p id="location-status-title" className="section-label">
            Location status
          </p>
          <p className="mt-1 text-xs normal-case tracking-normal text-slate-500">
            One-time browser location check against the prototype affected area.
          </p>
        </div>
        <span className="status-label text-slate-300">LOCAL CHECK</span>
      </div>

      <div className="panel-body">
        <div className="location-status-layout">
          <div className="location-status-result">
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
              Current result
            </p>
            <p
              className="location-status-value"
              aria-live="polite"
              aria-atomic="true"
            >
              {statusLabel}
            </p>
            <p className="mt-2 max-w-3xl text-xs leading-5 text-slate-500">
              Prototype geographic check only - not an official emergency-zone
              determination. Location status does not change the flood warning
              level.
            </p>
          </div>

          <button
            type="button"
            className="location-check-button"
            onClick={checkLocation}
            disabled={checking}
          >
            {checking ? "CHECKING LOCATION..." : "CHECK MY LOCATION"}
          </button>
        </div>
      </div>
    </section>
  );
}