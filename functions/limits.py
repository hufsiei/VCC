# limits.py — 사용자별 AI 호출 한도 (작업 72, 원본: docs/spec-v1.md 0장 [11/19])
#
# X-Token으로 확인한 사용자(colreg_no)마다 분당 10회·하루 100회. 넘으면 {"error": "잠시 뒤에 다시 시도해 주세요"}.
# 세는 단위: AI를 쓰는 서버 함수 요청 1건(askBoo 질문 1개 = 1회). askBoo는 한 질문에 AI를 최대 4번 부르므로
#   callAI 호출 횟수로 세면 분당 질문 2~3개에서 막힌다. 그래서 local_fn.py 입구에서 함수 요청 단위로 센다.
# 전역 상한(작업 86): AI 함수 요청 전체가 하루 GLOBAL_PER_DAY건. 시연 계정도 센다(사용자별 한도만 면제).
#   크레딧을 지키는 마지막 문 — 로그인한 계정이 많아도 하루 총량은 넘지 못한다. 기록은 aiUsage.json의 "_global" 키.
# 시연 계정은 사용자별 한도에서 제외(spec 0장). 닮은선배·집계·노트 조회처럼 AI를 안 부르는 함수는 세지 않는다.
# 기록: data/runtime/aiUsage.json (store.py) — 날짜가 바뀌면 그 사람의 하루 횟수를 0으로.
import time
from datetime import datetime, timedelta, timezone

import store

PER_MINUTE = 10
PER_DAY = 100
GLOBAL_PER_DAY = 2000
EXEMPT = {"H0143", "H0469", "H0241", "H0745", "staff01", "staff02"}   # 시연 계정(spec 0장)
MESSAGE = "잠시 뒤에 다시 시도해 주세요"
GLOBAL_MESSAGE = "오늘 사용량을 다 썼어요. 내일 다시 시도해 주세요"
GLOBAL_KEY = "_global"
KST = timezone(timedelta(hours=9))


def check(me, now=None):
    """한도 안이면 None을 돌려주고 1회를 센다. 넘었으면 {"error": ...}를 돌려주고 세지 않는다.
    순서: 전역 상한 → 사용자별 한도. 사용자별에서 막힌 요청은 전역에도 세지 않는다."""
    now = time.time() if now is None else now
    today = datetime.fromtimestamp(now, KST).strftime("%Y-%m-%d")
    with store.lock():
        usage = store.load("aiUsage", {})
        g = usage.setdefault(GLOBAL_KEY, {"day": today, "dayCount": 0})
        if g["day"] != today:
            g.update(day=today, dayCount=0)
        if g["dayCount"] >= GLOBAL_PER_DAY:
            return {"error": GLOBAL_MESSAGE}
        if me not in EXEMPT:
            u = usage.setdefault(me, {"day": today, "dayCount": 0, "recent": []})
            if u["day"] != today:
                u.update(day=today, dayCount=0, recent=[])
            u["recent"] = [t for t in u["recent"] if now - t < 60]
            if len(u["recent"]) >= PER_MINUTE or u["dayCount"] >= PER_DAY:
                return {"error": MESSAGE}
            u["recent"].append(now)
            u["dayCount"] += 1
        g["dayCount"] += 1
        store.save("aiUsage")
    return None
