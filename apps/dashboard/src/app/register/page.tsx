import { Suspense } from "react";

import { RegisterForm } from "@/components/auth/RegisterForm";

export const metadata = {
  title: "Request access · Inalpha",
  robots: { index: false, follow: false },
};

/** 公开注册申请页，放在 locale 控制台外壳之外，避免未登录组件发起受保护请求。 */
export default function RegisterPage() {
  return (
    <main className="grain flex min-h-dvh items-center justify-center px-4 py-10">
      <Suspense>
        <RegisterForm />
      </Suspense>
    </main>
  );
}
