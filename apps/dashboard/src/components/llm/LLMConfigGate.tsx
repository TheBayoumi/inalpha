"use client";

import { useEffect, useState } from "react";

import { LLMConfigModal } from "./LLMConfigModal";

const LS_DISMISSED = "inalpha-llm-config-dismissed";

/** 在所有控制台页面管理用户 LLM 配置入口。 */
export function LLMConfigGate() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const openSettings = () => setOpen(true);
    window.addEventListener("inalpha:open-llm-settings", openSettings);

    let mounted = true;
    if (!localStorage.getItem(LS_DISMISSED)) {
      void fetch("/api/user/settings")
        .then((response) => response.ok ? response.json() : null)
        .then((settings) => {
          if (mounted && settings && (!settings.configs || settings.configs.length === 0)) {
            setOpen(true);
          }
        })
        .catch(() => {});
    }

    return () => {
      mounted = false;
      window.removeEventListener("inalpha:open-llm-settings", openSettings);
    };
  }, []);

  return (
    <LLMConfigModal
      open={open}
      onClose={() => {
        setOpen(false);
        localStorage.setItem(LS_DISMISSED, "1");
      }}
    />
  );
}
