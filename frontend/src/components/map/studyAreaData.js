// Static geographic data for the FlashFlood prototype map.
// This module is visualization data only. It is not part of the backend risk request.

export const STUDY_LOCATIONS = {
  downstream: {
    id: "downstream-study-area",
    name: "Sonari / Charaideo",
    role: "Downstream study area",
    latitude: 27.028,
    longitude: 95.0312,
  },
  upstream: {
    id: "upstream-weather-reference",
    name: "Mokokchung",
    role: "Upstream weather reference",
    latitude: 26.31393,
    longitude: 94.51675,
  },
};

// PROTOTYPE / DEMONSTRATION GEOMETRY - NOT A REAL FLOOD BOUNDARY.
// The polygon is intentionally simple and only demonstrates a future
// geographic affected-area layer and point-in-polygon workflow.
export const PROTOTYPE_AFFECTED_AREA = {
  id: "prototype-affected-area-01",
  label: "Prototype affected area",
  positions: [
    [27.055, 94.995],
    [27.055, 95.067],
    [26.998, 95.067],
    [26.998, 94.995],
  ],
};

export const PROTOTYPE_SHELTERS = [
  {
    id: "shelter-01",
    name: "Prototype Shelter 01",
    latitude: 27.038,
    longitude: 95.015,
    description:
      "Demonstration shelter location - not an official emergency shelter.",
  },
  {
    id: "shelter-02",
    name: "Prototype Shelter 02",
    latitude: 27.017,
    longitude: 95.043,
    description:
      "Demonstration shelter location - not an official emergency shelter.",
  },
  {
    id: "shelter-03",
    name: "Prototype Shelter 03",
    latitude: 27.041,
    longitude: 95.052,
    description:
      "Demonstration shelter location - not an official emergency shelter.",
  },
];