# sessions.py — 로그인 토큰 (작업 73, 원본: docs/spec-v1.md 2-1 「누가 부르는지」)
#
# login이 issue()로 난수 토큰을 만들고, 화면(data.js)이 X-Token 헤더로 보낸다. 서버는 resolve()로 사용자를 안다.
# 같은 계정이 여러 번 로그인하면 토큰이 여러 개 생긴다(두 창 시연). 만료 24시간.
# 기록: data/runtime/sessions.json (store.py) — {토큰: {"me": colreg_no, "exp": 만료 시각(초)}}
import secrets
import time

import store

TTL = 24 * 60 * 60


def issue(me, now=None):
    """토큰을 새로 만들어 돌려준다."""
    now = time.time() if now is None else now
    token = secrets.token_urlsafe(24)
    with store.lock():
        sessions = store.load("sessions", {})
        sessions[token] = {"me": me, "exp": now + TTL}
        store.save("sessions")
    return token


def resolve(token, now=None):
    """토큰의 사용자(colreg_no). 없거나 만료면 "". 만료된 항목은 여기서 지운다."""
    token = str(token or "").strip()
    if not token:
        return ""
    now = time.time() if now is None else now
    with store.lock():
        sessions = store.load("sessions", {})
        s = sessions.get(token)
        if not s:
            return ""
        if s["exp"] <= now:
            del sessions[token]
            store.save("sessions")
            return ""
        return s["me"]


def revoke(token):
    """로그아웃. 없는 토큰이어도 오류 없이 지나간다."""
    with store.lock():
        sessions = store.load("sessions", {})
        if sessions.pop(str(token or "").strip(), None) is not None:
            store.save("sessions")
