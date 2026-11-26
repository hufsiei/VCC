# test_message_rules.py — 쪽지 규칙 경계값·spec 대조 (작업 85)
# 실행: cd functions && python test_message_rules.py
# 기준: docs/spec-v1.md 4장 login·getMe·recommendSeniors·sendMessage·getMessages·respondRequest
# test_messages.py가 기본 흐름을 보고, 여기서는 경계(6.99일/7일, 4건/5건), 거절·만료 뒤 재요청,
# 덧붙이기가 한도에 안 세지는지, login·getMe 응답 모양을 본다.
# AI를 부르지 않는다. 기록은 임시 폴더(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import account
import runtime_fns as rf
from runtime_fns import respondRequest
rf._call_ai = lambda *a, **k: {"ok": True, "json": {"ok": True}}   # 시험은 실제 AI를 부르지 않는다(쪽지검사 연결, 작업 27)

JUNIOR = "H0143"
MARBURG = "N-marburg"
CANDS = ["H0469", "H0241", "H0751", "H0995", "H0745"]   # 마르부르크 경험자(test_messages.py와 같음)
HELLO = "안녕하세요, 파견 준비가 궁금해서 쪽지 드려요."
fails = []

clock = [datetime(2026, 11, 24, 10, 0, tzinfo=rf.KST)]
rf.now = lambda: clock[0].isoformat(timespec="seconds")


def later(days):
    clock[0] += timedelta(days=days)


# [작업 38 D-1] 응답의 상대 값은 학번이 아니라 불투명 값(peer_ref). 이 시험은 학번으로 쓰고, 서버에는 화면처럼
# 불투명 값으로 보내고 받은 값은 학번으로 되돌려 본다. 불투명 값 자체는 test_messages.py 9절.
def sendMessage(me, p):
    return rf.sendMessage(me, {**p, "to": rf.peer_ref(me, p["to"])})


def previewNickname(me, p):
    return rf.previewNickname(me, {**p, "to": rf.peer_ref(me, p["to"])})


def recommendSeniors(me, p):
    r = rf.recommendSeniors(me, p)
    for x in r.get("seniors", []):
        x["studentId"] = rf.resolve_peer(me, x["studentId"])
    return r


def getMessages(me, p):
    r = rf.getMessages(me, p)
    for t in r["threads"]:
        t["withId"] = rf.resolve_peer(me, t["withId"])
    return r


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def thread(me, tid):
    return next((t for t in getMessages(me, {})["threads"] if t["threadId"] == tid), None)


def card(me, senior):
    return next((x for x in recommendSeniors(me, {"noteId": MARBURG, "more": True})["seniors"]
                 if x["studentId"] == senior), None)


def unlock(*ids):
    store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in ids)


def send(me, to, text=HELLO):
    return sendMessage(me, {"to": to, "text": text})


juniors = [f"H{n:04d}" for n in range(1, 20)]
unlock(JUNIOR, *juniors)

# ── 1. 닉네임 미리보기 = 보낼 때 이름 ────────────────────────────────────
pre = previewNickname(JUNIOR, {"to": CANDS[0]})["myNickname"]
s = send(JUNIOR, CANDS[0])
tid_a = s["threadId"]
expect("previewNickname 값이 sendMessage myNickname과 같음", s["ok"] and s["myNickname"] == pre)
expect("응답 모양 {ok, threadId, myNickname, at}", set(s) == {"ok", "threadId", "myNickname", "at"})

# ── 2. 덧붙이기는 한도에 세지 않음 · 3건째까지 됨 · 4건째 한도 ──────────────
for _ in range(3):
    send(JUNIOR, CANDS[0], "하나 더요.")
expect("같은 선배에게 여러 번 보내도 waiting 1건", getMessages(JUNIOR, {})["waitingCount"] == 1)
expect("2건째 요청 됨", send(JUNIOR, CANDS[1])["ok"])
tid_c = send(JUNIOR, CANDS[2]).get("threadId")
expect("3건째 요청 됨", tid_c is not None)
s = send(JUNIOR, CANDS[3])
expect("4건째는 reason 한도 + spec 문구", s == {"ok": False, "reason": "한도",
       "message": "답을 기다리는 쪽지가 3건이에요. 기다리는 요청을 취소하거나 선배가 답하면 더 보낼 수 있어요."})
expect("한도에 걸려도 대화가 생기지 않음", all(t["withId"] != CANDS[3] for t in getMessages(JUNIOR, {})["threads"]))

# ── 3. 수락되면 한도에서 빠짐 ────────────────────────────────────────────
respondRequest(CANDS[0], {"threadId": tid_a, "accept": True})
expect("수락 → waitingCount 2", getMessages(JUNIOR, {})["waitingCount"] == 2)

# ── 4. 거절: 다시 못 보냄, retryAt 없음 ───────────────────────────────────
tid_d = send(JUNIOR, CANDS[3])["threadId"]
r = respondRequest(CANDS[3], {"threadId": tid_d, "accept": False})
expect("거절 → declined + 옛 필드 accepted false", r == {"ok": True, "status": "declined", "accepted": False})
s = send(JUNIOR, CANDS[3])
expect("거절한 선배에게 다시 보내면 reason 상태", s.get("ok") is False and s.get("reason") == "상태")
expect("거절한 대화에는 retryAt 없음", "retryAt" not in thread(JUNIOR, tid_d))
c = card(JUNIOR, CANDS[3])
expect("거절한 선배 카드에도 retryAt 없음", c is not None and "retryAt" not in c)
expect("getMessages 각 대화에 옛 필드 accepted", thread(JUNIOR, tid_a)["accepted"] is True
       and thread(JUNIOR, tid_d)["accepted"] is False)

# ── 5. 취소 7일: 6.99일까지 막힘, 7일부터 같은 대화로 다시 ─────────────────
c0 = rf.now()
r = respondRequest(JUNIOR, {"threadId": tid_c, "cancel": True})
retry = (datetime.fromisoformat(c0) + timedelta(days=7)).isoformat(timespec="seconds")
expect("취소 응답 retryAt = 취소 + 7일(+09:00)", r.get("retryAt") == retry and retry.endswith("+09:00"))
expect("취소한 선배 카드 retryAt이 같은 값", (card(JUNIOR, CANDS[2]) or {}).get("retryAt") == retry)
expect("선배는 취소된 요청을 수락할 수 없음", "error" in respondRequest(CANDS[2], {"threadId": tid_c, "accept": True}))
later(6.99)
s = send(JUNIOR, CANDS[2])
expect("6.99일: reason 취소 + spec 문구 + retryAt", s == {"ok": False, "reason": "취소",
       "message": "요청을 취소한 선배에게는 7일 뒤에 다시 보낼 수 있어요.", "retryAt": retry})
later(0.01)
expect("7일: getMessages retryAt 없어짐", "retryAt" not in thread(JUNIOR, tid_c))
expect("7일: 카드 retryAt 없어짐", "retryAt" not in (card(JUNIOR, CANDS[2]) or {}))
# 위에서 보낸 CANDS[1] 요청은 7일이 지나 만료됐다 → 한도는 0건
s = send(JUNIOR, CANDS[2])
expect("7일: 같은 대화가 waiting으로 다시 열림", s["ok"] and s["threadId"] == tid_c
       and thread(JUNIOR, tid_c)["status"] == "waiting")

# ── 6. 만료 경계 · sendMessage 호출로도 판정 · 만료는 바로 다시 ─────────────
J2 = juniors[0]
tid_e = send(J2, CANDS[4])["threadId"]
later(6.99)
expect("6.99일: 아직 waiting", thread(J2, tid_e)["status"] == "waiting")
later(0.01)
store.load("messages", {})   # getMessages를 부르지 않고 sendMessage만으로 만료되는지 본다
s = send(J2, CANDS[0])
raw = store.load("messages", {})[tid_e]
expect("7일: sendMessage 호출에서 expired로 판정", s["ok"] and raw["status"] == "expired")
expect("만료 대화에는 retryAt 없음", "retryAt" not in thread(J2, tid_e))
s = send(J2, CANDS[4])
expect("만료한 선배에게 바로 다시 요청 = 같은 대화", s["ok"] and s["threadId"] == tid_e
       and thread(J2, tid_e)["status"] == "waiting")
expect("선배는 만료됐던 요청도 다시 받음(목록에 보임)", thread(CANDS[4], tid_e) is not None)

# ── 7. 다시 요청도 한도를 본다 ───────────────────────────────────────────
J3 = juniors[1]
tid_x = send(J3, CANDS[0])["threadId"]
respondRequest(J3, {"threadId": tid_x, "cancel": True})
later(7)
for h in CANDS[1:4]:
    send(J3, h)
s = send(J3, CANDS[0])
expect("7일 지난 재요청도 보낸 사람 3건 한도", s.get("reason") == "한도")

# ── 8. 받는 한도: waiting만 셈, 4건 → requestsFull false, 5건 → true ───────
TARGET = CANDS[1]
later(8)   # 지금까지의 waiting을 모두 만료시켜 TARGET 수를 0부터 센다
getMessages(JUNIOR, {})
pool = juniors[3:]
t_ok = send(pool[0], TARGET)["threadId"]
respondRequest(TARGET, {"threadId": t_ok, "accept": True})            # 수락된 대화는 세지 않음
for j in pool[1:5]:
    send(j, TARGET)
expect("waiting 4건 → requestsFull false", card(JUNIOR, TARGET)["requestsFull"] is False)
t5 = send(pool[5], TARGET)["threadId"]
expect("수락 1 + waiting 4 → 5건째 요청 됨", t5 is not None)
expect("waiting 5건 → requestsFull true", card(JUNIOR, TARGET)["requestsFull"] is True)
s = send(pool[6], TARGET)
expect("6건째는 reason 선배한도 + spec 문구", s == {"ok": False, "reason": "선배한도",
       "message": "지금은 이 선배에게 요청이 많아요. 질문함에 남기면 선배 인터뷰 때 함께 물어볼게요."})
respondRequest(pool[5], {"threadId": t5, "cancel": True})
expect("한 명이 취소하면 requestsFull false", card(JUNIOR, TARGET)["requestsFull"] is False)
expect("취소로 빈 자리에 다른 후배 요청", send(pool[6], TARGET)["ok"])

# ── 9. respondRequest 오류 모양 ──────────────────────────────────────────
expect("남의 대화 취소 → error", "error" in respondRequest(pool[1], {"threadId": t5, "cancel": True}))
expect("없는 대화 → error", "error" in respondRequest(JUNIOR, {"threadId": "T-없음", "cancel": True}))
expect("수락된 대화 취소 → reason 상태", respondRequest(pool[0], {"threadId": t_ok, "cancel": True}).get("reason") == "상태")

# ── 10. login·getMe 응답 모양 ────────────────────────────────────────────
store.save = lambda name: None   # sessions 기록을 남기지 않는다
store._cache["sessions"] = {}
os.environ["VCC_LOGIN_PW"] = json.dumps({"*": "pw", "staff01": "s", "staff02": "s"})
u = account.login("", {"id": "H0143", "pw": "pw"})["user"]
expect("login 학생 user = {colreg_no, status 학생, token}", set(u) == {"colreg_no", "status", "token"} and u["status"] == "학생")
u = account.login("", {"id": "staff01", "pw": "s"})["user"]
expect("login staff01 = 전체·총괄, 부서코드 없음", u["status"] == "직원" and u["부서명"] == "전체"
       and u["권한"] == "총괄" and "부서코드" not in u)
u = account.login("", {"id": "staff02", "pw": "s"})["user"]
expect("login staff02 = 혁신지원팀·D04·부서", (u["부서명"], u.get("부서코드"), u["권한"]) == ("혁신지원팀", "D04", "부서"))
expect("login 실패 모양", account.login("", {"id": "H0143", "pw": "x"})
       == {"ok": False, "reason": "아이디 또는 비밀번호가 맞지 않아요."})
me = account.getMe("H0469", {})
expect("getMe: 번호·비번 없음", "번호" not in me and "비번" not in me)
expect("getMe: 이수 기록 3종 + recommend + recommendable",
       all(k in me for k in ("비교과이수내역", "귀국보고서", "현장실습후기", "recommend", "recommendable")))
expect("getMe 귀국보고서 칸 = 학년도·학기·국가·대학명(본문 없음)",
       me["귀국보고서"] and all(list(x) == ["학년도", "학기", "국가", "대학명"] for x in me["귀국보고서"]))
expect("getMe recommend 모양", set(me["recommend"]) == {"ready", "by", "need", "talk", "ask"})

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
