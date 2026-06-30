"use client";

import { Plus, Save, Zap, Copy, Trash2 } from "lucide-react";
import type { StrategyLeg } from "../types";
import { LegCard } from "./LegCard";

interface LegListProps {
  legs: StrategyLeg[];
  onAdd: () => void;
  onUpdate: (id: string, updates: Partial<StrategyLeg>) => void;
  onRemove: (id: string) => void;
  onDuplicate: (id: string) => void;
  onSave: () => void;
}

export function LegList({ legs, onAdd, onUpdate, onRemove, onDuplicate, onSave }: LegListProps) {
  return (
    <div className="p-4 border border-[var(--ax-border)] rounded-xl bg-[var(--ax-surface)] space-y-4">
      <div className="flex items-center justify-between">
        <h4 className="font-bold text-[#c0c0c0] text-sm flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          Strategy Legs
        </h4>
        <button
          onClick={onAdd}
          className="px-2 py-1 bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded text-xs font-bold flex items-center gap-1 transition-all"
        >
          <Plus size={12} /> Add Leg
        </button>
      </div>

      <div className="space-y-3">
        {legs.map((leg, index) => (
          <LegCard
            key={leg.id}
            leg={leg}
            index={index}
            onUpdate={onUpdate}
            onRemove={onRemove}
            onDuplicate={onDuplicate}
          />
        ))}
      </div>

      <button
        onClick={onSave}
        className="w-full bg-[#4a7fcc] hover:bg-[#5a8fd0] text-[#f0f0f0] rounded text-xs font-bold py-2.5 flex items-center justify-center gap-2 transition-all"
      >
        <Save size={13} /> Save Strategy
      </button>
    </div>
  );
}
