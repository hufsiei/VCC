# test_limits.py — limits.py 시험 (작업 72·86). 실행: cd functions && python test_limits.py
# 전역 2,000건 상한, 시연 계정도 전역에 포함, 사용자별 한도는 시연 계정만 면제. 하나라도 틀리면 종료코드 1.
import sys
from datetime import datetime

import limits
import store

store.save = lambda name: None
fails = []
NOW = datetime(2027, 1, 15, 1, 0, tzinfo=limits.KST).timestamp()   # 임의의 한 날 새벽 1시(KST)


def fresh():
    store._cache["aiUsage"] = {}


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: {got!r} != {want!r}")


# 전역: 2,000번째까지 통과, 2,001번째 거절. 사용자를 바꿔 가며 사용자별 한도에 걸리지 않게 한다.
fresh()
# 50명이 40번씩(한 사람은 61초 간격이라 분당 한도, 하루 40회라 일일 한도에 안 걸린다)
res = [limits.check(f"U{i % 50}", now=NOW + (i // 50) * 61) for i in range(2000)]
check("2,000번째까지 통과", sum(1 for r in res if r is None), 2000)
check("2,001번째 거절", limits.check("U99", now=NOW + 2500), {"error": limits.GLOBAL_MESSAGE})
check("거절은 세지 않음", store.load("aiUsage", {})["_global"]["dayCount"], 2000)
check("시연 계정도 전역에 막힘", limits.check("H0143", now=NOW + 2500), {"error": limits.GLOBAL_MESSAGE})
check("다음 날 0으로", limits.check("U1", now=NOW + 86400), None)

# 시연 계정도 전역에 센다
fresh()
for _ in range(25):
    limits.check("H0143", now=NOW)
check("시연 계정은 전역에 포함", store.load("aiUsage", {})["_global"]["dayCount"], 25)
check("시연 계정은 사용자별 한도 면제(분당 10 넘어도 통과)", limits.check("H0143", now=NOW), None)
check("시연 계정은 사용자별 기록 없음", "H0143" in store.load("aiUsage", {}), False)

# 일반 사용자 한도는 그대로
fresh()
r = [limits.check("H0001", now=NOW) for _ in range(11)]
check("분당 10회까지 통과", r[:10], [None] * 10)
check("11번째 거절(사용자별 메시지)", r[10], {"error": limits.MESSAGE})
check("사용자별 거절은 전역에 세지 않음", store.load("aiUsage", {})["_global"]["dayCount"], 10)

print("\n".join(fails) or "test_limits: 모두 통과")
sys.exit(1 if fails else 0)
