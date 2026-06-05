"use client";

import React, { useMemo } from 'react';
import Map, { Source, Layer } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

// Light and dark mode style URLs (open, no token required)
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';
const DARK_STYLE  = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

interface Props {
  darkMode?: boolean;
}

export function IndiaHeatmap({ darkMode = false }: Props) {
  const data = useMemo(() => {
    const points: any[] = [];
    const clusters = [
      [77.2, 28.6], // Delhi
      [72.8, 19.0], // Mumbai
      [77.5, 12.9], // Bangalore
      [80.2, 13.0], // Chennai
      [88.3, 22.5], // Kolkata
      [78.4, 17.3], // Hyderabad
      [73.8, 18.5], // Pune
      [75.8, 26.9], // Jaipur
      [72.5, 23.0], // Ahmedabad
      [80.9, 26.8], // Lucknow
      [76.7, 30.7], // Chandigarh
      [85.8, 20.3], // Bhubaneswar
      [91.7, 26.1], // Guwahati
      [77.0, 8.5],  // Thiruvananthapuram
      [73.0, 22.3], // Surat
    ];

    clusters.forEach(cluster => {
      const numPoints = Math.floor(15 + Math.random() * 25);
      for (let i = 0; i < numPoints; i++) {
        points.push({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [
              cluster[0] + (Math.random() - 0.5) * 3,
              cluster[1] + (Math.random() - 0.5) * 3,
            ],
          },
          properties: { mag: Math.random() * 5 },
        });
      }
    });

    return { type: 'FeatureCollection', features: points };
  }, []);

  return (
    <div className="w-full h-[600px] rounded-xl overflow-hidden border border-gray-200 shadow-sm relative">
      <Map
        initialViewState={{ longitude: 82, latitude: 22, zoom: 3.8 }}
        mapStyle={darkMode ? DARK_STYLE : LIGHT_STYLE}
        style={{ width: '100%', height: '100%' }}
        attributionControl={false}
      >
        <Source type="geojson" data={data as any}>
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
        </Source>
      </Map>

      {/* Legend overlay */}
      <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg p-3 shadow-md border border-gray-100 text-xs">
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
