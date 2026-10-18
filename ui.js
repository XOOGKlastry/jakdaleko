/* Presentation and interaction layer. Geographic calculations remain in index.html. */
let presetIntent='near',showAllPresets=false,loadStage='konfiguracji usług';
const DAILY_GROUPS=[
  {label:'Sklep spożywczy',ids:['zabka','biedronka','lidl','dino','netto','kaufland','stokrotka']},
  {label:'Apteka',ids:['apteka']},{label:'Przystanek',ids:['przystanek']},
  {label:'Szkoła podstawowa',ids:['szkola']},{label:'Park lub skwer',ids:['park']}
];
function presetConditions(p){return p.sel.filter(([id])=>NETS[id]).map(([id,m,d])=>NETS[id].short+' '+(d==='near'?'< ':'≥ ')+fkm(m)).join(p.mode==='any'?' lub ':' · ')+(p.price?' · cena '+(p.price[0]==='lt'?'< ':'≥ ')+fmt(p.price[1])+' zł/m²':'');}
function buildPresets(){
  const choices=CFG.presets.filter(p=>(p.sel.every(s=>s[2]==='near')?'near':'far')===presetIntent);
  $('presets').innerHTML=choices.map((p,i)=>`<button class="preset" data-p="${esc(p.id)}" ${!showAllPresets&&i>=3?'hidden':''}><span class="preset-title">${esc(p.label)}<span aria-hidden="true">↗</span></span><span class="preset-conditions">${esc(presetConditions(p))}</span></button>`).join('');
  $('presets').querySelectorAll('button').forEach(b=>b.onclick=()=>{applyPreset(CFG.presets.find(p=>p.id===b.dataset.p));$('body').scrollTo({top:0,behavior:'smooth'});});
  $('morePresets').hidden=choices.length<=3;$('morePresets').textContent=showAllPresets?'Pokaż mniej ↑':`Więcej scenariuszy (${choices.length-3}) ↓`;
  $('morePresets').setAttribute('aria-expanded',String(showAllPresets));
}
function summaryText(){
  if(!K())return 'Wybierz usługę lub gotowy scenariusz, aby zobaczyć wyniki.';
  const clause=id=>`${NETS[id].short}: ${isNear(id)?'poniżej':'co najmniej'} ${fkm(st.th[id])}`;
  const required=st.sel.filter(isReq),optional=st.sel.filter(id=>!isReq(id));
  let text='Budynki, z których pieszo: ';
  if(required.length)text+=required.map(clause).join(' oraz ');
  if(optional.length)text+=(required.length?' oraz (':'')+optional.map(clause).join(' lub ')+(required.length?')':'');
  if(pcOn())text+=`; mediana cen ${st.pc.op==='lt'?'poniżej':'co najmniej'} ${fmt(st.pc.v)} zł/m²`;
  return text+'.';
}
function updateSummary(){
  if(!CFG||!$('filterSummary'))return;
  $('filterSummary').textContent=summaryText();
  document.querySelectorAll('#mode button,#logic button').forEach(b=>b.setAttribute('aria-pressed',String(b.classList.contains('on'))));
}
function updateMapKey(){
  if(!CFG||!LUT||!$('mapKey'))return;
  if(!K()){$('mapKey').hidden=true;return;}$('mapKey').hidden=false;
  $('mapKey').innerHTML=`<div class="key-title"><span class="dot" style="background:${NETS[st.sel[0]].fill}"></span>${esc(NETS[st.sel[0]].short)}<span>odległość piesza</span></div><div class="key-ramp" style="background:linear-gradient(90deg,${RAMP[st.theme].join(',')})"></div><div class="key-ticks">${STOPS.map((n,i)=>`<span>${i===0?'0':n===500?'500 m':n/1000+(i===STOPS.length-1?'+ km':'')}</span>`).join('')}</div><div class="key-foot">Szary: brak wyznaczonego dojścia</div>`;
}
function renderDailyPlaces(){
  const R=st.rep,box=$('dailyPlaces');if(!R||!box)return;
  box.innerHTML='<div class="rsec">Na co dzień <span>najbliższe dostępne miejsca</span></div>'+DAILY_GROUPS.map(g=>{
    const ids=g.ids.filter(id=>NETS[id]),rows=ids.map(id=>R.rows[id]);
    const pending=rows.some(r=>!r),incomplete=rows.some(r=>r&&r.error);
    const ready=rows.filter(r=>r&&!r.error&&r.code!==255).sort((a,b)=>a.code-b.code);
    const best=ready[0];
    if(pending)return `<div class="daily-row"><span>${g.label}</span><span class="hint">Wczytywanie…</span></div>`;
    if(!best)return `<div class="daily-row"><span>${g.label}<small>${incomplete?'Nie udało się pobrać danych':'Brak wyznaczonego dojścia'}</small></span><b>–</b></div>`;
    return `<button class="daily-row${R.focus===best.id?' selected':''}" data-place="${best.id}" ${!best.p?'disabled':''}><span>${g.label}<small>${esc(best.name||NETS[best.id].short)}${incomplete?' · niepełne dane':''}</small></span><b>${fcode(best.code)}<small>Pokaż miejsce ↗</small></b></button>`;
  }).join('')+'<p class="hint">Sklep: najbliższy spośród uwzględnionych marek. Szkoły publiczne. Brak danych nie oznacza braku usługi.</p><div id="placeDetail"></div>';
  box.querySelectorAll('[data-place]').forEach(b=>b.onclick=()=>focusPlace(b.dataset.place));
  if(R.focus)renderPlaceDetail(R.rows[R.focus]);
}
function renderPlaceDetail(row){
  const e=$('placeDetail');if(!e||!row||!row.p)return;const b=st.rep.b;
  const url=`https://www.google.com/maps/dir/?api=1&origin=${b.lat},${b.lon}&destination=${row.p[1]},${row.p[0]}&travelmode=walking`;
  e.innerHTML=`<div class="place-detail"><strong>${esc(row.name||NETS[row.id].label)}</strong><p>Linia na mapie wskazuje kierunek do miejsca. Nie przedstawia przebiegu drogi.</p><a href="${url}" target="_blank" rel="noopener noreferrer">Otwórz nawigację pieszą ↗</a><small>Google Maps wyznaczy własną trasę; odległość może się różnić.</small></div>`;
}
function focusPlace(id){if(!st.rep||!st.rep.rows[id]?.p)return;st.rep.focus=id;renderDailyPlaces();spider();fitReport();}
function showLoadError(error){
  console.error(error);const loader=$('loader');loader.classList.add('failed');loader.style.display='flex';loader.style.opacity=1;
  $('loadTitle').textContent='Nie udało się przygotować mapy';
  $('lt').textContent=`Problem podczas wczytywania ${loadStage}. Spróbuj ponownie. Opis projektu i źródła pozostają dostępne.`;
  $('loadActions').hidden=false;loader.querySelector('.pb').hidden=true;
  ['cntB','pctB','cntP','pctP'].forEach(id=>$(id).classList.remove('sk'));
  $('cntB').textContent='–';$('cntP').textContent='–';$('pctB').textContent='brak danych';$('pctP').textContent='brak danych';
  document.body.classList.add('data-unavailable');
}
function initUX(){
  $('presetIntent').onclick=e=>{const b=e.target.closest('[data-intent]');if(!b)return;presetIntent=b.dataset.intent;showAllPresets=false;document.querySelectorAll('#presetIntent button').forEach(x=>{x.classList.toggle('on',x===b);x.setAttribute('aria-pressed',String(x===b));});buildPresets();};
  $('morePresets').onclick=()=>{showAllPresets=!showAllPresets;buildPresets();};
  $('shareView').onclick=async()=>{try{await navigator.clipboard.writeText(location.href);toast('Link do widoku skopiowany');}catch(e){toast('Skopiuj adres strony z paska przeglądarki');}};
  $('retryLoad').onclick=()=>location.reload();
  $('dismissLoad').onclick=()=>{$('loader').style.display='none';$('methodDetails').open=true;$('methodDetails').scrollIntoView({behavior:'smooth',block:'start'});};
  const trap=e=>{
    if(e.key!=='Tab')return;
    const modal=[$('picker'),$('search')].find(el=>el.classList.contains('on'));if(!modal)return;
    const nodes=[...modal.querySelectorAll('button,input,a[href],[tabindex="0"]')].filter(el=>!el.disabled&&el.getClientRects().length);
    if(!nodes.length)return;const first=nodes[0],last=nodes[nodes.length-1];
    if(e.shiftKey&&(document.activeElement===first||!modal.contains(document.activeElement))){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&(document.activeElement===last||!modal.contains(document.activeElement))){e.preventDefault();first.focus();}
  };document.addEventListener('keydown',trap);
  $('rB').addEventListener('click',e=>{const row=e.target.closest('.rr');if(row&&st.rep)focusPlace(row.id.slice(3));});
  $('rB').addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.rr')){e.preventDefault();focusPlace(e.target.id.slice(3));}});
  $('picker').setAttribute('aria-modal','true');$('search').setAttribute('aria-modal','true');
}

function showMapUnavailable(){
  document.body.classList.add('map-unavailable');
  $('map').innerHTML='<div class="map-fallback"><span class="eyebrow">TRYB BEZ MAPY</span><h2>Sprawdź okolicę po adresie</h2><p>Ta przeglądarka nie udostępnia WebGL, potrzebnego do wyświetlenia mapy. Wyszukiwarka adresów, karta budynku i statystyki nadal działają.</p><button class="primary-button" id="fallbackSearch">Wyszukaj adres</button><small>Aby zobaczyć mapę, włącz akcelerację graficzną lub użyj innej przeglądarki.</small></div>';
  $('fallbackSearch').onclick=openSearch;
}
