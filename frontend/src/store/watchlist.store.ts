import { create } from "zustand";
import { persist } from "zustand/middleware";

interface WatchlistState {
  trackedSymbols: string[];
  addSymbol: (symbol: string) => void;
  removeSymbol: (symbol: string) => void;
  toggle: (symbol: string) => void;
  isTracked: (symbol: string) => boolean;
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set, get) => ({
      trackedSymbols: ["GTCO", "MTNN", "SEPLAT", "DANGCEM"],
      addSymbol: (symbol) =>
        set((s) =>
          s.trackedSymbols.includes(symbol)
            ? s
            : { trackedSymbols: [...s.trackedSymbols, symbol] },
        ),
      removeSymbol: (symbol) =>
        set((s) => ({ trackedSymbols: s.trackedSymbols.filter((x) => x !== symbol) })),
      toggle: (symbol) =>
        set((s) =>
          s.trackedSymbols.includes(symbol)
            ? { trackedSymbols: s.trackedSymbols.filter((x) => x !== symbol) }
            : { trackedSymbols: [...s.trackedSymbols, symbol] },
        ),
      isTracked: (symbol) => get().trackedSymbols.includes(symbol),
    }),
    { name: "ngx.watchlist" },
  ),
);
