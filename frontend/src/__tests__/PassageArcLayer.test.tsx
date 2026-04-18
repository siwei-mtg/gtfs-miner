import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { PassageArcLayer } from '@/components/PassageArcLayer';
import { MapContext } from '@/contexts/MapContext';
import maplibregl from 'maplibre-gl';

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockPopupInstance = {
  setLngLat: vi.fn().mockReturnThis(),
  setHTML: vi.fn().mockReturnThis(),
  addTo: vi.fn().mockReturnThis(),
  remove: vi.fn(),
};

vi.mock('maplibre-gl', () => ({
  default: {
    Popup: vi.fn(() => mockPopupInstance),
  },
}));

const mockToken = 'mock-jwt-token';
vi.mock('@/contexts/AuthContext', () => ({
  useAuthContext: vi.fn(() => ({ token: mockToken })),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

type Handler = (e: any) => void;
interface MockMap {
  getSource: ReturnType<typeof vi.fn>;
  addSource: ReturnType<typeof vi.fn>;
  getLayer: ReturnType<typeof vi.fn>;
  addLayer: ReturnType<typeof vi.fn>;
  setLayoutProperty: ReturnType<typeof vi.fn>;
  setPaintProperty: ReturnType<typeof vi.fn>;
  on: ReturnType<typeof vi.fn>;
  off: ReturnType<typeof vi.fn>;
  __handlers: Record<string, Handler>;
  __source: { setData: ReturnType<typeof vi.fn> };
  __hasLayer: boolean;
  __hasSource: boolean;
}

function createMockMap(): MockMap {
  const m: Partial<MockMap> = {};
  m.__handlers = {};
  m.__source = { setData: vi.fn() };
  m.__hasLayer = false;
  m.__hasSource = false;

  m.getSource = vi.fn((id: string) => (m.__hasSource && id === 'passage-arc' ? m.__source : undefined));
  m.addSource = vi.fn(() => { m.__hasSource = true; });
  m.getLayer = vi.fn((id: string) => (m.__hasLayer && id === 'passage-arc-layer' ? { id } : undefined));
  m.addLayer = vi.fn(() => { m.__hasLayer = true; });
  m.setLayoutProperty = vi.fn();
  m.setPaintProperty = vi.fn();
  m.on = vi.fn((event: string, layerIdOrHandler: string | Handler, maybeHandler?: Handler) => {
    const key = typeof layerIdOrHandler === 'string' ? `${event}:${layerIdOrHandler}` : event;
    const handler = typeof layerIdOrHandler === 'string' ? (maybeHandler as Handler) : (layerIdOrHandler as Handler);
    m.__handlers![key] = handler;
  });
  m.off = vi.fn();

  return m as MockMap;
}

const mockData = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[2.35, 48.85], [2.40, 48.88]] },
      properties: {
        id_ag_num_a: 1,
        id_ag_num_b: 2,
        nb_passage: 100,
        direction: 'AB',
        weight: 1.0,
        split_by: 'none',
      },
    },
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[2.40, 48.88], [2.35, 48.85]] },
      properties: {
        id_ag_num_a: 2,
        id_ag_num_b: 1,
        nb_passage: 40,
        direction: 'BA',
        weight: 0.4,
        split_by: 'none',
      },
    },
  ],
};

describe('PassageArcLayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should populate source with both AB and BA features', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });
    const map = createMockMap();

    render(
      <MapContext.Provider value={{ map: map as any }}>
        <PassageArcLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>,
    );

    await vi.waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/projects/p1/map/passage-arc?jour_type=1&split_by=none',
        { headers: { Authorization: `Bearer ${mockToken}` } },
      );
      expect(map.__source.setData).toHaveBeenCalled();
    });

    const payload = map.__source.setData.mock.calls[0][0];
    const directions = payload.features.map((f: any) => f.properties.direction);
    expect(directions).toContain('AB');
    expect(directions).toContain('BA');
  });

  it('should show tooltip with nb_passage on hover', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });
    const map = createMockMap();

    render(
      <MapContext.Provider value={{ map: map as any }}>
        <PassageArcLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>,
    );

    await vi.waitFor(() => expect(map.__source.setData).toHaveBeenCalled());

    const enterHandler = map.__handlers['mouseenter:passage-arc-layer'];
    expect(enterHandler).toBeDefined();

    enterHandler({
      lngLat: { lng: 2.375, lat: 48.865 },
      features: [
        { properties: { nb_passage: 100, direction: 'AB' } },
      ],
    });

    expect(maplibregl.Popup).toHaveBeenCalled();
    expect(mockPopupInstance.setLngLat).toHaveBeenCalledWith({ lng: 2.375, lat: 48.865 });
    const html = mockPopupInstance.setHTML.mock.calls[0][0] as string;
    expect(html).toContain('100');
    expect(html).toContain('AB');
  });

  it('should apply maxWidthPx prop to paint line-width expression', () => {
    const map = createMockMap();
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ type: 'FeatureCollection', features: [] }) });

    render(
      <MapContext.Provider value={{ map: map as any }}>
        <PassageArcLayer projectId="p1" jourType={1} visible={true} maxWidthPx={20} />
      </MapContext.Provider>,
    );

    expect(map.addLayer).toHaveBeenCalled();
    const layerSpec = map.addLayer.mock.calls[0][0];
    // line-width: ['*', ['get', 'weight'], 20]
    expect(layerSpec.paint['line-width']).toEqual(['*', ['get', 'weight'], 20]);
    // line-offset expression should also embed 20
    const offsetStr = JSON.stringify(layerSpec.paint['line-offset']);
    expect(offsetStr).toContain('20');
  });
});
