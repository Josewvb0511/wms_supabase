-- =========================================================
-- WMS - Migração Multiempresa + Custo
-- Execute no Supabase SQL Editor antes de publicar o código.
-- =========================================================

create table if not exists empresas (
    id bigserial primary key,
    codigo text not null unique,
    nome text not null,
    cnpj text,
    ativo boolean not null default true,
    criado_em timestamptz not null default now()
);

create table if not exists usuario_empresas (
    id bigserial primary key,
    usuario_id bigint not null references usuarios(id) on delete cascade,
    empresa_id bigint not null references empresas(id) on delete cascade,
    ativo boolean not null default true,
    criado_em timestamptz not null default now(),
    unique(usuario_id, empresa_id)
);

insert into empresas (codigo, nome, ativo)
values ('GERAL', 'Empresa Geral', true)
on conflict (codigo) do nothing;

alter table produtos add column if not exists empresa_id bigint references empresas(id);
alter table produtos add column if not exists custo_unitario numeric(18,6) not null default 0;
alter table produtos add column if not exists moeda_custo text not null default 'BRL';

alter table localizacoes add column if not exists empresa_id bigint references empresas(id);

alter table movimentacoes add column if not exists empresa_id bigint references empresas(id);
alter table movimentacoes add column if not exists custo_unitario numeric(18,6) not null default 0;
alter table movimentacoes add column if not exists custo_total numeric(18,6) not null default 0;

alter table inventario add column if not exists empresa_id bigint references empresas(id);
alter table inventario add column if not exists custo_unitario numeric(18,6) not null default 0;
alter table inventario add column if not exists custo_total numeric(18,6) not null default 0;

-- Preenche registros antigos com a empresa GERAL.
update produtos
set empresa_id = (select id from empresas where codigo = 'GERAL')
where empresa_id is null;

update localizacoes
set empresa_id = (select id from empresas where codigo = 'GERAL')
where empresa_id is null;

update movimentacoes
set empresa_id = (select id from empresas where codigo = 'GERAL')
where empresa_id is null;

update inventario
set empresa_id = (select id from empresas where codigo = 'GERAL')
where empresa_id is null;

-- Libera a empresa GERAL para todos os usuários atuais.
insert into usuario_empresas (usuario_id, empresa_id, ativo)
select u.id, e.id, true
from usuarios u
cross join empresas e
where e.codigo = 'GERAL'
on conflict (usuario_id, empresa_id) do nothing;

create index if not exists idx_produtos_empresa_id on produtos(empresa_id);
create index if not exists idx_localizacoes_empresa_id on localizacoes(empresa_id);
create index if not exists idx_movimentacoes_empresa_id on movimentacoes(empresa_id);
create index if not exists idx_inventario_empresa_id on inventario(empresa_id);
create index if not exists idx_usuario_empresas_usuario on usuario_empresas(usuario_id);
