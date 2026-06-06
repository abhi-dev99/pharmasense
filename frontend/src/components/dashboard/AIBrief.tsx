"use client";

import useSWR from 'swr';
import { Sparkles, RefreshCw } from 'lucide-react';
import { useState } from 'react';

const fetcherBase = (url: string) => fetch(url).then(res => res.json());

interface BriefResponse {
  brief_markdown: string;
}

function parseBold(text: string) {
  const parts = text.split(/(\*\*.*?\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} className="font-semibold text-gray-900">{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

export function AIBrief({ hospitalId }: { hospitalId: string }) {
  const [refreshKey, setRefreshKey] = useState(0);

  const { data, error, isLoading } = useSWR<BriefResponse>(
    [`/api/v1/brief/hospital/${hospitalId}`, refreshKey],
    ([url]) => fetcherBase(url),
    { revalidateOnFocus: false }
  );

  return (
    <div className="bg-gradient-to-r from-[#111111] to-[#2a2a2a] p-[1px] rounded-xl">
      <div className="bg-white rounded-[11px] px-5 py-3.5 flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          <Sparkles size={16} className="text-[#111111]" />
        </div>

        <div className="flex-1 min-w-0">
          <span className="text-[11px] font-bold text-gray-400 uppercase tracking-widest mr-2">AI Brief</span>
          {isLoading ? (
            <span className="inline-block h-3 w-64 bg-gray-100 rounded animate-pulse align-middle" />
          ) : error || !data ? (
            <span className="text-sm text-gray-400">Unable to generate brief.</span>
          ) : (
            <span className="text-sm text-gray-600 leading-relaxed">
              {parseBold(data.brief_markdown)}
            </span>
          )}
        </div>

        <button
          onClick={() => setRefreshKey(k => k + 1)}
          className="shrink-0 text-gray-400 hover:text-[#111] transition-colors mt-0.5"
          title="Regenerate brief"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>
    </div>
  );
}
