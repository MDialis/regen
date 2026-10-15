// src/hooks/useDeviceCapacity.ts
"use client";

import { useState, useEffect } from "react";

export function useDeviceCapacity(defaultLowVram: boolean = true) {
  const [lowVramMode, setLowVramMode] = useState<boolean>(defaultLowVram);

  useEffect(() => {
    if (typeof window !== "undefined" && window.navigator) {
      // @ts-expect-error - deviceMemory is not in standard TS DOM yet (Chrome/Edge only)
      const memory = navigator.deviceMemory || 4;
      const cores = navigator.hardwareConcurrency || 4;

      // For local LLMs: If the machine has < 8GB RAM or <= 4 CPU cores,
      // default to Low-VRAM mode (phi4-mini). Otherwise, enable heavier models.
      if (memory >= 8 && cores > 4) {
        setLowVramMode(false);
      } else {
        setLowVramMode(true);
      }
    }
  }, []);

  return { lowVramMode, setLowVramMode };
}
