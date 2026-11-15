-- 02_delete_my_account.sql — 회원 탈퇴: 로그인한 사람이 자기 계정만 지울 수 있다 (5차 A단계, 2026-11-15)
-- 계정을 지우면 별명 표(profiles)와 그 사람의 글(posts)도 함께 지워진다(on delete cascade).
-- 공지사항은 남고, 쓴 사람 칸만 비워진다(on delete set null).
create function public.delete_my_account() returns void
language sql security definer set search_path = '' as $$
  delete from auth.users where id = (select auth.uid());
$$;
revoke execute on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
