# test_judge_asklog.py — 실사용 답 채점(Q-13) 시험. AI는 가짜(돈을 쓰지 않는다), 결과 파일은 임시 폴더.
# 보는 것: ① 새 기록만 고름(id, 옛 기록은 시각+질문) ② 채점 입력에 앞 턴·판단값·답 문장·근거 원문 ③ JSON 형식 검사
#         ④ 실패한 건은 남기지 않아 다음에 다시 ⑤ --max 상한 ⑥ 기본 실행은 AI를 부르지 않음
# 실행: cd functions && python -X utf8 test_judge_asklog.py
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import askboo  # noqa: E402
import judge_asklog as J  # noqa: E402

fails = []


def expect(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  — {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


PROGRAM = "마르부르크필립스대학교"
EV = askboo.EVIDENCE[PROGRAM][0]
LOG = [
    {"id": "a1", "at": "2026-11-25T14:08", "status": "notes", "question": "인턴십 보통 언제 하는지", "lines": [],
     "programs": ["KOTRA 해외무역관(유럽 권역)"], "message": "관련 해봤노트가 5개 있어요.", "route": "질문정리", "intent": "탐색",
     "field": "현장실습", "section": None, "asked": None, "prev": None},
    {"id": "a2", "at": "2026-11-25T14:09", "status": "ok", "question": "마르부르크 기숙사 어땠어요?",
     "lines": [{"text": "기숙사는 괜찮았어요.", "cites": [EV["id"]]}], "programs": [PROGRAM], "message": None,
     "route": "질문정리", "intent": "경험질문", "field": "국제교류", "section": "생활", "asked": None,
     "prev": {"question": "인턴십 보통 언제 하는지", "status": "notes", "program": ""}},
    {"at": "2026-11-24T10:00", "status": "hold", "question": "옛 기록(id 없음)", "lines": [], "programs": [], "message": "보류"},
    {"id": "a3", "at": "2026-11-25T14:10", "status": "chat", "question": "이게 다야?", "lines": [], "programs": [], "message": "…",
     "route": "후속(더)", "prev": {"question": "인턴십 보통 언제 하는지", "status": "notes", "program": ""}},
]

# ② 채점 입력
txt = J.record_text(LOG[1])
expect("입력: 앞 턴·판단값·결과", "앞 턴: 후배: 인턴십 보통 언제 하는지 → BOO: 노트 안내" in txt and "의도=경험질문" in txt
       and "칸=생활" in txt and "결과: 답함" in txt, txt)
expect("입력: 답 문장에 근거 번호, 근거 원문", "기숙사는 괜찮았어요. [근거 1]" in txt and f"[1] {EV['text']}" in txt, txt)
expect("입력: 앞 턴 없음·답 문장 없음 표시", "앞 턴: (없음)" in J.record_text(LOG[0]) and "답 문장: (없음)" in J.record_text(LOG[0]))
expect("입력이 프롬프트 예시처럼 「출력:」으로 끝남", txt.endswith("\n출력:"))

# ③ 형식 검사
expect("형식: 정상", J.parse({"답했나": 3, "근거": 5, "길": 4, "이유": "x"}, True) == {"답했나": 3, "근거": 5, "길": 4, "이유": "x"})
expect("형식: 답 문장 없으면 근거 null", J.parse({"답했나": 3, "근거": 4, "길": 4, "이유": "x"}, False)["근거"] is None)
expect("형식: 범위 밖·문자·bool·이유 없음은 버림", all(J.parse(j, True) is None for j in (
    {"답했나": 6, "근거": 5, "길": 4, "이유": "x"}, {"답했나": "3", "근거": 5, "길": 4, "이유": "x"},
    {"답했나": True, "근거": 5, "길": 4, "이유": "x"}, {"답했나": 3, "근거": 5, "길": 4}, None, [])))

# ①④⑤ 실행
calls = []


def fake(작업명, messages, system=None):
    calls.append((작업명, messages[-1]["content"], system))
    if "옛 기록" in messages[-1]["content"]:
        return {"ok": True, "text": "모르겠어요", "json": None, "model": "fake"}   # 형식 오류 → 남기지 않음
    return {"ok": True, "text": "", "json": {"답했나": 2, "근거": 5, "길": 4, "이유": "핵심 비켜 감"}, "model": "fake"}


with tempfile.TemporaryDirectory() as d:
    path = Path(d) / "ask-judge.jsonl"
    ok, fail = J.run(LOG, 2, call=fake, path=path)
    expect("상한 --max 2: 두 건만", ok == 2 and fail == 0 and len(calls) == 2)
    expect("작업명 채점 + 프롬프트 파일", calls[0][0] == "채점" and "채점관" in (calls[0][2] or ""))
    ok, fail = J.run(LOG, 50, call=fake, path=path)
    expect("다시 돌리면 새 기록만(옛 기록 실패 1 + a3 1)", ok == 1 and fail == 1 and len(calls) == 4, (ok, fail, len(calls)))
    rows = J.read_judged(path)
    expect("결과 줄: 열쇠·점수·이유", [r["key"] for r in rows] == ["a1", "a2", "a3"] and rows[0]["이유"] == "핵심 비켜 감"
           and rows[0]["근거"] is None and rows[1]["근거"] == 5)
    expect("실패한 옛 기록은 다음에 다시 대상", [J.key_of(r) for r in J.new_rows(LOG, J.judged_keys(path))] == ["2026-11-24T10:00|옛 기록(id 없음)"])
    expect("요약 글", "채점 3건" in J.summary(rows) and "답했나 평균 2.0" in J.summary(rows))
    expect("결과에 학번 칸 없음", "H0" not in path.read_text(encoding="utf-8"))

# ⑥ 기본 실행은 AI를 부르지 않는다(건수·예상 금액만)
import ai  # noqa: E402
called = []
ai_call = ai.callAI
ai.callAI = lambda *a, **k: called.append(1)
J.load_log = lambda local: LOG
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = J.main(["--local"])
ai.callAI = ai_call
out = buf.getvalue()
expect("기본 실행: AI 안 부름, 예상 금액·오늘 사용액 출력", code == 0 and not called and "예상 $" in out and "오늘 내 AI $" in out, out)
expect("예상 금액은 Opus 단가로", 0 < J.estimate(1) < 0.1)

print()
print("실패 %d개" % len(fails) if fails else "전부 통과")
sys.exit(1 if fails else 0)
