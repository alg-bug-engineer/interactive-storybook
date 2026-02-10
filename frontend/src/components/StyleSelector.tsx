"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { listStoryStyles, type StoryStyle } from "@/services/api";

interface StyleSelectorProps {
  selectedStyleId: string | null;
  onSelectStyle: (styleId: string) => void;
}

const STYLE_ICONS: Record<string, string> = {
  q_cute: "🎨",
  watercolor_healing: "💧",
  classic_fairy_tale: "📖",
  chinese_ink_cute: "🖌️",
  minimal_simple: "✏️",
  clay_doll: "🧸",
};

export default function StyleSelector({ selectedStyleId, onSelectStyle }: StyleSelectorProps) {
  const [styles, setStyles] = useState<StoryStyle[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    async function loadStyles() {
      try {
        const styleList = await listStoryStyles();
        setStyles(styleList);
        // 如果没有选中风格，默认选择第一个
        if (!selectedStyleId && styleList.length > 0) {
          onSelectStyle(styleList[0].id);
        }
      } catch (error) {
        console.error("加载风格列表失败:", error);
      } finally {
        setLoading(false);
      }
    }
    loadStyles();
  }, []);

  if (loading) {
    return (
      <div className="mb-6">
        <p className="text-text-ui text-sm mb-3">加载风格中...</p>
      </div>
    );
  }

  const selectedStyle = styles.find((s) => s.id === selectedStyleId);

  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <label className="text-sm font-medium text-text-ui">选择故事风格</label>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-primary hover:underline"
        >
          {expanded ? "收起" : "展开"}
        </button>
      </div>

      {/* 当前选中的风格预览 */}
      {selectedStyle && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-3 p-3 rounded-lg border-2 border-primary/40 bg-primary/5"
        >
          <div className="flex items-start gap-2">
            <span className="text-2xl">{STYLE_ICONS[selectedStyle.id] || "🎨"}</span>
            <div className="flex-1">
              <div className="font-medium text-text-story">{selectedStyle.name}</div>
              <div className="text-xs text-text-ui mt-1">{selectedStyle.description}</div>
              <div className="text-xs text-primary/80 mt-1">
                适合：{selectedStyle.suitable_for}
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {/* 风格选择网格 */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              {styles.map((style) => (
                <motion.button
                  key={style.id}
                  type="button"
                  onClick={() => {
                    onSelectStyle(style.id);
                    setExpanded(false);
                  }}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    selectedStyleId === style.id
                      ? "border-primary bg-primary/10 shadow-md"
                      : "border-primary/20 bg-white hover:border-primary/40 hover:shadow-sm"
                  }`}
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-xl">{STYLE_ICONS[style.id] || "🎨"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm text-text-story mb-1">
                        {style.name}
                      </div>
                      <div className="text-xs text-text-ui mb-1">{style.description}</div>
                      <div className="text-xs text-primary/70">
                        适合：{style.suitable_for}
                      </div>
                    </div>
                    {selectedStyleId === style.id && (
                      <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="text-primary text-lg"
                      >
                        ✓
                      </motion.div>
                    )}
                  </div>
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
