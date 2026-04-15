import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { cn } from '@/lib/utils';

interface MapViewProps {
  projectId: string;
  jourType: number;
  onStopClick?: (idAgNum: number) => void;
  className?: string;
}

export const MapView: React.FC<MapViewProps> = ({
  projectId,
  jourType,
  onStopClick,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onStopClickRef = useRef(onStopClick);
  const [e1Visible, setE1Visible] = useState(true);
  const [e4Visible, setE4Visible] = useState(true);

  // Keep callback ref in sync without triggering map re-init
  useEffect(() => {
    onStopClickRef.current = onStopClick;
  }, [onStopClick]);

  // Map initialisation — re-runs only when project or day type changes
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '© OpenStreetMap contributors',
          },
        },
        layers: [{ id: 'osm-layer', type: 'raster', source: 'osm' }],
      },
      center: [2.3522, 48.8566],
      zoom: 11,
    });

    mapRef.current = map;

    map.on('load', () => {
      // E_1 — passage-ag (stop circles)
      map.addSource('passage-ag', {
        type: 'geojson',
        data: `/api/v1/projects/${projectId}/layers/e1?jour_type=${jourType}`,
      });
      map.addLayer({
        id: 'passage-ag-layer',
        type: 'circle',
        source: 'passage-ag',
        paint: { 'circle-radius': 5, 'circle-color': '#3b82f6' },
      });

      // E_4 — passage-arc (directed arcs)
      map.addSource('passage-arc', {
        type: 'geojson',
        data: `/api/v1/projects/${projectId}/layers/e4?jour_type=${jourType}`,
      });
      map.addLayer({
        id: 'passage-arc-layer',
        type: 'line',
        source: 'passage-arc',
        paint: { 'line-color': '#ef4444', 'line-width': 2 },
      });

      // Click on AG stop → call consumer callback
      map.on('click', 'passage-ag-layer', (e) => {
        const feature = e.features?.[0];
        if (feature?.properties?.['id_ag_num'] !== undefined) {
          onStopClickRef.current?.(feature.properties['id_ag_num'] as number);
        }
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [projectId, jourType]);

  // Toggle E_1 visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('passage-ag-layer')) return;
    map.setLayoutProperty('passage-ag-layer', 'visibility', e1Visible ? 'visible' : 'none');
  }, [e1Visible]);

  // Toggle E_4 visibility
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer('passage-arc-layer')) return;
    map.setLayoutProperty('passage-arc-layer', 'visibility', e4Visible ? 'visible' : 'none');
  }, [e4Visible]);

  return (
    <div className={cn('relative w-full h-full', className)} data-testid="map-view">
      <div ref={containerRef} className="absolute inset-0" />
      <div className="absolute top-2 right-2 z-10 bg-background border border-border rounded-md p-2 space-y-1 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label="toggle-e1"
            checked={e1Visible}
            onChange={(e) => setE1Visible(e.target.checked)}
          />
          E_1 passages-ag
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            aria-label="toggle-e4"
            checked={e4Visible}
            onChange={(e) => setE4Visible(e.target.checked)}
          />
          E_4 passages-arc
        </label>
      </div>
    </div>
  );
};
