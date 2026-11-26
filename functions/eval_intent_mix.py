# eval_intent_mix.py — 실사용 askLog의 길·의도 분포로 「겹쳐 돌리기(3-3)」 버리는 답쓰기 비율 추정 (작업 35 · #278, 미리)
#   python -X utf8 functions/eval_intent_mix.py            # 버킷(공개 서버) askLog — AI 안 부름, 읽기만
#   python -X utf8 functions/eval_intent_mix.py --local    # 이 PC의 data/runtime/askLog.json
#   --since 2026-11-26T14:15   # A안 켜진 뒤만(기본)
# 질문 글은 셈에만 쓰고 출력하지 않는다(이미 mask된 글이지만 화면·문서에 옮기지 않는다).
# 겹쳐 돌리기 대상 = 질문정리까지 간 기록(route가 「질문정리…」·「v1…」) 중 질문 글에 학교(프로그램) 이름이 잡히는 것.
#   그중 질문정리 의도가 경험질문(사람찾기+주제어 포함)이 아니거나, 질문정리가 다른 프로그램을 고른 것 = 버리는 답쓰기.
import argparse
import os
import sys
from collections import Counter

import paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--since", default="2026-11-26T14:15")
    a = ap.parse_args()
    if not a.local:
        paths.load_env()
        os.environ["STORE_BACKEND"] = "ncp"
        os.environ.setdefault("NCP_OS_PREFIX", "runtime/")
    import store
    import askboo
    log = [r for r in store.load("askLog", []) if isinstance(r, dict) and str(r.get("at", "")) >= a.since]
    print(f"askLog {a.since} 이후 {len(log)}건")
    route = Counter((r.get("route") or "?").split("·")[0].split("→")[0] for r in log)
    print("길:", dict(route.most_common()))
    clar = [r for r in log if (r.get("route") or "").startswith(("질문정리", "v1"))]
    print(f"질문정리까지 간 기록 {len(clar)}건 · 의도:", dict(Counter(r.get("intent") for r in clar).most_common()))
    named = []
    for r in clar:
        q = r.get("question") or ""
        progs = askboo.match_programs(q)
        if progs:
            named.append((r, progs))
    keep = waste = 0
    why = Counter()
    for r, progs in named:
        intent = r.get("intent")
        used = r.get("programs") or []
        if intent not in ("경험질문", "사람찾기"):
            waste += 1
            why[f"의도 {intent}"] += 1
        elif used and not set(used) & set(progs):
            waste += 1
            why["다른 프로그램"] += 1
        else:
            keep += 1
            why[f"쓰임({r.get('status')})"] += 1
    n = len(named)
    print(f"학교 이름이 글자로 잡힌 기록 {n}건 = 겹쳐 돌리기 대상 · 쓰임 {keep} · 버림 {waste}"
          + (f" ({waste / n:.0%})" if n else ""))
    print("  내역:", dict(why.most_common()))
    print(f"  전체 askBoo 대비 대상 비율 {n / len(log):.0%}" if log else "")


if __name__ == "__main__":
    sys.exit(main())
