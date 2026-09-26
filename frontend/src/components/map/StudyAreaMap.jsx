import "leaflet/dist/leaflet.css";

import {
  CircleMarker,
  MapContainer,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";

const DOWNSTREAM_STUDY_AREA = {
  name: "Sonari / Charaideo",
  role: "Downstream study area",
  position: [27.028, 95.0312],
};

const UPSTREAM_WEATHER_REFERENCE = {
  name: "Mokokchung",
  role: "Upstream weather reference",
  position: [26.31393, 94.51675],
};

const STUDY_BOUNDS = [
  UPSTREAM_WEATHER_REFERENCE.position,
  DOWNSTREAM_STUDY_AREA.position,
];

const DOWNSTREAM_STYLE = {
  color: "#38bdf8",
  fillColor: "#0284c7",
  fillOpacity: 0.86,
  weight: 2,
};

const UPSTREAM_STYLE = {
  color: "#c4b5fd",
  fillColor: "#7c3aed",
  fillOpacity: 0.86,
  weight: 2,
};

function ReferencePoint({ location, style, tooltipClassName }) {
  return (
    <CircleMarker
      center={location.position}
      radius={8}
      pathOptions={style}
    >
      <Tooltip
        permanent
        direction="top"
        offset={[0, -8]}
        opacity={1}
        className={tooltipClassName}
      >
        {location.name}
      </Tooltip>

      <Popup>
        <strong>{location.name}</strong>
        <br />
        {location.role}
      </Popup>
    </CircleMarker>
  );
}

export default function StudyAreaMap() {
  return (
    <section className="panel study-map-shell" aria-labelledby="study-area-map-title">
      <div className="panel-header">
        <div>
          <p id="study-area-map-title" className="section-label">
            Study area map
          </p>
          <p className="mt-1 text-xs normal-case tracking-normal text-slate-500">
            Prototype reference locations only - not a live flood boundary.
          </p>
        </div>
        <span className="status-label text-slate-300">REFERENCE VIEW</span>
      </div>

      <div className="panel-body">
        <div className="study-map-frame">
          <MapContainer
            className="study-area-map"
            bounds={STUDY_BOUNDS}
            boundsOptions={{ padding: [40, 40], maxZoom: 10 }}
            scrollWheelZoom
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              maxZoom={19}
            />

            <ReferencePoint
              location={DOWNSTREAM_STUDY_AREA}
              style={DOWNSTREAM_STYLE}
              tooltipClassName="study-map-tooltip study-map-tooltip-downstream"
            />

            <ReferencePoint
              location={UPSTREAM_WEATHER_REFERENCE}
              style={UPSTREAM_STYLE}
              tooltipClassName="study-map-tooltip study-map-tooltip-upstream"
            />
          </MapContainer>
        </div>

        <div className="mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
          <div className="study-map-reference">
            <span
              className="study-map-reference-dot study-map-reference-dot-downstream"
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-200">Sonari / Charaideo</strong>
              <br />
              Downstream study area
            </span>
          </div>

          <div className="study-map-reference">
            <span
              className="study-map-reference-dot study-map-reference-dot-upstream"
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-200">Mokokchung</strong>
              <br />
              Upstream weather reference
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}