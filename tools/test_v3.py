"""Test strony v3/v4 (Playwright, Edge headless): przewijanie panelu kółkiem, sieci, kombinacje, wyszukiwarka, raport, telefon.
Użycie: python test_v3.py <url> <katalog_zrzutów> [prefiks]"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1]; OUT = Path(sys.argv[2]); PFX = sys.argv[3] if len(sys.argv) > 3 else 'v3'
OUT.mkdir(parents=True, exist_ok=True); R = {}

def watch(page, tag):
    errs = []
    page.on('console', lambda m: errs.append(f'{m.type}: {m.text}') if m.type == 'error' else None)
    page.on('pageerror', lambda e: errs.append(f'pageerror: {e} | {(e.stack or "")[:600]}'))
    page.on('requestfailed', lambda r: errs.append(f'failed: {r.url} {r.failure}') if 'photon' not in r.url and 'cartocdn' not in r.url else None)
    page.on('response', lambda r: errs.append(f'http {r.status}: {r.url}') if r.status >= 400 else None)
    return errs

def ready(page, t0):
    page.wait_for_function('window.__ready', timeout=90000); return round((time.time() - t0) * 1000)

def idle(page, ms=60000):
    page.wait_for_function("!document.getElementById('bar').classList.contains('on')", timeout=ms); page.wait_for_timeout(400)

def desktop(p, w, h):
    tag = f'{w}x{h}'; b = p.chromium.launch(channel='msedge', headless=True, args=['--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
    pg = b.new_page(viewport={'width': w, 'height': h}); errs = watch(pg, tag); r = {}
    t0 = time.time(); pg.goto(URL, wait_until='domcontentloaded'); r['ready_ms'] = ready(pg, t0); idle(pg); r['idle_ms'] = round((time.time() - t0) * 1000)
    pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_1_start.png'))
    # przewijanie panelu prawdziwym kółkiem myszy
    box = pg.locator('#body').bounding_box(); pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
    before = pg.evaluate("document.getElementById('body').scrollTop")
    for _ in range(6): pg.mouse.wheel(0, 300); pg.wait_for_timeout(120)
    after = pg.evaluate("document.getElementById('body').scrollTop"); mx = pg.evaluate("(()=>{const b=document.getElementById('body');return b.scrollHeight-b.clientHeight})()")
    r['wheel_scroll'] = {'before': before, 'after': after, 'max': mx, 'ok': after > before}
    pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_2_scrolled.png'))
    for _ in range(40): pg.mouse.wheel(0, 400)
    pg.wait_for_timeout(300); r['wheel_bottom'] = pg.evaluate("(()=>{const b=document.getElementById('body');return [b.scrollTop,b.scrollHeight-b.clientHeight]})()")
    pg.mouse.wheel(0, -100000); pg.wait_for_timeout(300)
    # jedna sieć: przystanek kolejowy
    t = time.time(); pg.click('#nets .chip[data-n=przystanek_kolejowy]'); idle(pg); r['switch_net_ms'] = round((time.time() - t) * 1000)
    r['one_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
    # kombinacja: gotowy zestaw
    t = time.time(); pg.click('.preset[data-p=wyklucz]')
    pg.wait_for_function("document.getElementById('scan').hidden && !document.getElementById('cntB').classList.contains('sk')", timeout=240000)
    r['combo_scan_ms'] = round((time.time() - t) * 1000); r['combo_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
    # przesunięcie suwaka – przeliczenie natychmiastowe
    t = time.time(); s = pg.locator('#sel input[type=range]').first; s.focus(); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(150)
    r['combo_recalc_ms'] = pg.evaluate('window.__combo_ms'); r['combo_counts2'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
    # dodaj czwartą sieć ręcznie i przełącz na „którakolwiek”
    pg.click('#nets .chip[data-n=apteka]'); pg.wait_for_function("document.getElementById('scan').hidden && !document.getElementById('cntB').classList.contains('sk')", timeout=240000)
    pg.click('#logic button[data-l=any]'); pg.wait_for_timeout(500); r['combo_any'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]
    pg.click('#logic button[data-l=all]'); pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_3_combo.png'))
    # v4: zakładki i wyszukiwanie sieci, zestaw z warunkiem ceny, warstwa cen
    if pg.locator('#ntabs').count():
        pg.click('#ntabs button[data-c=zdrowie]'); pg.wait_for_timeout(250)
        r['tab_zdrowie'] = pg.evaluate("[...document.querySelectorAll('#nets .chip')].filter(b=>!b.hidden).map(b=>b.dataset.n)")
        pg.locator('#ntabs').scroll_into_view_if_needed(); pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_3b_tabs.png'))
        pg.click('#ntabs button[data-c=""]'); pg.fill('#nq', 'straz'); pg.wait_for_timeout(200)
        r['nq_straz'] = pg.evaluate("[...document.querySelectorAll('#nets .chip')].filter(b=>!b.hidden).map(b=>b.dataset.n)"); pg.fill('#nq', ''); pg.wait_for_timeout(100)
        pg.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2); pg.mouse.wheel(0, -100000); pg.wait_for_timeout(200)
    if pg.locator('.preset[data-p=tanio]').count():
        t = time.time(); pg.click('.preset[data-p=tanio]'); pg.wait_for_timeout(300)
        pg.wait_for_function("document.getElementById('scan').hidden && !document.getElementById('cntB').classList.contains('sk')", timeout=300000)
        r['tanio_ms'] = round((time.time() - t) * 1000); r['tanio_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]; r['tanio_pc'] = pg.evaluate('[pcOn(),st.pc.op,st.pc.v]')
        s = pg.locator('#pcS'); s.focus(); pg.keyboard.press('ArrowRight'); pg.keyboard.press('ArrowRight'); pg.wait_for_timeout(300)
        r['tanio_counts_9500'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]; r['tanio_url'] = pg.url.split('?')[-1].split('#')[0]
        pg.locator('#lyCw').scroll_into_view_if_needed(); pg.click('#lyCw'); pg.wait_for_timeout(300)
        pg.evaluate("map.jumpTo({center:[19.94,50.06],zoom:10.5})"); idle(pg); pg.wait_for_timeout(800)
        r['price_layer'] = pg.evaluate("[document.getElementById('lyC').checked,!!PRICE,PRICE?PRICE.g1.cells.length:0,PRICE?PRICE.g5.cells.length:0]")
        pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_3c_price.png'))
        pg.evaluate("map.jumpTo({center:[19.3,52.0],zoom:6})"); idle(pg); pg.wait_for_timeout(500); pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_3d_price_pl.png'))
    # wyszukiwarka
    pg.keyboard.press('Escape'); pg.mouse.click(w - 200, h // 2); pg.keyboard.press('/')
    pg.fill('#sq', 'Floriańska Kraków'); pg.wait_for_selector('.res', timeout=20000); pg.wait_for_timeout(600)
    r['search_results'] = pg.locator('.res .tt').all_inner_texts()[:5]
    pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_4_search.png'))
    t = time.time(); pg.keyboard.press('Enter')
    pg.wait_for_selector('#report.on', timeout=30000); pg.wait_for_function('window.__report_ms', timeout=90000); r['report_ms'] = round((time.time() - t) * 1000)
    idle(pg); pg.wait_for_timeout(1200)
    r['report_title'] = pg.inner_text('#rT'); r['report_rows'] = pg.locator('.rr').count(); r['report_first'] = pg.locator('.rr').first.inner_text().replace('\n', ' | ')
    r['report_known'] = pg.evaluate("[...document.querySelectorAll('.rr b')].filter(b=>b.textContent.trim()&&b.textContent.trim()!=='–'&&!b.classList.contains('sk')).length")
    r['report_named'] = pg.evaluate("[...document.querySelectorAll('.rr small')].filter(s=>s.textContent.trim()&&!s.querySelector('.sk')).length")
    r['lines'] = pg.evaluate('st.lines.map(l=>l.text)'); r['rank_files'] = pg.evaluate('RG.size')
    r['report_price'] = pg.inner_text('#rPrice').replace('\n', ' | ') if pg.locator('#rPrice').count() else None
    pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_5_report.png'))
    pg.emulate_media(media='print'); pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_6_print.png'), full_page=True); pg.emulate_media(media='screen')
    # kliknięcie w mapę (budynek) w innym miejscu
    pg.click('#rX'); pg.evaluate("map.jumpTo({center:[21.0122,52.2297],zoom:14})"); idle(pg); pg.wait_for_timeout(800)
    t = time.time(); pg.mouse.click(w // 2 + 100, h // 2); 
    try: pg.wait_for_selector('#report.on', timeout=15000); pg.wait_for_function('window.__report_ms', timeout=60000); r['click_report_ms'] = round((time.time() - t) * 1000)
    except Exception as e: r['click_report_ms'] = f'brak: {e}'
    idle(pg); pg.screenshot(path=str(OUT / f'{PFX}_desk_{tag}_7_warszawa.png'))
    r['errors'] = errs[:20]; b.close(); return r

def mobile(p):
    b = p.chromium.launch(channel='msedge', headless=True, args=['--enable-unsafe-swiftshader', '--use-angle=swiftshader'])
    ctx = b.new_context(**p.devices['iPhone 13']); pg = ctx.new_page(); errs = watch(pg, 'iphone'); r = {}
    t0 = time.time(); pg.goto(URL, wait_until='domcontentloaded'); r['ready_ms'] = ready(pg, t0); idle(pg); r['idle_ms'] = round((time.time() - t0) * 1000)
    pg.screenshot(path=str(OUT / f'{PFX}_iphone_1_start.png'))
    pg.tap('#grab'); pg.wait_for_timeout(500); pg.screenshot(path=str(OUT / f'{PFX}_iphone_2_sheet.png'))
    pg.tap('#mode button[data-m=combo]'); pg.wait_for_timeout(200)
    for n in ('poz', 'przystanek_kolejowy'): pg.tap(f'#nets .chip[data-n={n}]'); pg.wait_for_timeout(200)
    pg.wait_for_function("document.getElementById('scan').hidden && !document.getElementById('cntB').classList.contains('sk')", timeout=300000)
    r['combo_counts'] = [pg.inner_text('#cntB'), pg.inner_text('#cntP')]; pg.screenshot(path=str(OUT / f'{PFX}_iphone_3_combo.png'))
    pg.tap('#grab'); pg.wait_for_timeout(400); pg.tap('#msearch'); pg.fill('#sq', 'Zakopane'); pg.wait_for_selector('.res', timeout=20000); pg.wait_for_timeout(500)
    r['search_results'] = pg.locator('.res .tt').all_inner_texts()[:4]; pg.screenshot(path=str(OUT / f'{PFX}_iphone_4_search.png'))
    pg.fill('#sq', 'Krupówki 12 Zakopane'); pg.wait_for_timeout(2500); r['search_addr'] = pg.locator('.res .tt').all_inner_texts()[:3]
    t = time.time(); pg.locator('.res').first.tap()
    try: pg.wait_for_selector('#report.on', timeout=30000); pg.wait_for_function('window.__report_ms', timeout=90000); r['report_ms'] = round((time.time() - t) * 1000)
    except Exception as e: r['report_ms'] = f'brak: {e}'
    idle(pg); pg.wait_for_timeout(1200); pg.screenshot(path=str(OUT / f'{PFX}_iphone_5_report.png'))
    r['lines'] = pg.evaluate('st.lines.map(l=>l.text)'); r['errors'] = errs[:20]; b.close(); return r

with sync_playwright() as p:
    for w, h in (((1366, 768),) if 'ONLY1366' in sys.argv else ((1366, 768), (1920, 1080))):
        try: R[f'desk_{w}x{h}'] = desktop(p, w, h)
        except Exception as e: R[f'desk_{w}x{h}'] = {'fail': repr(e)[:400]}
    if 'ONLY1366' not in sys.argv and 'NOMOBILE' not in sys.argv:  # telefon: patrz test_mobile.py
      try: R['iphone13'] = mobile(p)
      except Exception as e: R['iphone13'] = {'fail': repr(e)[:400]}
print(json.dumps(R, ensure_ascii=False, indent=1))
(OUT / f'{PFX}_results.json').write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding='utf-8')
