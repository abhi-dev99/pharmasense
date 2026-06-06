"use client";

import React, { useState, useCallback } from 'react';
import Map, { Source, Layer, Popup } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import useSWR from 'swr';
import { Loader2, Activity } from 'lucide-react';

// Light and dark mode style URLs (open, no token required)
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
const DARK_STYLE  = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

interface Props {
  darkMode?: boolean;
  initialDisease?: string;
}

const fetcher = (url: string) => fetch(url).then(r => r.json());

const DISEASES = [
  { id: 'dengue', label: 'Dengue' },
  { id: 'malaria', label: 'Malaria' },
  { id: 'typhoid', label: 'Typhoid' },
];

export function IndiaHeatmap({ darkMode = false, initialDisease = "dengue" }: Props) {
  const [disease, setDisease] = useState(initialDisease);
  const { data, error, isLoading } = useSWR(`/api/v1/risk/national?disease=${disease}`, fetcher);
  const [hoverInfo, setHoverInfo] = useState<{
    longitude: number;
    latitude: number;
    districtName: string;
    riskScore: number;
    cases: number;
  } | null>(null);

  const onHover = useCallback((event: any) => {
    const {
      features,
      lngLat: { lng, lat }
    } = event;
    const hoveredFeature = features && features[0];

    if (hoveredFeature) {
      setHoverInfo({
        longitude: lng,
        latitude: lat,
        districtName: hoveredFeature.properties.name,
        riskScore: hoveredFeature.properties.mag / 5,
        cases: hoveredFeature.properties.cases || 0,
      });
    } else {
      setHoverInfo(null);
    }
  }, []);

  // Fallback to empty geojson while loading
  const geoData = data || { type: 'FeatureCollection', features: [] };

  return (
    <div className="w-full h-[600px] rounded-xl overflow-hidden border border-gray-200 shadow-sm relative group">
      {/* Disease Selector */}
      <div className="absolute top-4 left-4 z-20 bg-white/90 backdrop-blur-sm rounded-lg p-1.5 shadow-md border border-gray-100 flex gap-1">
        {DISEASES.map(d => (
          <button
            key={d.id}
            onClick={() => setDisease(d.id)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-colors ${
              disease === d.id 
                ? 'bg-[#111111] text-white shadow-sm' 
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-10 backdrop-blur-[1px]">
          <Loader2 className="w-8 h-8 animate-spin text-[#111111]" />
        </div>
      )}
      
      <Map
        initialViewState={{ longitude: 82, latitude: 22, zoom: 3.8 }}
        mapStyle={darkMode ? DARK_STYLE : LIGHT_STYLE}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
        interactiveLayerIds={['heatmap-points']}
        onMouseMove={onHover}
        onMouseLeave={() => setHoverInfo(null)}
      >
        <Source type="geojson" data={geoData}>
          <Layer
            id="heatmap-layer"
            type="heatmap"
            paint={{
              'heatmap-weight':     ['interpolate', ['linear'], ['get', 'mag'], 0, 0, 5, 1],
              'heatmap-intensity':  ['interpolate', ['linear'], ['zoom'], 0, 1, 9, 3],
              'heatmap-color': [
                'interpolate', ['linear'], ['heatmap-density'],
                0,   'rgba(0,0,0,0)',
                0.1, 'rgba(255,200,200,0.4)',
                0.3, '#fca5a5',
                0.5, '#f87171',
                0.7, '#ef4444',
                0.9, '#dc2626',
                1,   '#991b1b',
              ],
              'heatmap-radius':  ['interpolate', ['linear'], ['zoom'], 0, 20, 9, 40],
              'heatmap-opacity': 0.85,
            }}
          />
          {/* Invisible circle layer for hover events */}
          <Layer
            id="heatmap-points"
            type="circle"
            paint={{
              'circle-radius': 15,
              'circle-color': 'rgba(0,0,0,0)',
            }}
          />
        </Source>

        {hoverInfo && (
          <Popup
            longitude={hoverInfo.longitude}
            latitude={hoverInfo.latitude}
            offset={[0, -10]}
            closeButton={false}
            className="z-50"
            anchor="bottom"
          >
            <div className="p-2 min-w-[150px]">
              <div className="font-bold text-gray-900 mb-2 text-sm">{hoverInfo.districtName}</div>
              <div className="flex items-center gap-2 text-xs mb-1">
                <Activity className="w-3 h-3 text-red-500 shrink-0" />
                <span className="text-gray-500">Risk Level:</span>
                <span className={`font-semibold ${hoverInfo.riskScore > 0.6 ? 'text-red-600' : hoverInfo.riskScore > 0.3 ? 'text-orange-500' : 'text-emerald-600'}`}>
                  {hoverInfo.riskScore > 0.6 ? 'HIGH' : hoverInfo.riskScore > 0.3 ? 'MEDIUM' : 'LOW'}
                </span>
              </div>
              {hoverInfo.cases > 0 && (
                <div className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500">Reported Cases:</span>
                  <span className="font-semibold text-gray-800">{hoverInfo.cases.toLocaleString('en-IN')}</span>
                </div>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {/* Legend overlay */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-md border border-gray-100 text-xs z-20 pointer-events-none">
        <p className="font-semibold text-gray-700 mb-2">Risk Intensity</p>
        <div className="flex items-center gap-1">
          <div className="h-2 w-20 rounded-full" style={{ background: 'linear-gradient(to right, rgba(252,165,165,0.4), #ef4444, #991b1b)' }} />
        </div>
        <div className="flex justify-between text-gray-400 mt-1">
          <span>Low</span><span>High</span>
        </div>
      </div>
    </div>
  );
}
