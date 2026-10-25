// Günlük bülten üst bilgisi; farklı günlerden öneri karıştırmaz.
window.Today = {render() {
  const el=$("#today"), d=state.bulletinData;
  if(!d) {el.innerHTML="";return;}
  const date=new Date(d.day+"T12:00:00Z").toLocaleDateString("tr-TR",{weekday:"long",day:"numeric",month:"long"});
  const coverage=d.coverage;
  const detail=coverage?.detail_requested ? ` · Tam pazar detayı ${coverage.detail_loaded}/${coverage.detail_requested} maç` : "";
  el.innerHTML=`<p class="muted bulletin-summary">${esc(date)} · ${d.total} maç · ${d.groups.length} lig${detail} · ${d.fixture_only || 0} fikstür kaydı · İddaa güncellemesi: ${d.updated_at ? esc(fmtAgo(d.updated_at)) : "henüz alınmadı"}</p>`;
}};
