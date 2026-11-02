'use client';
import dynamic from 'next/dynamic';

const Map = dynamic(() => import('./Map'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-2xl border border-white/10">
      <div className="animate-pulse flex flex-col items-center gap-4">
        <div className="h-12 w-12 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-cyan-400 font-bold">지도를 불러오는 중입니다...</p>
      </div>
    </div>
  ),
});

export default function MapWrapper(props) {
  return <Map {...props} />;
}
