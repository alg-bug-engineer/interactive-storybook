"use client";

import { create } from "zustand";

const AUTH_TOKEN_KEY = "storybook_token";
const AUTH_USER_KEY = "storybook_user";

export interface AuthUser {
  email: string;
  is_paid: boolean;
  created_at?: string;
}

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  setAuth: (token: string, user: AuthUser) => void;
  logout: () => void;
  setUser: (user: AuthUser) => void;
  loadFromStorage: () => void;
}

function loadStored(): { token: string | null; user: AuthUser | null } {
  if (typeof window === "undefined") return { token: null, user: null };
  try {
    const t = localStorage.getItem(AUTH_TOKEN_KEY);
    const u = localStorage.getItem(AUTH_USER_KEY);
    return {
      token: t,
      user: u ? (JSON.parse(u) as AuthUser) : null,
    };
  } catch {
    return { token: null, user: null };
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,

  setAuth: (token: string, user: AuthUser) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(AUTH_TOKEN_KEY, token);
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    }
    set({ token, user });
  },

  logout: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_USER_KEY);
    }
    set({ token: null, user: null });
  },

  setUser: (user: AuthUser) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
    }
    set({ user });
  },

  loadFromStorage: () => set(loadStored()),
}));
