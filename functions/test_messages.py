# test_messages.py — 쪽지 규칙(11/18·11/20)과 recommendSeniors 목록 규칙 (작업 85)
# 실행: cd functions && python test_messages.py
# 기준: docs/spec-v1.md 4장 recommendSeniors·sendMessage·getMessages·respondRequest
# AI를 부르지 않는다. 기록은 임시 폴더에 쓴다(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import runtime_fns as rf
from runtime_fns import getInbox, respondRequest
rf._call_ai = lambda *a, **k: {"ok": True, "json": {"ok": True}}   # 시험은 실제 AI를 부르지 않는다(쪽지검사 연결, 작업 27)

JUNIOR, SENIOR1, SENIOR2 = "H0143", "H0469", "H0241"
MARBURG = "N-marburg"
BIG = "HUFS 동문멘토링 데이"      # 경험자 141명 — 9명 상한 확인용
HELLO = "안녕하세요, 마르부르크 파견 준비가 궁금해서 쪽지 드려요."
fails = []

# 시계: 테스트가 날짜를 옮길 수 있게 runtime_fns.now를 바꾼다
clock = [datetime(2026, 11, 21, 10, 0, tzinfo=rf.KST)]
rf.now = lambda: clock[0].isoformat(timespec="seconds")


# [작업 38 D-1] 응답의 상대 값은 학번이 아니라 불투명 값(peer_ref). 이 시험은 학번으로 쓰고, 서버에는 화면처럼
# 불투명 값으로 보내고 받은 값은 학번으로 되돌려 본다. 불투명 값 자체는 test_messages.py 9절.
def sendMessage(me, p):
    return rf.sendMessage(me, {**p, "to": rf.peer_ref(me, p["to"])})


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


def later(days):
    clock[0] += timedelta(days=days)


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def thread(me, tid):
    return next((t for t in getMessages(me, {})["threads"] if t["threadId"] == tid), None)


def unlock(*ids):
    """선배 추천 열림(demand.py) — 수요 인터뷰를 마친 것처럼 기록만 넣는다(열림 규칙 자체는 test_demand.py)."""
    store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in ids)


# ── 0. [11/22] 경험 나눔·수요 제공 전에는 추천·새 쪽지 요청이 잠김 ──────────
r = recommendSeniors(JUNIOR, {"noteId": MARBURG})
expect("잠김: 추천 목록 없이 locked + 안내", r.get("locked") is True and "seniors" not in r and r["recommend"]["ready"] is False)
expect("잠김: 닉네임 미리보기도 막힘", rf.previewNickname(JUNIOR, {"to": rf.peer_ref(JUNIOR, SENIOR1)}).get("locked") is True)
s = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})
expect("잠김: 새 쪽지 요청은 reason 잠김", s.get("ok") is False and s.get("reason") == "잠김")
unlock(JUNIOR)

# ── 1. 닮은선배: 처음 3명 → 더 보기 → 바닥 ─────────────────────────────
r = recommendSeniors(JUNIOR, {"noteId": MARBURG})
ids = [s["studentId"] for s in r["seniors"]]
expect("처음 3명, 1·2위는 선배1·선배2", r["shown"] == 3 and ids[:2] == [SENIOR1, SENIOR2] and r["hasMore"])
expect("이름은 학과 + 선배 + 글자", [s["nickname"] for s in r["seniors"][:2]] == ["독일어과 선배 A", "독일어과 선배 B"])
expect("이유 맨 앞은 「희망 프로그램을 경험했어요」", all(s["reasons"][0] == "희망 프로그램을 경험했어요" for s in r["seniors"]))
expect("응답에 학번 밖 개인 정보 없음", set(r["seniors"][0]) == {"studentId", "nickname", "score", "requestsFull", "reasons"})
r2 = recommendSeniors(JUNIOR, {"noteId": MARBURG})
expect("다시 불러도 같은 목록", [s["studentId"] for s in r2["seniors"]] == ids and r2["newCount"] == 0)
r = recommendSeniors(JUNIOR, {"noteId": MARBURG, "more": True})
expect("더 보기 → 후보 5명 전부, hasMore false", r["shown"] == 5 and not r["hasMore"])
expect("먼저 보인 3명은 순서 그대로", [s["studentId"] for s in r["seniors"]][:3] == ids)
r = recommendSeniors(JUNIOR, {"noteId": "마르부르크필립스대학교"})
expect("noteId 대신 프로그램 이름도 같은 노트", r["shown"] == 5)

big = recommendSeniors(JUNIOR, {"noteId": BIG})
for _ in range(5):
    big = recommendSeniors(JUNIOR, {"noteId": BIG, "more": True})
expect("후보가 많아도 최대 9명, 끝나면 hasMore false", big["shown"] == 9 and not big["hasMore"])
expect("없는 노트는 빈 목록", recommendSeniors(JUNIOR, {"noteId": "N-없음"})["seniors"] == [])

# 노트 버전이 바뀌면(saveConsent) 같은 크기로 다시 계산
store.load("shownSeniors", {})[JUNIOR][MARBURG]["ids"] = [SENIOR1, "H0745", "H0751"]   # 순위가 바뀐 옛 목록처럼
versions = store.load("noteVersions", {})
versions[MARBURG] = versions.get(MARBURG, 0) + 1
r = recommendSeniors(JUNIOR, {"noteId": MARBURG})
expect("버전 변경 → 재계산 + newCount", r["shown"] == 3 and r["seniors"][1]["studentId"] == SENIOR2 and r["newCount"] >= 1)
expect("재계산해도 같은 사람은 같은 글자", r["seniors"][1]["nickname"] == "독일어과 선배 B")

# ── 2. 쪽지 요청 → 선배당 1건 ───────────────────────────────────────────
s = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})
tid1 = s.get("threadId")
expect("첫 쪽지 = 요청(waiting)", s["ok"] and thread(JUNIOR, tid1)["status"] == "waiting")
s = sendMessage(JUNIOR, {"to": SENIOR1, "text": "하나 더 여쭤봐도 될까요?"})
expect("같은 선배에게 또 보내면 같은 대화에 붙음", s["ok"] and s["threadId"] == tid1 and len(thread(JUNIOR, tid1)["messages"]) == 2)
s = sendMessage(SENIOR1, {"to": JUNIOR, "text": "안녕하세요"})
expect("선배는 수락 전에 답장할 수 없음", not s["ok"] and s["reason"] == "상태")
expect("선배 화면에 요청이 보임", thread(SENIOR1, tid1)["role"] == "senior")

# ── 3. 보낸 사람 수락 대기 3건 한도 ──────────────────────────────────────
others = ["H0751", "H0995", "H0745"]
sendMessage(JUNIOR, {"to": others[0], "text": HELLO})
sendMessage(JUNIOR, {"to": others[1], "text": HELLO})
m = getMessages(JUNIOR, {})
expect("waitingCount 3 / waitingLimit 3", m["waitingCount"] == 3 and m["waitingLimit"] == 3)
s = sendMessage(JUNIOR, {"to": others[2], "text": HELLO})
expect("4번째 요청은 한도", not s["ok"] and s["reason"] == "한도")

# ── 4. 요청 취소 → 한도에서 빠짐 · 선배 화면에서 사라짐 · 7일 재요청 금지 ──
tid_c = thread(JUNIOR, sendMessage(JUNIOR, {"to": others[0], "text": "추가"})["threadId"])["threadId"]
expect("남의 요청은 취소 못 함", "error" in respondRequest(SENIOR1, {"threadId": tid_c, "cancel": True}))
retry_c = (datetime.fromisoformat(rf.now()) + timedelta(days=rf.COOLDOWN_DAYS)).isoformat(timespec="seconds")
c = respondRequest(JUNIOR, {"threadId": tid_c, "cancel": True})
expect("취소 → cancelled + retryAt(취소 + 7일, KST)", c == {"ok": True, "status": "cancelled", "retryAt": retry_c}
       and retry_c.endswith("+09:00"))
expect("[11/24] getMessages 취소한 대화에 retryAt", thread(JUNIOR, tid_c).get("retryAt") == retry_c)
expect("취소 아닌 대화에는 retryAt 없음", "retryAt" not in thread(JUNIOR, tid1))
rs = {x["studentId"]: x for x in recommendSeniors(JUNIOR, {"noteId": MARBURG})["seniors"]}
expect("[11/24] recommendSeniors: 취소한 선배 카드에만 retryAt",
       (others[0] not in rs or rs[others[0]].get("retryAt") == retry_c)
       and all("retryAt" not in x for h, x in rs.items() if h != others[0]))
rf._threads()["T-retry"] = {"asker": JUNIOR, "senior": SENIOR2, "askerNickname": "x", "status": "cancelled",
                            "cancelledAt": rf.now(), "requestedAt": rf.now(), "messages": [], "lastRead": {}}
rs = {x["studentId"]: x for x in recommendSeniors(JUNIOR, {"noteId": MARBURG})["seniors"]}
expect("[11/24] 목록에 있는 선배를 취소하면 카드에 retryAt", SENIOR2 in rs and rs[SENIOR2].get("retryAt") == retry_c)
del rf._threads()["T-retry"]
expect("취소한 요청은 선배 목록에서 사라짐", thread(others[0], tid_c) is None)
expect("선배의 요청 알림도 지워짐", not any(a.get("threadId") == tid_c for a in getInbox(others[0], {})["alerts"]))
expect("보낸 사람에게는 cancelled로 남음", thread(JUNIOR, tid_c)["status"] == "cancelled")
expect("다시 취소하면 상태 오류", respondRequest(JUNIOR, {"threadId": tid_c, "cancel": True})["reason"] == "상태")
expect("취소 뒤 한도 2건", getMessages(JUNIOR, {})["waitingCount"] == 2)
s = sendMessage(JUNIOR, {"to": others[0], "text": HELLO})
expect("취소한 선배에게 7일 안 재요청 금지 + retryAt", not s["ok"] and s["reason"] == "취소" and s.get("retryAt") == retry_c)
s = sendMessage(JUNIOR, {"to": others[2], "text": HELLO})
expect("취소로 빈 자리에 다른 선배 요청", s["ok"])

# ── 5. 수락·거절 ───────────────────────────────────────────────────────
a = respondRequest(SENIOR1, {"threadId": tid1, "accept": True})
expect("선배 수락 → accepted", a["ok"] and a["status"] == "accepted")
expect("수락된 요청은 다시 수락 못 함", respondRequest(SENIOR1, {"threadId": tid1, "accept": True})["reason"] == "상태")
expect("수락하면 선배가 답장 가능", sendMessage(SENIOR1, {"to": JUNIOR, "text": "반가워요!"})["ok"])
expect("보낸 사람은 수락 요청을 취소 못 함", respondRequest(JUNIOR, {"threadId": tid1, "cancel": True})["reason"] == "상태")
expect("남이 수락·거절 못 함", "error" in respondRequest(JUNIOR, {"threadId": tid1, "accept": True}))

# ── 5-1. [11/23] 목록만 보면 읽음으로 바꾸지 않음 · {read: threadId}면 그 대화만 ──
later(0.01)   # 시계가 멈춰 있으면 보낸 시각 = 읽은 시각이라 조금 옮긴다
getMessages(JUNIOR, {"read": tid1})
later(0.01)
sendMessage(SENIOR1, {"to": JUNIOR, "text": "궁금한 것 물어보세요."})
expect("선배 답장 → 안 읽음 1", thread(JUNIOR, tid1)["unread"] == 1)
expect("목록을 다시 봐도 안 읽음 그대로(닮은선배 버튼 상태용 호출)", thread(JUNIOR, tid1)["unread"] == 1)
other_tid = next(t["threadId"] for t in getMessages(JUNIOR, {})["threads"] if t["threadId"] != tid1)
getMessages(JUNIOR, {"read": other_tid})
expect("다른 대화를 읽어도 이 대화는 안 읽음", thread(JUNIOR, tid1)["unread"] == 1)
opened = next(t for t in getMessages(JUNIOR, {"read": tid1})["threads"] if t["threadId"] == tid1)
expect("대화를 여는 응답은 읽기 전 수", opened["unread"] == 1)
expect("연 뒤 목록에서는 0", thread(JUNIOR, tid1)["unread"] == 0)
expect("선배 쪽 읽음은 그대로(본인 것만 바뀜)", thread(SENIOR1, tid1)["unread"] == 0)

# ── 6. 받는 선배 5건 한도 → requestsFull ────────────────────────────────
juniors = ["H0001", "H0002", "H0003", "H0004", "H0005", "H0006"]
juniors = [h for h in juniors if h in rf.score._data()[0]][:6]
unlock(*juniors)
for j in juniors[:5]:
    sendMessage(j, {"to": SENIOR2, "text": HELLO})
s = sendMessage(juniors[5], {"to": SENIOR2, "text": HELLO})
expect("받는 선배 수락 대기 5건이면 선배한도", not s["ok"] and s["reason"] == "선배한도")
r = recommendSeniors(JUNIOR, {"noteId": MARBURG})
full = {x["studentId"]: x["requestsFull"] for x in r["seniors"]}
expect("추천 카드에 requestsFull", full.get(SENIOR2) is True and full.get(SENIOR1) is False)

# ── 7. 7일 자동 만료 ───────────────────────────────────────────────────
later(7)
m = getMessages(JUNIOR, {})
expired = [t for t in m["threads"] if t["status"] == "expired"]
expect("7일 지난 waiting → expired, 한도에서 빠짐", len(expired) == 2 and m["waitingCount"] == 0)
expect("보낸 사람에게 만료 알림", sum(a["text"] == rf.EXPIRED_ALERT for a in getInbox(JUNIOR, {})["alerts"]) == 2)
expect("만료된 요청은 선배 목록에서 사라짐", thread(others[1], expired[0]["threadId"]) is None
       and thread(others[2], expired[0]["threadId"]) is None)
expect("[11/24] 7일 지나면 retryAt 없음", "retryAt" not in thread(JUNIOR, tid_c))
expect("받는 선배 한도도 풀림", not recommendSeniors(JUNIOR, {"noteId": MARBURG})["seniors"][1]["requestsFull"])
s = sendMessage(JUNIOR, {"to": others[0], "text": HELLO})
expect("7일 지나면 취소한 선배에게 다시 요청(같은 대화)", s["ok"] and s["threadId"] == tid_c
       and thread(JUNIOR, tid_c)["status"] == "waiting")
expect("수락된 대화는 만료되지 않음", thread(JUNIOR, tid1)["status"] == "accepted")

# ── 8. 옛 기록(status "requested") 호환 ─────────────────────────────────
store.load("messages", {})["T-old"] = {"asker": "H0010", "senior": SENIOR1, "askerNickname": "조용한 고래",
                                        "status": "requested", "createdAt": rf.now(), "messages": [], "lastRead": {}}
expect("옛 requested는 waiting으로 읽음", thread(SENIOR1, "T-old")["status"] == "waiting")

# ── 9. [작업 38 D-1] 상대 학번 대신 불투명 값 ─────────────────────────────
import json
import re
COLREG = re.compile(r"\bH\d{4}\b|\bstaff\d+\b")      # colreg_no 모양(가상학생 H0001~, 직원 staff01~)
raw_rec = rf.recommendSeniors(JUNIOR, {"noteId": MARBURG})
raw_msg = rf.getMessages(JUNIOR, {})
ref1 = rf.peer_ref(JUNIOR, SENIOR1)
card = next((x for x in raw_rec["seniors"] if x["studentId"] == ref1), None)
conv = next((t for t in raw_msg["threads"] if t["threadId"] == tid1), None)
expect("같은 선배: recommendSeniors.studentId == getMessages.withId", card is not None and conv is not None
       and card["studentId"] == conv["withId"])
expect("불투명 값은 'p' + 16자리, 학번 모양 아님", all(re.fullmatch(r"p[0-9a-f]{16}", x["studentId"]) for x in raw_rec["seniors"]))
expect("다시 불러도 같은 값", rf.recommendSeniors(JUNIOR, {"noteId": MARBURG})["seniors"][0]["studentId"]
       == raw_rec["seniors"][0]["studentId"])
expect("보는 사람마다 다른 값", rf.peer_ref(JUNIOR, SENIOR1) != rf.peer_ref("H0010", SENIOR1))
sen = next(t for t in rf.getMessages(SENIOR1, {})["threads"] if t["threadId"] == tid1)
expect("선배 쪽 withId(보낸 후배)도 불투명 값이고 되풀림", not COLREG.search(sen["withId"])
       and rf.resolve_peer(SENIOR1, sen["withId"]) == JUNIOR)
expect("선배가 받은 withId로 답장(수락된 대화)", rf.sendMessage(SENIOR1, {"to": sen["withId"], "text": "또 물어보세요."})["ok"])
n_before = len(rf._threads())
for label, to in [("학번 그대로", SENIOR1), ("남(H0010)에게 나간 값", rf.peer_ref("H0010", SENIOR1)),
                  ("엉터리 값", "p0123456789abcdef"), ("빈 값", ""), ("숫자", 12345)]:
    r = rf.sendMessage(JUNIOR, {"to": to, "text": HELLO})
    expect(f"sendMessage {label} → 거절", "error" in r and not r.get("ok"))
    expect(f"previewNickname {label} → 거절", "error" in rf.previewNickname(JUNIOR, {"to": to}))
expect("거절된 값으로 대화가 생기지 않음", len(rf._threads()) == n_before)
expect("내 값(peer_ref(나, 나))으로는 나에게 못 보냄",
       "error" in rf.sendMessage(JUNIOR, {"to": rf.peer_ref(JUNIOR, JUNIOR), "text": HELLO}))
pv = rf.previewNickname(JUNIOR, {"to": raw_rec["seniors"][-1]["studentId"]})
expect("previewNickname은 카드의 studentId로 동작", "myNickname" in pv)
seen = []
for who in (JUNIOR, SENIOR1, SENIOR2, others[0]):
    seen += [rf.getMessages(who, {}), getInbox(who, {}), rf.recommendSeniors(who, {"noteId": MARBURG})]
seen += [rf.sendMessage(JUNIOR, {"to": ref1, "text": "감사합니다!"}), pv]
leak = sorted({m for x in seen for m in COLREG.findall(json.dumps(x, ensure_ascii=False))})
expect(f"응답 전체에 colreg_no 모양 없음{' ' + str(leak[:5]) if leak else ''}", not leak)
import os
old_secret = os.environ.get("VCC_PEER_SECRET")
os.environ["VCC_PEER_SECRET"] = "test-secret-1"
other_ref = rf.peer_ref(JUNIOR, SENIOR1)
expect("비밀이 다르면 다른 값 + 옛 값은 안 풀림", other_ref != ref1 and rf.resolve_peer(JUNIOR, ref1) is None
       and rf.resolve_peer(JUNIOR, other_ref) == SENIOR1)
os.environ.pop("VCC_PEER_SECRET")
if old_secret is not None:
    os.environ["VCC_PEER_SECRET"] = old_secret
expect("비밀을 되돌리면 원래 값", rf.peer_ref(JUNIOR, SENIOR1) == ref1)

# ── 쪽지검사 AI 연결(작업 27 후속): 가짜 callAI로 3경우 + 코드 규칙 우선 + 한도·캐시 ─────
import limits
calls = []


def fake(reply):
    def f(task, messages, system=None, **k):
        calls.append((task, messages, system))
        return reply
    return f


def ai_check(text, reply, me="H0999"):
    rf._slander_cache.clear()
    calls.clear()
    rf._call_ai = fake(reply)
    return rf.checkMessage(me, {"text": text}), len(calls)


r, n = ai_check("그 정도도 몰라요?", {"ok": True, "json": {"ok": False, "reason": "비방"}})
expect("AI 비방 판정: 막힘(reason 비방, 기존 모양)", r["ok"] is False and r["reason"] == "비방" and r["message"] and n == 1)
expect("AI 호출: 작업명 쪽지검사·예시 대화·쪽지 원문", calls[0][0] == "쪽지검사" and calls[0][1][-1]["content"].startswith("쪽지: 그 정도도") and len(calls[0][1]) > 1)
r, n = ai_check(HELLO, {"ok": True, "json": {"ok": True}})
expect("AI 정상 판정: 통과", r == {"ok": True} and n == 1)
for label, reply in [("호출 실패", {"ok": False, "json": None, "error": "boom"}), ("json 없음", {"ok": True, "json": None}),
                     ("형식 오류", {"ok": True, "json": {"ok": "no"}}), ("엉뚱한 json", {"ok": True, "json": {"x": 1}})]:
    r, n = ai_check(HELLO, reply)
    expect(f"AI {label}: 통과로 보고 막지 않음", r == {"ok": True} and n == 1)
r, n = ai_check("제 번호 010-1234-5678이에요", {"ok": True, "json": {"ok": True}})
expect("코드 규칙에 걸리면 AI를 부르지 않음(연락처)", r["ok"] is False and r["reason"] == "연락처" and n == 0)
r, n = ai_check("한심하네요", {"ok": True, "json": {"ok": True}})
expect("금지어도 AI를 부르지 않음", r["ok"] is False and r["reason"] == "비방" and n == 0)
r, n = ai_check(HELLO, {"ok": True, "json": {"ok": False, "reason": "비방"}}, me=None)
expect("로그인 없는 호출은 AI를 부르지 않음(한도를 셀 수 없음)", r == {"ok": True} and n == 0)
# 같은 글을 checkMessage → sendMessage로 이어 보내면 AI는 한 번(5분 캐시)
r, n = ai_check(HELLO, {"ok": True, "json": {"ok": True}})
rf.checkMessage("H0999", {"text": HELLO})
expect("같은 글 두 번째는 캐시(AI 1회)", len(calls) == 1)
# 한도: 분당 10 넘으면 AI 없이 통과, 한도 카운트는 AI를 부를 때만
store_usage = store.load("aiUsage", {})
store_usage.pop("H0888", None)
rf._call_ai = fake({"ok": True, "json": {"ok": True}})
rf._slander_cache.clear()
calls.clear()
for i in range(12):
    rf.checkMessage("H0888", {"text": f"{HELLO} {i}"})
expect("분당 한도 10회: 11번째부터 AI 안 부르고 통과", len(calls) == limits.PER_MINUTE)
r = rf.checkMessage("H0888", {"text": HELLO + " 한도 뒤"})
expect("한도 뒤에도 쪽지는 통과", r == {"ok": True})
rf._call_ai = lambda *a, **k: {"ok": True, "json": {"ok": True}}

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
