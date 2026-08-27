import { beforeAll, describe, expect, it, vi } from "vitest";

import { encryptApiKey } from "./encryption";
import { decryptUserApiKey, type UserLLMConfig } from "./user-preferences";

vi.mock("server-only", () => ({}));

beforeAll(() => {
  process.env.JWT_SECRET = "user-preferences-test-secret-at-least-32-bytes";
});

describe("decryptUserApiKey", () => {
  it("decrypts only the exact owner-scoped config reference", async () => {
    const aliceEncrypted = await encryptApiKey("alice-owner-key");
    const otherEncrypted = await encryptApiKey("other-config-key");
    const timestamp = "2026-08-27T00:00:00Z";
    const configs: UserLLMConfig[] = [
      {
        id: "config-alice",
        provider: "deepseek",
        api_key_encrypted: aliceEncrypted.ciphertext,
        api_key_nonce: aliceEncrypted.nonce,
        api_key_tag: aliceEncrypted.tag,
        created_at: timestamp,
        updated_at: timestamp,
      },
      {
        id: "config-other",
        provider: "openai",
        api_key_encrypted: otherEncrypted.ciphertext,
        api_key_nonce: otherEncrypted.nonce,
        api_key_tag: otherEncrypted.tag,
        created_at: timestamp,
        updated_at: timestamp,
      },
    ];

    await expect(
      decryptUserApiKey("user:alice", "config-alice", {
        configs,
        active_config_id: "config-other",
      }),
    ).resolves.toMatchObject({ id: "config-alice", api_key: "alice-owner-key" });
    await expect(
      decryptUserApiKey("user:alice", "missing", {
        configs,
        active_config_id: "config-other",
      }),
    ).resolves.toBeNull();
  });

  it("fails closed when the referenced ciphertext is damaged", async () => {
    const encrypted = await encryptApiKey("alice-owner-key");
    const config: UserLLMConfig = {
      id: "config-alice",
      provider: "deepseek",
      api_key_encrypted: `${encrypted.ciphertext}broken`,
      api_key_nonce: encrypted.nonce,
      api_key_tag: encrypted.tag,
      created_at: "2026-08-27T00:00:00Z",
      updated_at: "2026-08-27T00:00:00Z",
    };

    await expect(
      decryptUserApiKey("user:alice", "config-alice", { configs: [config] }),
    ).rejects.toThrow("Decryption failed");
  });
});
