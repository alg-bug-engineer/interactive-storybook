"use client";

import { useState } from "react";
import { motion } from "framer-motion";

interface InteractionPoint {
  type: string;
  prompt: string;
  hints?: string[];
}

interface InteractionPanelProps {
  visible: boolean;
  interactionPoint?: InteractionPoint | null;
  onSubmit: (input: string) => void;
  loading: boolean;
}

export default function InteractionPanel({
  visible,
  interactionPoint,
  onSubmit,
  loading,
}: InteractionPanelProps) {
  const [input, setInput] = useState("");

  if (!visible || !interactionPoint) return null;

  const handleSubmit = () => {
    const value = input.trim();
    if (!value || loading) return;
    onSubmit(value);
    setInput("");
  };

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="rounded-story-md border-2 border-secondary/30 bg-white p-4"
    >
      <p className="text-secondary font-medium mb-3">{interactionPoint.prompt}</p>
      {interactionPoint.hints && interactionPoint.hints.length > 0 && (
        <p className="text-sm text-text-ui mb-2">
          提示：{interactionPoint.hints.join(" · ")}
        </p>
      )}
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          placeholder="输入你的想法…"
          className="flex-1 px-4 py-2 rounded-story-sm border border-primary/30 focus:outline-none focus:ring-2 focus:ring-primary/50"
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || loading}
          className="px-4 py-2 rounded-story-sm bg-secondary text-white font-medium disabled:opacity-50"
        >
          {loading ? "提交中…" : "提交"}
        </button>
      </div>
    </motion.div>
  );
}
