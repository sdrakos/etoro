import { useState, useEffect, useCallback } from "react";
import type { Universe } from "../types/screener";

const STORAGE_KEY = "etoro.screener.universe";
const VALID: Universe[] = ["sp500", "nasdaq100", "combined"];

function readStored(): Universe {
  if (typeof window === "undefined") return "sp500";
  const v = window.localStorage.getItem(STORAGE_KEY);
  return (VALID as string[]).includes(v ?? "") ? (v as Universe) : "sp500";
}

export function useUniverse(): [Universe, (u: Universe) => void] {
  const [universe, setUniverse] = useState<Universe>(readStored);

  const select = useCallback((u: Universe) => {
    setUniverse(u);
    try {
      window.localStorage.setItem(STORAGE_KEY, u);
    } catch {
      // localStorage unavailable (private mode, SSR) — ignore
    }
  }, []);

  useEffect(() => {
    setUniverse(readStored());
  }, []);

  return [universe, select];
}
