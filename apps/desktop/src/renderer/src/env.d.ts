/// <reference types="vite/client" />

// 静态资源模块声明 — vite 构建时由 asset pipeline 处理
declare module '*.png' {
  const src: string
  export default src
}
declare module '*.svg' {
  const src: string
  export default src
}
