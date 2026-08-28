const DEFAULT_MAX_BYTES = 16 * 1024;

/** 公开 JSON 请求读取错误；保留安全的 HTTP 状态，不携带原始请求内容。 */
export class PublicJsonError extends Error {
  constructor(public status: 400 | 413 | 415) {
    super("invalid public JSON request");
    this.name = "PublicJsonError";
  }
}

/** 流式读取公开端点 JSON，并在分配完整正文前执行类型与字节上限检查。 */
export async function readLimitedJson(
  request: Request,
  maxBytes = DEFAULT_MAX_BYTES,
): Promise<unknown> {
  const contentType = request.headers.get("content-type")?.split(";", 1)[0]?.trim();
  if (contentType !== "application/json") throw new PublicJsonError(415);

  const declaredLength = Number(request.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maxBytes) {
    throw new PublicJsonError(413);
  }
  if (!request.body) throw new PublicJsonError(400);

  const reader = request.body.getReader();
  const decoder = new TextDecoder();
  let bytes = 0;
  let text = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > maxBytes) {
      await reader.cancel();
      throw new PublicJsonError(413);
    }
    text += decoder.decode(value, { stream: true });
  }
  text += decoder.decode();
  try {
    return JSON.parse(text) as unknown;
  } catch {
    throw new PublicJsonError(400);
  }
}
