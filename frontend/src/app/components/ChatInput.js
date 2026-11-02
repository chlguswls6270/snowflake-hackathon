"use client";

import { useState, useEffect, useRef } from 'react';
import MapWrapper from './MapWrapper';

// ── Configuration ────────────────────────────────────────────────────────────
const API_BASE = 'http://localhost:8001';

export default function ChatInput() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [apartments, setApartments] = useState(null);
  const [specialKeywords, setSpecialKeywords] = useState([]);
  const [visibleLimit, setVisibleLimit] = useState(6);
  const [activeDong, setActiveDong] = useState(null);
  const [dongChats, setDongChats] = useState({}); // Stores mini-chat states per dong
  const [rentalInsights, setRentalInsights] = useState({}); // Stores rental insight per dong
  
  const textareaRef = useRef(null);

  const resizeTextarea = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'; // Reset to calculate exact scroll height
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 250)}px`;
    }
  };

  const handleInput = (e) => {
    setPrompt(e.target.value);
    resizeTextarea();
  };

  useEffect(() => {
    // Give the DOM a tiny slice of time to render the textarea's layout before measuring
    const timer = setTimeout(() => resizeTextarea(), 50);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (activeDong && apartments) {
      const matchIndex = apartments.findIndex(a => a.emd === activeDong || a.emd.startsWith(activeDong));
      if (matchIndex !== -1) {
        // If the card is hidden because it's past the current visible limit, expand the limit
        setVisibleLimit(prev => Math.max(prev, matchIndex + 3));
        
        // Wait briefly for React to render the newly expanded items into the DOM
        setTimeout(() => {
          const matchedApt = apartments[matchIndex];
          const el = document.getElementById(`card-${matchedApt.emd}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 150);
      }
    }
  }, [activeDong, apartments]);

  // Auto-fetch rental insight when a new dong is activated
  useEffect(() => {
    if (!activeDong || !apartments) return;
    if (rentalInsights[activeDong]) return; // already fetched

    const apt = apartments.find(a => a.emd === activeDong || a.emd.startsWith(activeDong));
    if (!apt) return;

    // Parse sd / sgg from region string e.g. "서울 영등포구 여의도동"
    const parts = apt.region.split(' ');
    const sd_name = parts[0] || '서울';
    const sgg_name = parts[1] || '';

    setRentalInsights(prev => ({ ...prev, [activeDong]: { loading: true, text: null } }));

    fetch(`${API_BASE}/api/rental-insight`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dong_name: activeDong, sgg_name, sd_name })
    })
      .then(r => r.json())
      .then(data => {
        if (data.status === 'success') {
          setRentalInsights(prev => ({ ...prev, [activeDong]: { loading: false, text: data.insight } }));
        } else {
          throw new Error(data.detail);
        }
      })
      .catch(() => {
        setRentalInsights(prev => ({ ...prev, [activeDong]: { loading: false, text: null, error: true } }));
      });
  }, [activeDong, apartments]);

  const handleDongChatInput = (dongName, text) => {
    setDongChats(prev => ({
      ...prev,
      [dongName]: {
        ...(prev[dongName] || { history: [], isLoading: false }),
        input: text
      }
    }));
  };

  const handleDongChatSubmit = async (e, dongName) => {
    e.preventDefault();
    const chatData = dongChats[dongName] || { history: [], input: '', isLoading: false };
    if (!chatData.input || !chatData.input.trim() || chatData.isLoading) return;

    const userQuestion = chatData.input;
    
    // Optimistic UI update
    setDongChats(prev => ({
      ...prev,
      [dongName]: {
        ...prev[dongName],
        history: [...(prev[dongName]?.history || []), { role: 'user', text: userQuestion }],
        input: '',
        isLoading: true
      }
    }));

    try {
      const res = await fetch(`${API_BASE}/api/ask-dong`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dong_name: dongName, question: userQuestion })
      });
      const data = await res.json();
      
      if (res.ok && data.status === 'success') {
        setDongChats(prev => ({
          ...prev,
          [dongName]: {
            ...prev[dongName],
            history: [...prev[dongName].history, { role: 'ai', text: data.answer }],
            isLoading: false
          }
        }));
      } else {
        throw new Error(data.detail || "대답을 가져오지 못했습니다.");
      }
    } catch (err) {
      setDongChats(prev => ({
        ...prev,
        [dongName]: {
          ...prev[dongName],
          history: [...prev[dongName].history, { role: 'ai', text: "오류가 발생했습니다. 다시 시도해주세요." }],
          isLoading: false
        }
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    
    setLoading(true);
    setResponse(null);
    setApartments(null);
    setSpecialKeywords([]);
    setVisibleLimit(6);
    setActiveDong(null);
    setRentalInsights({}); // Clear stale rental insights on each new search
    
    try {
      const res = await fetch(`${API_BASE}/api/analyze-prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt })
      });
      const data = await res.json();
      setResponse(data);
      
      if (data.status === "success") {
        const recRes = await fetch(`${API_BASE}/api/recommend-apartments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data.parsed)
        });
        const recData = await recRes.json();
        setApartments(recData.recommendations);
        if (recData.special_requests) {
          setSpecialKeywords(recData.special_requests);
        }
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative w-full h-full bg-slate-50 pointer-events-auto">
      
      {/* 1. Map Background (Z-0) */}
      <div className="absolute inset-0 z-0 pointer-events-auto">
        <MapWrapper 
          apartments={apartments || []} 
          activeDong={activeDong} 
          setActiveDong={setActiveDong} 
        />
      </div>

      {/* 2. Floating Header (Z-10) */}
      <div className="absolute top-6 left-8 z-10 pointer-events-none animate-in fade-in slide-in-from-top-4 duration-700 bg-white/50 backdrop-blur-3xl px-7 py-6 rounded-[32px] border border-white/50 shadow-[0_8px_30px_rgb(0,0,0,0.06)]">
        <h1 className="text-4xl lg:text-5xl font-black tracking-tight text-slate-800 drop-shadow-sm flex items-end gap-2">
          큐동 <span className="text-2xl text-slate-500 font-bold mb-1">Q-Dong</span><br className="md:hidden" />
        </h1>
        <h2 className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 via-indigo-500 to-cyan-500 mt-1 text-2xl lg:text-3xl font-bold tracking-tight">
          내 삶에 꼭 맞는 동네 큐레이션
        </h2>
        <p className="mt-4 text-sm text-slate-700 bg-white/50 backdrop-blur-3xl px-4 py-1.5 rounded-full inline-block font-bold shadow-sm border border-white/50 tracking-wide">
          Powered by Snowflake Cortex AI
        </p>
      </div>

      {/* 3. Floating Left Panel (Z-10) - Appears after search */}
      {apartments && (
        <div className="absolute top-[220px] left-8 z-10 w-[420px] max-h-[calc(100vh-240px)] flex flex-col bg-white/50 backdrop-blur-3xl border border-white/50 rounded-[32px] shadow-[0_8px_30px_rgb(0,0,0,0.06)] overflow-hidden animate-in fade-in slide-in-from-left-8 duration-700 pointer-events-auto">
          {/* Header */}
          <div className="bg-white/40 border-b border-white/40 p-5 shrink-0 z-20">
            <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
              <span>🏡</span> AI 추천 동네 Top {apartments.length}
            </h3>
            {specialKeywords && specialKeywords.length > 0 && (
              <div className="mt-3 pt-3 border-t border-slate-200/50">
                <span className="text-[11px] text-indigo-600 font-extrabold mb-2 block tracking-wide uppercase">AI 반영 추가 키워드</span>
                <div className="flex flex-wrap gap-1.5">
                  {specialKeywords.map((kw, i) => (
                    <span key={i} className="text-[11.5px] bg-white/60 text-indigo-700 px-3 py-1 rounded-full border border-indigo-100/60 shadow-sm font-semibold">
                      #{kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          
          {/* List */}
          <div className="flex flex-col gap-3 overflow-y-auto px-4 pt-5 pb-24" 
               style={{ 
                 scrollbarWidth: 'none',
                 maskImage: 'linear-gradient(to bottom, transparent 0px, black 24px, black calc(100% - 60px), transparent 100%)',
                 WebkitMaskImage: 'linear-gradient(to bottom, transparent 0px, black 24px, black calc(100% - 60px), transparent 100%)'
               }}>
            {apartments.slice(0, visibleLimit).map((apt, idx) => {
              const isActive = activeDong === apt.emd || (activeDong && apt.emd.startsWith(activeDong));
              
              const legalToAdminMap = {
                '우면동': '양재동', '원지동': '양재동', '신원동': '내곡동',
                '염곡동': '내곡동', '포이동': '개포동', '일원동': '개포동'
              };
              const mappedAdmin = legalToAdminMap[apt.emd];

              return (
                <div 
                  key={idx} 
                  id={`card-${apt.emd}`}
                  onClick={() => setActiveDong(apt.emd)}
                  className={`cursor-pointer transition-colors border rounded-[20px] p-5 relative overflow-hidden shrink-0 bg-white/60 ${isActive ? 'border-blue-400 ring-2 ring-blue-400/30 shadow-[0_10px_30px_rgba(59,130,246,0.15)] z-10' : 'border-white/50 shadow-sm hover:border-blue-300'}`}
                >
                  <div className="absolute top-0 right-0 bg-gradient-to-bl from-blue-500 to-blue-400 text-white font-bold px-3 py-1 text-xs shadow-sm rounded-bl-xl">
                    매칭률 {apt.lifestyle_score}%
                  </div>
                  <h4 className="text-lg font-bold text-slate-800 flex items-center gap-2 flex-wrap pr-16">
                    <span className="bg-blue-100 text-blue-700 px-2.5 py-0.5 rounded-md text-sm shadow-sm border border-blue-200/60 font-black">
                      {idx + 1}위
                    </span>
                    {apt.region}
                    {mappedAdmin && (
                      <span className="text-[11px] bg-slate-100 text-slate-500 px-2 py-0.5 rounded-md font-semibold shadow-inner border border-slate-200/80 opacity-90 mt-1 sm:mt-0">
                        📍 지도: {mappedAdmin}
                      </span>
                    )}
                  </h4>
                  
                  {apt.matched_tags && apt.matched_tags.length > 0 && (
                    <div className="flex flex-col gap-1.5 mt-3">
                      {apt.matched_tags.map((tag, i) => (
                        <div key={i} className="bg-slate-50/60 rounded-lg py-2.5 px-3 border border-slate-200/30 transition-colors hover:bg-white/80 shadow-sm">
                          <div className="flex items-start gap-2.5">
                            <span className="text-[14px] mt-0.5 drop-shadow-sm">{tag.icon}</span> 
                            <div className="flex flex-col gap-0.5">
                              <strong className="font-bold text-slate-700 text-xs tracking-tight">{tag.title}</strong>
                              <p className="text-[11px] text-slate-500 font-medium leading-tight break-keep">
                                {tag.desc}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className="flex flex-col gap-1 mt-4 pt-4 border-t border-slate-200/40 text-xs text-slate-500 font-semibold">
                    <div className="flex justify-between items-center">
                      <span>평균 평당가</span> <strong className="text-slate-800 text-sm">{(apt.price_per_pyeong_krw / 100000000).toFixed(1)}억</strong>
                    </div>
                    <div className="flex justify-between items-center mt-1">
                      <span>예산 적합도</span> <strong className="text-blue-600 text-sm">결과: 약 {apt.affordable_size_pyeong}평 가능</strong>
                    </div>
                  </div>

                  {/* AJD Rental Insight Panel (Visible only when active) */}
                  {isActive && (
                    <div className="mt-4 border-t border-slate-200/40 pt-4 cursor-default" onClick={(e) => e.stopPropagation()}>
                      <div className="bg-gradient-to-br from-teal-50/60 to-emerald-50/40 backdrop-blur-md rounded-xl p-3.5 border border-teal-200/40 shadow-inner">
                        <div className="flex items-center gap-1.5 mb-2.5">
                          <span className="text-base">🏠</span>
                          <span className="text-[11px] font-extrabold text-teal-700 tracking-tight">이사 후 렌탈 가전 추천</span>
                          <span className="ml-auto text-[10px] text-teal-500/80 font-semibold bg-teal-100/60 px-2 py-0.5 rounded-full border border-teal-200/50">❄️ AJD × Cortex AI</span>
                        </div>
                        {rentalInsights[apt.emd]?.loading && (
                          <div className="flex items-center gap-2 text-[12px] text-teal-600 font-semibold py-1">
                            <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce"></span>
                            <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{animationDelay: '0.15s'}}></span>
                            <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-bounce" style={{animationDelay: '0.3s'}}></span>
                            <span className="ml-1">렌탈 데이터 분석 중...</span>
                          </div>
                        )}
                        {rentalInsights[apt.emd]?.error && (
                          <p className="text-[12px] text-slate-400 italic">렌탈 인사이트를 불러올 수 없습니다.</p>
                        )}
                        {rentalInsights[apt.emd]?.text && (
                          <p className="text-[12.5px] text-slate-700 leading-relaxed whitespace-pre-wrap font-medium">
                            {rentalInsights[apt.emd].text}
                          </p>
                        )}
                        {!rentalInsights[apt.emd] && (
                          <p className="text-[12px] text-slate-400 italic">잠시 후 분석이 시작됩니다...</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Snowflake Cortex Sub-Chat (Visible only when active) */}
                  {isActive && (
                    <div className="mt-4 border-t border-slate-200/40 pt-4 cursor-default" onClick={(e) => e.stopPropagation()}>
                      <div className="bg-white/40 backdrop-blur-md rounded-xl p-3 border border-white/60 shadow-inner flex flex-col gap-3">
                        <div className="text-[11px] font-bold text-slate-500 text-center flex items-center justify-center gap-1">
                          <span className="text-blue-500">❄️</span> Snowflake Cortex에게 물어보기
                        </div>
                        
                        {/* Chat history */}
                        {(dongChats[apt.emd]?.history || []).length > 0 && (
                          <div className="flex flex-col gap-3 max-h-[220px] overflow-y-auto hide-scroll px-1">
                            {dongChats[apt.emd].history.map((chat, cIdx) => (
                              <div key={cIdx} className={`flex ${chat.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div className={`max-w-[90%] text-[13px] px-3 py-2 rounded-[18px] shadow-sm whitespace-pre-wrap break-words leading-relaxed ${
                                  chat.role === 'user' 
                                  ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-br-sm' 
                                  : 'bg-white/90 border border-white text-slate-700 rounded-bl-sm font-medium'
                                }`}>
                                  {chat.text}
                                </div>
                              </div>
                            ))}
                            {dongChats[apt.emd]?.isLoading && (
                              <div className="flex justify-start">
                                <div className="bg-white/90 border border-white text-slate-500 px-3 py-2 rounded-2xl rounded-bl-sm shadow-sm flex items-center gap-1.5 h-9">
                                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce"></span>
                                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{animationDelay: '0.15s'}}></span>
                                  <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{animationDelay: '0.3s'}}></span>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                        
                        {/* Input Form */}
                        <form 
                          onSubmit={(e) => handleDongChatSubmit(e, apt.emd)}
                          className="relative mt-1"
                        >
                          <input
                            type="text"
                            className="w-full bg-white/70 focus:bg-white border border-white/80 focus:border-blue-400 focus:ring-2 focus:ring-blue-400/20 rounded-full py-2.5 pl-4 pr-10 text-[13px] text-slate-800 placeholder-slate-400 outline-none transition-all shadow-sm"
                            placeholder={`${apt.emd} 학군 정보 알려줘`}
                            value={dongChats[apt.emd]?.input || ''}
                            onChange={(e) => handleDongChatInput(apt.emd, e.target.value)}
                          />
                          <button 
                            type="submit"
                            disabled={dongChats[apt.emd]?.isLoading || !(dongChats[apt.emd]?.input?.trim())}
                            className="absolute right-1.5 top-1/2 -translate-y-1/2 bg-blue-500 hover:bg-blue-600 disabled:bg-slate-300 text-white p-1.5 rounded-full transition-colors shadow-sm"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                          </button>
                        </form>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            
            {apartments.length > visibleLimit && (
              <button 
                onClick={() => setVisibleLimit(prev => prev + 6)}
                className="py-3 mt-2 bg-white/50 hover:bg-white/60 backdrop-blur-3xl border border-white/50 rounded-xl text-blue-600 text-[15px] font-bold shadow-sm transition-colors text-center"
              >
                결과 더 보기 ▼
              </button>
            )}
            {apartments.length === 0 && (
              <div className="p-6 bg-white/50 backdrop-blur-3xl rounded-2xl text-center text-slate-800 font-bold border border-white/50 shadow-sm">
                조건에 맞는 동네를 찾을 수 없습니다.
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. Floating Prompt Bar (Z-20) */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-20 w-[90%] max-w-[800px] pointer-events-auto">
        <style dangerouslySetInnerHTML={{__html: `
          .hide-scroll::-webkit-scrollbar { display: none; }
          .hide-scroll { -ms-overflow-style: none; scrollbar-width: none; }
        `}} />
        <form onSubmit={handleSubmit} className="relative rounded-[28px] overflow-hidden group shadow-[0_8px_40px_rgb(0,0,0,0.08)] bg-white/50 backdrop-blur-3xl border border-white/50 hover:bg-white/60 focus-within:bg-white/80 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-400/30 transition-all duration-300">
          <textarea
            ref={textareaRef}
            className="hide-scroll w-full text-base lg:text-lg bg-transparent focus:outline-none text-slate-800 placeholder-slate-500 font-semibold resize-none flex min-h-[72px] py-[22px] pl-7 pr-[180px] shadow-inner"
            rows={1}
            placeholder="어떤 라이프스타일을 꿈꾸시나요? (예: 아기가 있고, 주말에 산책하기 좋은 동네, 예산 15억)"
            value={prompt}
            onChange={handleInput}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
          />
          <button 
            type="submit" 
            disabled={loading}
            className="absolute right-3 bottom-[10px] px-6 py-2.5 text-[15px] font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-500 hover:from-blue-500 hover:to-indigo-400 rounded-[18px] shadow-[0_4px_15px_rgba(79,70,229,0.3)] transition-transform active:scale-95 disabled:opacity-50 flex items-center justify-center h-11"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <svg className="animate-spin h-5 w-5 text-white" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                AI 분석 중...
              </span>
            ) : (apartments ? "다시 검색" : "AI 큐레이션 받기")}
          </button>
        </form>
      </div>

    </div>
  );
}
