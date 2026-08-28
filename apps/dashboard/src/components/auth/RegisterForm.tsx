"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";

import { pickLoginLocale } from "./login-locale";

const STRINGS = {
  en: {
    title: "Trial access",
    subtitle: "Tell us how you would like to explore Inalpha",
    name: "Name",
    email: "Email",
    note: "What would you like to explore? (optional)",
    submit: "Join the waitlist",
    submitting: "Submitting…",
    successTitle: "Request received",
    successBody: "We will review your request. If approved, you will receive a one-time activation link by email.",
    invalid: "Please check the form and try again",
    rateLimited: "Too many requests. Please wait before trying again",
    unavailable: "Registration service unavailable, try again later",
    back: "Back to sign in",
  },
  zh: {
    title: "申请试用",
    subtitle: "告诉我们你希望如何探索 Inalpha",
    name: "姓名",
    email: "邮箱",
    note: "你希望探索哪些方向？（选填）",
    submit: "加入候审名单",
    submitting: "提交中…",
    successTitle: "申请已收到",
    successBody: "我们会尽快审核。通过后，管理员会通过邮件发送一次性激活链接。",
    invalid: "请检查填写内容后重试",
    rateLimited: "申请过于频繁，请稍后再试",
    unavailable: "注册服务暂不可用，请稍后重试",
    back: "返回登录",
  },
};

const INPUT_CLASS =
  "rounded-md border border-border-subtle bg-bg-deep/60 px-3 py-2 text-sm text-fg outline-none transition-colors focus:border-cyan/50";

/** 公开试用申请表单；申请成功只进入 waitlist，不建立登录会话。 */
export function RegisterForm() {
  const params = useSearchParams();
  const from = params.get("from");
  const t = STRINGS[pickLoginLocale(from, undefined)];
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [applicationNote, setApplicationNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loginHref = `/login${from ? `?from=${encodeURIComponent(from)}` : ""}`;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          display_name: displayName,
          email,
          application_note: applicationNote,
        }),
      });
      if (response.ok) {
        setSuccess(true);
        return;
      }
      setError(
        response.status === 400
          ? t.invalid
          : response.status === 429
            ? t.rateLimited
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
      <div className="flex flex-col items-center gap-3 text-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/inalpha-seal.png" alt="Inalpha" width={56} height={56} className="seal-glow size-14" />
        <div>
          <div className="font-display text-2xl text-fg">Inalpha</div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.2em] text-fg-muted">{t.title}</div>
        </div>
      </div>

      {success ? (
        <div role="status" className="mt-8 text-center">
          <h1 className="text-lg font-medium text-fg">{t.successTitle}</h1>
          <p className="mt-3 text-sm leading-6 text-fg-muted">{t.successBody}</p>
          <a href={loginHref} className="mt-6 inline-block text-sm text-cyan hover:text-fg">{t.back}</a>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="mt-6">
          <p className="text-center text-sm text-fg-muted">{t.subtitle}</p>
          <div className="mt-6 flex flex-col gap-4">
            <Field label={t.name}>
              <input type="text" autoComplete="name" required maxLength={80} value={displayName} onChange={(event) => setDisplayName(event.target.value)} className={INPUT_CLASS} />
            </Field>
            <Field label={t.email}>
              <input type="email" autoComplete="email" required maxLength={254} value={email} onChange={(event) => setEmail(event.target.value)} className={INPUT_CLASS} />
            </Field>
            <Field label={t.note}>
              <textarea rows={3} maxLength={1000} value={applicationNote} onChange={(event) => setApplicationNote(event.target.value)} className={`${INPUT_CLASS} resize-none`} />
            </Field>
          </div>
          {error && <p role="alert" className="mt-4 text-center text-sm text-red-400">{error}</p>}
          <button type="submit" disabled={loading} className="mt-6 w-full rounded-md bg-cyan/15 py-2.5 text-sm font-medium text-cyan transition-colors hover:bg-cyan/25 disabled:opacity-50">
            {loading ? t.submitting : t.submit}
          </button>
          <a href={loginHref} className="mt-5 block text-center text-xs text-fg-muted hover:text-cyan">{t.back}</a>
        </form>
      )}
    </div>
  );
}

/** 注册字段统一标签，保持辅助说明与输入框关联布局一致。 */
function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-end justify-between gap-2 font-mono text-[11px] uppercase tracking-wider text-fg-muted">
        <span>{label}</span>
        {hint && <span className="normal-case tracking-normal text-fg-muted/60">{hint}</span>}
      </span>
      {children}
    </label>
  );
}
