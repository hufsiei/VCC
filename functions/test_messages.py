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
from runtime_fns import getInbox, getMessages, recommendSeniors, respondRequest, sendMessage

JUNIOR, SENIOR1, SENIOR2 = "H0143", "H0469", "H0241"
MARBURG = "N-marburg"
BIG = "HUFS 동문멘토링 데이"      # 경험자 141명 — 9명 상한 확인용
HELLO = "안녕하세요, 마르부르크 파견 준비가 궁금해서 쪽지 드려요."
fails = []

# 시계: 테스트가 날짜를 옮길 수 있게 runtime_fns.now를 바꾼다
clock = [datetime(2026, 11, 21, 10, 0, tzinfo=rf.KST)]
rf.now = lambda: clock[0].isoformat(timespec="seconds")


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
expect("잠김: 닉네임 미리보기도 막힘", rf.previewNickname(JUNIOR, {"to": SENIOR1}).get("locked") is True)
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
c = respondRequest(JUNIOR, {"threadId": tid_c, "cancel": True})
expect("취소 → cancelled", c == {"ok": True, "status": "cancelled"})
expect("취소한 요청은 선배 목록에서 사라짐", thread(others[0], tid_c) is None)
expect("선배의 요청 알림도 지워짐", not any(a.get("threadId") == tid_c for a in getInbox(others[0], {})["alerts"]))
expect("보낸 사람에게는 cancelled로 남음", thread(JUNIOR, tid_c)["status"] == "cancelled")
expect("다시 취소하면 상태 오류", respondRequest(JUNIOR, {"threadId": tid_c, "cancel": True})["reason"] == "상태")
expect("취소 뒤 한도 2건", getMessages(JUNIOR, {})["waitingCount"] == 2)
s = sendMessage(JUNIOR, {"to": others[0], "text": HELLO})
expect("취소한 선배에게 7일 안 재요청 금지", not s["ok"] and s["reason"] == "취소")
s = sendMessage(JUNIOR, {"to": others[2], "text": HELLO})
expect("취소로 빈 자리에 다른 선배 요청", s["ok"])

# ── 5. 수락·거절 ───────────────────────────────────────────────────────
a = respondRequest(SENIOR1, {"threadId": tid1, "accept": True})
expect("선배 수락 → accepted", a["ok"] and a["status"] == "accepted")
expect("수락된 요청은 다시 수락 못 함", respondRequest(SENIOR1, {"threadId": tid1, "accept": True})["reason"] == "상태")
expect("수락하면 선배가 답장 가능", sendMessage(SENIOR1, {"to": JUNIOR, "text": "반가워요!"})["ok"])
expect("보낸 사람은 수락 요청을 취소 못 함", respondRequest(JUNIOR, {"threadId": tid1, "cancel": True})["reason"] == "상태")
expect("남이 수락·거절 못 함", "error" in respondRequest(JUNIOR, {"threadId": tid1, "accept": True}))

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
expect("받는 선배 한도도 풀림", not recommendSeniors(JUNIOR, {"noteId": MARBURG})["seniors"][1]["requestsFull"])
s = sendMessage(JUNIOR, {"to": others[0], "text": HELLO})
expect("7일 지나면 취소한 선배에게 다시 요청(같은 대화)", s["ok"] and s["threadId"] == tid_c
       and thread(JUNIOR, tid_c)["status"] == "waiting")
expect("수락된 대화는 만료되지 않음", thread(JUNIOR, tid1)["status"] == "accepted")

# ── 8. 옛 기록(status "requested") 호환 ─────────────────────────────────
store.load("messages", {})["T-old"] = {"asker": "H0010", "senior": SENIOR1, "askerNickname": "조용한 고래",
                                        "status": "requested", "createdAt": rf.now(), "messages": [], "lastRead": {}}
expect("옛 requested는 waiting으로 읽음", thread(SENIOR1, "T-old")["status"] == "waiting")

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
