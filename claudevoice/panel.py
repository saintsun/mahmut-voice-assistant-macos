"""The control panel that opens in a browser.

Binds to 127.0.0.1 only. Shows the application's state and runs exactly the
same actions as the voice commands through buttons (cut / stop / start /
shortcut / switch).
"""
from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mahmut: Voice Assistant</title><style>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500&display=swap");
:root{
  --bg:#070910; --bg2:#0b0f1a;
  --card:rgba(18,23,36,.72); --line:rgba(120,160,255,.14);
  --fg:#e9eefb; --dim:#7e8aa6;
  --neon:#00e5ff; --neon2:#b14bff; --ok:#00ffa3; --warn:#ffcc45; --err:#ff4d6d;
  --glow:0 0 18px rgba(0,229,255,.35);
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0;padding:22px 18px 40px;color:var(--fg);
  font:14px/1.55 Inter,-apple-system,BlinkMacSystemFont,sans-serif;
  background:
    radial-gradient(900px 500px at 12% -8%, rgba(0,229,255,.12), transparent 60%),
    radial-gradient(760px 460px at 92% 4%, rgba(177,75,255,.12), transparent 62%),
    linear-gradient(180deg,var(--bg) 0%,var(--bg2) 100%);
  background-attachment:fixed;
}
/* Keep content from spreading on a wide window: centred, fixed width. */
.nav,.chips,section[data-p]{max-width:920px;margin-left:auto;margin-right:auto}
/* Buttons should not stretch forever, only as far as the row allows. */
button{min-width:0}
.tabs button{flex:0 0 auto;max-width:none}
.hd button,.fav button,.sess button,.vform button,.set button,
.addrow button,.hrow .addv{flex:0 0 auto}
.row{justify-content:flex-start}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:rgba(120,160,255,.2);border-radius:9px}
::-webkit-scrollbar-thumb:hover{background:rgba(0,229,255,.35)}

h1{font-size:15px;margin:0 0 18px;display:flex;align-items:center;gap:11px;
flex-wrap:wrap;letter-spacing:.02em}
h1 .nm{font-weight:700;font-size:16px;letter-spacing:.14em;text-transform:uppercase;
background:linear-gradient(92deg,var(--neon),var(--neon2));
-webkit-background-clip:text;background-clip:text;color:transparent;
filter:drop-shadow(0 0 12px rgba(0,229,255,.45))}
h1 .st{font-weight:500;font-size:12.5px;color:var(--dim)}
header{margin-bottom:16px}
header h1{margin-bottom:9px}
.nav{display:flex;align-items:center;gap:14px;flex-wrap:wrap;
background:var(--card);border:1px solid var(--line);border-radius:999px;
padding:9px 10px 9px 16px;margin-bottom:12px;backdrop-filter:blur(14px);
box-shadow:0 10px 30px rgba(0,0,0,.35)}
.brand{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.brand .ver{font-size:10.5px;color:var(--dim);font-family:"JetBrains Mono",monospace;
  padding:2px 7px;border:1px solid var(--line);border-radius:999px}
.brand .nm{font-weight:700;font-size:14px;letter-spacing:.13em;
text-transform:uppercase;
background:linear-gradient(92deg,var(--neon),var(--neon2));
-webkit-background-clip:text;background-clip:text;color:transparent;
filter:drop-shadow(0 0 10px rgba(0,229,255,.4))}
.tabs{display:flex;gap:5px;flex:1;justify-content:center;flex-wrap:wrap}
.tabs button{padding:7px 15px;border-radius:999px;
background:transparent;border:1px solid transparent;color:var(--dim);
font-size:13px;font-weight:500;box-shadow:none}
.tabs button:hover{color:var(--fg);background:rgba(255,255,255,.05);
border-color:transparent;box-shadow:none}
.tabs button.on{background:#fff;color:#0a0d16;font-weight:650;
box-shadow:0 0 20px rgba(255,255,255,.22)}
.navpause{flex:0 0 auto;min-width:auto;padding:6px 11px;font-size:13px;
border-radius:999px;line-height:1}
.navpause.on{background:rgba(255,204,69,.16);border-color:#ffcc45;
color:#ffcc45;box-shadow:0 0 16px rgba(255,204,69,.45)}
body.paused .card{opacity:.97}
body.paused:before{content:"";position:fixed;inset:0;pointer-events:none;
z-index:5;box-shadow:inset 0 0 0 2px rgba(255,204,69,.35);
animation:pulseEdge 2s ease-in-out infinite}
@keyframes pulseEdge{0%,100%{box-shadow:inset 0 0 0 2px rgba(255,204,69,.2)}
  50%{box-shadow:inset 0 0 0 2px rgba(255,204,69,.55)}}
.navsel{flex:0 0 auto;background:rgba(255,255,255,.05);
border:1px solid var(--line);border-radius:999px;color:var(--fg);
padding:7px 12px;font-size:12.5px;font-family:inherit;cursor:pointer}
.navsel:hover{border-color:rgba(0,229,255,.45);box-shadow:var(--glow)}
.navsel:focus{outline:none;border-color:rgba(0,229,255,.55)}
/* The status text overflowed the header: it now appears as a toast on the
   right and only the state icon stays in the header. */
.navst{flex:0 0 auto;font-size:15px;line-height:1;min-width:24px;text-align:center}
.toasts{position:fixed;top:16px;right:18px;z-index:120;display:flex;
  flex-direction:column;gap:9px;align-items:flex-end;pointer-events:none}
.toast{position:relative;max-width:340px;padding:10px 14px 10px 32px;
  border-radius:13px;font-size:12.5px;line-height:1.45;color:var(--fg);
  background:rgba(13,19,33,.95);border:1px solid var(--line);
  box-shadow:0 14px 34px rgba(0,0,0,.55);backdrop-filter:blur(12px);
  transform-origin:top right;
  /* requestAnimationFrame STOPS in a hidden tab, so the entry animation is
     driven by CSS instead of a JS class. */
  /* CSS animations FREEZE in a hidden tab and the toast stayed stuck on its
     first frame (opacity:0). The resting state is therefore visible and the
     entry animation is only added while the tab is in front (.anim). */
  opacity:1}
.toast.anim{animation:tIn .26s cubic-bezier(.2,.9,.3,1.2)}
/* The entry animation moves ONLY transform. Animating opacity means the
   animation freezes on its first frame when the tab is not painting in the
   background, and the toast never shows up (measured). */
@keyframes tIn{from{transform:translate(12px,-8px) scale(.96)}
  to{transform:none}}
.toast.out{animation:tOut .24s ease forwards}
@keyframes tOut{to{opacity:0;transform:translate(22px,-10px) scale(.96)}}
.toast::before{content:"";position:absolute;left:13px;top:50%;margin-top:-4px;
  width:8px;height:8px;border-radius:50%;background:var(--neon);
  box-shadow:0 0 10px var(--neon)}
.toast.err{border-color:rgba(255,77,109,.5);color:#ffb3c0;
  background:linear-gradient(180deg,rgba(255,77,109,.1),rgba(13,19,33,.95))}
.toast.err::before{background:var(--err);box-shadow:0 0 10px var(--err)}
.toast.ok{border-color:rgba(57,255,20,.55);color:#b4ff86;
  background:linear-gradient(180deg,rgba(57,255,20,.12),rgba(13,19,33,.95));
  box-shadow:0 10px 30px rgba(0,0,0,.5),0 0 18px rgba(57,255,20,.22)}
.toast.ok::before{background:#39ff14;box-shadow:0 0 12px #39ff14,0 0 22px rgba(57,255,20,.6)}
.toast.warn{border-color:rgba(232,255,0,.5);color:#eaff7a;
  background:linear-gradient(180deg,rgba(232,255,0,.11),rgba(13,19,33,.95));
  box-shadow:0 10px 30px rgba(0,0,0,.5),0 0 16px rgba(232,255,0,.18)}
.toast.warn::before{background:#e8ff00;box-shadow:0 0 12px #e8ff00,0 0 20px rgba(232,255,0,.5)}
.toast.info{border-color:rgba(0,229,255,.4);color:#a8f3ff;
  background:linear-gradient(180deg,rgba(0,229,255,.09),rgba(13,19,33,.95))}
.toast.mute{border-color:rgba(120,160,255,.18);color:var(--dim)}
.toast.mute::before{background:var(--dim);box-shadow:none}
@media (max-width:760px){.toasts{left:16px;right:16px;align-items:stretch}
  .toast{max-width:100%}}
section[data-p]{display:none}
section[data-p].on{display:block;animation:fade .18s ease}
@keyframes fade{from{opacity:0;transform:translateY(5px)}to{opacity:1}}
.chips{display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.chip{background:rgba(255,255,255,.04);border:1px solid var(--line);
border-radius:20px;padding:4px 11px;font-size:11px;color:var(--dim);
font-family:"JetBrains Mono",monospace;letter-spacing:.02em;white-space:nowrap}
.chip.ok{color:var(--ok);border-color:rgba(0,255,163,.3);
background:rgba(0,255,163,.07)}
.chip.err{color:var(--err);border-color:rgba(255,77,109,.35);
background:rgba(255,77,109,.09)}
.chip.warn{color:var(--warn);border-color:rgba(255,204,69,.3)}
.chip.bar{width:62px;padding:0;height:5px;border-radius:4px;
background:rgba(255,255,255,.07);overflow:hidden;align-self:center}
.chip.bar i{display:block;height:100%;
background:linear-gradient(90deg,var(--neon),var(--ok));
box-shadow:0 0 8px rgba(0,229,255,.6);transition:width .2s}
.dot{width:9px;height:9px;border-radius:50%;background:var(--dim);
box-shadow:0 0 10px currentColor;color:var(--dim);transition:.3s}

.card{background:var(--card);border:1px solid var(--line);border-radius:15px;
padding:15px 16px;margin-bottom:14px;backdrop-filter:blur(14px);
box-shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 10px 30px rgba(0,0,0,.35);
position:relative;overflow:hidden}
.card:before{content:"";position:absolute;left:0;right:0;top:0;height:1px;
background:linear-gradient(90deg,transparent,rgba(0,229,255,.55),transparent)}
.lbl{color:var(--dim);font-size:10.5px;text-transform:uppercase;
letter-spacing:.17em;margin-bottom:11px;font-weight:600}
/* Reading / Listening / Shortcuts cards side by side. */
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:13px;
align-items:stretch;margin-bottom:13px}
.g3 .card{margin-bottom:0;height:100%;display:flex;flex-direction:column}
.g3 .card .row{align-content:start}
.g3 .row{grid-template-columns:1fr}
.g3 .vol{max-width:none;gap:8px;padding-bottom:16px}
.g3 .swrow{padding-bottom:11px}
.g3 .swrow .t{font-size:13px}
@media (max-width:880px){.g3{grid-template-columns:1fr}}
/* Buffer takes the left half, the archive sits on the right. */
.g2{display:grid;grid-template-columns:1fr 1fr;gap:13px;
align-items:stretch;margin-bottom:13px}
.g2 .card{margin-bottom:0;display:flex;flex-direction:column;min-height:290px}
.g2 .addrow input{font-size:12.5px;padding:7px 10px}
/* Both cards the same height: inner areas fill the space. */
.g2 .buf{flex:1}
.g2 .hist{flex:1;max-height:none;min-height:150px}
@media (max-width:880px){.g2{grid-template-columns:1fr}}

/* Three-column grid: cards stay side by side instead of spreading. */
.row{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}
@media (max-width:620px){.row{grid-template-columns:repeat(2,1fr)}}
@media (max-width:400px){.row{grid-template-columns:1fr}}

button{background:rgba(255,255,255,.035);color:var(--fg);
border:1px solid var(--line);border-radius:10px;padding:9px 12px;
font-size:12.5px;font-family:inherit;font-weight:500;cursor:pointer;
min-width:0;transition:.16s;letter-spacing:.01em;
white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
button:hover{border-color:rgba(0,229,255,.5);background:rgba(0,229,255,.08);
box-shadow:var(--glow);color:#fff}
button:active{transform:translateY(1px)}
button:disabled{opacity:.3;cursor:default;box-shadow:none;
border-color:var(--line);background:rgba(255,255,255,.03)}
button.p{max-width:none;background:linear-gradient(95deg,rgba(0,229,255,.22),rgba(177,75,255,.22));
border-color:rgba(0,229,255,.5);color:#fff;font-weight:600;box-shadow:var(--glow)}
button.p:hover{background:linear-gradient(95deg,rgba(0,229,255,.34),rgba(177,75,255,.34));
box-shadow:0 0 26px rgba(0,229,255,.5)}
button.d{background:rgba(255,77,109,.1);border-color:rgba(255,77,109,.32)}
button.d:hover{background:rgba(255,77,109,.18);border-color:rgba(255,77,109,.6);
box-shadow:0 0 18px rgba(255,77,109,.3)}

.kv{display:flex;justify-content:space-between;padding:7px 0;
border-bottom:1px solid rgba(120,160,255,.08);font-size:13px}
.kv:last-child{border:0}
.kv span:first-child{color:var(--dim)}
.kv span:last-child{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:12px}

.buf{background:rgba(0,0,0,.35);border:1px solid var(--line);border-radius:11px;
padding:12px;min-height:46px;font-size:13px;color:var(--dim);word-break:break-word;
line-height:1.6}
.buf.has{color:var(--fg);border-color:rgba(0,229,255,.3);
box-shadow:0 0 16px rgba(0,229,255,.12) inset}

.sess{display:flex;align-items:center;gap:9px;padding:8px 0;
border-bottom:1px solid rgba(120,160,255,.08)}
.sess:last-child{border:0}
.sess .nm{flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.sess button{flex:0 0 auto;min-width:auto;padding:4px 9px;font-size:11px;
border-radius:8px}
.sess{gap:7px;padding:6px 0}
.sess .nm{font-size:12.5px}
.mini{font-size:11px;color:var(--dim);margin-top:9px;line-height:1.6}

.hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:11px}
.hd button{flex:0 0 auto;min-width:auto;padding:6px 12px;font-size:12px}
.hist{max-height:420px;overflow-y:auto;background:rgba(0,0,0,.3);
border:1px solid var(--line);border-radius:11px}
.hrow{display:flex;gap:10px;padding:9px 12px;
border-bottom:1px solid rgba(120,160,255,.07);cursor:pointer;font-size:13px;
transition:.12s}
.hrow:last-child{border:0}
.hrow:hover{background:rgba(0,229,255,.06)}
.hrow .tm{color:var(--dim);font-family:"JetBrains Mono",monospace;font-size:11.5px;
flex:0 0 auto;padding-top:1px}
.hrow .tx{flex:1;word-break:break-word}
.hrow .rs{font-size:11px;flex:0 0 auto;align-self:center;white-space:nowrap;
color:var(--dim)}
.hrow .rs.fire{color:var(--ok);font-weight:600;text-shadow:0 0 10px rgba(0,255,163,.5)}
.hrow .addv{flex:0 0 auto;min-width:auto;padding:2px 9px;font-size:14px;
line-height:1.2;border-radius:8px;opacity:.35}
.hrow:hover .addv{opacity:1}
.copied{color:var(--ok)!important}

.swrow{display:flex;align-items:center;justify-content:space-between;gap:12px;
padding:2px 2px 14px}
.swrow .t{font-size:14.5px;font-weight:500}
.swrow .s{font-size:11.5px;color:var(--dim);margin-top:3px}
.sw{position:relative;display:inline-block;width:52px;height:30px;flex:0 0 auto}
.sw input{opacity:0;width:0;height:0}
.sl{position:absolute;inset:0;cursor:pointer;background:rgba(255,255,255,.08);
border:1px solid var(--line);border-radius:30px;transition:.25s}
.sl:before{content:"";position:absolute;height:22px;width:22px;left:3px;top:3px;
background:#aab4cc;border-radius:50%;transition:.25s}
.sw input:checked+.sl{background:rgba(0,255,163,.18);
border-color:rgba(0,255,163,.55);box-shadow:0 0 16px rgba(0,255,163,.35)}
.sw input:checked+.sl:before{transform:translateX(22px);background:var(--ok);
box-shadow:0 0 12px var(--ok)}

.vol{display:flex;align-items:center;gap:11px;
padding:13px 2px 15px;max-width:340px}
.vol .vl{font-size:12px;color:var(--dim);flex:0 0 auto}
.vol input[type=range]{flex:1;-webkit-appearance:none;height:4px;border-radius:3px;
background:linear-gradient(90deg,rgba(0,229,255,.45),rgba(177,75,255,.45));
outline:none;cursor:pointer}
.vol input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:14px;
height:14px;border-radius:50%;background:#fff;cursor:pointer;
box-shadow:0 0 10px rgba(0,229,255,.7)}
.vol .vv{font-family:"JetBrains Mono",monospace;color:var(--dim);font-size:12px;
min-width:38px;text-align:right}

.set{display:flex;align-items:center;gap:11px;padding:8px 0;
border-bottom:1px solid rgba(120,160,255,.08)}
.set:last-of-type{border:0}
.set .k{flex:0 0 108px;font-size:12.5px;color:var(--dim)}
.set input,.set select{flex:1;background:rgba(0,0,0,.4);border:1px solid var(--line);
border-radius:9px;color:var(--fg);padding:8px 11px;font-size:13px;
font-family:inherit;min-width:0}
.set input:focus,.set select:focus{outline:none;border-color:rgba(0,229,255,.55);
box-shadow:var(--glow)}
.set button{flex:0 0 auto;min-width:auto;padding:8px 13px;font-size:12.5px}
.tstcard{border-color:rgba(0,229,255,.22)}
.tstres{margin-top:11px;padding:13px 15px;border-radius:11px;font-size:13.5px;
background:rgba(0,0,0,.4);border:1px solid var(--line);color:var(--dim);
display:flex;align-items:center;gap:10px;min-height:46px;transition:.18s}
.tstres:before{content:"›";font-size:16px;color:var(--dim);line-height:1}
.tstres.hit{color:var(--ok);border-color:rgba(0,255,163,.45);
background:rgba(0,255,163,.07);
box-shadow:0 0 20px rgba(0,255,163,.14) inset;font-weight:600}
.tstres.hit:before{content:"✓";color:var(--ok)}
.tstrow{display:flex;gap:9px}
.tstrow input{flex:1;padding:11px 14px;font-size:13.5px}

.fav{display:flex;align-items:center;gap:9px;padding:8px 0;
border-bottom:1px solid rgba(120,160,255,.08)}
.fav:last-child{border:0}
.fav .no{flex:0 0 27px;height:27px;border-radius:9px;
background:linear-gradient(135deg,rgba(0,229,255,.18),rgba(177,75,255,.18));
border:1px solid rgba(0,229,255,.28);display:flex;align-items:center;
justify-content:center;font-size:12px;font-weight:700;color:var(--neon);
font-family:"JetBrains Mono",monospace}
.fav .nm{flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;
white-space:nowrap}
.fav .nm.off{color:var(--dim)}
.fav button{flex:0 0 auto;min-width:auto;padding:4px 8px;font-size:11px;
border-radius:8px;line-height:1.3}
.fav{gap:6px;padding:6px 0}
.fav .no{flex:0 0 22px;height:22px;border-radius:7px;font-size:11px}
.fav .nm{font-size:12.5px}
.fav .x{color:#ff8a9c}
.fav .x:hover{border-color:rgba(255,77,109,.6);background:rgba(255,77,109,.14);
box-shadow:0 0 16px rgba(255,77,109,.28)}
.addrow{display:flex;gap:9px;margin-top:11px}
.tstrow input,.addrow input,.fav input.ed,.fav select.ln,.vform select{
background:rgba(0,0,0,.4);border:1px solid var(--line);border-radius:10px;
color:var(--fg);padding:9px 12px;font-size:13px;font-family:inherit;min-width:0}
.addrow input{flex:1}
.tstrow input:focus,.addrow input:focus,.fav input.ed:focus,
.vform select:focus,.set input:focus,.set select:focus{outline:none;
border-color:rgba(0,229,255,.55);box-shadow:var(--glow)}
.fav input.ed{flex:1;border-color:rgba(0,229,255,.5)}
.fav select.ln{flex:1;font-size:12px;padding:6px 9px}

.vform{background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.35);
border-radius:11px;padding:13px;margin:7px 0;
box-shadow:0 0 22px rgba(0,229,255,.1) inset}
.vform .hint{font-size:11.5px;color:var(--dim);margin-bottom:9px;line-height:1.6}
.vform .hint b{color:var(--neon);font-weight:600}
.vform .r2{display:flex;gap:9px;align-items:center}
.vform select{flex:1}
.vform button{flex:0 0 auto;min-width:auto;padding:9px 14px;font-size:13px}
.ctab{width:100%;border-collapse:collapse;font-size:12.5px}
.ctab th{text-align:left;color:var(--dim);font-size:10.5px;font-weight:600;
text-transform:uppercase;letter-spacing:.14em;padding:0 8px 8px;
border-bottom:1px solid var(--line)}
.ctab th.num,.ctab td.num{text-align:right;width:52px}
.ctab td{padding:7px 8px;border-bottom:1px solid rgba(120,160,255,.07);
vertical-align:middle}
.ctab tr.crow{cursor:pointer}
.ctab tr.crow:hover td{background:rgba(0,229,255,.06)}
.ctab .ed{width:92px;text-align:right}
.ctab .ed button{min-width:auto;padding:5px 11px;font-size:11.5px;
border-radius:8px;border-color:rgba(0,229,255,.35);
background:rgba(0,229,255,.09);color:var(--fg)}
.ctab .ed button:hover{background:rgba(0,229,255,.2);
border-color:rgba(0,229,255,.7);box-shadow:var(--glow)}
.modal{position:fixed;inset:0;z-index:100;background:rgba(4,6,12,.72);
backdrop-filter:blur(6px);display:flex;align-items:center;
justify-content:center;padding:24px}
.mbox{width:100%;max-width:620px;max-height:84vh;overflow-y:auto;
background:#0c111d;border:1px solid rgba(0,229,255,.4);border-radius:16px;
padding:18px;box-shadow:0 30px 80px rgba(0,0,0,.7),0 0 40px rgba(0,229,255,.15)}
.mhead{display:flex;align-items:center;gap:12px;margin-bottom:14px;
padding-bottom:12px;border-bottom:1px solid var(--line)}
.mhead span{flex:1;font-size:14.5px;font-weight:650}
.mx{flex:0 0 auto;min-width:auto;padding:4px 11px;font-size:17px;
border-radius:9px;line-height:1}
.mbox .cdet{background:transparent;border:0;padding:0;margin:0}
.ctab .ct{font-family:"JetBrains Mono",monospace;font-size:11px;
color:var(--dim);width:64px;text-align:right}
.ctab .cs{font-family:"JetBrains Mono",monospace;font-size:11.5px;
color:var(--neon)}
.ctab .cs input{width:100%;background:rgba(0,0,0,.45);
border:1px solid rgba(0,229,255,.5);border-radius:7px;color:var(--fg);
padding:4px 8px;font-size:11.5px;font-family:"JetBrains Mono",monospace}
.ctab .cs input:focus{outline:none}
.ctab td.det{padding:0 8px 8px}
.cdet{background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.3);
border-radius:11px;padding:12px;margin:7px 0}
.ph{display:flex;align-items:center;gap:8px;padding:5px 0;font-size:12.5px;
border-bottom:1px solid rgba(120,160,255,.07)}
.ph .pt{flex:1;font-family:"JetBrains Mono",monospace;font-size:11.5px}
.ph .lock{font-size:11px;color:var(--dim)}
.ph button{flex:0 0 auto;min-width:auto;padding:3px 8px;font-size:11px}
.cvar{margin-top:9px;font-size:11px;color:var(--dim);line-height:2}
.vrow{margin-bottom:4px}
.vch{display:inline-flex;align-items:center;gap:5px;margin:2px 3px;padding:2px 7px;
  border:1px solid var(--line);border-radius:7px;color:var(--fg);
  font-family:"JetBrains Mono",monospace;font-size:10.5px}
.vch button{all:unset;cursor:pointer;color:#ff8a9c;font-size:12px;line-height:1;opacity:.75}
.vch button:hover{opacity:1}
.vch.base{color:var(--neon);border-color:rgba(0,229,255,.35)}
.amsg{margin:9px 0 2px;padding:8px 11px;border-radius:9px;font-size:12px;
  background:rgba(255,77,109,.1);border:1px solid rgba(255,77,109,.35);color:#ffb3c0}
.tgt{font-size:10.5px;color:var(--neon);letter-spacing:.06em;
  text-transform:none;font-weight:600;margin-left:7px}
.alt{opacity:.42;filter:saturate(.5)}
.alt .card{pointer-events:none}
.alt .tgt{color:var(--dim)}
.pager{display:flex;align-items:center;justify-content:center;gap:9px;
  margin-top:9px;font-size:11.5px;color:var(--dim)}
.pager button{min-width:auto;padding:4px 11px;font-size:12px;line-height:1.1}
.pager button:disabled{opacity:.35;cursor:default}
.pager .pg{font-family:"JetBrains Mono",monospace;letter-spacing:.04em}
.mini.okmsg{color:#b4ff86}
.mini.errmsg{color:#ffb3c0}
.amsg.ok{background:rgba(0,255,163,.08);border-color:rgba(0,255,163,.3);color:#9affd8}
.cvar b{color:var(--neon);font-weight:600;font-family:"JetBrains Mono",monospace}
.inwrap{position:relative;flex:1;display:flex;min-width:0}
.inwrap input{flex:1;padding-right:42px!important}
.inmic{position:absolute;right:5px;top:50%;transform:translateY(-50%);
min-width:auto;padding:5px 9px;font-size:15px;border-radius:8px;
background:transparent;border:1px solid transparent;line-height:1}
.inmic:hover{background:rgba(0,229,255,.12);border-color:rgba(0,229,255,.4)}
.inmic.rec{background:rgba(255,77,109,.18);border-color:rgba(255,77,109,.6);
animation:pulseRec 1s ease-in-out infinite}
@keyframes pulseRec{0%,100%{box-shadow:0 0 0 rgba(255,77,109,0)}
  50%{box-shadow:0 0 18px rgba(255,77,109,.7)}}
.vp{position:relative;flex:1;min-width:0}
.vptrig{width:100%;text-align:left;background:rgba(0,0,0,.4);
border:1px solid var(--line);border-radius:9px;padding:8px 11px;
font-size:13px;color:var(--fg)}
.vptrig:hover{border-color:rgba(0,229,255,.45)}
.vppop{position:absolute;z-index:40;left:0;right:0;top:calc(100% + 6px);
background:#0d1220;border:1px solid rgba(0,229,255,.35);border-radius:11px;
padding:9px;box-shadow:0 18px 44px rgba(0,0,0,.6);
box-shadow:0 18px 44px rgba(0,0,0,.6), 0 0 22px rgba(0,229,255,.12)}
.vppop input{width:100%;background:rgba(0,0,0,.45);border:1px solid var(--line);
border-radius:8px;color:var(--fg);padding:8px 11px;font-size:12.5px;
font-family:inherit;margin-bottom:8px}
.vppop input:focus{outline:none;border-color:rgba(0,229,255,.55)}
.vplist{max-height:260px;overflow-y:auto}
.vpi{display:flex;gap:10px;align-items:center;padding:7px 9px;border-radius:8px;
cursor:pointer;font-size:12.5px}
.vpi:hover{background:rgba(0,229,255,.1)}
.vpi.on{background:rgba(0,229,255,.16);color:#fff}
.vpi .l{flex:0 0 94px;color:var(--dim);font-size:11.5px;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vpi .n{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.vpnone{padding:10px;color:var(--dim);font-size:12px;text-align:center}
.banner{max-width:920px;margin:0 auto 14px;display:flex;align-items:center;
gap:12px;padding:12px 16px;border-radius:13px;font-size:13px;
color:#ffe9a3;background:rgba(255,204,69,.09);
border:1px solid rgba(255,204,69,.45);
box-shadow:0 0 24px rgba(255,204,69,.18), 0 0 12px rgba(255,204,69,.12) inset}
.banner span{flex:1;line-height:1.5}
.banner button{flex:0 0 auto;min-width:auto;padding:8px 14px;font-size:12.5px;
color:#1a1405;background:#ffcc45;border-color:#ffcc45;font-weight:650;
box-shadow:0 0 18px rgba(255,204,69,.5)}
.banner button:hover{background:#ffd868;border-color:#ffd868;
box-shadow:0 0 26px rgba(255,204,69,.7)}
@keyframes pulseY{
  0%,100%{box-shadow:0 0 0 rgba(255,204,69,0);border-color:var(--line)}
  50%{box-shadow:0 0 22px rgba(255,204,69,.75);border-color:#ffcc45}}
@keyframes pulseBg{0%,100%{background:rgba(255,204,69,.05)}
  50%{background:rgba(255,204,69,.16)}}
.hl{animation:pulseY 1.1s ease-in-out infinite}
.hlbg{animation:pulseBg 1.1s ease-in-out infinite}
.cap{margin-top:10px;padding:10px;border-radius:9px;
background:rgba(0,255,163,.07);border:1px solid rgba(0,255,163,.35)}
</style></head><body>
<nav class="nav">
  <div class="brand"><span class="dot" id="dot"></span>
    <span class="nm">Mahmut: Voice Assistant</span>
    <span class="ver" id="ver"></span></div>
  <div class="tabs">
    <button data-p="kontrol" class="on" onclick="page('kontrol')" data-i18n="tab_control" title="" data-i18n-title="tt_tab_control">Kontrol</button>
    <button data-p="liste" onclick="page('liste')" data-i18n="tab_list" data-i18n-title="tt_tab_list">Liste</button>
    <button data-p="ayar" onclick="page('ayar')" data-i18n="tab_set" data-i18n-title="tt_tab_set">Ayarlar</button>
  </div>
  <button class="navpause" id="navPause" onclick="go('pause')"
    data-i18n-title="tt_pause">&#9208;</button>
  <span class="navst" id="ttl">bağlanıyor…</span>
  <select class="navsel" id="navLoc" data-i18n-title="tt_loc" onchange="setLoc(this.value)">
    <option value="tr">Türkçe</option><option value="en">English</option>
  </select>
</nav>
<div class="toasts" id="toasts"></div>
<div class="chips" id="chips" style="margin-bottom:15px"></div>
<div class="modal" id="modal" style="display:none" onclick="cmdClose(event)">
  <div class="mbox" onclick="event.stopPropagation()">
    <div class="mhead">
      <span id="mTitle"></span>
      <button class="mx" onclick="cmdClose()" title="Kapat">&times;</button>
    </div>
    <div id="mBody"></div>
  </div>
</div>
<div class="banner" id="banner" style="display:none">
  <span id="bannerTx"></span>
  <button onclick="gotoCmds()" data-i18n="btn_goto">Komutları aç</button>
</div>

<section data-p="kontrol" class="on">
<div class="g3">
<div class="card">
  <div class="lbl" data-i18n="s_read">Okuma</div>
  <div class="swrow">
    <div>
      <div class="t" data-i18n="read_toggle">Claude mesajlarını oku</div>
      <div class="s" id="ttss"></div>
    </div>
    <label class="sw"><input type="checkbox" id="swTts" onchange="toggleTts()">
      <span class="sl"></span></label>
  </div>
  <div class="vol">
    <span class="vl" data-i18n="vol">Ses</span>
    <input type="range" id="vol" min="0" max="100" step="5"
           oninput="volLive(this.value)" onchange="volSet(this.value)">
    <span class="vv" id="vv">—</span>
  </div>
  <div class="row" style="grid-template-columns:1fr">
    <button class="p" onclick="go('cut')" data-i18n-title="tt_cut" data-i18n="btn_cut">✂️&nbsp; Okumayı kes</button>
  </div>
</div>
<div class="card">
  <div class="lbl" data-i18n="s_listen">Dinleme</div>
  <div class="row">
    <button onclick="go('start')" data-i18n-title="tt_start" data-i18n="btn_start">▶&nbsp; Başla</button>
    <button onclick="go('stop')" data-i18n-title="tt_stop" data-i18n="btn_stop">⏸&nbsp; Dur</button>
    <button class="d" onclick="go('off')" data-i18n-title="tt_micoff" data-i18n="btn_micoff">⏹&nbsp; Mikrofonu kapat</button>
    <button onclick="go('mic_refresh')" data-i18n-title="tt_micref" data-i18n="btn_micref">🔄&nbsp; Mikrofonu yenile</button>
  </div>
</div>
<div class="card">
  <div class="lbl" data-i18n="s_hotkeys">Kısayollar</div>
  <div class="row" id="hk"></div>
</div>
</div>
<div class="g2">
<div class="card">
  <div class="lbl" data-i18n="s_buffer">Tampon</div>
  <div class="buf" id="buf"></div>
  <div class="row" style="margin-top:10px;grid-template-columns:repeat(2,1fr)">
    <button onclick="go('send')" data-i18n-title="tt_send" data-i18n="btn_send">Gönder</button>
    <button onclick="go('clear')" data-i18n-title="tt_clear" data-i18n="btn_clear">Temizle</button>
  </div>
  <div class="mini" id="heard"></div>
</div>
<div class="card">
  <div class="hd">
    <span class="lbl" style="margin:0" data-i18n="s_heard">Son duyulanlar</span>
    <span style="display:flex;gap:7px">
      <button onclick="copyAll()" id="cpy" data-i18n-title="tt_copyall" data-i18n="btn_copyall">Hepsini kopyala</button>
      <button onclick="histClear()" data-i18n="btn_clear">Temizle</button>
    </span>
  </div>
  <div class="hist" id="hist"></div>
  <div class="pager" id="pager"></div>
  <div class="mini" data-i18n="hint_heard">Bir satıra tıkla → panoya kopyalanır. Yeşil = komut tetikledi.</div>
</div>
</div>
</section>

<section data-p="liste">
<div class="card tstcard">
  <div class="lbl" data-i18n="s_test">Komut testi</div>
    <div class="tstrow">
      <span class="inwrap">
        <input id="tstIn" data-i18n-ph="ph_test" placeholder="bir cümle yaz, hangi komuta gittiğini gör…"
          oninput="testRun()" onkeydown="if(event.key==='Enter')testRun()">
        <button class="inmic" id="tstMic" onclick="testMic()"
          data-i18n-title="tt_testmic">&#127908;</button>
      </span>
      <button onclick="testRun()" data-i18n-title="tt_try" data-i18n="btn_try">Dene</button>
    </div>
    <div class="tstres" id="tstOut">bir şey yaz…</div>
    <div class="tstrow" id="tstAdd" style="margin-top:9px;display:none">
      <select id="tstCmd"></select>
      <button class="p" onclick="testAdd()" data-i18n-title="tt_addcmd" data-i18n="btn_addcmd">Bu komuta ekle</button>
    </div>
</div>

<div class="g2">
<div class="card">
  <div class="hd">
    <span class="lbl" style="margin:0"><span data-i18n="s_list">Liste</span>
      <span class="tgt" id="tgtA"></span></span>
    <button onclick="go('list_read')" data-i18n-title="tt_readlist" data-i18n="btn_readlist">🔊&nbsp; Listeyi oku</button>
  </div>
  <div id="fav"></div>
  <div class="addrow">
    <input id="favin" list="opensess" data-i18n-ph="ph_addconv" placeholder="konuşma adı ekle…"
           onkeydown="if(event.key==='Enter')favAdd()">
    <datalist id="opensess"></datalist>
    <button onclick="favAdd()" style="flex:0 0 auto;min-width:auto" data-i18n-title="tt_add" data-i18n="btn_add">Ekle</button>
  </div>
  <div class="mini" data-i18n="hint_list">Adı değiştirmek için ✎ ya da çift tıkla.</div>
</div>
<div class="card">
  <div class="lbl"><span data-i18n="s_open">Açık konuşmalar</span>
    <span class="tgt" id="tgtB"></span></div>
  <div id="sess"></div>
</div>
</div>

<div class="g2 alt" id="altWrap" style="display:none">
<div class="card">
  <div class="hd">
    <span class="lbl" style="margin:0"><span data-i18n="s_list">Liste</span>
      <span class="tgt" id="tgtC"></span></span>
    <span class="mini" data-i18n="alt_off">pasif</span>
  </div>
  <div id="fav2"></div>
  <div class="mini" data-i18n="hint_alt">Bu uygulama seçili değil. Ayarlar >
    Kod uygulaması'ndan geçersen bu liste etkin olur.</div>
</div>
<div class="card">
  <div class="lbl"><span data-i18n="s_open">Açık konuşmalar</span>
    <span class="tgt" id="tgtD"></span></div>
  <div id="sess2"></div>
</div>
</div>

<div class="card">
  <div class="lbl" data-i18n="s_cmds">Komut kalıpları</div>
  <div id="cmds"></div>
  <div class="mini" data-i18n="hint_cmds">Bir komuta tıkla, kalıplarını gör,
    sil ya da yenisini ekle. Mikrofon düğmesiyle söyleyerek de ekleyebilirsin.</div>
</div>
</section>

<section data-p="ayar">
<div class="g2">
<div class="card">
  <div class="lbl" data-i18n="s_voice_set">Ses ve dil</div>
  <div class="set">
    <span class="k" data-i18n="k_name">Çağrı adı</span>
    <input id="stName" data-i18n-title="tt_name" placeholder="mahmut"
      onkeydown="if(event.key==='Enter')saveName()">
    <button onclick="saveName()" data-i18n-title="tt_save" data-i18n="btn_save">Kaydet</button>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_mic">Mikrofon</span>
    <select id="stIn" data-i18n-title="tt_mic"
      onchange="go('set_input_device',this.value).then(r=>{if(r&&r.msg)toast(r.msg,toastKind(r.msg));})"></select>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_spk">Hoparlör</span>
    <select id="stOut" data-i18n-title="tt_spk"
      onchange="go('set_output_device',this.value).then(r=>{if(r&&r.msg)toast(r.msg,toastKind(r.msg));})"></select>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_lang">Konuşma dili</span>
    <select id="stLang" data-i18n-title="tt_lang" onchange="go('set_language',this.value)">
      <option value="tr" data-i18n="lang_tr">Türkçe</option>
      <option value="en" data-i18n="lang_en">İngilizce</option>
      <option value="auto" data-i18n="lang_auto">Otomatik algıla</option>
    </select>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_pack">Komut seti</span>
    <select id="stPack"></select>
    <button onclick="loadPack()" data-i18n-title="tt_loadreset" data-i18n="btn_loadreset">Yükle / Sıfırla</button>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_voice">Okuma sesi</span>
    <div class="vp" id="vp">
      <button class="vptrig" id="vpTrig" data-i18n-title="tt_voice"
        onclick="vpToggle()">—</button>
      <div class="vppop" id="vpPop" style="display:none">
        <input id="vpQ" data-i18n-ph="ph_search" placeholder="ara…"
          oninput="vpRender()" onkeydown="if(event.key==='Escape')vpClose()">
        <div class="vplist" id="vpList"></div>
      </div>
    </div>
    <button onclick="go('voice_test')" data-i18n-title="tt_voicetest"
      data-i18n="btn_test">Dene</button>
  </div>
  <div class="mini" data-i18n="hint_name">Çağrı adını değiştirirsen tüm komut kalıpları yeni ada taşınır, eski adın yazım varyantları silinir.</div>
</div>

<div class="card">
  <div class="lbl" data-i18n="s_system">Sistem</div>
  <div class="set">
    <span class="k" data-i18n="k_target">Kod uygulaması</span>
    <select id="stTarget" data-i18n-title="tt_target" onchange="setTarget(this.value)"></select>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_stophk">Okumayı kes kısayolu</span>
    <input id="stHk" data-i18n-title="tt_stophk" placeholder="cmd+alt+k"
      onkeydown="if(event.key==='Enter')saveHk()">
    <button onclick="saveHk()" data-i18n-title="tt_save" data-i18n="btn_save">Kaydet</button>
  </div>
  <div class="set">
    <span class="k" data-i18n="k_port">Panel portu</span>
    <input id="stPort" data-i18n-title="tt_port" placeholder="8765"
      oninput="portCheck()" onkeydown="if(event.key==='Enter')portSave()">
    <button id="portBtn" onclick="portSave()" disabled
      data-i18n-title="tt_portsave" data-i18n="btn_save">Kaydet</button>
  </div>
  <div class="mini" id="portMsg" style="margin:-2px 0 0"></div>
  <div class="mini" data-i18n="hint_system">Kısayol her yerden çalışır; öndeki uygulamaya da gittiği için boşta bir kombinasyon seç. Port doluysa panel sıradaki boş porta geçer.</div>
</div>
</div>
</section>

<script>
const ICON={off:"⚪️",sleep:"😴",armed:"🎙",live:"🔴"};
let HIST=[], TOUCH=0;
function toggleTts(){ TOUCH=Date.now(); go('tts'); }
let VTOUCH=0;
function volLive(v){ VTOUCH=Date.now(); document.getElementById("vv").textContent="%"+v; }
function volSet(v){ VTOUCH=Date.now(); go('volume',(v/100).toFixed(2)); }
let FAVEDIT=null;
function favEdit(i){
  FAVEDIT=i;
  const f=FAV[i]||{name:""};
  const opts=['<option value="">— açık konuşmaya bağla —</option>']
    .concat((SESS||[]).map(s=>`<option value="${esc(s.name)}">${esc(s.name)}</option>`))
    .join("");
  document.getElementById("fav").innerHTML=FAV.map((x,j)=> j!==i
    ? `<div class="fav"><span class="no">${j+1}</span>
       <span class="nm${x.open?"":" off"}">${esc(x.name)}</span></div>`
    : `<div class="fav"><span class="no">${j+1}</span>
       <input class="ed" id="faved" value="${esc(f.name)}"
         onkeydown="if(event.key==='Enter')favSave(${i});if(event.key==='Escape')favCancel()">
       <button class="p" onclick="favSave(${i})">Kaydet</button>
       <button onclick="favCancel()">İptal</button></div>
       <div class="fav"><span class="no">↳</span>
       <select class="ln" id="favln" onchange="favLink(${i},this.value)">${opts}</select></div>`
  ).join("");
  const el=document.getElementById("faved"); if(el){ el.focus(); el.select(); }
}
function favCancel(){ FAVEDIT=null; tick(); }
async function favSave(i){
  const v=document.getElementById("faved").value.trim();
  FAVEDIT=null;
  if(v) await go('fav_rename', i+"|"+v); else tick();
}
async function favLink(i,name){
  if(!name) return;
  FAVEDIT=null;
  await go('fav_link', i+"|"+name);
}
const I18N={
 tr:{tab_control:"Kontrol",tab_list:"Komutlar",tab_log:"Kayıtlar",tab_set:"Ayarlar",
  s_read:"Okuma",read_toggle:"Claude mesajlarını oku",btn_cut:"✂️ Okumayı kes",
  vol:"Ses",s_listen:"Dinleme",btn_start:"▶ Başla",btn_stop:"⏸ Dur",
  btn_micoff:"⏹ Mikrofonu kapat",btn_micref:"🔄 Mikrofonu yenile",
  s_hotkeys:"Kısayollar",s_buffer:"Tampon",btn_send:"Gönder",btn_clear:"Temizle",
  s_list:"Liste",btn_readlist:"🔊 Listeyi oku",ph_addconv:"konuşma adı ekle…",
  btn_add:"Ekle",s_open:"Açık konuşmalar",alt_off:"pasif",hint_alt:"Bu uygulama seçili değil. Ayarlar > Kod uygulaması'ndan geçersen bu liste etkin olur.",s_heard:"Son duyulanlar",tt_prev:"Önceki sayfa",tt_next:"Sonraki sayfa",rowcount:"({n} kayıt)",
  btn_copyall:"Hepsini kopyala",s_settings:"Ayarlar",k_name:"Çağrı adı",
  k_lang:"Konuşma dili",k_pack:"Komut seti",k_voice:"Okuma sesi",
  btn_save:"Kaydet",btn_loadreset:"Yükle / Sıfırla",s_test:"Komut testi",
  ph_test:"bir cümle yaz, hangi komuta gittiğini gör…",btn_try:"Dene",
  btn_addcmd:"Bu komuta ekle",lang_tr:"Türkçe",lang_en:"İngilizce",
  lang_auto:"Otomatik algıla",
  hint_list:"Adı değiştirmek için ✎ ya da çift tıkla.",
  hint_heard:"Bir satıra tıkla → panoya kopyalanır. Yeşil = komut tetikledi.",
  hint_name:"Çağrı adını değiştirirsen tüm komut kalıpları yeni ada taşınır, eski adın yazım varyantları silinir.",
  empty:"(boş)",nothing:"henüz bir şey duyulmadı",listempty:"liste boş",
  noconv:"açık konuşma yok",closed:"kapalı",go:"geç",lastheard:"son duyulan: ",
  copied:"kopyalandı ✓",connecting:"bağlanıyor…",nolink:"⚠️ bağlantı yok",
  typesomething:"bir şey yaz…",notcmd:"(komut değil)",perm_ok:"izin var",
  perm_no:"izin yok",queue:"kuyruk",on:"açık",off:"kapalı — hiçbir mesaj okunmaz",
  inqueue:"kuyrukta {n} mesaj",nohotkey:"tanımlı kısayol yok",
  cfm_pack:"Komut seti değişecek, eklediğin yazımlar silinecek. Favoriler korunur. Devam?",
  cfm_reset:"Komut kalıpları varsayılana dönecek, eklediğin yazımlar silinecek. Devam?",
  pickword:"Önce bir komut seç",cfm_clear:"Kayıtlar silinsin mi?",btn_edit:"Düzenle",
  tt_edit:"Kalıpları gör, sil ya da yenisini ekle",th_cmd:"Komut",th_sample:"Örnek kalıp",
  th_n:"Kalıp",tt_primary:"Çift tıkla: örnek kalıbı değiştir",
  tt_pause:"Sistemi duraklat — panelde çalışırken komutlar işlenmesin, mesajlar okunmasın",
  tt_resume:"Sistemi çalıştır",
  tt_testmic:"Mikrofonla dene: bas, söyle, sonuç hemen altta çıkar",btn_test:"Dene",
  tt_voicetest:"Seçili sesle örnek bir cümle okur",ph_search:"ara…",noresult:"sonuç yok",btn_goto:"Komutları aç",
  warn_nocustom:"Henüz kendi yazımlarını eklememişsin. Whisper komutları sık sık yanlış duyar; bir komutu açıp söyleyerek kendi söyleyişini eklersen çok daha az kaçar.",s_cmds:"Komut kalıpları",hint_cmds:"Bir komuta tıkla, kalıplarını gör, sil ya da yenisini ekle.",nophrase:"kalıp yok",ph_newphrase:"yeni kalıp yaz...",btn_cancel:"İptal",speaknow:"Konuş — duyduğumu onayına sunacağım.",heardq:"Duydum:",tt_phrm:"Bu kalıbı kaldır",tt_phlock:"Yerleşik kalıp, dil paketinden geliyor — kaldırılamaz",tt_phadd:"Yazdığın kalıbı bu komuta ekle",tt_capture:"Söyleyerek ekle: bas, konuş, beğenirsen onayla",tt_vrm:"Bu yazımı kelime setinden kaldır",k_target:"Kod uygulaması",s_voice_set:"Ses ve dil",k_mic:"Mikrofon",k_spk:"Hoparlör",dev_auto:"Otomatik",dev_auto_in:"Otomatik (kulaklık varsa kulaklık)",dev_auto_out:"Otomatik (sistem çıkışı)",tt_mic:"Dinlemenin yapılacağı mikrofon. Otomatik: kulaklık varsa kulaklık, yoksa dahili. Belirli bir cihaz seçersen kulaklık takılsa bile o kalır; seçtiğin cihaz yoksa dahiliye düşer.",tt_spk:"Okumanın çalacağı cihaz. Otomatik: sistem çıkışı.",s_system:"Sistem",hint_system:"Kısayol her yerden çalışır; öndeki uygulamaya da gittiği için boşta bir kombinasyon seç. Port doluysa panel sıradaki boş porta geçer.",k_stophk:"Okumayı kes kısayolu",k_port:"Panel portu",tt_port:"Panelin dinlediği port. Yaz, boş mu dolu mu hemen söyler.",tt_portsave:"Portu kaydet — panel yeni adrese taşınır, sayfa kendiliğinden gider",tt_stophk:"Okuma her yerde bu tuşla kesilir. Yazım: cmd+alt+. — değiştirici olarak cmd, alt, shift, ctrl kullanılır. Tuş basımı öndeki uygulamaya da gider, o yüzden boşta bir kombinasyon seç.",tt_target:"Mesajın yazılacağı uygulama. Cevapların okunması yalnızca Claude Code'da çalışır.",soon:"yakında",tt_vbase:"Ana kelime — kaldırılamaz",
  tt_cut:"O anki okumayı ve kuyruğu durdurur — sesle: “mahmut kes”",
  tt_start:"Dinlemeyi açar — sesle: “mahmut başla”",
  tt_stop:"Dinlemeyi durdurur, mikrofon açık kalır — sesle: “mahmut dur”",
  tt_micoff:"Mikrofonu tamamen kapatır; sesle açılamaz, buradan aç",
  tt_micref:"Giriş cihazını yeniden tarar (kulaklık takıp çıkardıysan)",
  tt_send:"Tampondaki metni Claude’a gönderir — sesle: “tamam mahmut”",
  tt_clear:"Tamponu boşaltır — sesle: “boşver mahmut”",
  tt_readlist:"Listeyi numaralı olarak sesli okur — sesle: “listeyi getir mahmut”",
  tt_add:"Yazdığın konuşmayı listeye ekler",
  tt_copyall:"Tüm kayıtları panoya kopyalar",
  tt_histclear:"Kayıt listesini siler",
  tt_save:"Çağrı adını kaydeder ve tüm komut kalıplarını yeni ada taşır",
  tt_loadreset:"Seçili komut setini yükler; aynısını seçersen varsayılana döner",
  tt_try:"Yazdığın cümlenin hangi komuta gittiğini gösterir",
  tt_addcmd:"Bu cümleyi seçtiğin komutun kalıbı olarak ekler",
  tt_loc:"Arayüz dili",tt_voice:"Claude’un cevaplarını okuyan ses",
  tt_lang:"Konuştuğun dil — Whisper bu dilde yazıya döker",
  tt_name:"Komutların başına/sonuna söylediğin çağrı adı",
  tt_rename:"Adı değiştir ya da açık bir konuşmaya bağla",
  tt_up:"Yukarı taşı",tt_down:"Aşağı taşı",
  tt_go:"Bu konuşmaya geç (kapalıysa açar)",tt_del:"Listeden çıkar",
  tt_mute:"Bu konuşmanın mesajları sesli okunsun mu",
  tt_hotkey:"Hedef uygulamaya kısayol gönderir",
  tt_addv:"Bu cümleyi bir komutun kalıbı yap",
  tt_tab_control:"Okuma, dinleme, kısayollar, tampon",
  tt_tab_list:"Numaralı hızlı erişim listesi",
  tt_tab_set:"Çağrı adı, dil, ses, komut testi"},
 en:{tab_control:"Control",tab_list:"Commands",tab_log:"Log",tab_set:"Settings",
  s_read:"Reading",read_toggle:"Read Claude's messages",btn_cut:"✂️ Stop reading",
  vol:"Volume",s_listen:"Listening",btn_start:"▶ Start",btn_stop:"⏸ Stop",
  btn_micoff:"⏹ Turn mic off",btn_micref:"🔄 Refresh mic",
  s_hotkeys:"Shortcuts",s_buffer:"Buffer",btn_send:"Send",btn_clear:"Clear",
  s_list:"List",btn_readlist:"🔊 Read the list",ph_addconv:"add conversation name…",
  btn_add:"Add",s_open:"Open conversations",alt_off:"inactive",hint_alt:"This application is not selected. Switch to it under Settings > Coding app to make this list live.",s_heard:"Recently heard",tt_prev:"Previous page",tt_next:"Next page",rowcount:"({n} rows)",
  btn_copyall:"Copy all",s_settings:"Settings",k_name:"Wake name",
  k_lang:"Speech language",k_pack:"Command set",k_voice:"Reading voice",
  btn_save:"Save",btn_loadreset:"Load / Reset",s_test:"Command test",
  ph_test:"type a sentence, see which command it hits…",btn_try:"Test",
  btn_addcmd:"Add to this command",lang_tr:"Turkish",lang_en:"English",
  lang_auto:"Auto detect",
  hint_list:"Double-click or ✎ to rename.",
  hint_heard:"Click a row → copied. Green = a command fired.",
  hint_name:"Changing the wake name moves all command patterns to it; the old name's spelling variants are dropped.",
  empty:"(empty)",nothing:"nothing heard yet",listempty:"list is empty",
  noconv:"no open conversations",closed:"closed",go:"go",lastheard:"last heard: ",
  copied:"copied ✓",connecting:"connecting…",nolink:"⚠️ no connection",
  typesomething:"type something…",notcmd:"(not a command)",perm_ok:"permission ok",
  perm_no:"no permission",queue:"queue",on:"on",off:"off — nothing is read",
  inqueue:"{n} in queue",nohotkey:"no shortcuts defined",
  cfm_pack:"The command set will change and your added spellings will be removed. Favorites are kept. Continue?",
  cfm_reset:"Command patterns will reset to defaults, your added spellings will be removed. Continue?",
  pickword:"Pick a command first",cfm_clear:"Clear the log?",btn_edit:"Edit",
  tt_edit:"View, remove or add patterns",th_cmd:"Command",th_sample:"Sample pattern",
  th_n:"Count",tt_primary:"Double-click to change the sample pattern",
  tt_pause:"Pause the system — no commands, no reading while you work in the panel",
  tt_resume:"Resume the system",
  tt_testmic:"Try by voice: click, speak, the result shows below",btn_test:"Test",
  tt_voicetest:"Reads a sample sentence with the selected voice",ph_search:"search…",noresult:"no results",btn_goto:"Open commands",
  warn_nocustom:"You have not added your own spellings yet. Whisper often mishears commands; open a command and add how you actually say it, and far fewer will slip.",s_cmds:"Command patterns",hint_cmds:"Click a command to see its patterns, remove or add new ones.",nophrase:"no patterns",ph_newphrase:"type a new pattern...",btn_cancel:"Cancel",speaknow:"Speak — I will show you what I heard.",heardq:"Heard:",tt_phrm:"Remove this pattern",tt_phlock:"Built-in pattern from the language pack, cannot be removed",tt_phadd:"Add the typed pattern to this command",tt_capture:"Add by speaking: click, talk, confirm if you like it",tt_vrm:"Remove this spelling from the word set",k_target:"Coding app",s_voice_set:"Voice & language",k_mic:"Microphone",k_spk:"Speaker",dev_auto:"Automatic",dev_auto_in:"Automatic (headset when present)",dev_auto_out:"Automatic (system output)",tt_mic:"Microphone used for listening. Automatic prefers a headset and falls back to the built-in mic. Pick a device and it stays even when a headset connects; if that device is gone it falls back.",tt_spk:"Where reading is played. Automatic uses the system output.",s_system:"System",hint_system:"The shortcut works everywhere; it also reaches the front app, so pick an unused combo. If the port is taken the panel moves to the next free one.",k_stophk:"Stop reading shortcut",k_port:"Panel port",tt_port:"The port the panel listens on. Type one and it tells you if it is free.",tt_portsave:"Save the port - the panel moves and this page follows",tt_stophk:"Stops reading anywhere. Format: cmd+alt+. — modifiers are cmd, alt, shift, ctrl. The keystroke also reaches the front app, so pick an unused combo.",tt_target:"Where messages are typed. Reading replies aloud only works with Claude Code.",soon:"soon",tt_vbase:"Base word - cannot be removed",
  tt_cut:"Stops the current reading and the queue — say “mahmut cut”",
  tt_start:"Starts listening — say “mahmut start”",
  tt_stop:"Stops listening, mic stays on — say “mahmut stop”",
  tt_micoff:"Turns the mic off completely; can’t be voice-woken after this",
  tt_micref:"Rescans input devices (after plugging headphones in or out)",
  tt_send:"Sends the buffer to Claude — say “okay mahmut”",
  tt_clear:"Empties the buffer — say “cancel mahmut”",
  tt_readlist:"Reads the numbered list aloud — say “list mahmut”",
  tt_add:"Adds the typed conversation to the list",
  tt_copyall:"Copies the whole log to the clipboard",
  tt_histclear:"Clears the log",
  tt_save:"Saves the wake name and moves all command patterns to it",
  tt_loadreset:"Loads the selected command set; pick the same one to reset",
  tt_try:"Shows which command your sentence would hit",
  tt_addcmd:"Adds this sentence as a pattern of the chosen command",
  tt_loc:"Interface language",tt_voice:"Voice that reads Claude’s replies",
  tt_lang:"The language you speak — Whisper transcribes in it",
  tt_name:"The wake name you say with every command",
  tt_rename:"Rename or link to an open conversation",
  tt_up:"Move up",tt_down:"Move down",
  tt_go:"Switch to this conversation (opens it if closed)",
  tt_del:"Remove from the list",
  tt_mute:"Read this conversation's messages aloud?",
  tt_hotkey:"Sends a shortcut to the target app",
  tt_addv:"Make this sentence a command pattern",
  tt_tab_control:"Reading, listening, shortcuts, buffer",
  tt_tab_list:"Numbered quick-access list",
  tt_tab_set:"Wake name, language, voice, command test"}};
let LOC="tr";
const LANGS={tr:"Türkçe",en:"İngilizce",de:"Almanca",fr:"Fransızca",
 es:"İspanyolca",it:"İtalyanca",pt:"Portekizce",ru:"Rusça",ar:"Arapça",
 zh:"Çince",ja:"Japonca",ko:"Korece",nl:"Felemenkçe",sv:"İsveççe",
 da:"Danca",no:"Norveççe",fi:"Fince",pl:"Lehçe",cs:"Çekçe",el:"Yunanca",
 he:"İbranice",hi:"Hintçe",id:"Endonezce",ms:"Malayca",th:"Tayca",
 vi:"Vietnamca",ro:"Rumence",hu:"Macarca",sk:"Slovakça",uk:"Ukraynaca",
 kk:"Kazakça",kn:"Kannada",bg:"Bulgarca",hr:"Hırvatça",ca:"Katalanca"};
const LANGS_EN={tr:"Turkish",en:"English",de:"German",fr:"French",
 es:"Spanish",it:"Italian",pt:"Portuguese",ru:"Russian",ar:"Arabic",
 zh:"Chinese",ja:"Japanese",ko:"Korean",nl:"Dutch",sv:"Swedish",
 da:"Danish",no:"Norwegian",fi:"Finnish",pl:"Polish",cs:"Czech",el:"Greek",
 he:"Hebrew",hi:"Hindi",id:"Indonesian",ms:"Malay",th:"Thai",
 vi:"Vietnamese",ro:"Romanian",hu:"Hungarian",sk:"Slovak",uk:"Ukrainian",
 kk:"Kazakh",kn:"Kannada",bg:"Bulgarian",hr:"Croatian",ca:"Catalan"};
let VOICES=[], VSEL="";
function vLang(name){
  const v=VOICES.find(x=>x.name===name); return v?v.lang:"";
}
function vLabel(name){
  if(!name) return "";
  const l=vLang(name);
  return l ? LANGNAME(l)+" ("+name+")" : name;
}
function vpToggle(){
  const pop=document.getElementById("vpPop");
  const open=pop.style.display==="none";
  pop.style.display=open?"block":"none";
  if(open){ vpRender(); const q=document.getElementById("vpQ"); q.value=""; q.focus(); }
}
function vpClose(){ document.getElementById("vpPop").style.display="none"; }
function vpRender(){
  const q=(document.getElementById("vpQ").value||"").toLocaleLowerCase();
  const cur=(document.getElementById("stLang")||{}).value||"tr";
  const rank=l=>l.startsWith(cur.slice(0,2))?0:(l.startsWith("en")?1:2);
  const rows=VOICES
    .filter(v=>!q || (LANGNAME(v.lang)+" "+v.name).toLocaleLowerCase().includes(q))
    .sort((a,b)=> rank(a.lang)-rank(b.lang)
      || LANGNAME(a.lang).localeCompare(LANGNAME(b.lang))
      || a.name.localeCompare(b.name));
  const el=document.getElementById("vpList");
  el.innerHTML = rows.length ? rows.map(v=>
    `<div class="vpi${v.name===VSEL?" on":""}" onclick="vpPick('${esc(v.name)}')">
      <span class="l">${esc(LANGNAME(v.lang))}</span>
      <span class="n">${esc(v.name)}</span></div>`).join("")
    : `<div class="vpnone">${t("noresult")}</div>`;
}
async function vpPick(n){
  VSEL=n; document.getElementById("vpTrig").textContent=vLabel(n);
  vpClose(); await go('set_voice', n);
}
document.addEventListener("click",e=>{
  const vp=document.getElementById("vp");
  if(vp && !vp.contains(e.target)) vpClose();
});
function LANGNAME(code){
  const two=code.slice(0,2), reg=code.slice(3);
  const tbl=(LOC==="en")?LANGS_EN:LANGS;
  return (tbl[two]||two.toUpperCase())+(reg?" ("+reg+")":"");
}
function t(k,v){ let x=(I18N[LOC]||I18N.tr)[k]||k;
  if(v) for(const n in v) x=x.replace("{"+n+"}",v[n]); return x; }
function applyLoc(){
  document.querySelectorAll("[data-i18n]").forEach(
    el=>el.textContent=t(el.dataset.i18n));
  document.querySelectorAll("[data-i18n-ph]").forEach(
    el=>el.placeholder=t(el.dataset.i18nPh));
  document.querySelectorAll("[data-i18n-title]").forEach(
    el=>el.title=t(el.dataset.i18nTitle));
  document.documentElement.lang=LOC;
}
function setLoc(l){ LOC=l;
  const ve=document.getElementById("stVoice"); if(ve) ve.dataset.n=""; try{localStorage.setItem("vp_loc",l);}catch(e){}
  applyLoc(); tick(); }
try{ const sl=localStorage.getItem("vp_loc"); if(sl) LOC=sl; }catch(e){}
let BOOT=null, SETTOUCH=0, COPEN=null, CDET=null, PEDIT=null, CAP={key:null,text:""};
async function cmdOpen(k){
  if(COPEN!==k) MMSG="";          // clear the old result when a different command is opened
  COPEN=k; CDET=null;
  document.getElementById("modal").style.display="flex";
  document.getElementById("mTitle").textContent="…";
  document.getElementById("mBody").innerHTML="";
  try{ CDET=await (await fetch("/api/command?k="+encodeURIComponent(k))).json(); }
  catch(e){ CDET={error:t("nolink")}; }
  renderModal();
}
function cmdClose(e){
  if(e && e.target && e.target.id!=="modal" && e.type==="click"
     && e.target.closest && e.target.closest(".mbox")) return;
  COPEN=null; CDET=null;
  document.getElementById("modal").style.display="none";
  if(CAP.key) go('capture_cancel');
}
function renderModal(){
  if(COPEN===null) return;
  document.getElementById("mTitle").textContent=
    (CDET && CDET.label) ? CDET.label : COPEN;
  document.getElementById("mBody").innerHTML=cmdDetail();
}
document.addEventListener("keydown",e=>{ if(e.key==="Escape") cmdClose(); });
function renderCmds(){
  const el=document.getElementById("cmds"); if(!el) return;
  el.innerHTML=`<table class="ctab"><thead><tr>
    <th>${t("th_cmd")}</th><th>${t("th_sample")}</th>
    <th class="num">${t("th_n")}</th><th></th><th></th></tr></thead><tbody>`
   + CMDS.map(c=>{
      const row=`<tr class="crow">
        <td>${esc(c.label)}</td>
        <td class="cs">${PEDIT===c.key
          ? `<input id="pri" value="${esc(c.sample||"")}"
               onclick="event.stopPropagation()"
               onkeydown="if(event.key==='Enter')priSave('${esc(c.key)}');if(event.key==='Escape')priCancel()">`
          : `<span ondblclick="event.stopPropagation();priEdit('${esc(c.key)}')"
               title="${t("tt_primary")}">${esc(c.sample||"—")}</span>`}</td>
        <td class="num">${c.n||0}</td>
        <td class="ct">${esc(c.key)}</td>
        <td class="ed"><button onclick="cmdOpen('${esc(c.key)}')"
          title="${t("tt_edit")}">${t("btn_edit")}</button></td></tr>`;
      return row;
    }).join("") + `</tbody></table>`;
  if(PEDIT){ const i=document.getElementById("pri"); if(i){ i.focus(); i.select(); } }
}
function priEdit(k){ PEDIT=k; renderCmds(); }
function priCancel(){ PEDIT=null; renderCmds(); }
async function priSave(k){
  const v=(document.getElementById("pri")||{}).value||"";
  PEDIT=null;
  if(v.trim()) await go('phrase_primary', k+"|"+v.trim()); else renderCmds();
}
function cmdDetail(){
  if(!CDET) return `<div class="cdet">...</div>`;
  if(CDET.error) return `<div class="cdet">${esc(CDET.error)}</div>`;
  const ed=new Set(CDET.editable||[]);
  const rows=(CDET.phrases||[]).map(ph=>
    `<div class="ph"><span class="pt">${esc(ph)}</span>`
    + (ed.has(ph)
       ? `<button class="x" onclick="event.stopPropagation();phRm('${esc(ph)}')" title="${t("tt_phrm")}">&times;</button>`
       : `<span class="lock" title="${t("tt_phlock")}">&#128274;</span>`)
    + `</div>`).join("")||`<div class="mini">${t("nophrase")}</div>`;
  const vs=Object.entries(CDET.variants||{}).map(([k,v])=>
    `<div class="vrow"><b>${esc(k)}</b> &rarr; ` + v.map(w=>
      (w.toLowerCase()===k.toLowerCase()
        ? `<span class="vch base" title="${t("tt_vbase")}">${esc(w)}</span>`
        : `<span class="vch">${esc(w)}<button onclick="event.stopPropagation();vRm('${esc(k)}','${esc(w)}')" title="${t("tt_vrm")}">&times;</button></span>`)
      ).join("") + `</div>`).join("");
  let cap="";
  if(CAP.key===CDET.key){
    cap = CAP.text
      ? `<div class="cap"><div style="margin-bottom:8px">${t("heardq")} <b>${esc(CAP.text)}</b></div>
         <div class="tstrow">
           <button class="p" onclick="event.stopPropagation();capCommit()">${t("btn_addcmd")}</button>
           <button onclick="event.stopPropagation();go('capture_cancel')">${t("btn_cancel")}</button></div></div>`
      : `<div class="cap"><div>${t("speaknow")}</div>
         <div class="tstrow" style="margin-top:8px">
           <button onclick="event.stopPropagation();go('capture_cancel')">${t("btn_cancel")}</button></div></div>`;
  }
  const msg=MMSG?`<div class="amsg${MMSG.startsWith("\u2705")?" ok":""}">${esc(MMSG)}</div>`:"";
  return `<div class="cdet" onclick="event.stopPropagation()">
    <div class="tstrow">
      <input id="phIn" placeholder="${t("ph_newphrase")}" onkeydown="if(event.key==='Enter')phAdd()">
      <button class="${HILITE?"hl":""}" onclick="phAdd()" title="${t("tt_phadd")}">${t("btn_add")}</button>
      <button class="${HILITE?"hl":""}" onclick="go('capture_start','${esc(CDET.key)}')" title="${t("tt_capture")}">&#127908;</button>
    </div>${cap}${msg}
    <div style="margin-top:12px">${rows}</div>${vs?`<div class="cvar">${vs}</div>`:""}</div>`;
}
let MMSG="";
async function phAdd(){
  const v=document.getElementById("phIn").value.trim();
  if(!v||!CDET) return;
  const r=await go('phrase_add', CDET.key+"|"+v); MMSG=r&&r.msg||"";
  cmdOpen(CDET.key);
}
async function phRm(ph){
  if(!CDET) return;
  const r=await go('phrase_remove', CDET.key+"|"+ph); MMSG=r&&r.msg||"";
  cmdOpen(CDET.key);
}
async function vRm(canon,w){
  if(!CDET) return;
  const r=await go('variant_remove', canon+"|"+w); MMSG=r&&r.msg||"";
  cmdOpen(CDET.key);
}
async function capCommit(){
  const r=await go('capture_commit'); MMSG=r&&r.msg||"";
  if(CDET) cmdOpen(CDET.key);
}
let HILITE=false;
function gotoCmds(){
  page('liste'); HILITE=true; renderCmds();
  const c=document.querySelector('[data-p="liste"] .card:last-child');
  if(c){ c.classList.add("hlbg"); c.scrollIntoView({behavior:"smooth",block:"center"}); }
  setTimeout(()=>{ HILITE=false; if(c) c.classList.remove("hlbg"); renderCmds(); }, 12000);
}
function page(p){
  document.querySelectorAll("section[data-p]").forEach(
    el=>el.classList.toggle("on", el.dataset.p===p));
  document.querySelectorAll(".tabs button").forEach(
    el=>el.classList.toggle("on", el.dataset.p===p));
  try{ localStorage.setItem("vp_page", p); }catch(e){}
}
try{ const sp=localStorage.getItem("vp_page"); if(sp) setTimeout(()=>page(sp),0); }catch(e){}
async function saveName(){
  const v=document.getElementById("stName").value.trim();
  if(v){ SETTOUCH=Date.now(); await go('set_name', v); }
}
async function packPick(v){
  const cur=document.getElementById("navPack").dataset.cur;
  if(v===cur) return;
  if(!confirm(t("cfm_pack"))){
    document.getElementById("navPack").value=cur; return; }
  SETTOUCH=Date.now(); await go('load_pack', v);
}
async function loadPack(){
  const v=document.getElementById("stPack").value;
  const cur=document.getElementById("stPack").dataset.cur;
  const msg=(v===cur)
    ? t("cfm_reset") : t("cfm_pack");
  if(!confirm(msg)) return;
  SETTOUCH=Date.now(); await go('load_pack', v);
}
async function testMic(){
  if(CAP.key==="__test__"){ await go('capture_cancel'); return; }
  await go('capture_start','__test__');
}
async function testRun(){
  const q=document.getElementById("tstIn").value;
  const out=document.getElementById("tstOut");
  const add=document.getElementById("tstAdd");
  if(!q.trim()){ out.textContent=t("typesomething"); out.className="tstres";
    add.style.display="none"; return; }
  let d; try{ d=await (await fetch("/api/test?q="+encodeURIComponent(q))).json(); }
  catch(e){ out.textContent="bağlantı yok"; return; }
  out.textContent=d.label||"—";
  out.className="tstres"+(d.cmd?" hit":"");
  add.style.display=d.cmd?"none":"flex";
  if(!d.cmd){
    document.getElementById("tstCmd").innerHTML=
      CMDS.map(c=>`<option value="${esc(c.key)}">${esc(c.label)}</option>`).join("");
  }
}
async function testAdd(){
  const q=document.getElementById("tstIn").value.trim();
  const c=document.getElementById("tstCmd").value;
  if(!q||!c) return;
  await go('phrase_add', c+"|"+q);
  setTimeout(testRun,250);
}
function favAdd(){
  const el=document.getElementById("favin"); const v=el.value.trim();
  if(!v) return; el.value=""; go('fav_add',v);
}
async function clip(txt,el,label){
  try{ await navigator.clipboard.writeText(txt); }
  catch(e){ const t=document.createElement("textarea"); t.value=txt;
    document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
  if(el){ const old=el.textContent; el.textContent=label||t("copied");
    el.classList.add("copied");
    setTimeout(()=>{el.textContent=old;el.classList.remove("copied")},1100); }
}
function copyOne(i,el){ const h=HIST[i]; if(!h) return;
  clip(h.text,el.querySelector(".tx"),t("copied")); }
let VAROPEN=null, CMDS=[], FAV=[], SESS=[];
function openVar(i){ VAROPEN=(VAROPEN===i?null:i); renderHist(); }
function closeVar(){ VAROPEN=null; renderHist(); }
function varForm(h){
  const copts=CMDS.map(c=>
    `<option value="${esc(c.key)}">${esc(c.label)}</option>`).join("");
  return `<div class="vform" onclick="event.stopPropagation()">
    <div class="hint">Komutu seç. <b>Kelimeleri ekle</b> cümleyi komutun
      kalıbıyla hizalayıp farklı kelimeleri yazım setine alır — bu kelimeler
      başka cümlelerde de tutar. Kalıplar anında yeniden derlenir.</div>
    <div class="r2">
      <select id="vcmd">${copts}</select>
      <button class="p" onclick="wordsAdd(${HIST.indexOf(h)})"
        title="kelimeleri komutun yazım setine ekler — başka cümlelerde de tutar"
        >Kelimeleri ekle</button>
    </div>
    <div class="hint" style="margin:10px 0 7px">Kelime sayısı kalıpla
      tutmazsa hizalama yapılamaz; o zaman cümlenin tamamını ekle:</div>
    <div class="r2">
      <button onclick="phraseAdd(${HIST.indexOf(h)})">Cümleyi ekle</button>
      <button onclick="closeVar()">İptal</button>
    </div></div>`;
}
async function wordsAdd(i){
  const h=HIST[i]; if(!h) return;
  const c=document.getElementById("vcmd").value;
  await go('words_add', c+"|"+h.text);
  VAROPEN=null; renderHist();
}
async function phraseAdd(i){
  const h=HIST[i]; if(!h) return;
  const c=document.getElementById("vcmd").value;
  await go('phrase_add', c+"|"+h.text);
  VAROPEN=null; renderHist();
}
async function histClear(){
  if(!HIST.length) return;
  if(!confirm(t("cfm_clear"))) return;
  await go('history_clear');
}
function copyAll(){
  const txt=HIST.map(h=>h.t+"  "+h.text+(h.result?"   → "+h.result:"   → "+t("notcmd"))).join("\\n");
  clip(txt,document.getElementById("cpy"),t("copied")); }
const COLOR={off:"#8b93a5",sleep:"#f5a623",armed:"#4c8dff",live:"#ff5f56"};
async function go(a,arg){
  let r=null;
  try{ r=await (await fetch("/api/action",{method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({action:a,arg:arg||null})})).json(); }catch(e){}
  setTimeout(tick,120);
  return r;
}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
let LASTST=null, LASTLINK=true;
// The toast colour follows the status text (Turkish + English keywords).
const TKIND=[
  // "already added" / "cannot be removed" are NOT errors: nothing happened.
  ["warn", /zaten|already|kaldırılamaz|kaldirilamaz|hazır değil|hazir degil|duraklat|uyku|kapalı|kapali|kesildi|iptal|bekl|paused|sleep|off|cancel|stopped/i],
  ["err",  /hata|başarısız|basarisiz|geçersiz|gecersiz|bulunamadı|bulunamadi|izin yok|error|failed|invalid|not found/i],
  ["ok",   /eklendi|kaldırıldı|kaldirildi|kaydedildi|seçildi|secildi|güncellendi|guncellendi|temizlendi|gönderildi|gonderildi|başarılı|basarili|hazır|hazir|added|removed|saved|sent|ready|done/i],
  ["info", /dinliyorum|konuş|konus|yakalandı|yakalandi|okuyorum|listening|speak|heard/i],
];
function toastKind(msg){
  for(const [k,re] of TKIND){ if(re.test(msg)) return k; }
  if(msg.indexOf("✅")===0) return "ok";
  if(msg.indexOf("🔴")===0) return "err";
  return "mute";
}
function toast(msg,kind){
  if(!msg) return;
  const w=document.getElementById("toasts"); if(!w) return;
  const el=document.createElement("div");
  el.className="toast"+(kind?" "+kind:"");
  el.textContent=msg;
  if(document.visibilityState==="visible") el.classList.add("anim");
  w.appendChild(el);
  while(w.children.length>3) w.removeChild(w.firstChild);
  setTimeout(()=>{ el.classList.add("out"); setTimeout(()=>el.remove(),260); },4500);
}
let PORTOK=null, PORTT=0;
function portCheck(){
  const el=document.getElementById("stPort"), btn=document.getElementById("portBtn"),
        msg=document.getElementById("portMsg");
  const v=el.value.trim();
  PORTOK=null; btn.disabled=true;
  if(!v){ msg.textContent=""; msg.className="mini"; return; }
  clearTimeout(PORTT);
  PORTT=setTimeout(async()=>{
    let r; try{ r=await (await fetch("/api/portcheck?p="+encodeURIComponent(v))).json(); }
    catch(e){ return; }
    msg.textContent=r.msg||"";
    msg.className="mini"+(r.free&&!r.same?" okmsg":" errmsg");
    PORTOK=(r.ok&&r.free&&!r.same)?r.port:null;
    btn.disabled=(PORTOK===null);
  },280);
}
async function portSave(){
  if(PORTOK===null) return;
  const r=await go('set_panel_port', String(PORTOK));
  if(r&&r.msg) toast(r.msg, toastKind(r.msg));
  // The panel is moving to a new port: take the page with it.
  setTimeout(()=>{ location.href="http://127.0.0.1:"+PORTOK+"/"; }, 1200);
}
function saveHk(){
  const el=document.getElementById("stHk"); if(!el) return;
  go('set_stop_hotkey', el.value.trim()).then(r=>{ if(r&&r.msg) toast(r.msg, toastKind(r.msg)); });
}
function setTarget(v){ go('set_target',v).then(r=>{ if(r&&r.msg) toast(r.msg, toastKind(r.msg)); }); }
function renderDevices(d){
  const dev=d.devices||{inputs:[],outputs:[]};
  const fill=(id, rows, cur, autoKey, active)=>{
    const el=document.getElementById(id); if(!el) return;
    const sig=rows.map(x=>x.name).join("|")+"/"+cur+"/"+(active||"");
    if(el.dataset.sig===sig) return;        // do not redraw on every tick
    el.dataset.sig=sig;
    const auto=t(autoKey)+(active?" — "+active:"");
    el.innerHTML=`<option value=""${cur?"":" selected"}>${esc(auto)}</option>`
      + rows.map(x=>`<option value="${esc(x.name)}"${x.name===cur?" selected":""}>`
                    + esc(x.name)+`</option>`).join("");
  };
  fill("stIn", dev.inputs||[], d.in_device||"", "dev_auto_in", d.in_active||"");
  fill("stOut", dev.outputs||[], d.out_device||"", "dev_auto_out", "");
}
function renderTargets(d){
  const el=document.getElementById("stTarget"); if(!el) return;
  const list=d.targets||[];
  const sig=list.map(x=>x.code+x.enabled).join("|")+"/"+(d.target||"");
  if(el.dataset.sig===sig) return;      // do not redraw on every tick
  el.dataset.sig=sig;
  el.innerHTML=list.map(x=>
    `<option value="${esc(x.code)}"${x.enabled?"":" disabled"}${x.code===d.target?" selected":""}>`
    + esc(x.label) + (x.enabled?"":" ("+t("soon")+")") + `</option>`).join("");
}
async function tick(){
  let d; try{ d=await (await fetch("/api/state")).json(); }catch(e){
    document.getElementById("ttl").textContent="⛔";
    if(LASTLINK){ LASTLINK=false; toast(t("nolink"),"err"); }
    return; }
  LASTLINK=true;
  const st=d.speaking?"🔊":(ICON[d.state]||"⚪️");
  document.getElementById("ttl").textContent=st;
  document.getElementById("ttl").title=d.status||"";
  // Show a toast when the status changed (not on the first load)
  const sv=d.status||"";
  if(LASTST===null) LASTST=sv;
  else if(sv!==LASTST){ LASTST=sv; toast(sv, toastKind(sv)); }
  document.title="Mahmut: Voice Assistant"+(d.speaking?" 🔊":"");
  document.getElementById("dot").style.background=d.speaking?"#2ecc71":(COLOR[d.state]||"#8b93a5");
  // If the user just touched it, skip updates for 1.5 s so they do not fight
  if(Date.now()-TOUCH>1500){ document.getElementById("swTts").checked=!!d.tts_enabled; }
  if(Date.now()-VTOUCH>1500){
    const pct=Math.round((d.volume==null?1:d.volume)*100);
    document.getElementById("vol").value=pct;
    document.getElementById("vv").textContent="%"+pct;
  }
  document.getElementById("ttss").textContent=d.tts_enabled
    ? (d.tts_queue?t("inqueue",{n:d.tts_queue}):t("on"))
    : t("off");
  const b=document.getElementById("buf");
  b.textContent=d.buffer||t("empty"); b.className="buf"+(d.buffer?" has":"");
  document.getElementById("heard").textContent=d.last_transcript?(t("lastheard")+d.last_transcript):"";
  // Reload the page when the app restarted (no need to open a new tab)
  if(d.boot){ if(BOOT===null) BOOT=d.boot; else if(BOOT!==d.boot){ location.reload(); return; } }
  HIST=d.history||[]; CMDS=d.commands||[];
  renderTargets(d);
  renderDevices(d);
  const vv=document.getElementById("ver");
  if(vv && d.version && vv.textContent!=="v"+d.version) vv.textContent="v"+d.version;
  const pp=document.getElementById("stPort");
  if(pp && document.activeElement!==pp && d.panel_port)
    pp.placeholder=String(d.panel_port);
  const hk=document.getElementById("stHk");
  if(hk && document.activeElement!==hk && d.stop_hotkey!==undefined)
    hk.placeholder=d.stop_hotkey||"cmd+alt+.";
  const nc=d.capture||{key:null,text:""};
  const capCh=(nc.key!==CAP.key)||(nc.text!==CAP.text); CAP=nc;
  const ce=document.getElementById("cmds");
  if(ce && !PEDIT && !ce.innerHTML) renderCmds();
  if(COPEN!==null && capCh) renderModal();
  // Command-test microphone: put the heard text in the box and show the
  // RESULT right away
  const tm=document.getElementById("tstMic");
  if(tm) tm.classList.toggle("rec", CAP.key==="__test__");
  if(CAP.key==="__test__" && CAP.text && capCh){
    const ti=document.getElementById("tstIn");
    if(ti){ ti.value=CAP.text; testRun(); }
    go('capture_cancel');
  }
  // Do NOT redraw the archive while a form is open: wiping the DOM on every
  // refresh closed the dropdown.
  if(VAROPEN!==null){ renderRest(d); return; }
  renderHist();
  renderRest(d);
}
let HPAGE=0;
const HPER=8;                       // rows per page
function histPages(){ return Math.max(1, Math.ceil(HIST.length/HPER)); }
function histGo(d){
  HPAGE=Math.min(histPages()-1, Math.max(0, HPAGE+d));
  renderHist();
}
function renderPager(){
  const el=document.getElementById("pager"); if(!el) return;
  const n=histPages();
  if(HIST.length<=HPER){ el.innerHTML=""; return; }
  el.innerHTML=
    `<button onclick="histGo(-1)" ${HPAGE<=0?"disabled":""} title="${t("tt_prev")}">&lsaquo;</button>`
    + `<span class="pg">${HPAGE+1} / ${n}</span>`
    + `<button onclick="histGo(1)" ${HPAGE>=n-1?"disabled":""} title="${t("tt_next")}">&rsaquo;</button>`
    + `<span style="margin-left:6px">${t("rowcount",{n:HIST.length})}</span>`;
}
function renderHist(){
  // If the list shrank (cleared), pull the open page back.
  if(HPAGE > histPages()-1) HPAGE=histPages()-1;
  const from=HPAGE*HPER, page=HIST.slice(from, from+HPER);
  renderPager();
  document.getElementById("hist").innerHTML=HIST.length?page.map((h,j)=>{
    const i=from+j;                 // ABSOLUTE index: the "+" form depends on it
    // CAREFUL: the template must start on the SAME line as `return`; on the
    // next line JavaScript inserts a semicolon and returns undefined.
    return `<div class="hrow" onclick="copyOne(${i},this)"><span class="tm">${esc(h.t)}</span>
     <span class="tx">${esc(h.text)}</span>
     <span class="rs${h.fired?" fire":""}">${esc(h.result||"")}</span>
     <button class="addv" title="${t("tt_addv")}"
       onclick="event.stopPropagation();openVar(${i})">+</button></div>`
     + (VAROPEN===i?varForm(h):"");}).join(""):
    `<div class="hrow"><span class="tx" style="color:var(--dim)">${t("nothing")}</span></div>`;
}
function renderAlt(d){
  const w=document.getElementById("altWrap"); if(!w) return;
  const a=d.alt||{};
  ["tgtA","tgtB"].forEach(id=>{const e=document.getElementById(id);
    if(e) e.textContent=d.target_label||"";});
  if(!a.available){ w.style.display="none"; return; }
  w.style.display="";
  ["tgtC","tgtD"].forEach(id=>{const e=document.getElementById(id);
    if(e) e.textContent=a.label||"";});
  document.getElementById("fav2").innerHTML=(a.favorites||[]).map((f,i)=>
    `<div class="fav"><span class="no">${i+1}</span>
     <span class="nm">${esc(f.name)}${f.open?"":" · "+t("closed")}</span></div>`).join("")
    || `<div class="mini">${t("nothing")}</div>`;
  document.getElementById("sess2").innerHTML=(a.sessions||[]).map(x=>
    `<div class="sess"><span class="nm">${x.routine?"⏱":"💬"} ${esc(x.name)}</span></div>`).join("")
    || `<div class="mini">${t("nothing")}</div>`;
}
function renderRest(d){
  renderAlt(d);
  document.getElementById("hk").innerHTML=(d.hotkeys||[]).map((h,i)=>
    `<button onclick="go('hotkey',${i})" title="${t("tt_hotkey")}">🎛&nbsp; ${esc(h)}</button>`).join("")||
    t("nohotkey");
  FAV=d.favorites||[]; SESS=d.sessions||[];
  if(FAVEDIT===null){
    document.getElementById("fav").innerHTML=FAV.length?FAV.map((f,i)=>
      `<div class="fav"><span class="no">${i+1}</span>
       <span class="nm${f.open?"":" off"}" ondblclick="favEdit(${i})"
         title="çift tıkla → yeniden adlandır">${esc(f.name)}${f.open?"":" · "+t("closed")}</span>
       <button onclick="favEdit(${i})" title="${t("tt_rename")}">✎</button>
       <button onclick="go('fav_move','${i}:-1')" ${i===0?"disabled":""}>↑</button>
       <button onclick="go('fav_move','${i}:1')" ${i===FAV.length-1?"disabled":""}>↓</button>
       <button onclick="go('fav_select',${i})">${t("go")}</button>
       <button class="x" onclick="go('fav_remove',${i})">×</button></div>`).join(""):
      t("listempty");
  }
  document.getElementById("opensess").innerHTML=(SESS||[])
    .map(s=>`<option value="${esc(s.name)}">`).join("");
  document.getElementById("sess").innerHTML=(SESS||[]).map(s=>
    `<div class="sess"><span class="nm">${s.routine?"⏱":"💬"} ${esc(s.name)}</span>
     <button onclick="go('mute','${esc(s.name)}')">${s.muted?"🔇":"🔊"}</button>
     <button onclick="go('switch','${esc(s.name)}')">${t("go")}</button></div>`).join("")||
    t("noconv");
  const cpu=d.cpu_pct==null?null:d.cpu_pct;
  const pz=!!d.paused;
  document.body.classList.toggle("paused", pz);
  const pb=document.getElementById("navPause");
  if(pb){ pb.classList.toggle("on", pz); pb.innerHTML=pz?"&#9654;":"&#9208;";
    pb.title=t(pz?"tt_resume":"tt_pause"); }
  const st=d.settings||{};
  const bn=document.getElementById("banner");
  if(bn){
    const none=(st.custom_count||0)===0;
    bn.style.display=none?"flex":"none";
    if(none) document.getElementById("bannerTx").textContent=t("warn_nocustom");
  }
  if(Date.now()-SETTOUCH>2000){
    const ne=document.getElementById("stName");
    if(ne && document.activeElement!==ne) ne.value=st.name||"";
    const le=document.getElementById("stLang");
    if(le) le.value=st.language||"auto";
    const pe=document.getElementById("stPack");
    if(pe && pe.options.length!==(st.packs||[]).length){
      pe.innerHTML=(st.packs||[]).map(x=>
        `<option value="${esc(x.code)}">${esc(x.label)}</option>`).join("");
    }
    if(pe){ pe.value=st.langpack||"tr"; pe.dataset.cur=st.langpack||"tr"; }

    VOICES=st.voices||[]; VSEL=st.voice||"";
    const vt=document.getElementById("vpTrig");
    if(vt) vt.textContent=vLabel(VSEL)||"—";
    if(document.getElementById("vpPop").style.display!=="none") vpRender();
  }
  const lvl=Math.min(100,Math.round((d.mic_rms||0)*900));
  document.getElementById("chips").innerHTML=[
    [d.ax?"ok":"err", d.ax?t("perm_ok"):t("perm_no")],
    [d.mic_running?"ok":"err", (d.mic_device||"mikrofon").replace(/'s /,"’s ")],
    ["bar", lvl],
    ["", (cpu==null?"—":cpu.toFixed(1)+"%")+" cpu"],
    ["", (d.rss_mb||0)+" mb"],
    [d.tts_queue?"warn":"", t("queue")+" "+(d.tts_queue||0)],
  ].map(([k,v])=> k==="bar"
    ? `<span class="chip bar"><i style="width:${v}%"></i></span>`
    : `<span class="chip ${k}">${esc(String(v))}</span>`).join("");
}
const nl=document.getElementById("navLoc"); if(nl) nl.value=LOC;
applyLoc(); tick(); setInterval(tick,1000);
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    app = None

    def log_message(self, *a):          # sessiz
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/state"):
            try:
                body = json.dumps(self.app.panel_state(), ensure_ascii=False)
            except Exception as exc:
                body = json.dumps({"status": f"hata: {exc}"})
            return self._send(200, body, "application/json; charset=utf-8")
        if self.path.startswith("/api/command"):
            from urllib.parse import parse_qs, urlparse
            k = parse_qs(urlparse(self.path).query).get("k", [""])[0]
            try:
                body = json.dumps(self.app.command_detail(k), ensure_ascii=False)
            except Exception as exc:
                body = json.dumps({"error": str(exc)})
            return self._send(200, body, "application/json; charset=utf-8")
        if self.path.startswith("/api/portcheck"):
            from urllib.parse import parse_qs, urlparse
            raw = parse_qs(urlparse(self.path).query).get("p", [""])[0]
            body = json.dumps(port_status(raw, self.app.panel.port),
                              ensure_ascii=False)
            return self._send(200, body, "application/json; charset=utf-8")
        if self.path.startswith("/api/test"):
            from urllib.parse import parse_qs, urlparse
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            try:
                body = json.dumps(self.app.classify(q), ensure_ascii=False)
            except Exception as exc:
                body = json.dumps({"cmd": None, "label": f"hata: {exc}"})
            return self._send(200, body, "application/json; charset=utf-8")
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        self._send(404, "yok", "text/plain; charset=utf-8")

    def do_POST(self):
        if not self.path.startswith("/api/action"):
            return self._send(404, "yok", "text/plain; charset=utf-8")
        # Any site in the browser can send a "simple" POST to 127.0.0.1
        # (text/plain passes without a preflight) and could run a command.
        # Requests from anywhere but our own page are rejected.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://127.0.0.1:{self.server.server_address[1]}",
                                     f"http://localhost:{self.server.server_address[1]}"):
            return self._send(403, json.dumps({"ok": False, "error": "yabancı kaynak"}),
                              "application/json; charset=utf-8")
        try:
            n = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(n) or b"{}")
            self.app.panel_action(req.get("action"), req.get("arg"))
            # The message is returned so it can be shown where it belongs
            # (the command dialog); the status line alone is not enough.
            body = json.dumps({"ok": True,
                               "msg": getattr(self.app, "_amsg", "")})
        except Exception as exc:
            body = json.dumps({"ok": False, "error": str(exc)})
        self._send(200, body, "application/json; charset=utf-8")


def port_status(raw, current: int) -> dict:
    """Yazilan portu dogrular: gecerli mi, bos mu, zaten bizde mi?"""
    try:
        port = int(str(raw).strip())
    except (TypeError, ValueError):
        return {"ok": False, "free": False, "msg": "sayı gir"}
    if not (1024 <= port <= 65535):
        return {"ok": False, "free": False, "port": port,
                "msg": "1024-65535 arası olmalı"}
    if port == int(current):
        return {"ok": True, "free": True, "port": port, "same": True,
                "msg": f"{port} zaten kullanılıyor (bu panel)"}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", port))
        return {"ok": True, "free": True, "port": port, "msg": f"{port} boş"}
    except OSError:
        return {"ok": True, "free": False, "port": port,
                "msg": f"{port} dolu — başka bir port seç"}
    finally:
        sock.close()


class Panel:
    def __init__(self, app, port: int = 8765):
        self.app = app
        self.port = port
        self.server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> bool:
        """Starts on the requested port, or the next free one if it is taken."""
        handler = type("H", (_Handler,), {"app": self.app})
        wanted = int(self.port)
        last = None
        for port in [wanted + i for i in range(10)] + [0]:
            try:
                # Loopback only: unreachable from outside.
                self.server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            except OSError as exc:
                last = exc
                continue
            self.port = self.server.server_address[1]
            if self.port != wanted:
                print(f"[panel] {wanted} dolu, {self.port} kullanılıyor")
            threading.Thread(target=self.server.serve_forever, daemon=True,
                             name="claudevoice-panel").start()
            return True
        print(f"[panel] açılamadı ({wanted}): {last}")
        return False

    def restart(self, port: int) -> bool:
        """Panel'i baska bir porta tasir (uygulamayi kapatmadan)."""
        self.stop()
        self.port = int(port)
        return self.start()

    def stop(self) -> None:
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None
