// Small local geometry helper used only for the prototype location check.
// Polygon positions use the existing [latitude, longitude] map-data format.

const BOUNDARY_EPSILON = 1e-10;

function isValidCoordinate(latitude, longitude) {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}

function isPointOnSegment(
  latitude,
  longitude,
  startLatitude,
  startLongitude,
  endLatitude,
  endLongitude,
) {
  const crossProduct =
    (longitude - startLongitude) * (endLatitude - startLatitude) -
    (latitude - startLatitude) * (endLongitude - startLongitude);

  if (Math.abs(crossProduct) > BOUNDARY_EPSILON) {
    return false;
  }

  const minLatitude = Math.min(startLatitude, endLatitude) - BOUNDARY_EPSILON;
  const maxLatitude = Math.max(startLatitude, endLatitude) + BOUNDARY_EPSILON;
  const minLongitude = Math.min(startLongitude, endLongitude) - BOUNDARY_EPSILON;
  const maxLongitude = Math.max(startLongitude, endLongitude) + BOUNDARY_EPSILON;

  return (
    latitude >= minLatitude &&
    latitude <= maxLatitude &&
    longitude >= minLongitude &&
    longitude <= maxLongitude
  );
}

export function isPointInPolygon(latitude, longitude, polygonPositions) {
  if (!isValidCoordinate(latitude, longitude)) {
    return false;
  }

  if (!Array.isArray(polygonPositions) || polygonPositions.length < 3) {
    return false;
  }

  const vertices = polygonPositions.map((position) => {
    if (
      !Array.isArray(position) ||
      position.length < 2 ||
      !isValidCoordinate(position[0], position[1])
    ) {
      return null;
    }

    return {
      latitude: position[0],
      longitude: position[1],
    };
  });

  if (vertices.some((vertex) => vertex === null)) {
    return false;
  }

  let inside = false;

  for (
    let currentIndex = 0, previousIndex = vertices.length - 1;
    currentIndex < vertices.length;
    previousIndex = currentIndex, currentIndex += 1
  ) {
    const current = vertices[currentIndex];
    const previous = vertices[previousIndex];

    if (
      isPointOnSegment(
        latitude,
        longitude,
        previous.latitude,
        previous.longitude,
        current.latitude,
        current.longitude,
      )
    ) {
      return true;
    }

    const crossesLatitude =
      current.latitude > latitude !== previous.latitude > latitude;

    if (!crossesLatitude) {
      continue;
    }

    const intersectionLongitude =
      ((previous.longitude - current.longitude) *
        (latitude - current.latitude)) /
        (previous.latitude - current.latitude) +
      current.longitude;

    if (longitude < intersectionLongitude) {
      inside = !inside;
    }
  }

  return inside;
}