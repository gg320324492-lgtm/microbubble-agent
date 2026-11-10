import{a7 as r,ac as s,aJ as a,aK as c,i,k as u,H as I}from"./index-BxUPl9Rf.js";const t={prefix:Math.floor(Math.random()*1e4),current:0},d=Symbol("elIdInjection"),m=()=>i()?u(d,t):t,f=n=>{const e=m();!r&&e===t&&s("IdInjection",`Looks like you are using server rendering, you must provide a id provider to ensure the hydration process to be succeed
usage: app.provide(ID_INJECTION_KEY, {
  prefix: number,
  current: number,
})`);const o=a();return c(()=>I(n)||`${o.value}-id-${e.prefix}-${e.current++}`)},y=Symbol("formContextKey"),l=Symbol("formItemContextKey");export{d as I,y as a,m as b,l as f,f as u};
