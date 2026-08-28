"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { pickLoginLocale } from "./login-locale";

const STRINGS = {
  en: {
    title: "Activate trial access",
    password: "New password",
    confirm: "Confirm password",
    hint: "At least 12 characters",
    submit: "Activate account",
    submitting: "Activating…",
    mismatch: "Passwords do not match",
    invalid: "This activation link is invalid, expired, or already used",
    busy: "Activation is busy. Please wait a few seconds and try again.",
    unavailable: "Activation service unavailable, try again later",
    success: "Account activated. You can now sign in.",
    login: "Continue to sign in",
  },
  zh: {
    title: "激活试用账号",
    password: "设置密码",
    confirm: "确认密码",
    hint: "至少 12 个字符",
    submit: "激活账号",
    submitting: "正在激活…",
    mismatch: "两次输入的密码不一致",
    invalid: "激活链接无效、已过期或已经使用",
    busy: "激活请求较多，请等待几秒后重试",
    unavailable: "激活服务暂不可用，请稍后重试",
    success: "账号已激活，现在可以登录。",
    login: "前往登录",
  },
};

const INPUT_CLASS =
  "rounded-md border border-border-subtle bg-bg-deep/60 px-3 py-2 text-sm text-fg outline-none transition-colors focus:border-cyan/50";

/** 一次性激活表单；读取 fragment 后立即清理地址栏，避免令牌留在历史记录。 */
export function ActivateForm() {
  const params = useSearchParams();
  const from = params.get("from");
  const t = STRINGS[pickLoginLocale(from, undefined)];
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loginHref = `/login${from ? `?from=${encodeURIComponent(from)}` : ""}`;

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const activationToken = fragment.get("token") ?? "";
    setToken(activationToken);
    if (!activationToken) setError(t.invalid);
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
  }, [t.invalid]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!token || password !== confirm) {
      setError(token ? t.mismatch : t.invalid);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/activate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, password }),
      });
      if (response.ok) {
        setToken("");
        setSuccess(true);
        return;
      }
      setError(
        response.status === 400 || response.status === 409
          ? t.invalid
          : response.status === 429
            ? t.busy
            : t.unavailable,
      );
    } catch {
      setError(t.unavailable);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-xl border border-border-subtle bg-bg-elev/70 p-8 shadow-lg backdrop-blur-md">
      <div className="text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/inalpha-seal.png" alt="Inalpha" width={56} height={56} className="seal-glow mx-auto size-14" />
        <h1 className="mt-4 text-xl font-medium text-fg">{t.title}</h1>
      </div>
      {success ? (
        <div role="status" className="mt-8 text-center">
          <p className="text-sm text-fg-muted">{t.success}</p>
          <a href={loginHref} className="mt-6 inline-block text-sm text-cyan hover:text-fg">{t.login}</a>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-xs text-fg-muted">
            {t.password} <span className="text-fg-muted/60">{t.hint}</span>
            <input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className={INPUT_CLASS} />
          </label>
          <label className="flex flex-col gap-1.5 text-xs text-fg-muted">
            {t.confirm}
            <input type="password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirm} onChange={(event) => setConfirm(event.target.value)} className={INPUT_CLASS} />
          </label>
          {error && <p role="alert" className="text-center text-sm text-fox-red">{error}</p>}
          <button type="submit" disabled={loading || !token} className="mt-2 rounded-md bg-cyan/15 py-2.5 text-sm font-medium text-cyan hover:bg-cyan/25 disabled:opacity-50">
            {loading ? t.submitting : t.submit}
          </button>
        </form>
      )}
    </div>
  );
}
