/* Sorteio real: resultado somente após confirmação persistida pelo servidor. */
(function(){
const API='https://m-master-view.lovable.app/api/public/roleta-sorteio';
const CONSENT='roleta-2026-10';
const TEST_MODE=new URLSearchParams(location.search).get('teste')==='1';
const RESERVATIONS_URL='https://natal.estudioliliancristina.com.br/';
const PRIZES=['50','20','5','5','10','ensaio'];
const REQUEST_TIMEOUT_MS=15000;
const spinSection=document.getElementById('spin');
const wheelStar=document.getElementById('wheelStar');
const parchment=document.getElementById('parchmentReveal');
const demoButton=document.getElementById('previewSpin');
if(!spinSection||!wheelStar||!parchment)return;
if(demoButton)demoButton.onclick=()=>{};
const style=document.createElement('style');
style.textContent='.roleta-form{max-width:360px;margin:18px auto;padding:18px;border:1px solid #c89b63;border-radius:12px;background:#260709;color:#ffe8bc;text-align:left;font:14px/1.5 system-ui,sans-serif}.roleta-form label{display:block;margin-bottom:10px}.roleta-form input[type=text]{width:100%;padding:12px;border-radius:6px;border:1px solid #c89b63;font-size:17px;margin-top:5px}.roleta-form button{width:100%;padding:12px;border:0;border-radius:8px;background:#e8bd75;color:#35180d;font-weight:700;cursor:pointer}.roleta-form button:disabled{opacity:.6}.roleta-status{min-height:26px;margin:12px 0;color:#ffe2ac}.roleta-copy{margin-top:10px;padding:10px 15px;background:#f7dfb3;color:#36180d;border:1px solid #8d5c2a;border-radius:6px;cursor:pointer}.roleta-form .consent{font-size:12px}.roleta-form .consent input{margin-right:8px}';
document.head.appendChild(style);
const form=document.createElement('form');
form.className='roleta-form';
form.innerHTML='<label>Seu CPF para participar<input id="roletaCpf" type="text" inputmode="numeric" autocomplete="off" maxlength="14" placeholder="000.000.000-00" required></label><label class="consent"><input id="roletaConsent" type="checkbox" required>Li e aceito o uso do meu CPF exclusivamente para controlar uma participação por pessoa, registrar e recuperar meu prêmio. O CPF é transformado em código criptográfico no servidor.</label><p id="roletaStatus" class="roleta-status" role="status" aria-live="polite"></p>';
spinSection.insertBefore(form,parchment);
const status=form.querySelector('#roletaStatus');
const cpfInput=form.querySelector('#roletaCpf');
const consent=form.querySelector('#roletaConsent');
let busy=false;
let ready=false;
let awarded=false;
let participant='';
// Uncertain issuance must be recovered, never automatically retried as a new spin.
const pendingParticipants=new Set();
let activeCoupon=null;
let expiryTimer=null;
const redeem=parchment.querySelector('#redeemPrize');
function disableRedemption(){
  redeem.removeAttribute('href');
  redeem.setAttribute('aria-disabled','true');
}
function clearCoupon(){
  clearInterval(expiryTimer);
  expiryTimer=null;
  activeCoupon=null;
  awarded=false;
  disableRedemption();
  parchment.classList.add('hidden');
  parchment.querySelector('.coupon-display strong').textContent='';
}
clearCoupon();
const instruction=spinSection.querySelector('.wheel-instruction');

if(instruction)instruction.innerHTML='☝️ TOQUE NA ESTRELA PARA GIRAR A ROLETA ✦';
const helper=document.createElement('p');helper.className='note';helper.textContent='Informe seu CPF e aceite a participação para continuar.';form.prepend(helper);
const goButton=document.createElement('button');goButton.type='button';goButton.id='roletaGoUp';goButton.textContent='✦ VIRAR A ROLETA ✦';goButton.style.cssText='display:block;width:100%;margin:15px 0 8px;padding:17px 12px;border-radius:999px;border:2px solid #ffe5a1;background:linear-gradient(110deg,#9d631b,#ffe7a0,#fff9d6,#d99b2f,#fff0ad,#9f621b);background-size:260% 100%;color:#3a1707;font:900 14px system-ui,sans-serif;letter-spacing:.06em;box-shadow:0 0 15px #ffe7a388,0 0 32px #f9c65c88;cursor:pointer;animation:goldSweep 3s linear infinite';form.append(goButton);
const recover=document.createElement('button');
recover.type='button';recover.id='roletaRecover';recover.textContent='Recuperar meu prêmio';
recover.style.cssText='margin-top:9px;background:transparent;color:#f7dfb3;border:1px solid #c89b63';
form.append(recover);
const recoverHint=document.createElement('p');recoverHint.className='note';recoverHint.textContent='Se já participou, informe o mesmo CPF e use Recuperar meu prêmio.';form.append(recoverHint);
form.style.maxWidth='340px';
const cpfDigits=value=>value.replace(/\D/g,'');
const cpfValido=value=>{const d=cpfDigits(value);if(d.length!==11||/^(\d)\1{10}$/.test(d))return false;const digito=tamanho=>{let soma=0;for(let i=0;i<tamanho;i++)soma+=Number(d[i])*(tamanho+1-i);const resto=(soma*10)%11;return resto===10?0:resto;};return digito(9)===Number(d[9])&&digito(10)===Number(d[10]);};
function updateControls(){
  ready=cpfValido(cpfInput.value)&&consent.checked;
  cpfInput.disabled=busy||TEST_MODE;
  consent.disabled=busy||TEST_MODE;
  const canSpin=ready&&!busy&&!awarded&&!TEST_MODE;
  goButton.disabled=!canSpin;
  recover.disabled=!ready||busy||TEST_MODE;
  wheelStar.setAttribute('aria-disabled',String(!canSpin));
  wheelStar.tabIndex=canSpin?0:-1;
  wheelStar.style.cursor=canSpin?'pointer':'not-allowed';
  wheelStar.setAttribute('aria-label',awarded?'Prêmio já registrado':canSpin?'Toque na estrela para girar a roleta':'Preencha seu CPF para participar da roleta');
}
function updateReady(){
  const digits=cpfDigits(cpfInput.value);
  if(participant!==digits){clearCoupon();participant=digits;}
  const valid=cpfValido(cpfInput.value);
  cpfInput.setCustomValidity(!digits?'Informe seu CPF.':valid?'':'CPF inválido. Confira os números.');
  updateControls();
  if(TEST_MODE){status.textContent='Modo teste: somente demonstração, sem sorteio real.';return;}
  if(busy||awarded)return;
  if(pendingParticipants.has(digits))status.textContent='Confirmação pendente. Use Recuperar meu prêmio antes de tentar novamente.';
  else if(ready)status.textContent='Pronto! Toque na estrela acima. ✨';
  else if(digits.length>0&&digits.length<11)status.textContent='Digite os 11 números do CPF.';
  else if(digits.length>=11&&!valid)status.textContent='CPF inválido. Confira os números digitados.';
  else if(valid&&!consent.checked)status.textContent='Marque o aceite para continuar.';
  else status.textContent='Informe seu CPF e aceite a participação para continuar.';
}
cpfInput.addEventListener('input',updateReady);
consent.addEventListener('change',()=>{if(!consent.checked)clearCoupon();updateReady();});
goButton.onclick=()=>{
  updateReady();
  if(!ready||busy||awarded||TEST_MODE||!form.reportValidity())return;
  cpfInput.blur();
  status.textContent=pendingParticipants.has(participant)?'Toque em Recuperar meu prêmio.':'Agora toque na estrela para girar! ✨';
  (document.querySelector('.wheel-frame')||wheelStar).scrollIntoView({behavior:'smooth',block:'center'});
  wheelStar.classList.add('roleta-ready');
};
const hand=document.createElement('div');hand.textContent='👇';hand.setAttribute('aria-hidden','true');hand.style.cssText='position:absolute;left:50%;top:-64px;transform:translateX(-50%);font-size:42px;filter:drop-shadow(0 0 10px #ffe9ac);animation:roletaPoint 1s ease-in-out infinite;pointer-events:none;z-index:15';wheelStar.style.position='relative';wheelStar.appendChild(hand);
const pointStyle=document.createElement('style');pointStyle.textContent='@keyframes roletaPoint{0%,100%{transform:translate(-50%,0)}50%{transform:translate(-50%,12px)}}@keyframes roletaWaiting{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}.wheel.roleta-waiting{animation:roletaWaiting 1.4s linear infinite!important;transition:none!important}';document.head.appendChild(pointStyle);
// Efeitos sonoros da experiência (Web Audio; sem arquivos externos).
const roletaSfx=(()=>{
 let ctx,spinTimer=null,spinning=false;
 const enabled=()=>{const m=document.getElementById('music');return !m?.muted && document.getElementById('soundToggle')?.getAttribute('aria-pressed')!=='false'};
 function context(){if(!enabled())return null;try{ctx=ctx||new (window.AudioContext||window.webkitAudioContext)();if(ctx.state==='suspended')ctx.resume().catch(()=>{});return ctx}catch(e){return null}}
 function tone(freq,duration=.07,vol=.055,type='triangle',delay=0){const c=context();if(!c)return;const t=c.currentTime+delay,o=c.createOscillator(),g=c.createGain();o.type=type;o.frequency.setValueAtTime(freq,t);g.gain.setValueAtTime(.001,t);g.gain.exponentialRampToValueAtTime(Math.max(.002,vol),t+.012);g.gain.exponentialRampToValueAtTime(.001,t+duration);o.connect(g);g.connect(c.destination);o.start(t);o.stop(t+duration+.02)}
 function noise(duration=.11,vol=.05,delay=0,highpass=450){const c=context();if(!c)return;const t=c.currentTime+delay,b=c.createBuffer(1,Math.ceil(c.sampleRate*duration),c.sampleRate),d=b.getChannelData(0);for(let i=0;i<d.length;i++)d[i]=(Math.random()*2-1);const src=c.createBufferSource(),f=c.createBiquadFilter(),g=c.createGain();src.buffer=b;f.type='highpass';f.frequency.value=highpass;g.gain.setValueAtTime(.001,t);g.gain.linearRampToValueAtTime(vol,t+.012);g.gain.exponentialRampToValueAtTime(.001,t+duration);src.connect(f);f.connect(g);g.connect(c.destination);src.start(t);src.stop(t+duration)}
 function startSpin(){stopSpin();context();spinning=true;let i=0;const pulse=()=>{if(!spinning)return;tone(370+(i%6)*38,.045,.043,'square');i++;spinTimer=setTimeout(pulse,Math.max(65,145-Math.min(i,35)*2))};pulse()}
 function stopSpin(){spinning=false;if(spinTimer){clearTimeout(spinTimer);spinTimer=null}}
 function parchment(){noise(.48,.095,0,220);noise(.38,.06,.19,320);tone(590,.26,.035,'sine',.24)}
 function celebrate(){// Palmas em camadas, gritos festivos sintetizados e sinos.
 for(let i=0;i<23;i++){const t=i*.105+Math.random()*.035;noise(.07,.07+Math.random()*.045,t,900);if(i%3===0)noise(.085,.05,t+.024,1200)}
 [523,659,784,1047,1318].forEach((f,i)=>tone(f,.32,.065,'sine',i*.115));
 // Coro festivo "êêê!" estilizado, sem voz gravada.
 for(let j=0;j<3;j++){tone(390+j*28,.55,.027,'sawtooth',.18+j*.11);tone(590+j*33,.48,.02,'sine',.25+j*.11)}
 }
 return {startSpin,stopSpin,parchment,celebrate,unlock:context};
})();
function couponFrom(result){return result?.coupon??result?.award?.coupon??null;}
function couponError(c){
  if(!c||typeof c!=='object'||Array.isArray(c)||
     !['string','number'].includes(typeof c.prize_id)||!PRIZES.includes(String(c.prize_id))||
     typeof c.code!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(c.code)||
     c.code.toUpperCase().startsWith('TESTE-'))return 'Resposta de cupom inválida. Use Recuperar meu prêmio.';
  if(c.status==='redeemed'||c.redeemed_at)return 'Este cupom já foi utilizado.';
  if(c.status==='expired')return 'Este cupom expirou.';
  // The Master contract deliberately issues a reusable 5% code with no expiry.
  // Only this explicit shared-prize shape is exempt from individual validity.
  if(String(c.prize_id)==='5'&&c.status==='shared'&&c.percent_off===5&&c.expires_at===null)return '';
  if(c.status==='applied')return 'Este cupom já está vinculado a uma reserva. Retome sua reserva para continuar.';
  if(c.status!==undefined&&c.status!=='issued')return 'Este cupom não está disponível para uso.';
  const expiry=typeof c.expires_at==='string'?Date.parse(c.expires_at):NaN;
  if(!Number.isFinite(expiry))return 'O servidor não confirmou a validade do cupom. Use Recuperar meu prêmio.';
  if(expiry<=Date.now())return 'Este cupom expirou.';
  return '';
}
function checkExpiration(){
  if(activeCoupon&&Date.parse(activeCoupon.expires_at)<=Date.now()){
    disableRedemption();
    const copy=parchment.querySelector('.roleta-copy');if(copy)copy.disabled=true;
    status.textContent='Este cupom expirou.';
    clearInterval(expiryTimer);
  }
}
redeem.addEventListener('click',event=>{
  checkExpiration();
  if(TEST_MODE||!activeCoupon||couponError(activeCoupon)){event.preventDefault();disableRedemption();}
});
function displayCoupon(c,{demo=false}={}){
if(!demo){
  const error=couponError(c);
  if(error){clearCoupon();status.textContent=error;return false;}
}
const prize=String(c.prize_id);
const labels={ensaio:'Ensaio Belém: crédito do Pacote 1 no lote da reserva', '50':'50% de desconto', '20':'20% de desconto', '10':'10% de desconto', '5':'5% de desconto'};
const label=labels[prize];
const creditInfo=prize==='ensaio'
  ? 'VOCÊ GANHOU UM ENSAIO BELÉM! Seu prêmio cobre o valor integral do Pacote 1 (10 fotos digitais). Se preferir qualquer outro pacote, você recebe um crédito equivalente ao valor do Pacote 1 do lote vigente na data da reserva: Lote 1: R$ 680,00; Lote 2: R$ 880,00; Lote 3: R$ 1.000,00. Esse valor é abatido do pacote escolhido e você paga somente a diferença, além de eventuais extras. O crédito não é cumulativo com outros descontos.'
  : label;
parchment.querySelector('h3').textContent='Seu presente de Belém!';
parchment.querySelector('.scroll-prize').textContent=creditInfo;
parchment.querySelector('.coupon-display').style.display='flex';
parchment.querySelector('.coupon-display strong').textContent=c.code;
parchment.querySelector('.coupon-display span').textContent=c.expires_at?'Válido até '+new Date(c.expires_at).toLocaleString('pt-BR'):demo?'Demonstração, sem validade no checkout.':'Código compartilhável de 5%. Sem prazo de expiração definido. Não cumulativo.';
parchment.querySelector('.scroll-instructions').textContent=prize==='ensaio'?'Copie seu código e escolha o pacote desejado no Belém Experience. O valor do Pacote 1 do lote da reserva será abatido automaticamente.':'Copie seu código e aplique na reserva do Belém Experience. Descontos não cumulativos.';
parchment.querySelector('.scroll-demo').textContent='';
if(redeem){redeem.textContent='✦ RESGATAR MEU PRÊMIO ✦';redeem.classList.add('gold-invite');redeem.style.cssText='display:inline-block;margin-top:20px;padding:18px 24px;border-radius:999px;background:linear-gradient(110deg,#a56a1c,#fff2b5,#d59c2b,#fff0a7,#9c601b);background-size:240% 100%;color:#3b1b0b;font-weight:900;text-decoration:none;box-shadow:0 0 28px #ffd36d,0 0 60px #e8a83b88;animation:goldPulse 1.8s ease-in-out infinite,goldSweep 3s linear infinite';}
let copy=parchment.querySelector('.roleta-copy');
if(!copy){copy=document.createElement('button');copy.type='button';copy.className='roleta-copy';parchment.querySelector('.coupon-display').after(copy);}
copy.disabled=false;
copy.textContent='Copiar cupom';
copy.onclick=async()=>{
  if(!demo&&couponError(c)){checkExpiration();return;}
  try{await navigator.clipboard.writeText(c.code);copy.textContent='Código copiado!';}
  catch{copy.textContent='Selecione e copie o código acima';}
};
parchment.classList.remove('hidden');
roletaSfx.parchment();setTimeout(()=>roletaSfx.celebrate(),450);
clearInterval(expiryTimer);
if(demo){
  activeCoupon=null;
  disableRedemption();
  awarded=false;
  status.textContent='Demonstração concluída. Nenhum prêmio real foi emitido.';
}else{
  activeCoupon=c;
  awarded=true;
  redeem.href=RESERVATIONS_URL;
  redeem.removeAttribute('aria-disabled');
  if(c.expires_at!==null)expiryTimer=setInterval(checkExpiration,1000);
  status.textContent='Prêmio confirmado e registrado!';
}
updateControls();
parchment.scrollIntoView({behavior:'smooth',block:'start'});
return true;
}
async function requestPrize(action){
  // Demo mode must never reach the real backend, including keyboard/form handlers.
  if(TEST_MODE||busy)return;
  updateReady();
  if(!ready||!form.reportValidity()){
    status.textContent='Preencha o CPF e aceite a participação antes de continuar.';
    form.scrollIntoView({behavior:'smooth',block:'center'});return;
  }
  if(action==='girar'&&awarded)return;
  const cpf=cpfDigits(cpfInput.value);
  if(action==='girar'&&pendingParticipants.has(cpf))action='consultar';
  busy=true;clearCoupon();updateControls();
  const wheel=document.querySelector('.wheel');
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),REQUEST_TIMEOUT_MS);
  if(action==='girar'){
    pendingParticipants.add(cpf);
    roletaSfx.startSpin();wheel.classList.add('roleta-waiting');
    status.textContent='A estrela está buscando seu prêmio... ✨';
  }else status.textContent='Consultando seu prêmio...';
  try{
    const res=await fetch(API,{
      method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({cpf,aceite:true,versao_aceite:CONSENT,acao:action}),
      cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer',signal:controller.signal
    });
    const data=await res.json();
    clearTimeout(timeout);
    if(!res.ok||data?.ok!==true){
      const msgs={
        DISTRIBUTION_DISABLED:'A distribuição de prêmios ainda não foi liberada.',
        NOT_CONFIGURED:'A roleta ainda está em configuração.',
        CPF_INVALID:'Confira seu CPF e tente novamente.',
        RATE_LIMITED:'Muitas tentativas. Aguarde um pouco.',
        SOLD_OUT:'Os prêmios desta campanha se esgotaram.',
        FORBIDDEN_ORIGIN:'Abra a roleta pelo endereço oficial.',
        COUPON_EXPIRED:'Este cupom expirou.',
        COUPON_REDEEMED:'Este cupom já foi utilizado.'
      };
      // An explicit refusal before issuance can be retried by the user. Unknown
      // failures remain pending because the server may already have committed.
      if(data?.ok===false&&['DISTRIBUTION_DISABLED','NOT_CONFIGURED','CPF_INVALID',
        'RATE_LIMITED','SOLD_OUT','FORBIDDEN_ORIGIN'].includes(data.code))pendingParticipants.delete(cpf);
      status.textContent=msgs[data?.code]||'Não foi possível confirmar o prêmio. Use Recuperar meu prêmio.';
      return;
    }
    const coupon=couponFrom(data);
    if(action==='consultar'&&coupon===null){
      status.textContent=pendingParticipants.has(cpf)
        ?'Nenhum prêmio confirmado ainda. Aguarde e use Recuperar meu prêmio novamente.'
        :'Nenhum prêmio registrado para este CPF.';
      return;
    }
    const error=couponError(coupon);
    if(error){status.textContent=error;return;}
    if(action==='girar'&&data.duplicate!==true){
      wheel.classList.remove('roleta-waiting');
      wheel.style.transition='none';wheel.style.transform='rotate(0deg)';void wheel.offsetWidth;
      wheel.style.transition='transform 6s cubic-bezier(.08,.7,.08,1)';
      const target=330-PRIZES.indexOf(String(coupon.prize_id))*60;
      const next=1800+((target%360)+360)%360;
      wheel.dataset.turns=String(next);wheel.style.transform='rotate('+next+'deg)';
      await new Promise(resolve=>setTimeout(resolve,6000));
    }
    if(displayCoupon(coupon))pendingParticipants.delete(cpf);
  }catch{
    status.textContent='Conexão interrompida ou resposta inválida. Use Recuperar meu prêmio para consultar o resultado registrado.';
  }finally{
    clearTimeout(timeout);roletaSfx.stopSpin();wheel.classList.remove('roleta-waiting');
    busy=false;updateControls();
  }
}
if(TEST_MODE){
  const testBtn=document.createElement('button');
  testBtn.type='button';
  testBtn.textContent='✦ TESTAR GIRO E CUPOM ✦';
  testBtn.style.cssText='display:block;width:100%;padding:16px;margin-top:12px;border-radius:999px;border:2px solid #ffe9ad;background:linear-gradient(110deg,#9d631b,#fff3c4,#d99b2f,#ffe8a0);color:#3a1707;font-weight:900;box-shadow:0 0 22px #ffd36d;cursor:pointer';
  form.append(testBtn);
  const notice=document.createElement('p');
  notice.className='note';
  notice.textContent='MODO TESTE: códigos demonstrativos não são válidos no checkout. Nenhum prêmio real é emitido.';
  form.append(notice);
  let testRunning=false;
  testBtn.onclick=async()=>{
    if(testRunning||busy)return;
    testRunning=true;testBtn.disabled=true;
    parchment.classList.add('hidden');
    const prizes=['50','20','5','5','10','ensaio'];
    const chosen='5';
    const wheel=document.querySelector('.wheel');
    roletaSfx.startSpin();wheel.classList.add('roleta-waiting');
    wheel.scrollIntoView({behavior:'smooth',block:'center'});
    await new Promise(resolve=>setTimeout(resolve,1200));
    wheel.classList.remove('roleta-waiting');
    wheel.style.transition='none';wheel.style.transform='rotate(0deg)';void wheel.offsetWidth;
    wheel.style.transition='transform 6s cubic-bezier(.08,.7,.08,1)';
    const index=prizes.indexOf(chosen);
    wheel.style.transform='rotate('+(1800+(330-index*60))+'deg)';
    await new Promise(resolve=>setTimeout(resolve,6000));
    const demoCode='TESTE-'+chosen.toUpperCase()+'-'+Math.random().toString(36).slice(2,8).toUpperCase();
    roletaSfx.stopSpin();displayCoupon({code:demoCode,prize_id:chosen,expires_at:null},{demo:true});
    const demo=parchment.querySelector('.scroll-demo');
    demo.textContent='⚠️ TESTE: cupom fictício. Não gera desconto nem reserva.';
    demo.style.cssText='display:block!important;color:#8b2118;font-weight:900;font-size:15px';
    const redeem=parchment.querySelector('#redeemPrize');
    if(redeem){redeem.removeAttribute('href');redeem.setAttribute('aria-disabled','true');redeem.textContent='✦ RESGATAR MEU PRÊMIO (TESTE) ✦';redeem.onclick=e=>{e.preventDefault();alert('Este é um cupom de teste, sem validade. O resgate real será liberado após homologação.');};}
    awarded=false;testRunning=false;testBtn.disabled=false;
  };
}
recover.onclick=()=>requestPrize('consultar');
form.onsubmit=e=>{e.preventDefault();updateReady();if(ready&&!busy&&!awarded&&!TEST_MODE){cpfInput.blur();status.textContent='Agora toque na estrela para descobrir seu prêmio. ✨';wheelStar.scrollIntoView({behavior:'smooth',block:'center'});}};
wheelStar.onclick=()=>{if(!busy&&!awarded){document.activeElement?.blur?.();requestPrize('girar');}};
wheelStar.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(!busy&&!awarded)requestPrize('girar');}};
clearCoupon();
updateReady();
})();
