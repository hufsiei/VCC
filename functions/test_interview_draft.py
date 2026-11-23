# test_interview_draft.py — 인터뷰 중간 저장(작업 79, spec 4장 saveInterviewDraft·getInterviewDraft [v2]).
# 실행: cd functions && python test_interview_draft.py. AI는 가짜(요약 1번), 기록은 임시 폴더. 하나라도 틀리면 종료코드 1.
import json
import re
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import interview
import runtime_fns
from runtime_fns import ROUTES, getInterviewDraft, saveInterviewDraft

PROGRAM, OTHER_PROGRAM = "마르부르크필립스대학교", "국립동양언어문화대학교 (이날코)"
ME, YOU = "H0469", "H0745"
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


A = [{"section": "팁", "question": "후배에게 팁이 있나요?", "answer": "기숙사 인터넷은 입주 첫 주에 신청하세요.", "extra": "버림"},
     {"questionId": "Q-0001", "skipped": True}]

expect("ROUTES에 두 함수", ROUTES.get("saveInterviewDraft") is saveInterviewDraft and ROUTES.get("getInterviewDraft") is getInterviewDraft)
expect("초안 없으면 빈 answers", getInterviewDraft(ME, {"program": PROGRAM}) == {"answers": []})
expect("프로그램 없으면 오류", "error" in saveInterviewDraft(ME, {"answers": A}))

# 1) 저장 → 읽기
r = saveInterviewDraft(ME, {"program": PROGRAM, "answers": A})
expect("저장: ok·savedAt·expiresAt(7일 뒤)", r.get("ok") and r.get("savedAt") and
       datetime.fromisoformat(r["expiresAt"]) - datetime.fromisoformat(r["savedAt"]) == timedelta(days=7))
g = getInterviewDraft(ME, {"program": PROGRAM})
expect("읽기: 같은 answers(모르는 키는 버림)", g.get("savedAt") == r["savedAt"] and g["answers"] == [
    {k: v for k, v in A[0].items() if k != "extra"}, A[1]])
expect("본인만: 남은 못 읽음", getInterviewDraft(YOU, {"program": PROGRAM}) == {"answers": []})
expect("프로그램별: 다른 프로그램은 없음", getInterviewDraft(ME, {"program": OTHER_PROGRAM}) == {"answers": []})

# 2) 덧쓰기·상한
saveInterviewDraft(ME, {"program": PROGRAM, "answers": A[:1]})
expect("다시 저장하면 덧씀", len(getInterviewDraft(ME, {"program": PROGRAM})["answers"]) == 1)
long = [{"section": "팁", "question": f"질문 {i}", "answer": "가" * 1500} for i in range(40)]
saveInterviewDraft(YOU, {"program": PROGRAM, "answers": long})
gl = getInterviewDraft(YOU, {"program": PROGRAM})["answers"]
expect("상한: 30개·답 1000자", len(gl) == 30 and all(len(a["answer"]) == 1000 for a in gl))
expect("빈 answers면 초안을 지움", saveInterviewDraft(YOU, {"program": PROGRAM, "answers": []}).get("ok")
       and getInterviewDraft(YOU, {"program": PROGRAM}) == {"answers": []})

# 3) 7일 지나면 없음(읽을 때 파일에서도 지움)
saveInterviewDraft(YOU, {"program": OTHER_PROGRAM, "answers": A[:1]})
with store.lock():
    drafts = store.load("interviewDrafts", {})
    drafts[f"{YOU}|{OTHER_PROGRAM}"]["savedAt"] = (datetime.fromisoformat(runtime_fns.now()) - timedelta(days=7, minutes=1)).isoformat()
expect("7일 지나면 없음", getInterviewDraft(YOU, {"program": OTHER_PROGRAM}) == {"answers": []})
expect("지난 초안은 파일에서도 지움", f"{YOU}|{OTHER_PROGRAM}" not in store.load("interviewDrafts", {}))
expect("다른 사람의 지나지 않은 초안은 그대로", f"{ME}|{PROGRAM}" in store.load("interviewDrafts", {}))


# 4) summarizeInterview가 끝나면 초안을 지운다
def fake_call(작업명, messages, system=None):
    from ai import first_json
    c = messages[-1]["content"]
    text = (json.dumps({"문장": [re.search(r"답: (.*)\n출력", c, re.S).group(1)]}, ensure_ascii=False) if 작업명 == "요약"
            else {"일치검사": '{"일치":true}', "1인칭": "{}"}[작업명])
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


interview.callAI = fake_call
d = interview.summarizeInterview(ME, {"program": PROGRAM, "transcript": A[:1]})
expect("요약하면 초안 삭제", d.get("saved") and getInterviewDraft(ME, {"program": PROGRAM}) == {"answers": []})

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
