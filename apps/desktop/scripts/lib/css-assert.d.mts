// css-assert.mjs 的类型声明（供 TS 测试消费）
export declare const BRAND_PRIMARY: string
export declare function specificity(selector: string): [number, number, number]
export declare function compareSpecificity(a: number[], b: number[]): -1 | 0 | 1
export declare function collectDeclarations(
  css: string,
  prop: string,
  baseIndex?: number
): Array<{ selector: string; value: string; index: number }>
export declare function winningDeclaration(
  declarations: Array<{ selector: string; value: string; index: number }>
): { selector: string; value: string; index: number } | null
export declare function normalizeCssValue(v: unknown): string
export declare function assertCssVariable(
  cssTexts: string[],
  prop: string,
  expected: string
): { ok: boolean; winner: { selector: string; value: string; index: number } | null; reason?: string }
