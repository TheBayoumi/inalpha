import { getTranslations } from "next-intl/server";

import { WaitlistClient } from "@/components/admin/WaitlistClient";

/** 管理员试用审核页；API 仍会在服务端实时校验 admin 角色。 */
export default async function AdminWaitlistPage() {
  const t = await getTranslations("adminWaitlist");
  return (
    <section>
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan">Admin</div>
        <h1 className="mt-2 font-display text-3xl text-fg">{t("title")}</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-fg-muted">{t("subtitle")}</p>
      </div>
      <WaitlistClient />
    </section>
  );
}
