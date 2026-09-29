// release-utils.mjs 的类型声明 — 供测试与 TS 侧消费（实现为纯 ESM JS，构建脚本直接运行不需编译）

export declare const ENV_UPDATE_FEED: string
export declare const OUT_CLEANUP_BATCH_SIZE: number

export interface VersionSyncResult {
  ok: boolean
  version?: string
  reason?: string
}

export interface LatestYmlInput {
  version: string
  fileName: string
  sha512: string
  size: number
  releaseDate?: string
}

export interface LatestYmlExpectation {
  version: string
  fileName: string
  sha512: string
  size: number
  /** DL-7 Part A：带此字段时 verifyLatestYml 校验 releaseNotes 存在且一致；未带时校验其省略 */
  releaseNotes?: string
}

export interface VerifyResult {
  ok: boolean
  issues: string[]
}

export interface ArtifactNames {
  exe: string
  blockmap: string
  latestYml: string
}

export declare function extractAppVersion(source: string): string | null
export declare function checkVersionSync(input: { pkgVersion: string; constantsSource: string }): VersionSyncResult
export declare function buildLatestYml(input: LatestYmlInput, releaseNotes?: string | null): string
export declare function extractChangelogSection(changelogSource: string, version: string): string | null
export declare function verifyLatestYml(ymlText: string, expected: LatestYmlExpectation): VerifyResult
export declare function chunk<T>(items: T[], size: number): T[][]
export declare function planOutCleanup(topLevelEntries: string[], batchSize?: number): string[][]
export declare function artifactNames(version: string): ArtifactNames
export declare function classifyNativeAbi(probe: { ok: boolean; error?: string }): 'node' | 'electron' | 'unknown'
export declare function electronTarget(version: string): string
