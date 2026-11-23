# test_edited_lines.py — 고친 문장 수 editedLines (11/23, 다시 요약 경고용)
# 실행: cd functions && python test_edited_lines.py
# 기준: docs/spec-v1.md 4장 getInbox [11/23 고치기]. AI 없음. 기록은 임시 폴더(data/runtime을 건드리지 않음). 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

from runtime_fns import getInbox, getMyNote, saveConsent, save_my_note, updateMyNote

SENIOR = "H0469"
PROGRAM = "마르부르크필립스대학교"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def draft(n):
    my = {"sections": [{"name": "생활", "lines": [{"text": f"나는 {n}번째 요약 문장을 말했다."}, {"text": "기숙사는 300유로였다."}]}]}
    pub = {"sections": [{"name": "생활", "lines": [
        {"lineId": f"L-D{n}-1", "text": f"{n}번째 요약 문장이에요.", "match": True, "identifying": False},
        {"lineId": f"L-D{n}-2", "text": "기숙사는 300유로였어요.", "match": True, "identifying": False}]}]}
    return my, pub


def card():
    return next(c for c in getInbox(SENIOR, {})["myNotes"] if c["program"] == PROGRAM)


mid = save_my_note(SENIOR, PROGRAM, "D-0001", *draft(1), answered=3)
expect("처음 요약: editedLines 0", card()["editedLines"] == 0 and getMyNote(SENIOR, {"id": mid})["editedLines"] == 0)

updateMyNote(SENIOR, {"id": mid, "changed": [{"section": "생활", "index": 0, "text": "나는 고친 문장을 썼다."}]})
expect("내 경험노트 1문장 고침 → 1", card()["editedLines"] == 1)

saveConsent(SENIOR, {"draftId": "D-0001", "consent": True,
                     "edits": {"removed": [], "changed": [{"lineId": "L-D1-2", "text": "기숙사는 한 달 300유로였어요."}]}})
expect("공개 문장 1문장 고침 → 2(두 노트를 함께 셈)", card()["editedLines"] == 2)
expect("getMyNote도 같은 값", getMyNote(SENIOR, {"id": mid})["editedLines"] == 2)

updateMyNote(SENIOR, {"id": mid, "changed": [{"section": "생활", "index": 0, "text": "나는 다시 고친 문장을 썼다."}]})
expect("같은 문장을 다시 고쳐도 한 번만 셈", card()["editedLines"] == 2)

# 다시 요약(summarizeInterview → save_my_note)하면 두 초안이 새 AI 문장으로 바뀐다 → 경고가 필요한 이유
save_my_note(SENIOR, PROGRAM, "D-0002", *draft(2), answered=4)
expect("다시 요약하면 고친 문장이 사라짐(0)", card()["editedLines"] == 0)

print(f"\n{'통과' if not fails else '실패'}: {len(fails)}건 틀림")
sys.exit(1 if fails else 0)
