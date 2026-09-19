// upload-release-oss.mjs 的类型声明（供 TS 测试消费）
export interface OssCreds {
  bucket: string
  endpoint: string
  accessKeyId: string
  accessKeySecret: string
}
export declare function parseCreds(text: string): OssCreds
export declare function normalizeEndpoint(endpoint: string): string
export declare const ENV_AK: string
export declare const ENV_SK: string
export declare const ENV_BUCKET: string
export declare const ENV_ENDPOINT: string
export declare const DEFAULT_BUCKET: string
export declare const DEFAULT_ENDPOINT: string
export declare function parseCredsFromEnv(env: Record<string, string | undefined>): OssCreds | null
export declare function describeCredsSource(creds: OssCreds, from: string): string
export declare function ossKey(version: string, fileName: string): string
export declare function ossObjectKey(opts: { prefix?: string; version: string; fileName: string }): string
export declare function parseOssError(text: string): { code: string; message: string; requestId: string; hostId: string }
export declare function explainOssError(code: string): string
export declare function describeOssFailure(status: number, text: string): string
export declare function canonicalResource(bucket: string, key: string): string
export declare function signV1(opts: {
  verb: string
  contentMd5?: string
  contentType?: string
  date: string
  canonicalizedResource: string
  accessKeySecret: string
}): string
export declare function authHeader(accessKeyId: string, signature: string): string
export declare function contentMd5(buf: Buffer): string
export declare function objectUrl(endpoint: string, bucket: string, key: string): string
export declare function formatBytes(n: number): string
export declare function verifySize(actual: number, expected: number): { ok: boolean; reason?: string }
export declare function verifySha256(buf: Buffer, expectedHex: string): { ok: boolean; actual: string; reason?: string }
