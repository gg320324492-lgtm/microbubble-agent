import{a1 as a,a6 as s,aC as o,aD as i,g as u,i as c,A as d}from"./index-BGaPgi7X.js";const r={prefix:Math.floor(Math.random()*1e4),current:0},I=Symbol("elIdInjection"),p=()=>u()?c(I,r):r,f=n=>{const e=p();!a&&e===r&&s("IdInjection",`Looks like you are using server rendering, you must provide a id provider to ensure the hydration process to be succeed
usage: app.provide(ID_INJECTION_KEY, {
  prefix: number,
  current: number,
})`);const t=o();return i(()=>d(n)||`${t.value}-id-${e.prefix}-${e.current++}`)};export{I,p as a,f as u};
