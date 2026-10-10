-- Execute no projeto Supabase EXCLUSIVO da campanha, nunca no banco de reservas existente.
create extension if not exists pgcrypto;
create table if not exists public.campaign_sources (id text primary key, description text not null);
insert into public.campaign_sources(id,description) values ('pizzaria','Pizzaria'),('panfletos','Escolas e panfletos'),('supermercado','Banner supermercado'),('banner2','Segundo banner'),('direto','Acesso direto') on conflict do nothing;
create table if not exists public.campaign_events (id uuid primary key default gen_random_uuid(), source_id text references public.campaign_sources(id), event_type text not null check(event_type in ('visit','video_started','wheel_viewed','spin_requested','reservation_clicked')), session_id uuid, created_at timestamptz not null default now());
create table if not exists public.campaign_prizes (id text primary key, title text not null, total integer, claimed integer not null default 0 check(claimed>=0), discount_percent integer, check(total is null or total>=0), check(total is null or claimed<=total));
insert into public.campaign_prizes(id,title,total,discount_percent) values ('ensaio','Ensaio Belém + 10 fotos digitais',1,null),('50','50% de desconto',3,50),('20','20% de desconto',10,20),('10','10% de desconto',150,10),('5','5% de desconto',null,5) on conflict do nothing;
create table if not exists public.campaign_awards (id uuid primary key default gen_random_uuid(), session_id uuid not null unique, source_id text references public.campaign_sources(id), prize_id text not null references public.campaign_prizes(id), coupon_code text not null unique, status text not null default 'issued' check(status in ('issued','redeemed','expired')), issued_at timestamptz not null default now(), expires_at timestamptz not null, redeemed_at timestamptz);
create index if not exists campaign_awards_expiration on public.campaign_awards(status,expires_at);
alter table public.campaign_events enable row level security;
alter table public.campaign_prizes enable row level security;
alter table public.campaign_awards enable row level security;
alter table public.campaign_sources enable row level security;
-- Nenhuma política de acesso público. Eventos, giros, prêmios e resgates devem passar por funções de servidor autenticadas.
-- Para garantir cotas e distribuição: transação SQL com SELECT FOR UPDATE; nunca sortear no navegador.
-- Vincular cupom ao checkout real antes de habilitar a roleta.
