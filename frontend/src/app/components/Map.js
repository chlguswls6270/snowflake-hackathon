'use client';

import { useEffect, useState, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default Leaflet icons (though we mainly use polygons, still good to have)
import 'leaflet-defaulticon-compatibility/dist/leaflet-defaulticon-compatibility.css';
import 'leaflet-defaulticon-compatibility';

// A component to handle map flying/zooming
function MapController({ activeBounds }) {
  const map = useMap();
  
  useEffect(() => {
    if (activeBounds) {
      map.flyToBounds(activeBounds, {
        paddingTopLeft: [480, 50], // Dodge Left Sidebar (420w + 32px gap)
        paddingBottomRight: [50, 150], // Dodge Bottom Prompt Bar
        maxZoom: 15, // Lifted threshold to allow deep dive into individual neighborhoods
        duration: 1.5,
        easeLinearity: 0.25
      });
    }
  }, [activeBounds, map]);

  return null;
}

export default function Map({ apartments, activeDong, setActiveDong }) {
  const [geoData, setGeoData] = useState(null);
  const [activeBounds, setActiveBounds] = useState(null);
  const geoJsonRef = useRef(null);

  // The top 5 recommended Dongs to highlight
  const allDongs = apartments.map(apt => apt.emd);
  const top5Dongs = apartments.slice(0, 5).map(apt => apt.emd);

  useEffect(() => {
    // Fetch newly merged Legal Dong Map Data (법정동 병합 버전)
    fetch('/seoul_geo_merged.json')
      .then(res => res.json())
      .then(data => {
        setGeoData(data);
      })
      .catch(err => console.error("Failed to load map regions:", err));
  }, []);

  // Global robust matcher logic
  const isDongMatch = (polygonName, dbName) => {
    if (!dbName || !polygonName) return false;
    if (dbName === polygonName) return true;
    if (dbName.startsWith(polygonName)) return true;
    if (polygonName.endsWith('가동') && dbName.startsWith(polygonName.replace('가동', ''))) return true;
    
    const legalToAdminMap = {
      '우면동': '양재동', '원지동': '양재동', '신원동': '내곡동',
      '염곡동': '내곡동', '포이동': '개포동', '일원동': '개포동'
    };
    if (legalToAdminMap[dbName] === polygonName) return true;
    if (legalToAdminMap[dbName] && legalToAdminMap[dbName].startsWith(polygonName)) return true;
    return false;
  };

  useEffect(() => {
    // When apartments are updated, find the collective bounding box of all recommended areas
    if (apartments && apartments.length > 0 && geoJsonRef.current) {
      setTimeout(() => {
        if (!geoJsonRef.current) return;
        
        let hasValidBounds = false;
        const groupBounds = L.latLngBounds();

        geoJsonRef.current.eachLayer((layer) => {
          if (!layer.feature || !layer.feature.properties) return;
          
          let dongName = layer.feature.properties.name;
          if (dongName === '여의동') dongName = '여의도동';
          
          const isRec = apartments.some(apt => isDongMatch(dongName, apt.emd));
          if (isRec && layer.getBounds) {
            groupBounds.extend(layer.getBounds());
            hasValidBounds = true;
          }
        });

        if (hasValidBounds) {
          setActiveBounds(groupBounds);
        }
      }, 150); // slight debounce to ensure Leaflet rendered the GEO JSON
    }
  }, [apartments, geoData]);

  const onEachFeature = (feature, layer) => {
    let dongName = feature.properties.name;
    
    // Exception Mapping: Administrative '여의동' -> Legal '여의도동' (Matches DB)
    if (dongName === '여의동') dongName = '여의도동';

    const matchDong = (dbDong) => isDongMatch(dongName, dbDong);

    const matchedIndex = apartments.findIndex(apt => matchDong(apt.emd));
    const isRecommended = matchedIndex !== -1;
    const isTop5 = isRecommended && matchedIndex < 5;
    const rank = isRecommended ? matchedIndex + 1 : null;
    const isActive = activeDong ? matchDong(activeDong) : false;

    // Updated Glassmorphism style for map polygons
    layer.setStyle({
      fillColor: isRecommended ? '#ffffff' : 'transparent', // Unified white glass fill
      weight: isActive ? 5 : (isTop5 ? 4 : (isRecommended ? 3 : 1)),
      opacity: isRecommended ? 1 : 0.2, // Full opacity for borders to ensure they punch through visually
      color: isActive ? '#4338ca' : (isTop5 ? '#2563eb' : (isRecommended ? '#3b82f6' : '#cbd5e1')), // Indigo 700 -> Blue 600 -> Blue 500 -> Slate
      fillOpacity: isActive ? 0.0 : (isTop5 ? 0.6 : (isRecommended ? 0.45 : 0.0)) // Active becomes purely transparent to reveal map
    });

    // Glassmorphism Tooltip Formatting
    let rankText = `<div class="bg-white/70 backdrop-blur-md px-2.5 py-1.5 rounded-[12px] border border-white/80 shadow-sm text-center">
      <strong class="text-[13px] text-slate-800 tracking-tight font-extrabold whitespace-nowrap">${dongName}</strong>
    </div>`;
    
    if (isRecommended) {
      const dbDong = apartments[matchedIndex].emd;
      let subText = '';
      
      // If the legal DB name differs severely from the map polygon name
      if (dbDong !== dongName && !dbDong.startsWith(dongName.replace('가동', ''))) {
        subText = `<div class="text-[10.5px] text-slate-500 font-semibold leading-tight mt-0.5">(지도: ${dongName})</div>`;
      }
      
      const primaryName = dbDong !== dongName ? dbDong : dongName;
      
      if (isActive) {
        rankText = `<div class="bg-white/95 backdrop-blur-xl px-3.5 py-2 rounded-2xl border-2 border-indigo-500 shadow-[0_8px_20px_rgba(79,70,229,0.3)] text-center scale-110 origin-center transition-all">
          <strong class="text-[14px] text-indigo-700 font-black tracking-tight whitespace-nowrap">${rank}위 ${primaryName}</strong>
          ${subText}
        </div>`;
      } else if (isTop5) {
        rankText = `<div class="bg-white/85 backdrop-blur-xl px-3 py-1.5 rounded-2xl border-2 border-blue-400 shadow-[0_4px_12px_rgba(0,0,0,0.1)] text-center">
          <strong class="text-[13px] text-slate-800 font-black tracking-tight whitespace-nowrap"><span class="text-blue-600">${rank}위</span> ${primaryName}</strong>
          ${subText}
        </div>`;
      } else {
        rankText = `<div class="bg-white/80 backdrop-blur-md px-3 py-1.5 rounded-[14px] border-2 border-blue-300 shadow-sm text-center">
          <strong class="text-[12.5px] text-slate-800 font-bold tracking-tight whitespace-nowrap">${rank}위 ${primaryName}</strong>
          ${subText}
        </div>`;
      }
    }

    // Tooltip Execution - remove all default leaflet background styles
    if (isTop5 || isActive) {
      layer.bindTooltip(rankText, { 
        permanent: true, 
        direction: 'center',
        className: 'custom-glass-tooltip'
      });
    } else if (isRecommended) {
      layer.bindTooltip(rankText, {
        direction: 'center',
        className: 'custom-glass-tooltip'
      });
    }

    // Glassmorphism Interaction
    layer.on({
      mouseover: (e) => {
        if (!isActive && isRecommended) {
          e.target.setStyle({ 
            weight: isTop5 ? 5 : 4, 
            fillOpacity: isTop5 ? 0.75 : 0.55, 
            color: isTop5 ? '#1d4ed8' : '#2563eb' 
          });
        }
      },
      mouseout: (e) => {
        if (!isActive && isRecommended) {
          e.target.setStyle({ 
            weight: isTop5 ? 4 : 3, 
            fillOpacity: isTop5 ? 0.6 : 0.45, 
            color: isTop5 ? '#2563eb' : '#3b82f6' 
          });
        }
      },
      click: (e) => {
        if (isRecommended) {
          setActiveDong(dongName);
          setActiveBounds(e.target.getBounds());
        }
      }
    });

    // If this is the active dong (from sidebar click), auto-bound it
    if (isActive) {
      setTimeout(() => {
        setActiveBounds(layer.getBounds());
      }, 100);
    }
  };

  if (!geoData) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-slate-900 rounded-2xl border border-white/10">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-400"></div>
      </div>
    );
  }

  // Initial center on Seoul
  const seoulCenter = [37.5665, 126.9780];

  return (
    <div className="w-full h-full rounded-2xl overflow-hidden shadow-2xl relative bg-slate-50">
      <MapContainer 
        center={seoulCenter} 
        zoom={11} 
        style={{ height: '100%', width: '100%', backgroundColor: '#f1f5f9' }}
        zoomControl={false}
        preferCanvas={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        
        <GeoJSON 
          ref={geoJsonRef}
          key={activeDong + allDongs.join('-')} // Force re-render on state change for styling
          data={geoData} 
          onEachFeature={onEachFeature} 
        />
        
        <MapController activeBounds={activeBounds} />
      </MapContainer>
    </div>
  );
}
