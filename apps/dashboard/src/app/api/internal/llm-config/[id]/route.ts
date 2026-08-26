import { jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

import { decryptUserApiKey } from "@/lib/user-preferences";

const ALG = process.env.JWT_ALGORITHM ?? "HS256";

function secret(): Uint8Array {
  const value = process.env.JWT_SECRET;
  if (!value) throw new Error("JWT_SECRET is required");
  return new TextEncoder().encode(value);
}

/** Resolves an existing encrypted owner credential for the Evolver service only. */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const configId = (await params).id;
  const raw = request.headers.get("authorization");
  const token = raw?.match(/^Bearer\s+(.+)$/i)?.[1];
  if (!token) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  let subject: string;
  try {
    const { payload } = await jwtVerify(token, secret(), {
      algorithms: [ALG],
      requiredClaims: ["sub", "exp"],
    });
    if (
      payload.token_use !== "evolver_credential" ||
      payload.config_id !== configId ||
      typeof payload.sub !== "string" ||
      !payload.sub
    ) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    subject = payload.sub;
  } catch {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const config = await decryptUserApiKey(subject, configId);
  if (!config) return NextResponse.json({ error: "not_found" }, { status: 404 });
  return NextResponse.json(
    {
      config_id: config.id,
      provider: config.provider,
      model: config.model ?? null,
      base_url: config.custom_base_url ?? null,
      api_key: config.api_key,
    },
    { headers: { "Cache-Control": "no-store" } },
  );
}
