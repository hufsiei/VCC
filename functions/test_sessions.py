# test_sessions.py — sessions.py 시험 (작업 73). 실행: cd functions && python test_sessions.py
# 실제 data/runtime을 건드리지 않게 메모리만 쓴다(store.save를 막는다). 하나라도 틀리면 종료코드 1.
import sys

import sessions
import store

store.save = lambda name: None   # 파일에 쓰지 않는다
store._cache["sessions"] = {}

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: {got!r} != {want!r}")


t = sessions.issue("H0143", now=1000)
check("왕복", sessions.resolve(t, now=1001), "H0143")
t2 = sessions.issue("H0143", now=1000)
check("같은 계정 토큰 여러 개", t != t2 and sessions.resolve(t2, now=1001) == "H0143", True)
check("만료 직전", sessions.resolve(t, now=1000 + sessions.TTL - 1), "H0143")
check("만료 후", sessions.resolve(t, now=1000 + sessions.TTL), "")
check("만료 항목 삭제", t in store.load("sessions", {}), False)
sessions.revoke(t2)
check("revoke 후", sessions.resolve(t2, now=1001), "")
check("없는 토큰", sessions.resolve("nope"), "")
check("빈 토큰", sessions.resolve(""), "")
sessions.revoke("nope")   # 오류 없이 지나감

print("\n".join(fails) or "test_sessions: 모두 통과")
sys.exit(1 if fails else 0)
