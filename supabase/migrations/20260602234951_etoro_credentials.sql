create table if not exists public.etoro_credentials (
    user_id        uuid primary key,
    public_key_enc text not null,
    user_key_enc   text not null,
    environment    text not null default 'demo' check (environment in ('real','demo')),
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now()
);

alter table public.etoro_credentials enable row level security;

create policy "own creds - select" on public.etoro_credentials
    for select to authenticated using ((select auth.uid()) = user_id);
create policy "own creds - insert" on public.etoro_credentials
    for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "own creds - update" on public.etoro_credentials
    for update to authenticated using ((select auth.uid()) = user_id)
                                    with check ((select auth.uid()) = user_id);
create policy "own creds - delete" on public.etoro_credentials
    for delete to authenticated using ((select auth.uid()) = user_id);
