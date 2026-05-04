import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { API_ORIGIN } from '@/api/client';
import { useMap } from '@/contexts/MapContext';
import { useAuthContext } from '@/contexts/AuthContext';
import { generatePieSvg, generateFallbackCircleSvg, getRouteTypeColor, getRouteTypeLabel } from '@/lib/map-utils';
import { buildPassageMapQuery, type SousLigneKey } from '@/lib/passage-map-query';
import { fetchPassageAG } from '@/lib/passage-ag-cache';

interface PassageAGLayerProps {
  projectId: string;
  jourType: number;
  /** Optional: restrict pies to these lignes (id_ligne_num).  Empty = no filter. */
  ligneIds?: number[];
  /** Optional: restrict pies to these (id_ligne_num, sous_ligne) pairs.  Empty = no filter. */
  sousLigneKeys?: SousLigneKey[];
  visible?: boolean;
  onRouteTypesChange?: (routeTypes: string[]) => void;
  onLoadingChange?: (loading: boolean) => void;
  /** Fired when the user clicks a marker.  shiftKey lets the Dashboard
   *  discriminate additive (Shift) vs replace-single selection. */
  onStopClick?: (idAgNum: number, shiftKey: boolean) => void;
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
  ligneIds,
  sousLigneKeys,
  visible = true,
  onRouteTypesChange,
  onLoadingChange,
  onStopClick,
}) => {
  const { map } = useMap();
  const { token } = useAuthContext();
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  // Stable fetch key — strings compare by value so array refs don't matter.
  const qs = buildPassageMapQuery({ jourType, ligneIds, sousLigneKeys });

  useEffect(() => {
    if (!map || !visible) {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
      onRouteTypesChange?.([]);
      return;
    }

    // Guard against late responses from a previous fetch overwriting fresh
    // markers — e.g. the slow initial unfiltered fetch returning after the
    // user has already picked a ligne and the filtered fetch landed.
    let cancelled = false;

    const fetchData = async () => {
      onLoadingChange?.(true);
      try {
        const url = `${API_ORIGIN}/api/v1/projects/${projectId}/map/passage-ag?${qs}`;
        const cacheKey = `${projectId}|${qs}`;
        const data = await fetchPassageAG<any>(url, cacheKey, token);
        if (cancelled) return;

        markersRef.current.forEach((m) => m.remove());
        markersRef.current = [];
        popupRef.current?.remove();
        popupRef.current = null;

        // Proportional-area scaling: radius ∝ √(count / maxCount).
        // Flannery's perception principle — area, not radius, should scale with value.
        // Prefer the global max returned by the backend (independent of ligne /
        // sous-ligne filters) so a filtered view stays visually comparable to the
        // unfiltered one.  Fall back to a local max for legacy responses.
        const localMax = Math.max(
          0,
          ...data.features.map((f: any) => f.properties.nb_passage_total ?? 0),
        );
        const maxCount = Math.max(1, data.max_passage_total ?? localMax);

        data.features.forEach((feature: any) => {
          const { coordinates } = feature.geometry;
          const { id_ag_num, by_route_type, nb_passage_total, stop_name } = feature.properties;

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

            if (typeof id_ag_num === 'number') {
              onStopClick?.(id_ag_num, e.shiftKey);
            }
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
        if (!cancelled) console.error('Error loading PassageAGLayer:', error);
      } finally {
        if (!cancelled) onLoadingChange?.(false);
      }
    };

    fetchData();

    return () => {
      cancelled = true;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      popupRef.current?.remove();
      popupRef.current = null;
    };
  }, [map, visible, projectId, qs, onRouteTypesChange, onLoadingChange]);

  return null;
};

PassageAGLayer.displayName = 'PassageAGLayer';
