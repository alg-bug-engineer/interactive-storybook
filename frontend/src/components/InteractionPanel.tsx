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

// 默认选项配置（当 hints 为空时使用）
const DEFAULT_OPTIONS: Record<string, string[]> = {
  guess: ["好事发生了✨", "遇到了困难😰", "找到了宝藏🎁", "交到了朋友👫"],
  choice: ["去左边👈", "去右边👉", "停下来🤚", "继续前进🚶"],
  name: ["小星星⭐", "小月亮🌙", "小太阳☀️", "小云朵☁️", "小花朵🌸"],
  describe: ["勇敢的💪", "善良的❤️", "聪明的🧠", "可爱的😊", "活泼的🎉"],
};

// 互动类型对应的 emoji
const TYPE_EMOJIS: Record<string, string> = {
  guess: "🤔",
  choice: "🎯",
  name: "✏️",
  describe: "💭",
};

export default function InteractionPanel({
  visible,
  interactionPoint,
  onSubmit,
  loading,
}: InteractionPanelProps) {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  if (!visible || !interactionPoint) return null;

  // 获取选项：优先使用 hints，否则使用默认选项
  const options = interactionPoint.hints && interactionPoint.hints.length > 0
    ? interactionPoint.hints
    : DEFAULT_OPTIONS[interactionPoint.type] || DEFAULT_OPTIONS.guess;

  const handleOptionClick = (option: string) => {
    if (loading) return;
    setSelectedOption(option);
    // 延迟一下让用户看到选中效果
    setTimeout(() => {
      // 移除 emoji 符号，只提交文本内容
      const cleanOption = option.replace(/[\u{1F300}-\u{1F9FF}]|[\u{2600}-\u{26FF}]/gu, "").trim();
      onSubmit(cleanOption);
      setSelectedOption(null);
    }, 300);
  };

  const typeEmoji = TYPE_EMOJIS[interactionPoint.type] || "💡";

  return (
    <motion.div
      initial={{ y: 20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="rounded-story-md border-2 border-secondary/30 bg-gradient-to-br from-white to-secondary/5 p-5 shadow-lg"
    >
      {/* 标题 */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-3xl">{typeEmoji}</span>
        <p className="text-secondary font-bold text-lg flex-1">{interactionPoint.prompt}</p>
      </div>

      {/* 选项按钮网格 */}
      <div className="grid grid-cols-2 gap-3">
        {options.map((option, index) => (
          <motion.button
            key={index}
            onClick={() => handleOptionClick(option)}
            disabled={loading}
            className={`relative px-4 py-4 rounded-xl font-medium text-base transition-all ${
              selectedOption === option
                ? "bg-secondary text-white shadow-xl scale-95"
                : "bg-white border-2 border-secondary/20 text-text-story hover:border-secondary hover:shadow-md hover:scale-105"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
            whileHover={{ scale: loading ? 1 : 1.05 }}
            whileTap={{ scale: loading ? 1 : 0.95 }}
          >
            <span className="block text-center">{option}</span>
            {selectedOption === option && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute top-1 right-1 w-5 h-5 bg-white rounded-full flex items-center justify-center text-secondary text-xs"
              >
                ✓
              </motion.div>
            )}
          </motion.button>
        ))}
      </div>

      {/* 加载提示 */}
      {loading && (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center text-text-ui text-sm mt-3"
        >
          正在生成故事续集...
        </motion.p>
      )}
    </motion.div>
  );
}
