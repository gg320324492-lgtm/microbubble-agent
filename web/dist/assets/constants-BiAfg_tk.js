import{a5 as r,aa as s,aH as a,aI as i,i as c,k as u,H as I}from"./index-BpXInvoL.js";const t={prefix:Math.floor(Math.random()*1e4),current:0},d=Symbol("elIdInjection"),m=()=>c()?u(d,t):t,f=n=>{const e=m();!r&&e===t&&s("IdInjection",`Looks like you are using server rendering, you must provide a id provider to ensure the hydration process to be succeed
usage: app.provide(ID_INJECTION_KEY, {
  prefix: number,
  current: number,
})`);const o=a();return i(()=>I(n)||`${o.value}-id-${e.prefix}-${e.current++}`)},y=Symbol("formContextKey"),l=Symbol("formItemContextKey");export{d as I,y as a,m as b,l as f,f as u};
