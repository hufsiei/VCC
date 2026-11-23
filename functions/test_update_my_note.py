# test_update_my_note.py — 내 경험노트 문장 고치기 updateMyNote (11/23)
# 실행: cd functions && python test_update_my_note.py
# 기준: docs/spec-v1.md 4장 updateMyNote. AI 없음. 기록은 임시 폴더(data/runtime을 건드리지 않음). 틀리면 종료코드 1.
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import runtime_fns as rf
from runtime_fns import getMyNote, saveConsent, updateMyNote

SENIOR, OTHER = "H0469", "H0102"
MY_1 = "나는 질의응답 때 궁금한 점을 직접 여쭤봤다."
MY_2 = "2~3학년에게 추천한다고 했다."
PUB_2 = "2~3학년에게 추천한다고 했어요."
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def life(view):
    return next(s for s in view["sections"] if s["name"] == "생활")["lines"]


def stored(i):
    return store.load("myNotes", {})["M-0001"]["myNote"]["sections"][0]["lines"][i]


store.load("myNotes", {})["M-0001"] = {
    "owner": SENIOR, "program": "마르부르크필립스대학교", "draftId": "D-0001", "share": "private", "answered": 3,
    "updatedAt": "2026-11-23T10:00:00+09:00",
    "myNote": {"sections": [{"name": "생활", "lines": [{"text": MY_1}, {"text": MY_2}]}]},
    "publicDraft": {"sections": [{"name": "생활", "lines": [
        {"lineId": "L-D1-1", "text": "질의응답 때 궁금한 점을 직접 여쭤봤어요.", "match": True, "identifying": False},
        {"lineId": "L-D1-2", "text": PUB_2, "match": True, "identifying": False}]}]},
}

# ── 1. 고치기 → 내 경험노트만 바뀜 ───────────────────────────────────
MINE = "2~3학년에게 꼭 추천하고 싶다. 나도 2학년 때 들었으면 좋았을 것 같다."
r = updateMyNote(SENIOR, {"id": "M-0001", "changed": [{"section": "생활", "index": 1, "text": f" {MINE} "}]})
expect("응답 ok + getMyNote 모양", r.get("ok") is True and r.get("id") == "M-0001" and "sections" in r)
expect("응답의 문장이 고친 문장(공백 제거) + edited", life(r)[1]["text"] == MINE and life(r)[1].get("edited") is True)
expect("고치지 않은 문장은 edited 없음", "edited" not in life(r)[0])
expect("저장: aiText에 처음 AI 문장", stored(1).get("aiText") == MY_2 and stored(1)["text"] == MINE)
expect("해봤노트 공개 문장은 그대로", life(r)[1]["publicText"] == PUB_2)
expect("updatedAt 갱신", store.load("myNotes", {})["M-0001"]["updatedAt"] != "2026-11-23T10:00:00+09:00")
expect("getMyNote에도 edited", life(getMyNote(SENIOR, {"id": "M-0001"}))[1].get("edited") is True)

# ── 2. 두 번째 고침: aiText는 처음 그대로 ────────────────────────────
updateMyNote(SENIOR, {"id": "M-0001", "changed": [{"section": "생활", "index": 1, "text": "2~3학년에게 추천하고 싶다."}]})
expect("두 번째 고침도 aiText는 처음 AI 문장", stored(1)["aiText"] == MY_2)
r = updateMyNote(SENIOR, {"id": "M-0001", "changed": [{"section": "생활", "index": 0, "text": MY_1}]})
expect("같은 문장으로 저장하면 고침 아님", r.get("ok") and "edited" not in stored(0))

# ── 3. 형식 오류: 아무것도 안 바뀜 ───────────────────────────────────
before = stored(0)["text"]
for name, payload in [
    ("changed 없음", {"id": "M-0001"}),
    ("빈 목록", {"id": "M-0001", "changed": []}),
    ("없는 칸", {"id": "M-0001", "changed": [{"section": "비용", "index": 0, "text": "가"}]}),
    ("범위 밖 index", {"id": "M-0001", "changed": [{"section": "생활", "index": 5, "text": "가"}]}),
    ("index가 글자", {"id": "M-0001", "changed": [{"section": "생활", "index": "0", "text": "가"}]}),
    ("index가 true", {"id": "M-0001", "changed": [{"section": "생활", "index": True, "text": "가"}]}),
]:
    expect(f"오류: {name}", "error" in updateMyNote(SENIOR, payload))
r = updateMyNote(SENIOR, {"id": "M-0001", "changed": [{"section": "생활", "index": 0, "text": "바뀌면 안 됨"},
                                                     {"section": "생활", "index": 1, "text": "   "}]})
expect("빈 문장 오류 + 어느 문장인지", r.get("error") and r.get("index") == 1)
expect("하나라도 틀리면 아무것도 안 바뀜", stored(0)["text"] == before)
r = updateMyNote(SENIOR, {"id": "M-0001", "changed": [{"section": "생활", "index": 0, "text": "가" * (rf.MAX_EDIT_CHARS + 1)}]})
expect("300자 넘으면 오류", "error" in r and stored(0)["text"] == before)

# ── 4. 남의 노트·없는 노트 ───────────────────────────────────────────
r = updateMyNote(OTHER, {"id": "M-0001", "changed": [{"section": "생활", "index": 0, "text": "남이 고침"}]})
expect("남의 노트는 볼 수 없는 기록", r == {"error": "볼 수 없는 기록이에요"} and stored(0)["text"] == before)
expect("없는 노트도 같은 오류", updateMyNote(SENIOR, {"id": "M-9999", "changed": [{"section": "생활", "index": 0, "text": "가"}]})
       == {"error": "볼 수 없는 기록이에요"})

# ── 5. 내 경험노트를 고친 뒤 공유해도 해봤노트에는 공개 문장이 간다 ────
saveConsent(SENIOR, {"draftId": "D-0001", "consent": True, "edits": {"removed": []}})
texts = [x["text"] for x in store.load("noteLines", [])]
expect("해봤노트에는 공개 문장(해요체)", PUB_2 in texts and not any("싶다" in t for t in texts))

print(f"\n{'통과' if not fails else '실패'}: {len(fails)}건 틀림")
sys.exit(1 if fails else 0)
