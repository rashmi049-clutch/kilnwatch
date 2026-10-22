// Small geodesy helpers: distances on the sphere (good to <0.5% at NCR scale) and
// circle polygons for the 800 m CPCB siting rings.
const R = 6371008.8;
const rad = (d: number) => (d * Math.PI) / 180;

export function distM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const dLat = rad(lat2 - lat1), dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

export function circle(lat: number, lon: number, radiusM: number, steps = 48): [number, number][] {
  const ring: [number, number][] = [];
  const dLat = (radiusM / R) * (180 / Math.PI);
  const dLon = dLat / Math.cos(rad(lat));
  for (let i = 0; i <= steps; i++) {
    const t = (2 * Math.PI * i) / steps;
    ring.push([+(lon + dLon * Math.cos(t)).toFixed(6), +(lat + dLat * Math.sin(t)).toFixed(6)]);
  }
  return ring;
}

export const googleSat = (lat: number, lon: number) =>
  `https://www.google.com/maps/place/${lat},${lon}/@${lat},${lon},250m/data=!3m1!1e3`;
export const waybackLink = (lat: number, lon: number) =>
  `https://livingatlas.arcgis.com/wayback/#mapCenter=${lon}%2C${lat}%2C17`;
