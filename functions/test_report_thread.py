# test_report_thread.py — 쪽지 신고·차단 reportThread (11/23, 작업 28 ⋮ 메뉴)
# 실행: cd functions && python test_report_thread.py
# 기준: docs/spec-v1.md 4장 reportThread. AI 없음. 기록은 임시 폴더(data/runtime을 건드리지 않음). 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import runtime_fns as rf
from runtime_fns import getInbox, getMessages, reportThread, respondRequest, sendMessage

JUNIOR, SENIOR1, SENIOR2, OTHER = "H0143", "H0469", "H0241", "H0102"
HELLO = "안녕하세요, 마르부르크 파견 준비가 궁금해서 쪽지 드려요."
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def thread(me, tid):
    return next((t for t in getMessages(me, {})["threads"] if t["threadId"] == tid), None)


store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in (JUNIOR, OTHER))   # 선배 추천 열림

# ── 1. 수락된 대화: 신고만 → 대화는 이어짐 ─────────────────────────────
tid = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})["threadId"]
respondRequest(SENIOR1, {"threadId": tid, "accept": True})
r = reportThread(SENIOR1, {"threadId": tid, "reason": "불쾌한 표현이 있어요"})
expect("신고만: reported, 차단 아님", r == {"ok": True, "reported": True, "blocked": False, "status": "accepted"})
rec = store.load("threadReports", [])
expect("신고 기록: 대화·사람·역할·사유", len(rec) == 1 and rec[0]["threadId"] == tid and rec[0]["by"] == SENIOR1
       and rec[0]["role"] == "senior" and rec[0]["reason"] == "불쾌한 표현이 있어요")
expect("신고만 하면 계속 보낼 수 있음", sendMessage(JUNIOR, {"to": SENIOR1, "text": "감사합니다!"})["ok"])
expect("사유도 차단도 없으면 오류", "error" in reportThread(SENIOR1, {"threadId": tid}))
expect("사유 글자 수 상한", reportThread(SENIOR1, {"threadId": tid, "reason": "가" * 300})["ok"]
       and len(store.load("threadReports", [])[-1]["reason"]) == rf.REASON_MAX)

# ── 2. 남의 대화·없는 대화는 못 부름 ───────────────────────────────────
expect("남의 대화는 볼 수 없는 기록", reportThread(OTHER, {"threadId": tid, "reason": "기타"}) == {"error": "볼 수 없는 기록이에요"})
expect("없는 대화도 같은 오류", "error" in reportThread(JUNIOR, {"threadId": "T-9999", "block": True}))

# ── 3. 차단 → 양쪽 다 못 보냄, 상대에게 알림 없음 ───────────────────────
alerts_before = len(getInbox(JUNIOR, {})["alerts"])
r = reportThread(SENIOR1, {"threadId": tid, "reason": "불쾌한 표현이 있어요", "block": True})
expect("신고+차단", r["ok"] and r["reported"] and r["blocked"] and r["status"] == "blocked")
s = sendMessage(JUNIOR, {"to": SENIOR1, "text": "왜 답이 없으세요?"})
expect("차단당한 쪽은 reason 차단", s == {"ok": False, "reason": "차단", "message": rf.BLOCKED_MESSAGE})
expect("차단한 쪽도 못 보냄", sendMessage(SENIOR1, {"to": JUNIOR, "text": "안녕하세요"})["reason"] == "차단")
expect("상대에게 알림 없음", len(getInbox(JUNIOR, {})["alerts"]) == alerts_before)
expect("목록: 차단한 쪽 blockedByMe true", thread(SENIOR1, tid)["blockedByMe"] is True and thread(SENIOR1, tid)["status"] == "blocked")
expect("목록: 차단당한 쪽 blockedByMe false", thread(JUNIOR, tid)["blockedByMe"] is False)
expect("차단된 대화는 수락·취소 못 함", respondRequest(SENIOR1, {"threadId": tid, "accept": True})["reason"] == "상태"
       and respondRequest(JUNIOR, {"threadId": tid, "cancel": True})["reason"] == "상태")
expect("다시 차단해도 그대로", reportThread(JUNIOR, {"threadId": tid, "block": True})["status"] == "blocked"
       and store.load("messages", {})[tid]["blockedBy"] == SENIOR1)
expect("차단만(사유 없음)은 신고 기록을 늘리지 않음", len(store.load("threadReports", [])) == 3)

# ── 4. 보낸 사람이 기다리는 요청을 차단 → 한도에서 빠지고 선배 요청 알림 지움 ──
tid2 = sendMessage(OTHER, {"to": SENIOR2, "text": HELLO})["threadId"]
expect("요청 알림이 선배에게 감", any(a.get("threadId") == tid2 for a in getInbox(SENIOR2, {})["alerts"]))
r = reportThread(OTHER, {"threadId": tid2, "block": True})
expect("asker 차단: 신고 없이 blocked", r["ok"] and not r["reported"] and r["blocked"])
expect("한도에서 빠짐", getMessages(OTHER, {})["waitingCount"] == 0)
expect("선배의 요청 알림 지움", not any(a.get("threadId") == tid2 for a in getInbox(SENIOR2, {})["alerts"]))
expect("차단 전 상태 기록", store.load("messages", {})[tid2]["statusBeforeBlock"] == "waiting")

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
