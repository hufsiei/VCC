# test_recommend_optout.py — 닮은선배 추천받기 끄기 setRecommendable (11/23)
# 실행: cd functions && python test_recommend_optout.py
# 기준: docs/spec-v1.md 4장 setRecommendable. AI 없음. 기록은 임시 폴더(data/runtime을 건드리지 않음). 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import notes
import runtime_fns as rf
rf._call_ai = lambda *a, **k: {"ok": True, "json": {"ok": True}}   # 시험은 실제 AI를 부르지 않는다(쪽지검사 연결, 작업 27)
from account import getMe
from runtime_fns import recommendSeniors, respondRequest, sendMessage, setRecommendable

JUNIOR, OTHER, SENIOR1 = "H0143", "H0102", "H0469"   # SENIOR1 = 시연 선배1(마르부르크 경험)
NOTE = notes.note_id("마르부르크필립스대학교")
HELLO = "안녕하세요, 마르부르크 파견 준비가 궁금해서 쪽지 드려요."
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def ids(me, more=False):
    return [s["studentId"] for s in recommendSeniors(me, {"noteId": NOTE, "more": more})["seniors"]]


store.load("demands", []).extend({"id": f"R-{h}", "owner": h} for h in (JUNIOR, OTHER))   # 선배 추천 열림

# ── 1. 기본은 켬 ──────────────────────────────────────────────────────
expect("getMe 기본 recommendable true", getMe(SENIOR1, {})["recommendable"] is True)
expect("기본: 선배1이 추천 목록에 있음", SENIOR1 in ids(JUNIOR))

# ── 2. 형식 검사 ──────────────────────────────────────────────────────
expect("on이 없으면 오류", "error" in setRecommendable(SENIOR1, {}))
expect("on이 글자면 오류", "error" in setRecommendable(SENIOR1, {"on": "false"}))

# ── 3. 끄기 → 후보·새 요청에서 빠짐 ──────────────────────────────────
expect("끄기 응답", setRecommendable(SENIOR1, {"on": False}) == {"ok": True, "recommendable": False})
expect("끄기 두 번도 같은 결과(멱등)", setRecommendable(SENIOR1, {"on": False})["recommendable"] is False)
expect("getMe recommendable false", getMe(SENIOR1, {})["recommendable"] is False)
expect("이미 본 목록에서도 빠짐", SENIOR1 not in ids(JUNIOR))
expect("처음 보는 사람 목록에도 없음", SENIOR1 not in ids(OTHER) and SENIOR1 not in ids(OTHER, more=True))
s = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})
expect("새 쪽지 요청은 reason 추천 제외", s == {"ok": False, "reason": "추천 제외", "message": rf.OPT_OUT_MESSAGE})

# ── 4. 다시 켜기 → 돌아옴 ─────────────────────────────────────────────
expect("켜기 응답", setRecommendable(SENIOR1, {"on": True}) == {"ok": True, "recommendable": True})
expect("다시 켜면 목록에 돌아옴", SENIOR1 in ids(OTHER) or SENIOR1 in ids(OTHER, more=True))

# ── 5. 이미 수락한 대화는 끈 뒤에도 이어짐 ────────────────────────────
tid = sendMessage(JUNIOR, {"to": SENIOR1, "text": HELLO})["threadId"]
respondRequest(SENIOR1, {"threadId": tid, "accept": True})
setRecommendable(SENIOR1, {"on": False})
expect("수락한 대화: 후배가 계속 보냄", sendMessage(JUNIOR, {"to": SENIOR1, "text": "감사합니다!"})["ok"])
expect("수락한 대화: 선배도 답함", sendMessage(SENIOR1, {"to": JUNIOR, "text": "네, 물어보세요."})["ok"])

# ── 6. 내 설정만 바뀜 ────────────────────────────────────────────────
expect("다른 사람 설정은 그대로", getMe(OTHER, {})["recommendable"] is True)

print(f"\n{'통과' if not fails else '실패'}: {len(fails)}건 틀림")
sys.exit(1 if fails else 0)
