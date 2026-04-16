import { createContext, useContext } from 'react';
import maplibregl from 'maplibre-gl';

interface MapContextType {
  map: maplibregl.Map | null;
}

export const MapContext = createContext<MapContextType>({ map: null });

export const useMap = () => useContext(MapContext);
