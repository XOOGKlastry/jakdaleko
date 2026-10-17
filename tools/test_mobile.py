"""Test mobilny v3.1/v4 (Playwright, Edge headless, prawdziwe zdarzenia dotyku przez CDP):
Pixel 7 (412x915) i iPhone 13, motyw ciemny i jasny: wybór sieci w trybie jednej sieci przez przycisk + pełnoekranowy wybór,
przewijanie arkusza palcem do końca (mapa nie może się przesunąć), przeciąganie uchwytu, kombinacja z kierunkiem blisko/daleko i „lub”,
oraz (Pixel 7 ciemny) kombinacja 10 sieci + próba przekroczenia limitu.
Użycie: python test_mobile.py <url> <katalog_zrzutów> [prefiks] [TEN]"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1]; OUT = Path(sys.argv[2]); PFX = sys.argv[3] if len(sys.argv) > 3 else 'v31'
OUT.mkdir(parents=True, exist_ok=True); R = {}
DONE = "document.getElementById('scan').hidden && !document.getElementById('cntB').classList.contains('sk')"

def watch(page):
    errs = []
    page.on('console', lambda m: errs.append(f'{m.type}: {m.text}') if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append(f'pageerror: {e} | {(e.stack or "")[:500]}'))
    page.on('response', lambda r: errs.append(f'http {r.status}: {r.url}') if r.status >= 400 else None)
    return errs

def idle(pg, ms=90000):
    pg.wait_for_function("!document.getElementById('bar').classList.contains('on')", timeout=ms); pg.wait_for_timeout(400)

def swipe(cdp, pg, x, y1, y2, steps=10):
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y1}]})
    for i in range(1, steps + 1):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y1 + (y2 - y1) * i / steps}]}); pg.wait_for_timeout(16)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); pg.wait_for_timeout(350)

def in_view(pg, sel):
    """czy element jest widoczny w obszarze arkusza i ekranu BEZ przewijania"""
    return pg.evaluate("""s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect(),b=document.getElementById('body').getBoundingClientRect();
      return r.height>0&&r.top>=b.top-1&&r.bottom<=Math.min(b.bottom,innerHeight)+1&&getComputedStyle(e).visibility!=='hidden';}""", sel)

def run(p, dev, scheme, ten):
    tag = f"{'pixel7' if 'Pixel' in dev else 'iphone13'}_{scheme}"; r = {}
    b = p.chromium.launch(channel='msedge', headless=True, args=['--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
    d = dict(p.devices[dev]); ctx = b.new_context(**d, color_scheme=scheme); pg = ctx.new_page(); errs = watch(pg); cdp = ctx.new_cdp_session(pg)
    r['viewport'] = d['viewport']; t0 = time.time(); pg.goto(URL, wait_until='domcontentloaded'); pg.wait_for_function('window.__ready', timeout=120000); idle(pg)
    r['ready_ms'] = round((time.time() - t0) * 1000); r['theme'] = pg.evaluate('st.theme')
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_1_start.png'))
    r['pick_btn_in_view'] = in_view(pg, '#pickBtn'); r['pick_btn_text'] = pg.inner_text('#pickBtn')
    # 1) jedna sieć: przycisk -> pełnoekranowa lista -> wyszukanie -> wybór
    pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on', timeout=5000); pg.wait_for_timeout(300)
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_2_picker.png'))
    pg.fill('#pq', 'apte'); pg.wait_for_timeout(200); r['picker_filtered_visible'] = pg.evaluate("[...document.querySelectorAll('#plist .chip')].filter(b=>!b.hidden&&b.offsetParent).map(b=>b.dataset.n)")
    t = time.time(); pg.tap('#plist .chip[data-n=apteka]'); pg.wait_for_function("!document.getElementById('picker').classList.contains('on')", timeout=5000)
    idle(pg); r['one_switch_ms'] = round((time.time() - t) * 1000); r['one_sel'] = pg.evaluate('st.sel'); r['one_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
    r['one_btn_after'] = pg.inner_text('#pickBtn'); pg.screenshot(path=str(OUT / f'{PFX}_{tag}_3_one_apteka.png'))
    # 1b) zmiana przez zakładkę kategorii (Transport -> przystanek kolejowy)
    pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on'); pg.tap('#ptabs button[data-c=transport]'); pg.wait_for_timeout(250)
    r['tab_chip_in_view'] = pg.evaluate("(()=>{const e=document.querySelector('#plist .chip[data-n=przystanek_kolejowy]').getBoundingClientRect();return e.top>=0&&e.bottom<=innerHeight})()")
    pg.tap('#plist .chip[data-n=przystanek_kolejowy]'); idle(pg); r['one_sel2'] = pg.evaluate('st.sel')
    # 1c) v4: nowa kategoria (Zdrowie -> szpital) i powrót do przystanku kolejowego
    pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on'); pg.tap('#ptabs button[data-c=zdrowie]'); pg.wait_for_timeout(250)
    r['tab_zdrowie_in_view'] = pg.evaluate("(()=>{const e=document.querySelector('#plist .chip[data-n=szpital]').getBoundingClientRect();return e.top>=0&&e.bottom<=innerHeight})()")
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_3b_picker_zdrowie.png')); pg.tap('#plist .chip[data-n=szpital]'); idle(pg); r['one_sel3'] = pg.evaluate('st.sel')
    pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on'); pg.tap('#ptabs button[data-c=transport]'); pg.wait_for_timeout(250); pg.tap('#plist .chip[data-n=przystanek_kolejowy]'); idle(pg)
    # 2) przewijanie arkusza palcem (zwinięty) do samego dołu; mapa nie może się ruszyć
    c0 = pg.evaluate('[map.getCenter().lng,map.getCenter().lat,map.getZoom()]'); bb = pg.locator('#body').bounding_box(); x = bb['x'] + bb['width'] * 0.5
    y_hi, y_lo = bb['y'] + 40, bb['y'] + bb['height'] - 30
    swipe(cdp, pg, x, y_lo, y_hi); r['sheet_scroll_1'] = pg.evaluate("document.getElementById('body').scrollTop")
    for _ in range(60):
        swipe(cdp, pg, x, y_lo, y_hi, 6)
        if pg.evaluate("(()=>{const b=document.getElementById('body');return b.scrollTop>=b.scrollHeight-b.clientHeight-2})()"): break
    r['sheet_bottom'] = pg.evaluate("(()=>{const b=document.getElementById('body');return [Math.round(b.scrollTop),b.scrollHeight-b.clientHeight]})()")
    c1 = pg.evaluate('[map.getCenter().lng,map.getCenter().lat,map.getZoom()]'); r['map_moved_by_sheet'] = any(abs(a - b_) > 1e-6 for a, b_ in zip(c0, c1))
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_4_sheet_bottom.png'))
    for _ in range(80):
        swipe(cdp, pg, x, y_hi, y_lo, 6)
        if pg.evaluate("document.getElementById('body').scrollTop<=0"): break
    # 3) przeciągnięcie uchwytu w górę i w dół
    g = pg.locator('#grab').bounding_box(); gx, gy = g['x'] + g['width'] / 2, g['y'] + g['height'] / 2; h0 = pg.evaluate("document.getElementById('panel').getBoundingClientRect().height")
    swipe(cdp, pg, gx, gy, 120); pg.wait_for_timeout(400); h1 = pg.evaluate("document.getElementById('panel').getBoundingClientRect().height")
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_5_expanded.png'))
    g = pg.locator('#grab').bounding_box(); swipe(cdp, pg, gx, g['y'] + g['height'] / 2, d['viewport']['height'] - 60); pg.wait_for_timeout(400)
    h2 = pg.evaluate("document.getElementById('panel').getBoundingClientRect().height"); pg.tap('#grab'); pg.wait_for_timeout(450)
    h3 = pg.evaluate("document.getElementById('panel').getBoundingClientRect().height"); pg.tap('#grab'); pg.wait_for_timeout(450)
    r['sheet_heights'] = {'start': round(h0), 'drag_up': round(h1), 'drag_down': round(h2), 'tap_open': round(h3), 'tap_close': round(pg.evaluate("document.getElementById('panel').getBoundingClientRect().height"))}
    # 4) kombinacja: POZ (daleko) + przystanek kolejowy (blisko) + apteka (lub)
    pg.tap('#mode button[data-m=combo]'); pg.wait_for_timeout(200); r['combo_btn_in_view'] = in_view(pg, '#pickBtn')
    pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on')
    for n in ('poz', 'apteka'): pg.tap(f'#plist .chip[data-n={n}]'); pg.wait_for_timeout(150)
    r['picker_info'] = pg.inner_text('#pinfo'); pg.screenshot(path=str(OUT / f'{PFX}_{tag}_6_picker_multi.png')); pg.tap('#pDone'); pg.wait_for_timeout(200)
    r['combo_sel'] = pg.evaluate('st.sel')
    pg.tap('#sel [data-d=przystanek_kolejowy]'); pg.wait_for_timeout(150); pg.tap('#sel [data-r=apteka]'); pg.wait_for_timeout(150); pg.tap('#sel [data-r=poz]'); pg.wait_for_timeout(150)
    pg.wait_for_function(DONE, timeout=400000); r['combo_scan_ms'] = pg.evaluate('window.__scan_ms')
    r['combo_state'] = pg.evaluate("st.sel.map(id=>id+':'+(isNear(id)?'blisko':'daleko')+':'+(isReq(id)?'musi':'lub'))"); r['combo_logic_hint'] = pg.inner_text('#logicH')
    r['combo_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]; r['combo_url'] = pg.url.split('?')[-1]; r['combo_top1'] = pg.locator('#top tr').first.inner_text().replace('\t', ' ')
    pg.screenshot(path=str(OUT / f'{PFX}_{tag}_7_combo.png'))
    # 4b) v4: warunek ceny mieszkań
    if pg.locator('#pcAdd').count():
        pg.locator('#pcAdd').scroll_into_view_if_needed(); pg.tap('#pcAdd'); pg.wait_for_timeout(500); pg.wait_for_function(DONE, timeout=400000)
        r['pc_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]; r['pc_state'] = pg.evaluate('[pcOn(),st.pc.op,st.pc.v,document.getElementById("lyC").checked]')
        pg.locator('#pcS').scroll_into_view_if_needed(); pg.screenshot(path=str(OUT / f'{PFX}_{tag}_7b_price.png'))
    if ten:
        pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on')
        for n in ('przystanek', 'szkola', 'przedszkole', 'zabka', 'biedronka', 'bankomat', 'any_locker'): pg.tap(f'#plist .chip[data-n={n}]'); pg.wait_for_timeout(120)
        pg.tap('#pDone'); pg.wait_for_function(DONE, timeout=600000); pg.wait_for_timeout(1500); pg.wait_for_function(DONE, timeout=600000); r['ten_scan_ms'] = pg.evaluate('window.__scan_ms'); r['ten_k'] = pg.evaluate('K()')
        r['ten_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
        s = pg.locator('#sel input[type=range]').nth(3); s.focus(); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(400); r['ten_recalc_ms'] = round(pg.evaluate('window.__combo_ms'))
        r['ten_heap_mb'] = pg.evaluate("performance.memory?Math.round(performance.memory.usedJSHeapSize/1048576):null")
        pg.screenshot(path=str(OUT / f'{PFX}_{tag}_8_ten.png'))
        pg.tap('#pickBtn'); pg.wait_for_selector('#picker.on')
        for n in ('lidl', 'dino'): pg.tap(f'#plist .chip[data-n={n}]'); pg.wait_for_timeout(120)
        r['k12'] = pg.evaluate('K()'); pg.tap('#plist .chip[data-n=netto]'); pg.wait_for_timeout(200); r['k_after_13th'] = pg.evaluate('K()'); r['cap_toast'] = pg.inner_text('#toast')
        r['cap_off_chips'] = pg.locator('#plist .chip.off').count(); pg.screenshot(path=str(OUT / f'{PFX}_{tag}_9_cap.png')); pg.tap('#pDone')
    # 5) raport po stuknięciu w mapę (Kraków)
    pg.evaluate("map.jumpTo({center:[19.94,50.06],zoom:15})"); idle(pg); pg.wait_for_timeout(600); t = time.time()
    pg.touchscreen.tap(d['viewport']['width'] // 2, 200)
    try:
        pg.wait_for_selector('#report.on, .maplibregl-popup', timeout=20000)
        if pg.locator('.maplibregl-popup').count(): r['tap_result'] = 'popup punktu: ' + pg.inner_text('.maplibregl-popup h3')
        else: pg.wait_for_function('window.__report_ms', timeout=90000); r['tap_result'] = 'raport: ' + pg.inner_text('#rT'); r['report_far_ok'] = pg.evaluate("[document.querySelectorAll('.rr.far').length,document.querySelectorAll('.rr.ok').length]")
        r['tap_ms'] = round((time.time() - t) * 1000)
    except Exception as e: r['tap_result'] = f'brak: {str(e)[:100]}'
    idle(pg); pg.wait_for_timeout(800); pg.screenshot(path=str(OUT / f'{PFX}_{tag}_10_report.png'))
    r['report_price'] = pg.inner_text('#rPrice').replace('\n', ' | ') if pg.locator('#rPrice').count() else None
    r['errors'] = errs[:20]; b.close(); return r

with sync_playwright() as p:
    for dev, sch in (('Pixel 7', 'dark'), ('Pixel 7', 'light'), ('iPhone 13', 'dark'), ('iPhone 13', 'light')):
        k = f"{dev}_{sch}"
        if 'QUICK' in sys.argv and k not in ('Pixel 7_dark',): continue
        try: R[k] = run(p, dev, sch, 'TEN' in sys.argv and k == 'Pixel 7_dark')
        except Exception as e: R[k] = {'fail': repr(e)[:600]}
        print(k, json.dumps(R[k], ensure_ascii=False)[:3000], flush=True)
(OUT / f'{PFX}_mobile_results.json').write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding='utf-8')
