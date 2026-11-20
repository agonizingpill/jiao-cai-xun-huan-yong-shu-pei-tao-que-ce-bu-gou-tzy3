import{esc}from'../utils/format.js';import{SUBJECTS}from'../constants.js';
export const money=n=>'¥'+(n/100).toFixed(2);
export function title(n,h,p){return `<div class="heading"><span>XUNSHU / ${n}</span><h1>${h}</h1><p>${p}</p></div>`}
export function spine(e){return `<div class="spine"><span>${esc(SUBJECTS[e.subject]||e.subject)}</span><b>${esc(e.title)}</b><small>${esc(e.version)} / ${esc(e.code)}</small></div>`}
export function copytag(copy,d){let e=d.editions.find(e=>e.id===copy.edition_id);return `<span class="copytag"><b>${esc(copy.barcode)}</b><small>${esc(e?.title)} / ${esc(e?.version)}</small></span>`}
export function checklist(p,d){return `<ul class="checklist">${d.pack_lines.filter(l=>l.pack_id===p.id).map(l=>{let e=d.editions.find(e=>e.id===l.edition_id),assigned=d.assignments.filter(a=>a.line_id===l.id&&a.replacement_for_id===null).length;return `<li><span>${esc(e.title)}<small>${esc(e.version)}</small></span><b>${assigned}/${l.quantity}</b><i style="--fill:${Math.min(100,assigned/l.quantity*100)}%"></i></li>`}).join('')}</ul>`}
export function options(xs,label,selected){return xs.map(x=>`<option value="${x.id}" ${x.id===Number(selected)?'selected':''}>${esc(label(x))}</option>`).join('')}
export function field(name,label,type='text',value='',attrs=''){return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${attrs}></label>`}
export function action(path,label,disabled=false){return `<button type="button" data-action="${path}" ${disabled?'disabled':''}>${label}</button>`}
export const writer=s=>s.user.role!=='viewer';export const supervisor=s=>s.user.role==='supervisor';
