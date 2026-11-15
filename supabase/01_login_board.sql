-- 01_login_board.sql — 회원 별명·공지사항·게시글 표와 "누가 무엇을 할 수 있나" 규칙 (5차, 2026-11-15)
-- Supabase 프로젝트 water-signal에 적용했다. 비밀번호는 여기 없다(Supabase 로그인 기능이 암호화해 보관).
-- 아이디는 '아이디@users.water-signal.invalid' 꼴의 이메일로 바꿔 가입한다(.invalid는 실제로 없는 주소).

-- ① 회원 별명 표 ─────────────────────────────────────────
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,  -- 로그인 계정과 1:1
  username text not null unique check (username ~ '^[a-z0-9]{4,20}$'), -- 영문 소문자·숫자 4~20자
  nickname text not null check (char_length(nickname) between 2 and 12),
  is_admin boolean not null default false,                            -- 관리자는 나중에 한 명만 직접 정한다
  age14_confirmed boolean not null check (age14_confirmed),           -- "만 14세 이상" 체크를 한 사람만
  created_at timestamptz not null default now()
);

-- 가입하면 자동으로 별명 표에 한 줄을 만든다. 규칙에 안 맞으면 가입 자체가 실패한다.
create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  name text := new.raw_user_meta_data ->> 'username';
begin
  if new.email is distinct from name || '@users.water-signal.invalid' then
    raise exception '아이디와 이메일 모양이 맞지 않아요';
  end if;
  insert into public.profiles (id, username, nickname, age14_confirmed)
  values (new.id, name, new.raw_user_meta_data ->> 'nickname',
          coalesce((new.raw_user_meta_data ->> 'age14')::boolean, false));
  return new;
end;
$$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();
revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- 지금 로그인한 사람이 관리자인가? (규칙 안에서 쓴다)
create function public.is_admin() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select is_admin from public.profiles where id = (select auth.uid())), false);
$$;
revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- ② 공지사항 표 ───────────────────────────────────────────
create table public.notices (
  id bigint generated always as identity primary key,
  title text not null check (char_length(title) between 1 and 50),
  body text not null check (char_length(body) between 1 and 2000),
  author_id uuid default auth.uid() references public.profiles (id) on delete set null,
  created_at timestamptz not null default now()
);

-- ③ 게시글 표 ─────────────────────────────────────────────
create table public.posts (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references public.profiles (id) on delete cascade,
  title text not null check (char_length(title) between 1 and 50),
  body text not null check (char_length(body) between 1 and 2000),
  created_at timestamptz not null default now()
);
create index posts_user_id_idx on public.posts (user_id);
create index notices_author_id_idx on public.notices (author_id);

-- 규칙(RLS) 켜기: 켜면 아래에 적은 것만 할 수 있다 ─────────────
alter table public.profiles enable row level security;
alter table public.notices enable row level security;
alter table public.posts enable row level security;

-- 별명: 누구나 볼 수 있다(아이디·관리자 여부 칸은 아래 권한에서 숨긴다)
create policy "별명은 누구나 본다" on public.profiles for select to anon, authenticated using (true);

-- 공지: 누구나 읽고, 관리자만 쓰고 고치고 지운다
create policy "공지는 누구나 읽는다" on public.notices for select to anon, authenticated using (true);
create policy "공지는 관리자만 쓴다" on public.notices for insert to authenticated
  with check ((select public.is_admin()));
create policy "공지는 관리자만 고친다" on public.notices for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy "공지는 관리자만 지운다" on public.notices for delete to authenticated
  using ((select public.is_admin()));

-- 게시글: 누구나 읽고, 회원은 자기 이름으로만 쓰고, 내 글은 나·모든 글은 관리자가 지운다
create policy "글은 누구나 읽는다" on public.posts for select to anon, authenticated using (true);
create policy "글은 회원이 자기 이름으로 쓴다" on public.posts for insert to authenticated
  with check (user_id = (select auth.uid()));
create policy "내 글은 나, 모든 글은 관리자가 지운다" on public.posts for delete to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

-- 표 권한: 필요한 것만 연다 ─────────────────────────────────
revoke all on public.profiles, public.notices, public.posts from anon, authenticated;
grant select (id, nickname, created_at) on public.profiles to anon, authenticated;  -- 아이디·관리자 칸은 숨김
grant select on public.notices, public.posts to anon, authenticated;
grant insert, update, delete on public.notices to authenticated;
grant insert, delete on public.posts to authenticated;
