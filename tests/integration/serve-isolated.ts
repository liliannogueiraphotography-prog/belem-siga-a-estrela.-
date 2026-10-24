/** TEST TRANSPORT ONLY. Never deploy. Original Master route and SQL remain authoritative.
 * Run with Bun from the Master checkout, passing its absolute path as argv[2].
 * Requires the disposable fixture schema and an explicit isolation marker.
 */
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
const master = resolve(process.argv[2] ?? '../bel-m-masterpiece');
const { default: postgres } = await import(pathToFileURL(join(master,'node_modules/postgres/src/index.js')).href);
const db = postgres({host:'127.0.0.1',port:55432,user:'fixture_admin',database:'postgres',ssl:false,max:8});
const [marker] = await db`select current_user as username,value from public.isolated_test_marker`;
if(marker?.username!=='fixture_admin'||marker.value!==true)throw new Error('Disposable fixture database required');
const nativeFetch = globalThis.fetch;
globalThis.fetch = ((input, init) => {
  const url = new URL(typeof input==='string'?input:input instanceof URL?input.href:input.url);
  if(url.origin!=='http://127.0.0.1:55433')throw new Error('External requests forbidden in isolated transport');
  return nativeFetch(input,init);
}) as typeof fetch;
process.env.SUPABASE_URL='http://127.0.0.1:55433';
process.env.SUPABASE_SERVICE_ROLE_KEY='fixture-service-role-only';
process.env.ROLETA_CPF_PEPPER='isolated-fixture-only-not-a-production-secret-000000000000';
const { Route } = await import(pathToFileURL(join(master,'src/routes/api/public/roleta-sorteio.ts')).href);
const route = Route.options.server.handlers;
async function rpc(name:string,args:Record<string,unknown>){
  if(!/^belem_(public|roleta)_\w+$/.test(name))throw new Error('Unexpected fixture RPC');
  const keys=Object.keys(args);
  if(keys.some(k=>!/^p_\w+$/.test(k)))throw new Error('Unexpected arguments');
  const [row]=await db.unsafe(`select public.${name}(${keys.map((k,i)=>`${k} => $${i+1}`).join(',')}) as result`,keys.map(k=>args[k]));
  return row.result;
}
Bun.serve({hostname:'127.0.0.1',port:55433,async fetch(request:Request){
 const url=new URL(request.url);
 try{
  if(url.pathname==='/health')return Response.json({isolated:true});
  if(url.pathname==='/api/public/roleta-sorteio'){
   if(request.method==='OPTIONS')return route.OPTIONS({request});
   if(request.method==='POST')return route.POST({request});
   return new Response(null,{status:405});
  }
  if(url.pathname==='/fixture/reset'&&request.method==='POST'){
   const {prize}=await request.json();
   if(!['5','10','20','50','ensaio'].includes(prize))return new Response(null,{status:400});
   await db`truncate belem_roleta_shared_uses,belem_roleta_shared_awards,belem_roleta_coupons,belem_roleta_draw_attempts,belem_roleta_participants,belem_payment_attempts,belem_payments,belem_credit_applications,belem_coupon_redemptions,belem_reservations,belem_slots,belem_customers cascade`;
   // Deterministic prizes only in this marked, disposable database.
   await db`update belem_roleta_prizes set active=true,weight=case when prize_id=${prize} then 1 else 0 end`;
   await db`update belem_roleta_config set distribution_enabled=true`;
   return Response.json({ok:true});
  }
  if(url.pathname==='/fixture/reservation'&&request.method==='POST'){
   const {extras=0}=await request.json();
   const [c]=await db`insert into belem_customers(full_name,whatsapp,source) values('ISOLATED BROWSER FIXTURE','5565999990000','isolated_roleta_e2e') returning id`;
   const [s]=await db`insert into belem_slots(starts_at,ends_at) values('2026-12-02 12:00Z','2026-12-02 13:00Z') returning id`;
   const [r]=await db`insert into belem_reservations(customer_id,slot_id,status,hold_expires_at,terms_accepted,terms_accepted_at,base_price_cents,total_base_price_cents,total_card_price_cents,tier_index,package_code,additional_guests_amount_cents,public_token) values(${c.id},${s.id},'awaiting_payment',now()+interval '2 hours',true,now(),68000,${68000+extras},${68000+extras},1,'pacote-1',${extras},gen_random_uuid()::text) returning id,public_token`;
   return Response.json(r);
  }
  if(url.pathname==='/fixture/snapshot'){
   const reservations=await db`select id,status,discount_applied_cents,total_base_price_cents from belem_reservations order by created_at`;
   const coupons=await db`select code,prize_id,status,reservation_id from belem_roleta_coupons`;
   const shared=await db`select code,status,reservation_id from belem_roleta_shared_uses`;
   const payments=await db`select provider,method,amount_cents,status from belem_payments`;
   const attempts=await db`select count(*)::int as count from belem_payment_attempts`;
   const participants=await db`select identity_kind,consent_version,length(token_hash)=64 as hashed from belem_roleta_participants`;
   return Response.json({reservations,coupons,shared,payments,attempts:attempts[0].count,participants});
  }
  if(url.pathname.startsWith('/rest/v1/rpc/')&&request.method==='POST'){
   const name=url.pathname.split('/').pop()!;
   // Unrelated display configuration fixtures; coupon logic is never replaced.
   if(name==='belem_public_bank_pix_config')return Response.json({active:true,pix_key:'fixture-only'});
   if(name==='belem_public_boleto_status')return Response.json({is_boleto_2x:false});
   if(name==='belem_public_payment_notice')return Response.json({ok:true,confirmed:false});
   if(name.includes('contract')||name.includes('terms_snapshot'))return Response.json({terms_accepted_at:new Date().toISOString()});
   return Response.json(await rpc(name,await request.json()));
  }
  return new Response(null,{status:404});
 }catch(error){return Response.json({message:error instanceof Error?error.message:'Isolated request failed'},{status:400});}
}});
console.log('Isolated original-route/RPC transport ready on loopback 55433');
