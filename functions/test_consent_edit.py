# test_consent_edit.py — 공개 동의 시트에서 고친 문장 (saveConsent edits.changed, 11/23)
# 실행: cd functions && python test_consent_edit.py
# 기준: docs/spec-v1.md 4장 saveConsent [11/20]·[11/23 고치기]. AI 없음. 기록은 임시 폴더(data/runtime을 건드리지 않음). 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import runtime_fns as rf
from runtime_fns import getMyNote, saveConsent

SENIOR, OTHER = "H0469", "H0102"
PROGRAM = "마르부르크필립스대학교"
AI_1 = "특강이 끝나고 질의응답 때 궁금한 것을 직접 여쭤봤어요."
AI_2 = "2~3학년에게 추천한다고 했어요."
AI_3 = "기숙사는 한 달에 300유로였어요."
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def pub_line(line_id):
    note = store.load("myNotes", {})["M-0001"]
    return next(ln for s in note["publicDraft"]["sections"] for ln in s["lines"] if ln["lineId"] == line_id)


def shared_texts():
    return sorted(r["text"] for r in store.load("noteLines", []) if r.get("myNoteId") == "M-0001")


store.load("myNotes", {})["M-0001"] = {
    "owner": SENIOR, "program": PROGRAM, "draftId": "D-0001", "share": "private", "answered": 3,
    "myNote": {"sections": [{"name": "생활", "lines": [{"text": "질의응답 때 직접 여쭤봤다."},
                                                     {"text": "2~3학년에게 추천한다고 했다."},
                                                     {"text": "기숙사는 한 달에 300유로였다."}]}]},
    "publicDraft": {"sections": [{"name": "생활", "lines": [
        {"lineId": "L-D1-1", "text": AI_1, "match": True, "identifying": False},
        {"lineId": "L-D1-2", "text": AI_2, "match": False, "identifying": False},
        {"lineId": "L-D1-3", "text": AI_3, "match": True, "identifying": False}]}]},
}

# ── 1. 고친 문장이 해봤노트와 공개 초안에 함께 들어감 ─────────────────
MINE = "2~3학년에게 추천하고 싶어요."
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True,
                         "edits": {"removed": [], "changed": [{"lineId": "L-D1-2", "text": f"  {MINE}  "}]}})
expect("공유 성공·3문장", r.get("ok") is True and r.get("added") == 3 and "rejected" not in r)
expect("해봤노트에 고친 문장(앞뒤 공백 제거)", MINE in shared_texts() and AI_2 not in shared_texts())
ln = pub_line("L-D1-2")
expect("공개 초안 text가 고친 문장", ln["text"] == MINE)
expect("edited 표시 + aiText에 AI 원래 문장", ln.get("edited") is True and ln.get("aiText") == AI_2)
expect("고친 문장은 match 표시를 지움", "match" not in ln)
expect("고치지 않은 문장은 그대로", pub_line("L-D1-1")["text"] == AI_1 and "edited" not in pub_line("L-D1-1"))
my = store.load("myNotes", {})["M-0001"]["myNote"]["sections"][0]["lines"][1]["text"]
expect("내 경험노트 문장은 따로(그대로)", my == "2~3학년에게 추천한다고 했다.")

# ── 2. 다시 열어 공유(공유 범위 바꾸기)해도 고친 문장 유지 ────────────
v = getMyNote(SENIOR, {"id": "M-0001"})
life = next(s for s in v["sections"] if s["name"] == "생활")
expect("getMyNote publicText가 고친 문장", life["lines"][1]["publicText"] == MINE)
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True, "edits": {"removed": ["L-D1-1"], "changed": []}})
expect("다시 공유: 2문장, 고친 문장 유지", r.get("added") == 2 and MINE in shared_texts() and AI_2 not in shared_texts())
expect("두 번째로 고쳐도 aiText는 처음 AI 문장", saveConsent(SENIOR, {"draftId": "D-0001", "consent": True, "edits": {
    "removed": [], "changed": [{"lineId": "L-D1-2", "text": "2~3학년에게 꼭 추천해요."}]}})["ok"]
       and pub_line("L-D1-2")["aiText"] == AI_2)

# ── 3. 빈 문장·긴 문장·연락처 ────────────────────────────────────────
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True,
                         "edits": {"removed": [], "changed": [{"lineId": "L-D1-1", "text": "   "}]}})
expect("빈 문장은 고침으로 보지 않음(원래 문장 공유)", r.get("ok") and "rejected" not in r and pub_line("L-D1-1")["text"] == AI_1)
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True,
                         "edits": {"removed": [], "changed": [{"lineId": "L-D1-3", "text": "가" * (rf.MAX_EDIT_CHARS + 1)}]}})
expect("긴 문장은 rejected 길이", [x["reason"] for x in r.get("rejected", [])] == ["길이"])
expect("거절된 문장은 공개 초안을 바꾸지 않음", pub_line("L-D1-3")["text"] == AI_3)
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True,
                         "edits": {"removed": [], "changed": [{"lineId": "L-D1-3", "text": "궁금하면 010-1234-5678로 연락 주세요."}]}})
expect("연락처는 rejected(기존 검사)", len(r.get("rejected", [])) == 1 and pub_line("L-D1-3")["text"] == AI_3
       and not any("010" in t for t in shared_texts()))

# ── 4. 남의 초안은 못 고침 ────────────────────────────────────────────
r = saveConsent(OTHER, {"draftId": "D-0001", "consent": True,
                        "edits": {"removed": [], "changed": [{"lineId": "L-D1-1", "text": "남이 고친 문장이에요."}]}})
expect("남의 초안은 볼 수 없는 기록", r == {"error": "볼 수 없는 기록이에요"} and pub_line("L-D1-1")["text"] == AI_1)

# ── 5. [11/25 작업 35 P3] 근거 건수 기준 — 공개 동의 시트(consent.js)와 해봤노트 상단이 같은 수 ──────
# 시연 재현: 시트 「60→61건」(인터뷰 1건) vs 노트 상단 64건(문장 4개). 기준은 spec 5장 evidenceCount
# = 보고서 문단 + 동의 인터뷰 「문장」 수. 시트는 「listNotes 근거 − 이 경험노트의 sharedLines + 켠 문장 수」로 센다.
import notes


def list_count():
    card = next(c for c in notes.listNotes(SENIOR, {"filter": {"q": PROGRAM}})["notes"] if c["program"] == PROGRAM)
    return card["evidenceCount"]


def sheet_after(before, my_note_id, on):
    """consent.js renderTarget과 같은 셈."""
    shared = rf.getMyNote(SENIOR if my_note_id == "M-0001" else OTHER, {"id": my_note_id})["sharedLines"]
    return max(0, before - shared) + on if on else before


lines4 = ["학기 중에는 수업이 많아 인턴을 병행하기 어려웠어요.", "방학에는 단기 인턴을 했어요.",
          "준비 과정은 처음 생각보다 할 일이 많았어요.", "기숙사 인터넷은 직접 신청해야 해서 첫 2주는 없었어요."]
store.load("myNotes", {})["M-0002"] = {
    "owner": OTHER, "program": PROGRAM, "draftId": "D-0002", "share": "private", "answered": 3,
    "myNote": {"sections": [{"name": "생활", "lines": [{"text": t} for t in lines4]}]},
    "publicDraft": {"sections": [{"name": "생활", "lines": [
        {"lineId": f"L-D2-{i}", "text": t, "match": True, "identifying": False} for i, t in enumerate(lines4, 1)]}]},
}
before = list_count()
want = sheet_after(before, "M-0002", 4)
r = saveConsent(OTHER, {"draftId": "D-0002", "consent": True, "edits": {"removed": []}})
after = list_count()
expect("처음 공유 4문장: 근거는 +4(+1 아님)", r.get("added") == 4 and after == before + 4)
expect("시트 셈 = 공유 뒤 listNotes", want == after)
expect("해봤노트 상단(getNote) = listNotes", notes.getNote(OTHER, {"id": r["noteId"]})["evidenceCount"] == after)

before = list_count()
want = sheet_after(before, "M-0002", 2)
r = saveConsent(OTHER, {"draftId": "D-0002", "consent": True, "edits": {"removed": ["L-D2-1", "L-D2-2"]}})
expect("다시 공유(4→2문장): 이미 실린 문장은 바뀌어 끼워짐 → 근거 −2", list_count() == before - 2 == want)
before = list_count()
want = sheet_after(before, "M-0001", 3)
r = saveConsent(SENIOR, {"draftId": "D-0001", "consent": True, "edits": {"removed": []}})
expect("다른 선배 노트 다시 공유도 같은 셈", r.get("added") == 3 and list_count() == want)

print(f"\n{'통과' if not fails else '실패'}: {len(fails)}건 틀림")
sys.exit(1 if fails else 0)
