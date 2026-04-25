import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MapView } from '@/components/organisms/MapView';

// ── maplibre-gl mock ─────────────────────────────────────────────────────────
// Captures load and click callbacks so tests can invoke them manually.
// Must be declared in module scope before vi.mock() factory runs.

let loadCallback: (() => void) | undefined;
let clickCallback:
  | ((e: { features?: Array<{ properties: Record<string, unknown> }> }) => void)
  | undefined;

const mockMapInstance = {
  on: vi.fn(
    (
      event: string,
      layerOrCallback: string | (() => void),
      callback?: (e: { features?: Array<{ properties: Record<string, unknown> }> }) => void,
    ) => {
      if (event === 'load' && typeof layerOrCallback === 'function') {
        loadCallback = layerOrCallback as () => void;
      }
      if (event === 'click' && layerOrCallback === 'passage-ag-layer' && callback) {
        clickCallback = callback;
      }
    },
  ),
  addSource: vi.fn(),
  addLayer: vi.fn(),
  getLayer: vi.fn(() => true),
  setLayoutProperty: vi.fn(),
  remove: vi.fn(),
};

vi.mock('maplibre-gl', () => ({
  default: {
    Map: vi.fn(() => mockMapInstance),
  },
}));

// ── Tests ────────────────────────────────────────────────────────────────────

describe('MapView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadCallback = undefined;
    clickCallback = undefined;
    // Restore getLayer mock after clearAllMocks resets it
    mockMapInstance.getLayer.mockReturnValue(true);
  });

  it('test_mapview_renders', () => {
    render(<MapView projectId="proj-1" jourType={1} />);
    expect(screen.getByTestId('map-view')).toBeInTheDocument();
  });

  it('test_layer_toggles_visible', () => {
    render(<MapView projectId="proj-1" jourType={1} />);

    const e1Toggle = screen.getByRole('checkbox', { name: /toggle-e1/i });
    const e4Toggle = screen.getByRole('checkbox', { name: /toggle-e4/i });

    // Both start checked
    expect(e1Toggle).toBeChecked();
    expect(e4Toggle).toBeChecked();

    // Uncheck E_1
    fireEvent.click(e1Toggle);
    expect(e1Toggle).not.toBeChecked();

    // Re-check E_1
    fireEvent.click(e1Toggle);
    expect(e1Toggle).toBeChecked();

    // Uncheck E_4
    fireEvent.click(e4Toggle);
    expect(e4Toggle).not.toBeChecked();
  });

  it('test_stop_click_callback', () => {
    const onStopClick = vi.fn();
    render(<MapView projectId="proj-1" jourType={1} onStopClick={onStopClick} />);

    // Simulate the map 'load' event to trigger source/layer/click registration
    expect(loadCallback).toBeDefined();
    loadCallback!();

    // After load, the click handler on 'passage-ag-layer' should be registered
    expect(clickCallback).toBeDefined();

    // Simulate a map click on an AG feature
    clickCallback!({
      features: [{ properties: { id_ag_num: 42 } }],
    });

    expect(onStopClick).toHaveBeenCalledOnce();
    expect(onStopClick).toHaveBeenCalledWith(42);
  });
});
