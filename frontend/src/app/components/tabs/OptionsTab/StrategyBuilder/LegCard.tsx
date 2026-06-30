"use client";

import { Copy, Trash2 } from "lucide-react";
import type { StrategyLeg } from "../types";

interface LegCardProps {
  leg: StrategyLeg;
  index: number;
  onUpdate: (id: string, updates: Partial<StrategyLeg>) => void;
  onRemove: (id: string) => void;
  onDuplicate: (id: string) => void;
}

export function LegCard({ leg, index, onUpdate, onRemove, onDuplicate }: LegCardProps) {
  return (
    <div className="bg-[#111] border border-[var(--ax-border)]/60 rounded-lg p-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-[#a0a0a0]">Leg {index + 1}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onDuplicate(leg.id)}
            className="p-1 text-[#a0a0a0] hover:text-[#c0c0c0] transition-colors"
            title="Duplicate"
          >
            <Copy size={12} />
          </button>
          <button
            onClick={() => onRemove(leg.id)}
            className="p-1 text-[#a0a0a0] hover:text-rose-400 transition-colors"
            title="Remove"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Position + Type */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Position</label>
          <div className="grid grid-cols-2 gap-1">
            <button
              onClick={() => onUpdate(leg.id, { position: "BUY" })}
              className={`py-1 text-[10px] font-bold rounded border transition-all ${
                leg.position === "BUY" ? "bg-[#0d1a10] border-emerald-500 text-emerald-400" : "bg-[#111] border-[var(--ax-border)] text-[#a0a0a0]"
              }`}
            >
              BUY
            </button>
            <button
              onClick={() => onUpdate(leg.id, { position: "SELL" })}
              className={`py-1 text-[10px] font-bold rounded border transition-all ${
                leg.position === "SELL" ? "bg-[#1a0d0d] border-rose-500 text-rose-400" : "bg-[#111] border-[var(--ax-border)] text-[#a0a0a0]"
              }`}
            >
              SELL
            </button>
          </div>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Type</label>
          <div className="grid grid-cols-2 gap-1">
            <button
              onClick={() => onUpdate(leg.id, { option_type: "CE" })}
              className={`py-1 text-[10px] font-bold rounded border transition-all ${
                leg.option_type === "CE" ? "bg-[#1c2030] border-[#4a7fcc] text-[#93b4ff]" : "bg-[#111] border-[var(--ax-border)] text-[#a0a0a0]"
              }`}
            >
              CE
            </button>
            <button
              onClick={() => onUpdate(leg.id, { option_type: "PE" })}
              className={`py-1 text-[10px] font-bold rounded border transition-all ${
                leg.option_type === "PE" ? "bg-[#1c1a30] border-violet-500 text-violet-400" : "bg-[#111] border-[var(--ax-border)] text-[#a0a0a0]"
              }`}
            >
              PE
            </button>
          </div>
        </div>
      </div>

      {/* Qty + Lots */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Qty</label>
          <input
            type="number"
            value={leg.qty}
            onChange={e => onUpdate(leg.id, { qty: Number(e.target.value) })}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-mono font-semibold"
          />
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Lots</label>
          <input
            type="number"
            value={leg.lot_multiplier}
            onChange={e => onUpdate(leg.id, { lot_multiplier: Number(e.target.value) })}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-mono font-semibold"
          />
        </div>
      </div>

      {/* Strike */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Strike</label>
          <select
            value={leg.strike_criteria}
            onChange={e => onUpdate(leg.id, { strike_criteria: e.target.value })}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-semibold"
          >
            <option value="ATM">ATM</option>
            <option value="ITM">ITM</option>
            <option value="OTM">OTM</option>
            <option value="ATM+POINTS">ATM + Points</option>
            <option value="ATM+PERCENT">ATM + %</option>
          </select>
        </div>
        <div>
          <label className="block text-[10px] uppercase font-bold text-[#606060] mb-1">Value</label>
          <input
            type="number"
            value={leg.strike_value}
            onChange={e => onUpdate(leg.id, { strike_value: Number(e.target.value) })}
            className="w-full text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-mono font-semibold"
          />
        </div>
      </div>

      {/* SL */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={leg.sl_enabled}
          onChange={e => onUpdate(leg.id, { sl_enabled: e.target.checked })}
          className="w-3 h-3"
        />
        <span className="text-[10px] font-bold text-[#606060]">SL</span>
        {leg.sl_enabled && (
          <div className="flex items-center gap-1 flex-1">
            <input
              type="number"
              value={leg.sl_value}
              onChange={e => onUpdate(leg.id, { sl_value: Number(e.target.value) })}
              className="w-16 text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-mono"
            />
            <select
              value={leg.sl_type}
              onChange={e => onUpdate(leg.id, { sl_type: e.target.value })}
              className="text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-semibold"
            >
              <option value="PERCENT">%</option>
              <option value="POINTS">pts</option>
            </select>
          </div>
        )}
      </div>

      {/* TP */}
      <div className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={leg.tp_enabled}
          onChange={e => onUpdate(leg.id, { tp_enabled: e.target.checked })}
          className="w-3 h-3"
        />
        <span className="text-[10px] font-bold text-[#606060]">TP</span>
        {leg.tp_enabled && (
          <div className="flex items-center gap-1 flex-1">
            <input
              type="number"
              value={leg.tp_value}
              onChange={e => onUpdate(leg.id, { tp_value: Number(e.target.value) })}
              className="w-16 text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-mono"
            />
            <select
              value={leg.tp_type}
              onChange={e => onUpdate(leg.id, { tp_type: e.target.value })}
              className="text-xs bg-[#111] border border-[var(--ax-border)] rounded px-2 py-1 text-[#c0c0c0] font-semibold"
            >
              <option value="PERCENT">%</option>
              <option value="POINTS">pts</option>
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
