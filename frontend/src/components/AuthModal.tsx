"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { register, login } from "@/services/api";
import { useAuthStore } from "@/stores/authStore";

const EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

function validateEmail(email: string): boolean {
  return EMAIL_RE.test(email.trim());
}

interface AuthModalProps {
  open: boolean;
  onClose: () => void;
  defaultTab?: "login" | "register";
}

export default function AuthModal({
  open,
  onClose,
  defaultTab = "login",
}: AuthModalProps) {
  const [tab, setTab] = useState<"login" | "register">(defaultTab);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const setAuth = useAuthStore((s) => s.setAuth);

  useEffect(() => {
    if (open) setTab(defaultTab);
  }, [open, defaultTab]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    const eTrim = email.trim();
    const pTrim = password.trim();
    if (!eTrim) {
      setError("请输入邮箱");
      return;
    }
    if (!validateEmail(eTrim)) {
      setError("请输入正确的邮箱格式");
      return;
    }
    if (!pTrim) {
      setError("请输入密码");
      return;
    }
    if (tab === "register" && pTrim.length < 6) {
      setError("密码至少 6 位");
      return;
    }
    setLoading(true);
    try {
      if (tab === "register") {
        const data = await register(eTrim, pTrim);
        setAuth(data.token, data.user);
      } else {
        const data = await login(eTrim, pTrim);
        setAuth(data.token, data.user);
      }
      onClose();
      setEmail("");
      setPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="bg-white rounded-2xl shadow-xl max-w-sm w-full p-6"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex border-b border-amber-200 mb-4">
            <button
              type="button"
              onClick={() => { setTab("login"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium ${tab === "login" ? "text-primary border-b-2 border-primary" : "text-text-ui"}`}
            >
              登录
            </button>
            <button
              type="button"
              onClick={() => { setTab("register"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium ${tab === "register" ? "text-primary border-b-2 border-primary" : "text-text-ui"}`}
            >
              注册
            </button>
          </div>

          <form onSubmit={handleSubmit}>
            <label className="block text-sm font-medium text-text-story mb-1">邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              className="w-full px-4 py-2 rounded-story-md border-2 border-primary/30 mb-3 focus:border-primary focus:outline-none"
              autoComplete="email"
            />
            <label className="block text-sm font-medium text-text-story mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === "register" ? "至少 6 位" : "密码"}
              className="w-full px-4 py-2 rounded-story-md border-2 border-primary/30 mb-3 focus:border-primary focus:outline-none"
              autoComplete={tab === "register" ? "new-password" : "current-password"}
            />
            {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2 rounded-story-md border-2 border-primary/40 text-primary font-medium"
              >
                取消
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-2 rounded-story-md bg-primary text-white font-medium disabled:opacity-60"
              >
                {loading ? "请稍候…" : tab === "login" ? "登录" : "注册"}
              </button>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
