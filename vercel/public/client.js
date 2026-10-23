'use strict';
const $ = id => document.getElementById(id);
let running = false, pending = false, revision = 0, timer;
const figureMap = new Map();
function payload(){return {tickers:$('tickers').value,weights:$('weights').value,initial_investment:Number($('investment').value),scenario:$('scenario').value,days:Number($('days').value),paths:Number($('paths').value)}}
function status(text,error=false){$('status').hidden=false;$('status').textContent=text;$('status').classList.toggle('error',error)}
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el}
async function plotVisible(){
 for(const [key,fig] of figureMap){const el=$(key);if(el && !el.closest('[hidden]')){
  await Plotly.react(el,fig.data,fig.layout,{responsive:true,displaylogo:false,toImageButtonOptions:{format:'png'}});
 }}
}
async function render(data){
 $('description').textContent=data.description;
 $('metrics').replaceChildren(...data.metrics.map(m=>{const card=node('div',undefined,'metric');
 const negative=String(m.delta).startsWith('-');const bad=m.delta==='Danger'||(negative && m.delta!=='Safe');
 card.append(node('div',m.label,'metric-label'),node('div',m.value,'metric-value'),node('div',m.delta,'metric-delta '+(bad?'red':'green')));return card}));
 const table=node('table'),head=node('thead'),row=node('tr'),body=node('tbody');
 const report=data.tables[0];report.columns.forEach(x=>row.append(node('th',x)));head.append(row);
 report.data.forEach(values=>{const tr=node('tr');values.forEach(x=>tr.append(node('td',String(x))));body.append(tr)});table.append(head,body);$('classification').replaceChildren(table);
 figureMap.clear();data.charts.forEach(c=>figureMap.set(c.key,c.figure));
 $('results').hidden=false;await plotVisible();$('status').hidden=true;
}
async function run(){
 clearTimeout(timer);
 if(!$('settings').reportValidity())return;
 if(running){pending=true;return;}
 running=true;pending=false;const current=revision;$('run').disabled=true;$('results').hidden=true;
 status('Fetching market data and running the original Python simulation…');
 try{
  if(typeof Plotly==='undefined')throw new Error('Chart library could not load. Refresh the page.');
  const response=await fetch('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});
  const raw=await response.text();let data;
  try{data=JSON.parse(raw)}catch{throw new Error(`Server returned HTTP ${response.status}. Check Vercel runtime logs (timeout, quota or startup error).`)}
  if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);
  if(current===revision)await render(data);
 }catch(e){if(current===revision)status(e.message,true)}
 finally{running=false;$('run').disabled=false;if(pending || current!==revision){pending=false;run()}}
}
function changed(){revision++;$('results').hidden=true;clearTimeout(timer);timer=setTimeout(run,500)}
$('settings').addEventListener('submit',e=>{e.preventDefault();revision++;run()});
$('settings').addEventListener('change',changed);
for(const [id,out] of [['days','daysValue'],['paths','pathsValue']])$(id).addEventListener('input',()=>$(out).textContent=Number($(id).value).toLocaleString('en-US'));
$('minus').onclick=()=>{$('investment').value=Math.max(1000000,Number($('investment').value)-5000000);changed()};
$('plus').onclick=()=>{$('investment').value=Number($('investment').value)+5000000;changed()};
document.querySelectorAll('[role=tab]').forEach(button=>button.addEventListener('click',async()=>{
 document.querySelectorAll('[role=tab]').forEach(b=>b.setAttribute('aria-selected',String(b===button)));
 document.querySelectorAll('[role=tabpanel]').forEach(p=>p.hidden=p.id!=='panel-'+button.dataset.panel);
 await plotVisible();
}));
run();
const resizeObserver=new ResizeObserver(entries=>{
 for(const {target} of entries){if(target.data&&!target.closest('[hidden]'))Plotly.Plots.resize(target)}
});
document.querySelectorAll('.chart').forEach(el=>resizeObserver.observe(el));
