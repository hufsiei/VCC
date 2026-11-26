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


# ---------- 로그인 실패 한도 (작업 38, 11/26) ----------
# 계정(정규화한 colreg_no)마다 LOGIN_WINDOW초 안에 LOGIN_FAILS번 틀리면 LOGIN_LOCK초 동안 그 계정의 로그인을 막는다.
# 막힌 동안은 맞는 비번도 받지 않는다(받으면 맞힌 순간을 알려 주는 셈이라 반복 시도를 못 막는다).
# 시연 경계: 성공한 로그인은 세지 않고 그 계정의 실패 기록을 지운다 — 여러 창에서 맞는 비번으로 몇 번을 들어와도 안 막힌다.
#   누가 시연 계정을 일부러 틀려도 막히는 건 60초뿐. 급하면 reset_runtime.py가 loginFails도 지운다.
# 세는 대상은 students.json에 있는 계정만(account.login이 행을 찾은 뒤 부른다) — 아무 아이디나 넣어 기록을 불리지 못하게.
# 기록: data/runtime/loginFails.json {colreg_no: {"since": 창 시작(초), "fails": 정수, "until": 잠금 끝(초, 0이면 없음)}}
#   fails는 정수라 ncp에서 두 컨테이너가 같이 세도 더해진다(store._merge).
LOGIN_FAILS = 5
LOGIN_WINDOW = 60
LOGIN_LOCK = 60
LOGIN_KEY = "loginFails"


def login_wait(uid, now=None):
    """막혀 있으면 남은 초(1 이상 정수), 아니면 0. 읽기만 한다."""
    now = time.time() if now is None else now
    with store.lock():
        r = store.load(LOGIN_KEY, {}).get(uid)
    if not r or r.get("until", 0) <= now:
        return 0
    return max(1, int(r["until"] - now + 0.999))


def login_failed(uid, now=None):
    """틀린 비번 1회를 센다. 이번에 막혔으면 남은 초(LOGIN_LOCK), 아니면 0."""
    now = time.time() if now is None else now
    with store.lock():
        rec = store.load(LOGIN_KEY, {})
        for k in [k for k, v in rec.items()   # 지난 기록 정리: 창도 잠금도 끝난 계정
                  if k != uid and now - v.get("since", 0) >= LOGIN_WINDOW and v.get("until", 0) <= now]:
            del rec[k]
        r = rec.get(uid)
        if not r or now - r.get("since", 0) >= LOGIN_WINDOW:
            r = rec[uid] = {"since": now, "fails": 0, "until": 0}
        r["fails"] += 1
        locked = r["fails"] >= LOGIN_FAILS
        if locked:   # 잠그고 창을 잠금 끝으로 옮긴다 — 풀린 뒤에는 다시 5번
            r.update(since=now + LOGIN_LOCK, fails=0, until=now + LOGIN_LOCK)
        store.save(LOGIN_KEY)
    return LOGIN_LOCK if locked else 0


def login_ok(uid):
    """로그인 성공: 그 계정의 실패 기록을 지운다(없으면 저장하지 않음)."""
    with store.lock():
        rec = store.load(LOGIN_KEY, {})
        if rec.pop(uid, None) is not None:
            store.save(LOGIN_KEY)
