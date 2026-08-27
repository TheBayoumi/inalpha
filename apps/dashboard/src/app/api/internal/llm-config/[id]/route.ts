import { createPublicKey } from "node:crypto";

import { jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

import { decryptUserApiKey } from "@/lib/user-preferences";
import { getPool } from "@/lib/db";

const MAX_CREDENTIAL_TTL_SECONDS = 3_600;
const GRANT_AUDIENCE = "inalpha-dashboard-credential";

function publicKey(): ReturnType<typeof createPublicKey> {
  const value = process.env.EVOLUTION_CREDENTIAL_PUBLIC_KEY_B64?.trim();
  if (!value) throw new Error("EVOLUTION_CREDENTIAL_PUBLIC_KEY_B64 is required");
  return createPublicKey({ key: Buffer.from(value, "base64"), format: "der", type: "spki" });
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
    const { payload } = await jwtVerify(token, publicKey(), {
      algorithms: ["EdDSA"],
      audience: GRANT_AUDIENCE,
      requiredClaims: ["sub", "jti", "iat", "exp", "aud"],
    });
    const issuedAt = payload.iat;
    const expiresAt = payload.exp;
    const now = Math.floor(Date.now() / 1_000);
    if (
      payload.token_use !== "evolver_credential" ||
      payload.config_id !== configId ||
      typeof payload.operation_id !== "string" ||
      payload.operation_id.length < 8 ||
      typeof payload.llm_config_digest !== "string" ||
      !/^[0-9a-f]{64}$/.test(payload.llm_config_digest) ||
      typeof payload.jti !== "string" ||
      !payload.jti ||
      typeof payload.sub !== "string" ||
      !payload.sub ||
      typeof issuedAt !== "number" ||
      typeof expiresAt !== "number" ||
      expiresAt <= issuedAt ||
      expiresAt - issuedAt > MAX_CREDENTIAL_TTL_SECONDS ||
      issuedAt > now
    ) {
      return NextResponse.json({ error: "forbidden" }, { status: 403 });
    }
    subject = payload.sub;

    let consumed;
    try {
      consumed = await getPool().query(
        `INSERT INTO evolution_credential_grant_uses
         (jti,owner_sub,config_id,operation_id,config_digest,consumed_at)
         VALUES ($1,$2,$3,$4,$5,NOW()) ON CONFLICT (jti) DO NOTHING RETURNING jti`,
        [
          payload.jti,
          subject,
          configId,
          payload.operation_id,
          payload.llm_config_digest,
        ],
      );
    } catch {
      return NextResponse.json({ error: "credential_ledger_unavailable" }, { status: 503 });
    }
    if (consumed.rowCount !== 1) {
      return NextResponse.json({ error: "credential_grant_consumed" }, { status: 409 });
    }
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
