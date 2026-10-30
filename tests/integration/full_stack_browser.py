"""Opt-in real raffle page -> original Master POST/RPC -> original checkout -> DB.
Requires the isolated loopback services described in README.md. No production I/O.
"""
import functools
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[2]
API='https://m-master-view.lovable.app/api/public/roleta-sorteio'
CHECKOUT='https://natal.estudioliliancristina.com.br/'
LOCAL='http://127.0.0.1:55433'
SITE='http://127.0.0.1:8081'

def local(path,data=None,headers=None):
    request=urllib.request.Request(LOCAL+path,data=None if data is None else json.dumps(data).encode(),
        headers={'content-type':'application/json',**(headers or {})})
    try:
        with urllib.request.urlopen(request,timeout=15) as response:
            return response.status,response.read()
    except urllib.error.HTTPError as response:
        return response.code,response.read()

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*_):pass

class FullStackBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status,body=local('/health')
        if status!=200 or json.loads(body)!={'isolated':True}:raise RuntimeError('Isolated transport required')
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(ROOT)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.p=sync_playwright().start()
        cls.engine=os.environ.get('BELEM_BROWSER','chromium')
        if cls.engine=='webkit':
            options={'executable_path':os.environ['BROWSER_EXECUTABLE']} if os.environ.get('BROWSER_EXECUTABLE') else {}
            cls.browser=cls.p.webkit.launch(**options)
        elif cls.engine=='chromium':cls.browser=cls.p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        else:raise ValueError('BELEM_BROWSER must be chromium or webkit')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.p.stop();cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':390,'height':844},reduced_motion='reduce',is_mobile=self.engine=='webkit',has_touch=self.engine=='webkit')
        self.errors=[];self.blocked=[];self.raffle_responses=[];self.target=None
        self.context.route('**/*',self.intercept)
        self.context.on('page',lambda p:p.on('pageerror',lambda e:self.errors.append(str(e))))
        self.page=self.context.new_page();self.page.set_default_timeout(15000)
        self.context.add_init_script('''const delay=window.setTimeout;
            window.setTimeout=(fn,ms,...a)=>delay(fn,[1200,6000].includes(ms)?0:ms,...a);''')

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors,[])
        self.assertEqual(self.blocked,[],'No unhandled request may leave the isolated stack')

    def intercept(self,route):
        url=route.request.url
        if url==API:
            status,body=local('/api/public/roleta-sorteio',route.request.post_data_json,
                {'Origin':'https://roleta.estudioliliancristina.com.br'})
            self.raffle_responses.append(json.loads(body))
            route.fulfill(status=status,content_type='application/json',body=body)
        elif url==CHECKOUT and self.target:
            route.fulfill(status=302,headers={'location':self.target})
        elif urlsplit(url).netloc in (urlsplit(self.base).netloc,'127.0.0.1:8081'):
            route.continue_()
        elif any(url.startswith('blob:'+origin+'/') for origin in (self.base,SITE)):
            route.continue_()
        elif 'fonts.googleapis.com' in url or 'fonts.gstatic.com' in url:
            route.fulfill(status=200,content_type='text/css',body='')
        elif url in ('https://bzrcdn.openai.com/sdk/oaiq.min.js',
                     'https://connect.facebook.net/en_US/fbevents.js'):
            # Do not load analytics or send synthetic visits/conversions to providers.
            route.fulfill(status=200,content_type='application/javascript',body='/* isolated test: analytics disabled */')
        else:
            self.blocked.append(url);route.abort()

    def journey(self,prize,video=False):
        status,_=local('/fixture/reset',{'prize':prize});self.assertEqual(status,200)
        self.page.goto(self.base+'/?origem=pizzaria',wait_until='domcontentloaded')
        expect(self.page.locator('#roletaCpf')).to_be_attached()
        if video:
            self.page.locator('#enter').click()
            expect(self.page.locator('#experience')).to_be_visible()
            self.page.wait_for_function("document.getElementById('film').readyState>=2")
            self.page.locator('#film').evaluate('(v)=>{v.muted=true;v.playbackRate=16;v.play().catch(()=>{})}')
            expect(self.page.locator('#wheelBtn')).to_be_enabled(timeout=20000)
            self.page.locator('#wheelBtn').click(force=True)
        else:
            self.page.evaluate("document.getElementById('entry').classList.add('hidden');document.getElementById('spin').classList.remove('hidden')")
        self.page.locator('#roletaCpf').fill('12345678909')
        self.page.locator('#roletaConsent').check()
        self.page.locator('#wheelStar').dispatch_event('click')
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        result=self.raffle_responses[-1]
        self.assertTrue(result['ok']);self.assertEqual(result['coupon']['prize_id'],prize)
        code=self.page.locator('.coupon-display strong').inner_text()
        expect(self.page.locator('#roletaCpf')).to_be_enabled()
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual(self.raffle_responses[-1]['coupon']['code'],code)
        _,data=local('/fixture/reservation',{'extras':0 if prize=='ensaio' else 10000})
        reservation=json.loads(data)
        self.target=SITE+'/pagamento/'+reservation['id']+'?token='+reservation['public_token']
        with self.context.expect_page() as opened:self.page.locator('#redeemPrize').click(force=True)
        checkout=opened.value;checkout.set_default_timeout(20000)
        field=checkout.get_by_label('Cupom / crédito (opcional)')
        expect(field).to_be_visible()
        field.fill('INVALID-FIXTURE')
        checkout.get_by_role('button',name='Aplicar',exact=True).click()
        expect(checkout.get_by_text('Cupom inválido ou não disponível para este cadastro.',exact=True)).to_be_visible()
        field.fill(code);checkout.get_by_role('button',name='Aplicar',exact=True).click()
        if prize=='ensaio':
            checkout.wait_for_url('**/confirmacao/*',timeout=20000)
        else:
            expect(checkout.get_by_text('Restante a pagar',exact=True)).to_be_visible()
            expected=78000-68000*int(prize)//100
            text=f'{expected//100:,}'.replace(',','.')+f',{expected%100:02d}'
            expect(checkout.locator('body')).to_contain_text(text)
            checkout.reload()
            expect(checkout.get_by_text('Restante a pagar',exact=True)).to_be_visible()
            expect(checkout.locator('body')).to_contain_text(text)
        _,body=local('/fixture/snapshot');state=json.loads(body)
        self.assertEqual(len(state['participants']),1)
        self.assertTrue(state['participants'][0]['hashed'])
        self.assertEqual(state['participants'][0]['identity_kind'],'cpf')
        self.assertEqual(state['participants'][0]['consent_version'],'roleta-2026-10')
        r=state['reservations'][0]
        self.assertEqual(r['discount_applied_cents'],68000 if prize=='ensaio' else 68000*int(prize)//100)
        self.assertEqual(state['attempts'],0)
        if prize=='ensaio':
            self.assertEqual(r['status'],'confirmed')
            self.assertEqual(state['coupons'][0]['status'],'redeemed')
            self.assertEqual(state['payments'],[dict(provider='admin_coupon',method='credit',amount_cents=0,status='paid')])
        else:
            self.assertEqual(r['status'],'awaiting_payment')
            self.assertEqual(state['payments'],[])
            record=state['shared'][0] if prize=='5' else state['coupons'][0]
            self.assertEqual(record['status'],'applied')
        return code

    def test_shared_5_from_draw_through_actual_checkout_and_database(self):
        self.assertEqual(self.journey('5'),'ESTRELA5')

    def test_individual_10_through_actual_checkout_and_database(self):self.journey('10')
    def test_individual_20_through_actual_checkout_and_database(self):self.journey('20')
    def test_individual_50_through_actual_checkout_and_database(self):self.journey('50')
    def test_video_to_main_prize_to_confirmed_zero_total_reservation(self):self.journey('ensaio',video=True)

if __name__=='__main__':unittest.main(verbosity=2)
