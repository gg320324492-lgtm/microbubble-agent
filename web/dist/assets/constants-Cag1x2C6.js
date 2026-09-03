import{a2 as r,a7 as s,aL as a,aP as i,g as c,i as u,A as I}from"./index-BmdykG2h.js";const t={prefix:Math.floor(Math.random()*1e4),current:0},d=Symbol("elIdInjection"),m=()=>c()?u(d,t):t,f=n=>{const e=m();!r&&e===t&&s("IdInjection",`Looks like you are using server rendering, you must provide a id provider to ensure the hydration process to be succeed
usage: app.provide(ID_INJECTION_KEY, {
  prefix: number,
  current: number,
})`);const o=a();return i(()=>I(n)||`${o.value}-id-${e.prefix}-${e.current++}`)},y=Symbol("formContextKey"),l=Symbol("formItemContextKey");export{d as I,m as a,y as b,l as f,f as u};
