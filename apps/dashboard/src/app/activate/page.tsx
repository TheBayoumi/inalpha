import { Suspense } from "react";

import { ActivateForm } from "@/components/auth/ActivateForm";

/** 公开账号激活页；令牌从 URL fragment 读取，不进入服务器日志。 */
export default function ActivatePage() {
  return (
    <main className="flex min-h-dvh items-center justify-center bg-bg-deep px-4 py-10">
      <Suspense fallback={null}>
        <ActivateForm />
      </Suspense>
    </main>
  );
}
