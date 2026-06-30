"use client";

import { Package } from "lucide-react";
import type { StrategyTemplate } from "../types";

interface TemplateLoaderProps {
  templates: StrategyTemplate[];
  loading: boolean;
  onSelect: (templateId: string) => void;
}

export function TemplateLoader({ templates, loading, onSelect }: TemplateLoaderProps) {
  if (loading) {
    return (
      <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)]">
        <p className="text-xs text-[#a0a0a0]">Loading templates...</p>
      </div>
    );
  }

  if (templates.length === 0) return null;

  return (
    <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-3">
      <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
        <Package className="w-4 h-4 text-[#93b4ff]" />
        Templates
      </h4>
      <div className="space-y-2">
        {templates.map(t => (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            className="w-full text-left p-2.5 rounded-lg border border-[var(--ax-border)]/60 bg-[#111] hover:bg-[#161616] transition-all"
          >
            <div className="text-xs font-bold text-[#c0c0c0]">{t.name}</div>
            <div className="text-[10px] text-[#a0a0a0] mt-0.5">{t.description}</div>
            <div className="text-[10px] text-[#606060] font-mono mt-1">{t.example}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
