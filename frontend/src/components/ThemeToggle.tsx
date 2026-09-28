"use client";
import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const [theme, setTheme] = useState<string>("dark");
  useEffect(() => { setTheme(document.documentElement.dataset.theme || "dark"); }, []);
  function flip() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("ip-theme", next); } catch {}
    setTheme(next);
  }
  return (
    <button onClick={flip} aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
      className={`w-9 h-9 shrink-0 rounded-full grid place-items-center border border-line bg-surface text-muted hover:text-paper transition-colors ${className}`}>
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}
