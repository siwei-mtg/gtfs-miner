import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { useMap } from '@/contexts/MapContext';
import { useAuthContext } from '@/contexts/AuthContext';

interface PassageArcLayerProps {
  projectId: string;
  jourType: number;
  visible?: boolean;
  maxWidthPx?: number;
}

const LAYER_ID = 'passage-arc-layer';
const SOURCE_ID = 'passage-arc';

function buildPaint(mw: number): maplibregl.LinePaint {
  return {
    'line-color': '#ef4444',
    // line_width = weight × maxWidthPx
    'line-width': ['*', ['get', 'weight'], mw] as unknown as maplibregl.DataDrivenPropertyValueSpecification<number>,
    // line_offset = sign(direction) × (line_width/2 + 0.1)
    //   sign(AB) = +1, sign(BA) = -1
    'line-offset': [
      '*',
      ['case', ['==', ['get', 'direction'], 'AB'], 1, -1],
      ['+', ['*', ['*', ['get', 'weight'], mw], 0.5], 0.1],
    ] as unknown as maplibregl.DataDrivenPropertyValueSpecification<number>,
    // Hide arcs with zero passages
    'line-opacity': ['case', ['==', ['get', 'nb_passage'], 0], 0, 1] as unknown as maplibregl.DataDrivenPropertyValueSpecification<number>,
  };
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!,
  );
}

export const PassageArcLayer: React.FC<PassageArcLayerProps> = ({
  projectId,
  jourType,
  visible = true,
  maxWidthPx = 40,
}) => {
  const { map } = useMap();
  const { token } = useAuthContext();
  const popupRef = useRef<maplibregl.Popup | null>(null);

  useEffect(() => {
    if (!map) return;

    // Idempotent source + layer creation (component owns them)
    if (!map.getSource(SOURCE_ID)) {
      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });
    }
    if (!map.getLayer(LAYER_ID)) {
      map.addLayer({
        id: LAYER_ID,
        type: 'line',
        source: SOURCE_ID,
        paint: buildPaint(maxWidthPx),
      });
    } else {
      const p = buildPaint(maxWidthPx);
      map.setPaintProperty(LAYER_ID, 'line-width', p['line-width']);
      map.setPaintProperty(LAYER_ID, 'line-offset', p['line-offset']);
      map.setPaintProperty(LAYER_ID, 'line-opacity', p['line-opacity']);
    }

    map.setLayoutProperty(LAYER_ID, 'visibility', visible ? 'visible' : 'none');

    if (!visible) {
      popupRef.current?.remove();
      popupRef.current = null;
      return;
    }

    const onEnter = (e: maplibregl.MapLayerMouseEvent) => {
      if (!e.features?.length) return;
      const f = e.features[0];
      const nb = f.properties?.nb_passage;
      const dir = f.properties?.direction;
      popupRef.current?.remove();
      popupRef.current = new maplibregl.Popup({ closeButton: false, closeOnClick: false })
        .setLngLat(e.lngLat)
        .setHTML(
          `<div style="font-size:0.8125rem;"><strong>${escapeHtml(String(dir ?? ''))}</strong> · ${nb} passages</div>`,
        )
        .addTo(map);
    };
    const onLeave = () => {
      popupRef.current?.remove();
      popupRef.current = null;
    };
    map.on('mouseenter', LAYER_ID, onEnter);
    map.on('mouseleave', LAYER_ID, onLeave);

    const fetchData = async () => {
      try {
        const res = await fetch(
          `/api/v1/projects/${projectId}/map/passage-arc?jour_type=${jourType}&split_by=none`,
          { headers: token ? { Authorization: `Bearer ${token}` } : {} },
        );
        if (!res.ok) throw new Error('Failed to fetch arc passage data');
        const data = await res.json();
        const src = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
        src?.setData(data);
      } catch (err) {
        console.error('Error loading PassageArcLayer:', err);
      }
    };
    fetchData();

    return () => {
      map.off('mouseenter', LAYER_ID, onEnter);
      map.off('mouseleave', LAYER_ID, onLeave);
      popupRef.current?.remove();
      popupRef.current = null;
    };
  }, [map, visible, projectId, jourType, maxWidthPx, token]);

  return null;
};

PassageArcLayer.displayName = 'PassageArcLayer';
