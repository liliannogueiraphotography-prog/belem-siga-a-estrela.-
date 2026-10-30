"""Browser regressions. All raffle responses are intercepted; no real CPF is sent."""
import functools
import json
import os
from pathlib import Path
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
API = 'https://m-master-view.lovable.app/api/public/roleta-sorteio'
RESERVATIONS = 'https://natal.estudioliliancristina.com.br/'
# Synthetic checksum-valid identifiers used exclusively with intercepted requests.
CPF = '12345678909'
OTHER_CPF = '98765432100'


def coupon(prize='5', **changes):
    result = dict(code='BELEM-FICTICIO-0001', prize_id=prize, status='issued',
                  expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
    result.update(changes)
    return result


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


class RouletteBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0),
            functools.partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.engine = os.environ.get('BELEM_BROWSER', 'chromium')
        if cls.engine == 'webkit':
            options = {'executable_path': os.environ['BROWSER_EXECUTABLE']} if os.environ.get('BROWSER_EXECUTABLE') else {}
            cls.browser = cls.playwright.webkit.launch(**options)
        elif cls.engine == 'chromium':
            browser_path = os.environ.get('CHROMIUM_EXECUTABLE', '/usr/bin/chromium')
            cls.browser = cls.playwright.chromium.launch(executable_path=browser_path,args=['--no-sandbox'])
        else:
            raise ValueError('BELEM_BROWSER must be chromium or webkit')

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':390,'height':844},
            reduced_motion='reduce', service_workers='block',is_mobile=self.engine=='webkit',has_touch=self.engine=='webkit')
        self.page = self.context.new_page()
        self.page.set_default_timeout(5000)
        self.errors = []
        self.calls = []
        self.external = []
        self.responses = []
        self.allow_media = False
        self.handler = None
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.page.route('**/*', self.route)
        # Only shorten visual animation delays. Request timeout stays unchanged.
        self.page.add_init_script('''const originalTimeout=window.setTimeout;
            window.setTimeout=(fn,ms,...args)=>originalTimeout(fn,
                [1200,6000].includes(ms)?0:ms,...args);''')

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], 'Unexpected JavaScript errors')
        self.assertEqual(self.external, [], 'External traffic must never escape mocks')

    def route(self, route):
        url = route.request.url
        if url == API:
            self.calls.append(route.request.post_data_json)
            if self.handler:
                self.handler(route)
            elif self.responses:
                response = self.responses.pop(0)
                route.fulfill(status=response.get('status', 200),
                    content_type=response.get('content_type', 'application/json'),
                    body=response.get('body', json.dumps(response.get('json'))))
            else:
                self.external.append('Unexpected unmocked API call')
                route.abort()
        elif urlsplit(url).netloc == urlsplit(self.base).netloc:
            if url.endswith(('.MP4', '.mp3')) and not self.allow_media:
                route.abort()
            else:
                route.continue_()
        elif url.startswith('blob:'+self.base+'/'):
            # WebKit exposes origin-local blob workers to routing; no network I/O.
            route.continue_()
        else:
            self.external.append(url)
            route.abort()

    def open(self, query='', spin=True):
        self.page.goto(self.base+'/'+query, wait_until='domcontentloaded')
        expect(self.page.locator('#roletaCpf')).to_be_attached()
        if spin:
            self.page.evaluate("""document.getElementById('entry').classList.add('hidden');
                document.getElementById('spin').classList.remove('hidden');""")

    def fill(self, cpf=CPF):
        self.page.locator('#roletaCpf').fill(cpf)
        self.page.locator('#roletaConsent').check()

    def spin(self):
        self.page.locator('#wheelStar').dispatch_event('click')

    def wait_done(self):
        expect(self.page.locator('#roletaCpf')).to_be_enabled()
        expect(self.page.locator('.wheel')).not_to_have_class('wheel roleta-waiting')

    def assert_no_coupon(self):
        expect(self.page.locator('#parchmentReveal')).to_be_hidden()
        self.assertIsNone(self.page.locator('#redeemPrize').get_attribute('href'))

    def answer(self, c=None, **data):
        self.responses.append({'json':dict(ok=True, coupon=c, **data)})

    def test_invalid_cpf_or_missing_consent_never_reaches_backend(self):
        self.open()
        for cpf in ('', '123', '11111111111', '12345678900', 'abcdefghijk'):
            self.page.locator('#roletaCpf').fill(cpf)
            self.spin()
            expect(self.page.locator('#wheelStar')).to_have_attribute('aria-disabled','true')
        self.page.locator('#roletaCpf').fill(CPF)
        self.spin()
        self.assertEqual(self.calls, [])
        self.assert_no_coupon()

    def test_all_five_prizes_match_server_result_and_reservation_link(self):
        for prize, label in [('5','5%'),('10','10%'),('20','20%'),('50','50%'),('ensaio','VOCÊ GANHOU UM ENSAIO')]:
            with self.subTest(prize=prize):
                self.open('?origem=pizzaria')
                self.fill('123.456.789-09')
                self.answer(coupon(prize))
                self.spin()
                expect(self.page.locator('#parchmentReveal')).to_be_visible()
                expect(self.page.locator('.scroll-prize')).to_contain_text(label)
                self.assertRegex(self.calls[-1]['comprovante'],r'^[0-9a-f]{64}$')
                self.assertEqual({k:v for k,v in self.calls[-1].items() if k!='comprovante'}, dict(cpf=CPF,aceite=True,versao_aceite='roleta-2026-10',acao='girar'))
                expect(self.page.locator('#source')).to_have_text('pizzaria')
                expect(self.page.locator('#redeemPrize')).to_have_attribute('href',RESERVATIONS)
                expect(self.page.locator('#wheelStar')).to_have_attribute('aria-disabled','true')
                self.wait_done()
                self.spin()
                self.assertEqual(self.page.locator('#wheelStar').get_attribute('tabindex'),'-1')
        text=self.page.locator('.scroll-prize').inner_text()
        for price in ('680,00','880,00','1.000,00'):
            self.assertIn(price,text)
        self.assertEqual(len(self.calls),5)

    def test_recover_uses_consultar_without_new_spin(self):
        self.open();self.fill();self.answer(coupon('20'))
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual([c['acao'] for c in self.calls],['consultar'])
        self.assertIsNone(self.page.locator('.wheel').get_attribute('data-turns'))

    def test_master_shared_five_percent_contract_has_no_expiry(self):
        self.open();self.fill()
        self.answer(coupon(code='ESTRELA5',status='shared',percent_off=5,expires_at=None))
        self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        expect(self.page.locator('.coupon-display strong')).to_have_text('ESTRELA5')
        expect(self.page.locator('.coupon-display span')).to_contain_text('compartilhável de 5%')
        expect(self.page.locator('#redeemPrize')).to_have_attribute('href',RESERVATIONS)

    def test_admin_configured_shared_code_is_accepted_from_server(self):
        self.open();self.fill()
        self.answer(coupon(code='ESTRELA-NOVO5',status='shared',percent_off=5,expires_at=None),duplicate=True)
        self.spin()
        expect(self.page.locator('.coupon-display strong')).to_have_text('ESTRELA-NOVO5')

    def test_shared_exception_does_not_admit_other_prizes_or_missing_expiry(self):
        for c in (coupon('10',status='shared',percent_off=10,expires_at=None),
                  coupon('5',status='shared',percent_off=50,expires_at=None),
                  coupon('5',status='issued',expires_at=None)):
            self.open();self.fill();self.answer(c);self.spin()
            expect(self.page.locator('#roletaStatus')).not_to_contain_text('buscando')
            self.wait_done();self.assert_no_coupon()

    def test_recover_handles_legacy_nested_coupon_consistently(self):
        self.open();self.fill()
        self.responses.append({'json':dict(ok=True,award=dict(coupon=coupon('10')))})
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('.scroll-prize')).to_contain_text('10%')

    def test_recover_without_coupon_does_not_announce_a_prize(self):
        self.open();self.fill();self.answer()
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Nenhum prêmio registrado')
        self.assert_no_coupon()

    def test_duplicate_returns_same_coupon_without_animation_or_second_call(self):
        self.open();self.fill();self.answer(coupon('50'),duplicate=True)
        self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertIsNone(self.page.locator('.wheel').get_attribute('data-turns'))
        self.spin()
        self.page.locator('#wheelStar').dispatch_event('keydown',{'key':'Enter'})
        self.assertEqual(len(self.calls),1)

    def test_mutating_participant_invalidates_previous_coupon(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.page.locator('#roletaCpf').fill(OTHER_CPF)
        self.assert_no_coupon()
        self.page.locator('#roletaConsent').uncheck()
        expect(self.page.locator('#roletaRecover')).to_be_disabled()

    def test_receipt_survives_reload_without_storing_cpf(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        first=self.calls[-1]['comprovante']
        self.open();self.fill();self.answer(coupon(),duplicate=True)
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual(self.calls[-1]['comprovante'],first)
        self.assertNotEqual(first,CPF)
        self.assertNotIn(CPF,self.page.evaluate('JSON.stringify(localStorage)'))

    def test_storage_failure_sends_no_request_or_coupon(self):
        self.open();self.fill()
        self.page.evaluate("()=>{indexedDB.open=()=>{throw new Error('Storage disabled')}}")
        self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Nenhum pedido foi enviado')
        self.wait_done();self.assert_no_coupon()
        self.assertEqual(self.calls,[])

    def test_unknown_outcome_can_retry_only_after_explicit_server_refusal(self):
        self.open();self.fill()
        self.handler=lambda route:route.abort('failed');self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Conexão interrompida')
        self.wait_done();self.handler=None
        self.responses.append({'status':403,'json':dict(ok=False,code='RECOVERY_REQUIRED')})
        self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Nenhum novo prêmio')
        self.wait_done();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual([c['acao'] for c in self.calls],['girar','consultar','girar'])

    def test_two_tabs_share_one_transactional_receipt(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        first=self.calls[-1]['comprovante']
        second=self.context.new_page()
        second.route('**/*',self.route)
        second.goto(self.base,wait_until='domcontentloaded')
        expect(second.locator('#roletaCpf')).to_be_attached()
        second.evaluate("document.getElementById('entry').classList.add('hidden');document.getElementById('spin').classList.remove('hidden')")
        second.locator('#roletaCpf').fill(CPF);second.locator('#roletaConsent').check()
        self.answer(coupon(),duplicate=True);second.locator('#wheelStar').dispatch_event('click')
        expect(second.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual(self.calls[-1]['comprovante'],first)
        second.close()

    def test_withdrawing_consent_hides_coupon(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.page.locator('#roletaConsent').uncheck()
        self.assert_no_coupon()

    def test_busy_state_blocks_double_clicks_and_identity_changes(self):
        self.open();self.fill()
        held=[]
        self.handler=lambda route:held.append(route)
        self.spin()
        expect(self.page.locator('.wheel')).to_have_class('wheel roleta-waiting')
        expect(self.page.locator('#roletaCpf')).to_be_disabled()
        expect(self.page.locator('#roletaConsent')).to_be_disabled()
        expect(self.page.locator('#roletaRecover')).to_be_disabled()
        self.spin();self.spin()
        self.assertEqual(len(self.calls),1)
        held[0].fulfill(json=dict(ok=True,coupon=coupon(),duplicate=True))
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.wait_done()

    def test_network_failure_recovers_instead_of_issuing_again(self):
        self.open();self.fill()
        self.handler=lambda route:route.abort('failed')
        self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Conexão interrompida')
        self.wait_done()
        self.handler=None;self.answer(coupon())
        self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual([c['acao'] for c in self.calls],['girar','consultar'])

    def test_timeout_releases_controls_and_preserves_recovery(self):
        self.open();self.fill();self.page.clock.install()
        held=[]
        self.handler=lambda route:held.append(route)
        self.spin()
        expect(self.page.locator('.wheel')).to_have_class('wheel roleta-waiting')
        expect(self.page.locator('#roletaCpf')).to_be_disabled()
        self.page.clock.fast_forward(15001)
        expect(self.page.locator('#roletaStatus')).to_contain_text('Conexão interrompida')
        self.wait_done()
        self.assert_no_coupon()
        held[0].abort()

    def test_malformed_or_untrusted_response_never_enables_redemption(self):
        invalid=[None,{},coupon(prize='100'),coupon(prize=['5']),coupon(code='<script>'),coupon(code='TESTE-5-ABC'),
                 coupon(expires_at=None),coupon(expires_at='invalid'),coupon(status='revoked'),
                 coupon(status='redeemed'),coupon(redeemed_at=datetime.now(timezone.utc).isoformat()),
                 coupon(status='expired'),coupon(expires_at='2020-01-01T00:00:00Z')]
        for bad in invalid:
            with self.subTest(response=bad):
                self.open();self.fill();self.answer(bad);self.spin()
                expect(self.page.locator('#roletaStatus')).not_to_contain_text('buscando')
                self.wait_done();self.assert_no_coupon()
        for response in ({'ok':'true','coupon':coupon()}, {'ok':False,'coupon':coupon()}):
            self.open();self.fill();self.responses.append({'json':response});self.spin()
            expect(self.page.locator('#roletaStatus')).to_contain_text('Não foi possível confirmar')
            self.assert_no_coupon()

    def test_api_failure_codes_are_displayed_without_a_coupon(self):
        for code, message, http in [('FORBIDDEN_ORIGIN','endereço oficial',403),
                ('RATE_LIMITED','Muitas tentativas',429),('DISTRIBUTION_DISABLED','não foi liberada',503),
                ('NOT_CONFIGURED','configuração',503),('SOLD_OUT','esgotaram',409),
                ('CPF_INVALID','Confira seu CPF',400)]:
            with self.subTest(code=code):
                self.open();self.fill()
                self.responses.append({'status':http,'json':dict(ok=False,code=code)})
                self.spin()
                expect(self.page.locator('#roletaStatus')).to_contain_text(message)
                self.wait_done();self.assert_no_coupon()

    def test_html_response_is_handled_and_controls_recover(self):
        self.open();self.fill()
        self.responses.append({'status':502,'content_type':'text/html','body':'<h1>Proxy unavailable</h1>'})
        self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('Conexão interrompida')
        self.wait_done();self.assert_no_coupon()

    def test_explicit_refusal_can_be_retried_after_service_is_available(self):
        self.open();self.fill()
        self.responses.append({'status':503,'json':dict(ok=False,code='DISTRIBUTION_DISABLED')})
        self.spin()
        expect(self.page.locator('#roletaStatus')).to_contain_text('não foi liberada')
        self.wait_done();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.assertEqual([c['acao'] for c in self.calls],['girar','girar'])

    def test_failed_recovery_cannot_leave_previous_coupon_redeemable(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.wait_done()
        self.responses.append({'status':409,'json':dict(ok=False,code='COUPON_REDEEMED')})
        self.page.locator('#roletaRecover').click()
        expect(self.page.locator('#roletaStatus')).to_contain_text('já foi utilizado')
        self.assert_no_coupon()

    def test_coupon_expires_while_page_stays_open(self):
        self.open();self.fill();self.page.clock.install()
        self.answer(coupon(expires_at=(datetime.now(timezone.utc)+timedelta(seconds=10)).isoformat()),duplicate=True)
        self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.page.clock.fast_forward(12000)
        expect(self.page.locator('#roletaStatus')).to_have_text('Este cupom expirou.')
        self.assertIsNone(self.page.locator('#redeemPrize').get_attribute('href'))
        expect(self.page.locator('.roleta-copy')).to_be_disabled()

    def test_clipboard_unavailable_has_fallback_without_js_error(self):
        self.open();self.fill();self.answer(coupon(),duplicate=True);self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        self.page.evaluate("Object.defineProperty(navigator,'clipboard',{value:undefined})")
        self.page.locator('.roleta-copy').click()
        expect(self.page.locator('.roleta-copy')).to_have_text('Selecione e copie o código acima')

    def test_demo_mode_never_calls_api_from_any_handler(self):
        self.open('?teste=1')
        self.page.evaluate("""document.getElementById('roletaCpf').value='12345678909';
            document.getElementById('roletaConsent').checked=true;""")
        self.spin()
        self.page.locator('#wheelStar').dispatch_event('keydown',{'key':'Enter'})
        self.page.locator('#roletaRecover').dispatch_event('click')
        self.page.locator('#roletaGoUp').dispatch_event('click')
        self.page.locator('.roleta-form').dispatch_event('submit')
        self.page.get_by_role('button',name='✦ TESTAR GIRO E CUPOM ✦').click()
        expect(self.page.locator('.scroll-demo')).to_contain_text('cupom fictício')
        expect(self.page.locator('.coupon-display strong')).to_contain_text('TESTE-5-')
        self.assertIsNone(self.page.locator('#redeemPrize').get_attribute('href'))
        self.assertEqual(self.calls,[])
        expect(self.page.locator('#roletaStatus')).not_to_contain_text('confirmado e registrado')

    def test_old_localstorage_demo_cannot_override_a_real_result(self):
        self.context.add_init_script("localStorage.setItem('belem_roleta_demo_spin_v1',JSON.stringify({prize:'50%'}))")
        self.open();self.assert_no_coupon()
        self.fill();self.answer(coupon('5'),duplicate=True);self.spin()
        expect(self.page.locator('.scroll-prize')).to_have_text('5% de desconto')

    def test_video_to_raffle_to_coupon_user_journey(self):
        self.allow_media=True
        self.open('?origem=pizzaria',spin=False)
        self.page.locator('#enter').click()
        expect(self.page.locator('#experience')).to_be_visible()
        expect(self.page.locator('#wheelBtn')).to_be_disabled()
        self.page.wait_for_function("document.getElementById('film').readyState>=2")
        self.page.locator('#film').evaluate('(v)=>{v.muted=true;v.playbackRate=16;v.play().catch(()=>{})}')
        expect(self.page.locator('#wheelBtn')).to_be_enabled(timeout=15000)
        self.page.locator('#wheelBtn').click(force=True)
        expect(self.page.locator('#spin')).to_be_visible()
        self.fill();self.answer(coupon('10'));self.spin()
        expect(self.page.locator('#parchmentReveal')).to_be_visible()
        expect(self.page.locator('#redeemPrize')).to_have_attribute('href',RESERVATIONS)
        self.assertEqual(len(self.calls),1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
