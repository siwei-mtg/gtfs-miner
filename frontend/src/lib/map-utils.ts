/**
 * Standard colors for GTFS route types.
 */
export const ROUTE_TYPE_COLORS: Record<string, string> = {
  '0': '#42abef', // Tramway (Sky Blue)
  '1': '#ee1c25', // Metro (Red)
  '2': '#f18c22', // Rail (Orange)
  '3': '#00a44d', // Bus (Green)
  '4': '#1a4494', // Ferry (Navy Blue)
  '5': '#9c27b0', // Cable Car (Purple)
  '6': '#9c27b0', // Gondola
  '7': '#9c27b0', // Funicular
  '11': '#6d4c41', // Trolleybus (Brown)
  '12': '#9c27b0', // Monorail
  default: '#757575', // Unknown (Grey)
};

/**
 * Returns the color associated with a route_type.
 */
export function getRouteTypeColor(routeType: string): string {
  return ROUTE_TYPE_COLORS[routeType] || ROUTE_TYPE_COLORS.default;
}

/**
 * Human-readable labels for GTFS route types (French).
 */
export const ROUTE_TYPE_LABELS: Record<string, string> = {
  '0': 'Tramway',
  '1': 'Métro',
  '2': 'Train',
  '3': 'Bus',
  '4': 'Ferry',
  '5': 'Téléphérique',
  '6': 'Gondole',
  '7': 'Funiculaire',
  '11': 'Trolleybus',
  '12': 'Monorail',
};

export function getRouteTypeLabel(routeType: string): string {
  return ROUTE_TYPE_LABELS[routeType] ?? `Type ${routeType}`;
}

/**
 * Generates an SVG pie chart as a string.
 * @param data Mapping of category (route_type) to count.
 * @param radius Radius of the pie chart.
 */
export function generatePieSvg(data: Record<string, number>, radius: number): string {
  const total = Object.values(data).reduce((sum, val) => sum + val, 0);
  if (total === 0) return '';

  let cumulativeAngle = 0;
  const sectors: string[] = [];

  // Sort keys for deterministic rendering
  const sortedKeys = Object.keys(data).sort();

  sortedKeys.forEach((key) => {
    const value = data[key];
    const angle = (value / total) * 360;
    const color = getRouteTypeColor(key);

    if (angle >= 360) {
      sectors.push(`<circle cx="${radius}" cy="${radius}" r="${radius}" fill="${color}" />`);
    } else if (angle > 0) {
      const x1 = radius + radius * Math.cos((Math.PI * (cumulativeAngle - 90)) / 180);
      const y1 = radius + radius * Math.sin((Math.PI * (cumulativeAngle - 90)) / 180);
      
      cumulativeAngle += angle;
      
      const x2 = radius + radius * Math.cos((Math.PI * (cumulativeAngle - 90)) / 180);
      const y2 = radius + radius * Math.sin((Math.PI * (cumulativeAngle - 90)) / 180);
      
      const largeArcFlag = angle > 180 ? 1 : 0;
      
      const pathData = [
        `M ${radius} ${radius}`,
        `L ${x1} ${y1}`,
        `A ${radius} ${radius} 0 ${largeArcFlag} 1 ${x2} ${y2}`,
        'Z',
      ].join(' ');
      
      sectors.push(`<path d="${pathData}" fill="${color}" stroke="white" stroke-width="0.5" />`);
    }
  });

  const size = radius * 2;
  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
      ${sectors.join('\n')}
      <circle cx="${radius}" cy="${radius}" r="${radius}" fill="none" stroke="white" stroke-width="1" />
    </svg>
  `;
}

/**
 * Neutral-color fallback circle used when a stop has a valid passage total
 * but the per-route_type breakdown is unavailable (e.g. broken D2 calendar).
 */
export function generateFallbackCircleSvg(radius: number, color: string = '#94a3b8'): string {
  const size = radius * 2;
  return `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${radius}" cy="${radius}" r="${radius}" fill="${color}" fill-opacity="0.7" stroke="#475569" stroke-width="1" />
    </svg>
  `;
}
