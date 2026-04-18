import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { PassageAGLayer } from '@/components/PassageAGLayer';
import { MapContext } from '@/contexts/MapContext';
import maplibregl from 'maplibre-gl';

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockMarkerInstance = {
  setLngLat: vi.fn().mockReturnThis(),
  addTo: vi.fn().mockReturnThis(),
  remove: vi.fn(),
};

const mockPopupInstance = {
  setLngLat: vi.fn().mockReturnThis(),
  setHTML: vi.fn().mockReturnThis(),
  addTo: vi.fn().mockReturnThis(),
  remove: vi.fn(),
};

vi.mock('maplibre-gl', () => ({
  default: {
    Marker: vi.fn(() => mockMarkerInstance),
    Popup: vi.fn(() => mockPopupInstance),
  },
}));

const mockToken = 'mock-jwt-token';
vi.mock('@/contexts/AuthContext', () => ({
  useAuthContext: vi.fn(() => ({ token: mockToken })),
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

const mockMap = {
  getLayer: vi.fn(),
  setLayoutProperty: vi.fn(),
};

const mockData = {
  type: 'FeatureCollection',
  features: [
    {
      geometry: { type: 'Point', coordinates: [2.35, 48.85] },
      properties: {
        id_ag_num: 42,
        stop_name: 'Test Stop',
        nb_passage_total: 100,
        by_route_type: { '3': 70, '0': 30 },
      },
    },
  ],
};

function getMarkerElement(): HTMLElement {
  const calls = vi.mocked(maplibregl.Marker).mock.calls;
  expect(calls.length).toBeGreaterThan(0);
  return (calls[0][0] as { element: HTMLElement }).element;
}

describe('PassageAGLayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch data with Authorization header and create markers when visible', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });

    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>
    );

    await vi.waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/api/v1/projects/p1/map/passage-ag?jour_type=1', {
        headers: { 'Authorization': `Bearer ${mockToken}` },
      });
      expect(maplibregl.Marker).toHaveBeenCalled();
    });

    expect(mockMarkerInstance.setLngLat).toHaveBeenCalledWith([2.35, 48.85]);
    expect(mockMarkerInstance.addTo).toHaveBeenCalledWith(mockMap);
  });

  it('should remove markers on unmount', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });

    const { unmount } = render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>
    );

    await vi.waitFor(() => expect(maplibregl.Marker).toHaveBeenCalled());

    unmount();

    expect(mockMarkerInstance.remove).toHaveBeenCalled();
  });

  it('should not fetch data if not visible', () => {
    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer projectId="p1" jourType={1} visible={false} />
      </MapContext.Provider>
    );

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it('should show Popup on hover and remove on mouse leave', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });

    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>
    );

    await vi.waitFor(() => expect(maplibregl.Marker).toHaveBeenCalled());

    const el = getMarkerElement();

    act(() => {
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    });

    expect(maplibregl.Popup).toHaveBeenCalled();
    expect(mockPopupInstance.setLngLat).toHaveBeenCalledWith([2.35, 48.85]);
    expect(mockPopupInstance.addTo).toHaveBeenCalledWith(mockMap);

    const html = mockPopupInstance.setHTML.mock.calls[0][0] as string;
    expect(html).toContain('Test Stop');
    expect(html).toContain('100');
    expect(html).toContain('Bus');
    expect(html).toContain('Tramway');

    // Hover config must not include a close button or close-on-click behaviour.
    const popupArgs = vi.mocked(maplibregl.Popup).mock.calls[0][0] as {
      closeButton?: boolean;
      closeOnClick?: boolean;
    };
    expect(popupArgs.closeButton).toBe(false);
    expect(popupArgs.closeOnClick).toBe(false);

    // Leaving the marker removes the popup.
    const removeCallsBefore = mockPopupInstance.remove.mock.calls.length;
    act(() => {
      el.dispatchEvent(new MouseEvent('mouseleave', { bubbles: true }));
    });
    expect(mockPopupInstance.remove.mock.calls.length).toBeGreaterThan(removeCallsBefore);
  });

  it('should render fallback marker when by_route_type is empty but total > 0', async () => {
    const fallbackData = {
      type: 'FeatureCollection',
      features: [
        {
          geometry: { type: 'Point', coordinates: [2.35, 48.85] },
          properties: {
            id_ag_num: 42,
            stop_name: 'Broken Calendar Stop',
            nb_passage_total: 86,
            by_route_type: {},
          },
        },
      ],
    };
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => fallbackData });

    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer projectId="p1" jourType={1} visible={true} />
      </MapContext.Provider>
    );

    await vi.waitFor(() => expect(maplibregl.Marker).toHaveBeenCalled());

    // Marker still created (fallback SVG populated)
    expect(mockMarkerInstance.setLngLat).toHaveBeenCalledWith([2.35, 48.85]);

    // Hover shows a popup with the fallback note
    const el = getMarkerElement();
    act(() => {
      el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
    });
    const html = mockPopupInstance.setHTML.mock.calls[0][0] as string;
    expect(html).toContain('Broken Calendar Stop');
    expect(html).toContain('86');
    expect(html).toContain('Données calendrier indisponibles');
  });

  it('should report loading state via onLoadingChange around fetch', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });
    const onLoadingChange = vi.fn();

    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer
          projectId="p1"
          jourType={1}
          visible={true}
          onLoadingChange={onLoadingChange}
        />
      </MapContext.Provider>
    );

    await vi.waitFor(() => expect(maplibregl.Marker).toHaveBeenCalled());

    // Sequence: true (start) → false (finally).
    expect(onLoadingChange).toHaveBeenCalledWith(true);
    expect(onLoadingChange).toHaveBeenCalledWith(false);
    const lastCall = onLoadingChange.mock.calls.at(-1);
    expect(lastCall?.[0]).toBe(false);
  });

  it('should emit unique route_types via onRouteTypesChange after fetch', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => mockData });
    const onRouteTypesChange = vi.fn();

    render(
      <MapContext.Provider value={{ map: mockMap as any }}>
        <PassageAGLayer
          projectId="p1"
          jourType={1}
          visible={true}
          onRouteTypesChange={onRouteTypesChange}
        />
      </MapContext.Provider>
    );

    await vi.waitFor(() => {
      const lastCall = onRouteTypesChange.mock.calls.at(-1)?.[0];
      expect(lastCall).toBeDefined();
      expect(new Set(lastCall)).toEqual(new Set(['0', '3']));
    });
  });
});
