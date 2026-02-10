"use client";

import { useCallback, useState, useEffect } from "react";

export function useNarrator() {
  const [isSpeaking, setIsSpeaking] = useState(false);

  const narrate = useCallback((text: string) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "zh-CN";
    u.rate = 0.85;
    u.pitch = 1.1;
    const voices = synth.getVoices();
    const zh = voices.find((v) => v.lang.startsWith("zh"));
    if (zh) u.voice = zh;
    u.onstart = () => setIsSpeaking(true);
    u.onend = () => setIsSpeaking(false);
    u.onerror = () => setIsSpeaking(false);
    synth.speak(u);
  }, []);

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { narrate, stop, isSpeaking };
}
