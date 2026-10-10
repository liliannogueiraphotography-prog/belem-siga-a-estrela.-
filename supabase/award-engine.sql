-- Executar somente após configurar integração do checkout e aprovação para ativar a campanha.
-- Esta função é acessível SOMENTE ao backend com service_role.
-- O cliente público não recebe permissão para chamá-la diretamente.
create table if not exists public.campaign_control (
  id boolean primary key default true check (id),
  enabled boolean not null default false,
  spins_total bigint not null default 0,
  created_at timestamptz not null default now()
);
insert into public.campaign_control(id,enabled) values(true,false) on conflict do nothing;
alter table public.campaign_control enable row level security;

create or replace function public.issue_campaign_award(
  p_session uuid, p_source text
) returns table(prize text, coupon text, valid_until timestamptz)
language plpgsql security definer
set search_path = public, pg_temp
as $$
declare
  v_enabled boolean;
  v_spin bigint;
  v_prize text := '5';
  v_coupon text;
  v_expiry timestamptz;
  v_existing public.campaign_awards%rowtype;
  v_roll float8;
  v_claimed int;
  v_total int;
  v_threshold bigint;
begin
  if p_session is null then raise exception 'Sessão obrigatória'; end if;
  select * into v_existing from public.campaign_awards where session_id=p_session;
  if found then
    return query select v_existing.prize_id,v_existing.coupon_code,v_existing.expires_at;
    return;
  end if;
  select enabled,spins_total into v_enabled,v_spin from public.campaign_control where id=true for update;
  if not found or not v_enabled then raise exception 'Campanha ainda não ativada'; end if;
  v_spin:=v_spin+1;
  -- Distribuição progressiva conservadora; limites continuam sendo rígidos.
  -- Nunca libera o prêmio principal antes de 50 giros, nem 50% antes de 20.
  v_roll:=random();
  if v_spin>=50 and v_roll<0.001 then v_prize:='ensaio';
  elsif v_spin>=20 and v_roll<0.004 then v_prize:='50';
  elsif v_spin>=10 and v_roll<0.02 then v_prize:='20';
  elsif v_spin>=5 and v_roll<0.12 then v_prize:='10';
  end if;
  select claimed,total into v_claimed,v_total from public.campaign_prizes where id=v_prize for update;
  if v_total is not null and v_claimed>=v_total then v_prize:='5'; end if;
  update public.campaign_prizes set claimed=claimed+1 where id=v_prize;
  update public.campaign_control set spins_total=v_spin where id=true;
  v_coupon:='BELEM-'||upper(substr(encode(gen_random_bytes(10),'hex'),1,16));
  v_expiry:=now()+case when v_prize in ('ensaio','50') then interval '2 hours' else interval '24 hours' end;
  insert into public.campaign_awards(session_id,source_id,prize_id,coupon_code,expires_at)
  values(p_session,case when exists(select 1 from public.campaign_sources where id=p_source) then p_source else 'direto' end,v_prize,v_coupon,v_expiry);
  return query select v_prize,v_coupon,v_expiry;
end;
$$;
revoke all on function public.issue_campaign_award(uuid,text) from public,anon,authenticated;
grant execute on function public.issue_campaign_award(uuid,text) to service_role;
-- IMPORTANTE: session_id sozinho não impede abuso; o backend deverá autenticar
-- participação, impor limites e só emitir cupom quando o checkout puder validá-lo.
-- Nunca habilitar campaign_control.enabled até os testes de checkout e resgate.
