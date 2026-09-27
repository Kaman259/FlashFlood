import "leaflet/dist/leaflet.css";

import { useEffect, useState } from "react";

import {
  CircleMarker,
  MapContainer,
  Polygon,
  Popup,
  TileLayer,
  Tooltip,
} from "react-leaflet";

import {
  PROTOTYPE_AFFECTED_AREA,
  PROTOTYPE_SHELTERS,
  STUDY_LOCATIONS,
} from "./studyAreaData.js";

function toPosition(location) {
  return [location.latitude, location.longitude];
}

const STUDY_BOUNDS = [
  toPosition(STUDY_LOCATIONS.upstream),
  toPosition(STUDY_LOCATIONS.downstream),
  ...PROTOTYPE_AFFECTED_AREA.positions,
  ...PROTOTYPE_SHELTERS.map(toPosition),
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

const AFFECTED_AREA_STYLE = {
  color: "#94a3b8",
  fillColor: "#475569",
  fillOpacity: 0.24,
  weight: 2,
};

const SHELTER_STYLE = {
  color: "#f8fafc",
  fillColor: "#334155",
  fillOpacity: 0.95,
  weight: 2,
};

function ReferencePoint({ location, style, tooltipClassName }) {
  return (
    <CircleMarker
      center={toPosition(location)}
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

function PrototypeShelter({ shelter }) {
  return (
    <CircleMarker
      center={toPosition(shelter)}
      radius={6}
      pathOptions={SHELTER_STYLE}
    >
      <Tooltip direction="top" offset={[0, -7]} opacity={1}>
        {shelter.name}
      </Tooltip>

      <Popup>
        <strong>{shelter.name}</strong>
        <br />
        Prototype shelter
        <br />
        {shelter.description}
      </Popup>
    </CircleMarker>
  );
}

export default function StudyAreaMap() {
  const [online, setOnline] = useState(() => navigator.onLine);

  useEffect(() => {
    function handleOnline() {
      setOnline(true);
    }

    function handleOffline() {
      setOnline(false);
    }

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  return (
    <section className="panel study-map-shell" aria-labelledby="study-area-map-title">
      <div className="panel-header">
        <div>
          <p id="study-area-map-title" className="section-label">
            Study area map
          </p>
          <p className="mt-1 text-xs normal-case tracking-normal text-slate-500">
            Prototype affected area and shelters are demonstration geography only -
            not a real flood boundary or official shelter data.
          </p>
        </div>
        <span className="status-label text-slate-300">
          {online ? "ONLINE MAP" : "OFFLINE — CACHED TILES IF AVAILABLE"}
        </span>
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

            <Polygon
              positions={PROTOTYPE_AFFECTED_AREA.positions}
              pathOptions={AFFECTED_AREA_STYLE}
            >
              <Tooltip sticky opacity={1}>
                PROTOTYPE AFFECTED AREA
              </Tooltip>

              <Popup>
                <strong>{PROTOTYPE_AFFECTED_AREA.label}</strong>
                <br />
                Demonstration geometry only - not a real flood boundary.
              </Popup>
            </Polygon>

            <ReferencePoint
              location={STUDY_LOCATIONS.downstream}
              style={DOWNSTREAM_STYLE}
              tooltipClassName="study-map-tooltip study-map-tooltip-downstream"
            />

            <ReferencePoint
              location={STUDY_LOCATIONS.upstream}
              style={UPSTREAM_STYLE}
              tooltipClassName="study-map-tooltip study-map-tooltip-upstream"
            />

            {PROTOTYPE_SHELTERS.map((shelter) => (
              <PrototypeShelter key={shelter.id} shelter={shelter} />
            ))}
          </MapContainer>
        </div>

        <div
          className="study-map-legend mt-3 grid gap-2 text-xs text-slate-400 sm:grid-cols-2 xl:grid-cols-4"
          aria-label="Map legend"
        >
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

          <div className="study-map-reference">
            <span
              className="study-map-area-swatch"
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-200">Prototype affected area</strong>
              <br />
              Demonstration geometry
            </span>
          </div>

          <div className="study-map-reference">
            <span
              className="study-map-reference-dot study-map-reference-dot-shelter"
              aria-hidden="true"
            />
            <span>
              <strong className="text-slate-200">Prototype shelter</strong>
              <br />
              Demonstration location
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}