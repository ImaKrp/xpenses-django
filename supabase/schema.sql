create table if not exists public.categories (
    id bigint generated always as identity primary key,
    name text not null,
    icon text not null default 'circle',
    color text not null default '#6F6F6F',
    type text not null default 'default' check (type in ('default', 'custom'))
);

insert into public.categories (name, icon, color, type) values
    ('alimentação', 'utensils', '#73A942', 'default'),
    ('moradia', 'home', '#DF5555', 'default'),
    ('saúde', 'heart-pulse', '#CA3EAB', 'default'),
    ('compras', 'shopping-bag', '#B5A137', 'default'),
    ('educação', 'graduation-cap', '#9437B5', 'default'),
    ('transporte', 'car', '#37B5AD', 'default'),
    ('saldo', 'piggy-bank', '#5837B5', 'default'),
    ('outros', 'more-horizontal', '#6F6F6F', 'default')
on conflict do nothing;

create or replace function create_user_schema(p_user_id bigint)
returns void as $$
declare
    schema_name text := format('user_%s', p_user_id);
begin
    execute format('create schema if not exists %I', schema_name);

    execute format($f$
        create table if not exists %I.categories (
            id bigint generated always as identity primary key,
            name text not null,
            icon text not null default 'circle',
            color text not null default '#6F6F6F',
            type text not null default 'custom' check (type in ('custom'))
        )
    $f$, schema_name);

    execute format($f$
        create table if not exists %I.transactions (
            id bigint generated always as identity primary key,
            title text not null,
            category_id bigint,
            value numeric(12,2) not null,
            date date not null,
            frequency text not null default 'unique' check (frequency in ('unique', 'recurrent')),
            type text not null default 'despesa' check (type in ('receita', 'despesa'))
        )
    $f$, schema_name);

    execute format($f$
        create table if not exists %I.profiles (
            user_id bigint primary key,
            name text not null default '',
            image_url text
        )
    $f$, schema_name);

    execute format($f$
        create table if not exists %I.insight_snapshots (
            year int not null,
            month int not null,
            receita numeric(12,2) not null default 0,
            despesa numeric(12,2) not null default 0,
            necessities numeric(12,2) not null default 0,
            wants numeric(12,2) not null default 0,
            savings numeric(12,2) not null default 0,
            pct_necessities double precision not null default 0,
            pct_wants double precision not null default 0,
            pct_savings double precision not null default 0,
            primary key (year, month)
        )
    $f$, schema_name);
end;
$$ language plpgsql;
