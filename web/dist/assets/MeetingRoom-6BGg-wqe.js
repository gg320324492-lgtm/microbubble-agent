import{F as e,H as t,I as n,J as r,K as i,P as a,Q as o,R as s,U as c,V as l,Y as u,at as d,it as f,o as p,q as m,rt as h,tt as g,z as _}from"./index-K5PlgXJF.js";import{t as v}from"./_plugin-vue_export-helper-CXTkFu_Z.js";var y=`
class ResampleProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this.targetRate = 16000
    this._buffer = []
  }

  process(inputs, outputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const channel = input[0]
    const inputRate = sampleRate
    const ratio = inputRate / this.targetRate

    // 简单线性重采样（降采样到 16kHz）
    const outputLength = Math.floor(channel.length / ratio)
    const output = new Float32Array(outputLength)
    for (let i = 0; i < outputLength; i++) {
      const srcIdx = i * ratio
      const srcIdxFloor = Math.floor(srcIdx)
      const frac = srcIdx - srcIdxFloor
      const a = channel[srcIdxFloor] || 0
      const b = channel[Math.min(srcIdxFloor + 1, channel.length - 1)] || 0
      output[i] = a + (b - a) * frac
    }

    this.port.postMessage({ type: 'audio', data: output.buffer }, [output.buffer])
    return true
  }
}
registerProcessor('resample-processor', ResampleProcessor)
`,b=null;function x(){let e=null,t=null,n=null,r=null;function i(){if(!b){let e=new Blob([y],{type:`application/javascript`});b=URL.createObjectURL(e)}return b}async function a(a){r=a,t=await navigator.mediaDevices.getUserMedia({audio:{sampleRate:{ideal:16e3},channelCount:{ideal:1},echoCancellation:!0,noiseSuppression:!0,autoGainControl:!1}}),e=new AudioContext({sampleRate:16e3});let o=e.createMediaStreamSource(t);await e.audioWorklet.addModule(i()),n=new AudioWorkletNode(e,`resample-processor`),n.port.onmessage=e=>{e.data.type===`audio`&&r&&r(new Float32Array(e.data.data))},o.connect(n)}function o(){n&&=(n.port.onmessage=null,n.disconnect(),null),e&&=(e.close(),null),t&&=(t.getTracks().forEach(e=>e.stop()),null),r=null}function s(){return e!=null&&e.state===`running`}return{start:a,stop:o,isActive:s}}var S={class:`top-bar`},C={class:`meeting-label`},w={key:0,class:`listening-status`},T={key:1,class:`timer`},E={key:0,class:`standby`},D={key:1,class:`listening-hint`},O={class:`wave-animation`},k={class:`tx-time`},A={class:`tx-text`},j={key:0,class:`speaker-bar`},M={class:`speaker-name`},N={class:`speaker-conf`},P={class:`bottom-bar`},ee=[`disabled`],F=[`disabled`],I=v({__name:`MeetingRoom`,props:{meetingId:{type:[Number,String],required:!0},meetingTitle:{type:String,default:``}},emits:[`meeting-ended`],setup(v,{emit:y}){let b=v,I=y,{start:L,stop:R}=x(),z=g(!1),B=g(!1),V=g(0),H=g(``),U=g(0),W=g([]),G=g(`listening`),K=g(null),q=null,J=null,Y=null,X={},Z=[`#FF7A5C`,`#60A5FA`,`#4ADE80`,`#FBBF24`,`#F87171`,`#A78BFA`,`#22D3EE`,`#FB923C`];function Q(e){return X[e]||(X[e]=Z[Object.keys(X).length%Z.length]),X[e]}let te=e(()=>W.value.length===0?`小气正在聆听...`:`已转写 ${W.value.length} 条`);async function ne(){try{let e=location.protocol===`https:`?`wss:`:`ws:`,t=localStorage.getItem(`access_token`)||``;q=new WebSocket(`${e}//${location.host}/api/v1/ws/meeting/${b.meetingId}/live?token=${encodeURIComponent(t)}`),q.onopen=async()=>{J&&clearInterval(J),z.value=!0,V.value=0,W.value=[],J=setInterval(()=>{V.value++},1e3),await L(re)},q.onmessage=e=>{try{let t=JSON.parse(e.data);t.type===`transcript`?(W.value.push({speaker:t.speaker||`未知`,speaker_confidence:t.speaker_confidence||0,text:t.text||``,start:t.start||0}),t.speaker_confidence>.4&&(H.value=t.speaker,U.value=Math.round((t.speaker_confidence||0)*100),Y&&clearTimeout(Y),Y=setTimeout(()=>{H.value=``},3500)),c(()=>{K.value&&(K.value.scrollTop=K.value.scrollHeight)})):t.type===`ai_reply`?W.value.push({speaker:`小气助手`,speaker_confidence:1,text:t.text||``,start:V.value,is_ai:!0}):t.type===`meeting_ended`&&(p.success(`会议已自动分析完成`),I(`meeting-ended`,{meetingId:b.meetingId,entries:W.value,analysis:t.analysis}))}catch{}},q.onerror=()=>{p.error(`连接失败`),$()}}catch(e){p.error(`启动失败: `+e.message)}}function re(e){if(!q||q.readyState!==WebSocket.OPEN||B.value)return;let t=new Int16Array(e.length);for(let n=0;n<e.length;n++)t[n]=Math.max(-32768,Math.min(32767,Math.round(e[n]*32767)));q.send(t.buffer)}function $(){R(),q&&=(q.close(),null),J&&=(clearInterval(J),null),Y&&=(clearTimeout(Y),null),z.value=!1,H.value=``}function ie(){B.value=!B.value}async function ae(){q&&q.send(JSON.stringify({type:`ai_chat`,text:`小气，总结一下目前的讨论`}))}function oe(e){let t=Math.floor(e/60),n=e%60;return`${String(t).padStart(2,`0`)}:${String(n).padStart(2,`0`)}`}function se(e){if(e==null)return``;let t=Math.floor(e/60),n=Math.floor(e%60);return`${String(t).padStart(2,`0`)}:${String(n).padStart(2,`0`)}`}return i(()=>{z.value&&$()}),(e,i)=>{let c=u(`el-avatar`);return m(),_(`div`,{class:h([`call-screen`,{active:z.value}])},[n(`div`,S,[n(`span`,C,d(v.meetingTitle||`声纹会议`),1),z.value?(m(),_(`div`,w,[n(`span`,{class:h([`pulse-dot`,G.value])},null,2),n(`span`,null,d(te.value),1)])):s(``,!0),z.value?(m(),_(`span`,T,d(oe(V.value)),1)):s(``,!0)]),n(`div`,{class:`transcript-main`,ref_key:`transcriptPanel`,ref:K},[z.value?W.value.length===0?(m(),_(`div`,D,[n(`div`,O,[(m(),_(a,null,r(5,e=>n(`span`,{key:e,class:`wave-bar`,style:f({animationDelay:`${e*.1}s`})},null,4)),64))]),i[1]||=n(`p`,null,`小气正在聆听...`,-1)])):s(``,!0):(m(),_(`div`,E,[...i[0]||=[n(`div`,{class:`standby-icon`},`🎙`,-1),n(`h3`,null,`声纹创建会议`,-1),n(`p`,null,`点击下方按钮开始，小气将实时转录并识别发言人`,-1)]])),(m(!0),_(a,null,r(W.value,(e,t)=>(m(),_(`div`,{key:t,class:`tx-entry`},[n(`span`,{class:`tx-speaker`,style:f({color:Q(e.speaker)})},d(e.speaker),5),n(`span`,k,d(se(e.start)),1),n(`span`,A,d(e.text),1)]))),128))],512),H.value&&z.value?(m(),_(`div`,j,[t(c,{size:32,style:f({background:Q(H.value)})},{default:o(()=>[l(d(H.value[0]),1)]),_:1},8,[`style`]),n(`span`,M,d(H.value),1),n(`span`,N,d(U.value)+`%`,1)])):s(``,!0),n(`div`,P,[n(`button`,{class:h([`ctrl-btn`,{muted:B.value}]),disabled:!z.value,onClick:ie},[n(`span`,null,d(B.value?`🔇`:`🎤`),1),n(`small`,null,d(B.value?`已静音`:`静音`),1)],10,ee),z.value?(m(),_(`button`,{key:1,class:`ctrl-btn hangup-btn`,onClick:$},[...i[3]||=[n(`span`,null,`📞`,-1),n(`small`,null,`结束会议`,-1)]])):(m(),_(`button`,{key:0,class:`ctrl-btn start-btn`,onClick:ne},[...i[2]||=[n(`span`,null,`🎙`,-1),n(`small`,null,`开始会议`,-1)]])),n(`button`,{class:`ctrl-btn`,disabled:!z.value,onClick:ae},[...i[4]||=[n(`span`,null,`🤖`,-1),n(`small`,null,`呼叫小气`,-1)]],8,F)])],2)}}},[[`__scopeId`,`data-v-c707404a`]]);export{I as t};