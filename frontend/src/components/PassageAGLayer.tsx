import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { useMap } from '@/contexts/MapContext';
import { useAuthContext } from '@/contexts/AuthContext';
import { generatePieSvg, generateFallbackCircleSvg, getRouteTypeColor, getRouteTypeLabel } from '@/lib/map-utils';

interface PassageAGLayerProps {
  projectId: string;
  jourType: number;
  visible?: boolean;
  onRouteTypesChange?: (routeTypes: string[]) => void;
  onLoadingChange?: (loading: boolean) => void;
}

const MIN_RADIUS_PX = 6;
const MAX_RADIUS_PX = 30;

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
}

function buildPopupHTML(
  stop_name: string,
  nb_passage_total: number,
  by_route_type: Record<string, number>,
): string {
  const hasBreakdown = Object.keys(by_route_type).length > 0;
  const rows = Object.entries(by_route_type)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(
      ([rt, count]) => `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:0.8125rem;">
          <span style="display:flex;align-items:center;gap:6px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:9999px;background-color:${getRouteTypeColor(rt)};"></span>
            <span>${escapeHtml(getRouteTypeLabel(rt))}</span>
          </span>
          <span style="font-family:ui-monospace,SFMono-Regular,monospace;">${count}</span>
        </div>
      `,
    )
    .join('');
  const fallbackNote = hasBreakdown
    ? ''
    : `<div style="font-size:0.75rem;color:#6b7280;font-style:italic;margin-top:4px;">Données calendrier indisponibles — répartition par ligne non calculable.</div>`;
  return `
    <div style="min-width:180px;">
      <div style="font-weight:600;margin-bottom:2px;">${escapeHtml(stop_name)}</div>
      <div style="font-size:0.75rem;color:#6b7280;margin-bottom:6px;">Total : ${nb_passage_total} passages</div>
      <div style="display:flex;flex-direction:column;gap:2px;">${rows}</div>
      ${fallbackNote}
    </div>
  `;
}

export const PassageAGLayer: React.FC<PassageAGLayerProps> = ({
  projectId,
  jourType,
  visible = true,
  onRouteTypesChange,
  onLoadingChange,
}) => {
  const { map } = useMap();
  const { token } = useAuthContext();
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  useEffect(() => {
    if (!map || !visible) {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
      onRouteTypesChange?.([]);
      return;
    }

    const fetchData = async () => {
      onLoadingChange?.(true);
      try {
        const response = await fetch(`/api/v1/projects/${projectId}/map/passage-ag?jour_type=${jourType}`, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        });
        if (!response.ok) throw new Error('Failed to fetch AG passage data');
        const data = await response.json();

        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        popupRef.current?.remove();
        popupRef.current = null;

        // Proportional-area scaling: radius ∝ √(count / maxCount).
        // Flannery's perception principle — area, not radius, should scale with value.
        const maxCount = Math.max(
          1,
          ...data.features.map((f: any) => f.properties.nb_passage_total ?? 0),
        );

        data.features.forEach((feature: any) => {
          const { coordinates } = feature.geometry;
          const { by_route_type, nb_passage_total, stop_name } = feature.properties;

          const totalVal = Math.max(1, nb_passage_total);
          const radius = Math.max(
            MIN_RADIUS_PX,
            MAX_RADIUS_PX * Math.sqrt(totalVal / maxCount),
          );

          const hasBreakdown = Object.keys(by_route_type ?? {}).length > 0;
          const svgString = hasBreakdown
            ? generatePieSvg(by_route_type, radius)
            : generateFallbackCircleSvg(radius);
          if (!svgString) return;

          const el = document.createElement('div');
          el.innerHTML = svgString;
          el.className = 'cursor-pointer';
          el.title = `${stop_name} (${nb_passage_total} passages)`;

          const marker = new maplibregl.Marker({ element: el })
            .setLngLat([coordinates[0], coordinates[1]])
            .addTo(map);

          // Click-triggered popup, dismissed by close button or map click.
          el.addEventListener('click', (e) => {
            e.stopPropagation();
            popupRef.current?.remove();
            popupRef.current = new maplibregl.Popup({
              closeButton: true,
              closeOnClick: true,
              offset: radius + 4,
            })
              .setLngLat([coordinates[0], coordinates[1]])
              .setHTML(buildPopupHTML(stop_name, nb_passage_total, by_route_type))
              .addTo(map);
          });

          markersRef.current.push(marker);
        });

        const routeTypes = Array.from(
          new Set(
            data.features.flatMap((f: any) =>
              Object.keys(f.properties.by_route_type ?? {}),
            ),
          ),
        ) as string[];
        onRouteTypesChange?.(routeTypes);
      } catch (error) {
        console.error('Error loading PassageAGLayer:', error);
      } finally {
        onLoadingChange?.(false);
      }
    };

    fetchData();

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
    };
  }, [map, visible, projectId, jourType, onRouteTypesChange, onLoadingChange]);

  return null;
};

PassageAGLayer.displayName = 'PassageAGLayer';
