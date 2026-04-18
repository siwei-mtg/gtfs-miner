import React, { useLayoutEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { cn } from '@/lib/utils';
import { MapContext } from '@/contexts/MapContext';
import { useAuthContext } from '@/contexts/AuthContext';
import { PieChartLegend } from '@/components/molecules/PieChartLegend';

interface MapViewProps {
  projectId: string;
  jourType: number;
  className?: string;
  children?: React.ReactNode;
}

export const MapView: React.FC<MapViewProps> = ({
  projectId,
  jourType,
  className,
  children,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { token } = useAuthContext();
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const [e1Visible, setE1Visible] = useState(true);
  const [e4Visible, setE4Visible] = useState(true);
  const [availableRouteTypes, setAvailableRouteTypes] = useState<string[]>([]);
  const [e1Loading, setE1Loading] = useState(false);
  const [e4Loading, setE4Loading] = useState(false);

  // Map initialisation — re-runs only when project or day type changes.
  // Bounds are fetched from the backend BEFORE creating the MapLibre instance
  // so the map opens directly at the project extent (no flash of default Paris).
  useLayoutEffect(() => {
    if (!containerRef.current) return;

    let mounted = true;
    let newMap: maplibregl.Map | null = null;

    const init = async () => {
      let bounds: [[number, number], [number, number]] | undefined;
      try {
        const res = await fetch(`/api/v1/projects/${projectId}/map/bounds`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        });
        if (res.ok) {
          const { min_lng, min_lat, max_lng, max_lat } = await res.json();
          bounds = [[min_lng, min_lat], [max_lng, max_lat]];
        }
      } catch {
        // fall through to default center below
      }

      if (!mounted || !containerRef.current) return;

      const baseOptions: maplibregl.MapOptions = {
        container: containerRef.current,
        style: {
          version: 8,
          sources: {
            osm: {
              type: 'raster',
              tiles: [
                'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'https://b.tile.openstreetmap.org/{z}/{x}/{y}.png',
                'https://c.tile.openstreetmap.org/{z}/{x}/{y}.png',
              ],
              tileSize: 256,
              minzoom: 0,
              maxzoom: 19,
              attribution: '© OpenStreetMap contributors',
            },
          },
          layers: [{ id: 'osm-layer', type: 'raster', source: 'osm' }],
        },
        transformRequest: (url) => {
          // Automatically inject auth header for API requests
          if (token && (url.startsWith('/api') || url.includes('/map/'))) {
            return {
              url,
              headers: { 'Authorization': `Bearer ${token}` }
            };
          }
          return { url };
        },
      };

      newMap = new maplibregl.Map(
        bounds
          ? { ...baseOptions, bounds, fitBoundsOptions: { padding: 50, maxZoom: 14 } }
          : { ...baseOptions, center: [2.3522, 48.8566], zoom: 11 }
      );

      newMap.on('load', () => {
        if (!mounted) return;
        newMap!.resize(); // force canvas to adopt final CSS dimensions
        newMap!.addControl(
          new maplibregl.NavigationControl({ showCompass: false, showZoom: true }),
          'bottom-left',
        );
        setMap(newMap!);
      });
    };

    init();

    return () => {
      mounted = false;
      newMap?.remove();
      setMap(null);
    };
  }, [projectId]); // Map itself does not depend on jourType; layers re-fetch on jourType change.
  // token excluded intentionally — closure is stable enough.

  return (
    <MapContext.Provider value={{ map }}>
      <div className={cn('relative w-full h-full min-h-[400px]', className)} data-testid="map-view">
        <div ref={containerRef} className="w-full h-full" />
        
        {/* Layer Controls */}
        <div className="absolute top-2 right-2 z-10 bg-background/90 backdrop-blur-sm border border-border rounded-md p-2 space-y-1 text-xs shadow-sm">
          <label className="flex items-center gap-2 cursor-pointer hover:bg-accent/50 p-1 rounded transition-colors">
            <input
              type="checkbox"
              aria-label="toggle-e1"
              checked={e1Visible}
              onChange={(e) => setE1Visible(e.target.checked)}
              className="accent-primary"
            />
            E_1 passages-ag
          </label>
          <label className="flex items-center gap-2 cursor-pointer hover:bg-accent/50 p-1 rounded transition-colors">
            <input
              type="checkbox"
              aria-label="toggle-e4"
              checked={e4Visible}
              onChange={(e) => setE4Visible(e.target.checked)}
              className="accent-primary"
            />
            E_4 passages-arc
          </label>
        </div>

        {/* Legend — lists route_types present in the currently-loaded E_1 data */}
        {e1Visible && <PieChartLegend routeTypes={availableRouteTypes} />}

        {/* Loading indicator (top center) — shown while any active layer is fetching */}
        {(e1Loading || e4Loading) && (
          <div
            role="status"
            className="absolute top-2 left-1/2 -translate-x-1/2 z-10 bg-background/90 backdrop-blur-sm border border-border rounded-md px-3 py-1.5 text-xs shadow-sm flex items-center gap-2"
          >
            <span className="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
            Chargement des passages…
          </div>
        )}

        {/* Child Layers (e.g. PassageAGLayer) */}
        {map && children && (
          <div className="hidden">
            {React.Children.map(children, child => {
              if (React.isValidElement(child)) {
                // Pass visibility state to known children layers
                // This is a simple way to sync with the internal checkboxes
                const childType = (child.type as any).displayName || (child.type as any).name;
                if (childType === 'PassageAGLayer') {
                  return React.cloneElement(child as React.ReactElement<any>, {
                    visible: e1Visible,
                    projectId,
                    jourType,
                    onRouteTypesChange: setAvailableRouteTypes,
                    onLoadingChange: setE1Loading,
                  });
                }
                if (childType === 'PassageArcLayer') {
                  return React.cloneElement(child as React.ReactElement<any>, {
                    visible: e4Visible,
                    projectId,
                    jourType,
                    onLoadingChange: setE4Loading,
                  });
                }
                return React.cloneElement(child as React.ReactElement<any>, { visible: true });
              }
              return child;
            })}
          </div>
        )}
      </div>
    </MapContext.Provider>
  );
};
