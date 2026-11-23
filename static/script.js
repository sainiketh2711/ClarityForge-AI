
const $ = s => document.querySelector(s);
async function api(url, options={}) {
  const r = await fetch(url, options);
  const data = await r.json().catch(()=>({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function refresh(){
  const [stats, docs, facts] = await Promise.all([api('/api/stats'),api('/api/documents'),api('/api/facts')]);
  $('#statDocs').textContent=stats.documents; $('#statFacts').textContent=stats.facts;
  $('#statChars').textContent=stats.characters.toLocaleString();
  $('#documents').innerHTML=docs.documents.map(d=>`<div class="doc"><div><b>${esc(d.filename)}</b><small>${d.fact_count} statements · ${d.char_count.toLocaleString()} chars</small></div><button class="danger" onclick="removeDoc('${d.id}')">Remove</button></div>`).join('') || '<p class="muted">No documents uploaded yet.</p>';
  $('#facts').innerHTML=facts.facts.slice(0,40).map(f=>`<div class="fact"><small>${esc(f.source)}</small><p>${esc(f.statement)}</p></div>`).join('') || '<p class="muted">Your extracted statements will appear here.</p>';
}
window.removeDoc=async id=>{if(confirm('Remove this document and its statements?')){await api('/api/documents/'+id,{method:'DELETE'});refresh();}};
$('#uploadForm').addEventListener('submit',async e=>{
  e.preventDefault(); const fd=new FormData(); [...$('#files').files].forEach(f=>fd.append('files',f));
  $('#uploadMsg').textContent='Processing documents…';
  try{const d=await api('/api/upload',{method:'POST',body:fd});$('#uploadMsg').textContent=`Added ${d.added.length} document(s). ${d.errors.join(' ')}`;refresh();}
  catch(err){$('#uploadMsg').textContent=err.message;}
});
$('#askForm').addEventListener('submit',async e=>{
  e.preventDefault();$('#answer').textContent='Searching the local knowledge base…';
  try{const d=await api('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('#question').value})});
  $('#answer').textContent=d.answer;
  $('#evidence').innerHTML=d.evidence.map(x=>`<div class="evidence"><b>${esc(x.source)}</b><p>${esc(x.statement)}</p><small>Score ${x.score} · Matched: ${esc(x.matched_terms.join(', '))}</small></div>`).join('') || '<p class="muted">No evidence found.</p>';
  $('#reasoning').innerHTML=d.reasoning.map(x=>`<li>${esc(x)}</li>`).join('');
  }catch(err){$('#answer').textContent=err.message;}
});
$('#factSearch').addEventListener('input',async()=>{const d=await api('/api/facts?q='+encodeURIComponent($('#factSearch').value));$('#facts').innerHTML=d.facts.map(f=>`<div class="fact"><small>${esc(f.source)}</small><p>${esc(f.statement)}</p></div>`).join('')||'<p class="muted">No matches.</p>';});
$('#exportBtn').onclick=()=>location.href='/api/export';
$('#clearBtn').onclick=async()=>{if(confirm('Delete all uploaded documents and extracted statements?')){await api('/api/clear',{method:'POST'});$('#answer').textContent='';$('#evidence').innerHTML='';$('#reasoning').innerHTML='';refresh();}};
refresh().catch(e=>console.error(e));
