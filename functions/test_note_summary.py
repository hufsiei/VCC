# test_note_summary.py — getNote 칸별 요약 문단 summary·newLines (작업 78, spec 4장 getNote [v2])
# 실행: cd functions && python test_note_summary.py
# notes.json에 summary가 아직 없으므로 메모리의 마르부르크 노트에 summary를 넣어 시험한다. AI 없음.
# 기록은 임시 폴더에 쓴다(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import json
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import notes

fails = []


def expect(name, ok):
    print(("통과 " if ok else "실패 ") + name)
    if not ok:
        fails.append(name)


def sec(note, name):
    return next((s for s in note["sections"] if s["name"] == name), None)


NID, PROGRAM, ME = "N-marburg", "마르부르크필립스대학교", "H0143"
base = notes.NOTES[NID]
cost_ids = [ln["sourceId"] for ln in sec(base, "비용")["lines"]]
life_ids = [ln["sourceId"] for ln in sec(base, "생활")["lines"]]
sec(base, "비용")["summary"] = [
    {"text": "한 달 생활비는 110만~140만 원 사이였어요.", "sources": cost_ids[:2], "years": [2025, 2026]},
    {"text": "정착 초기 비용은 따로 들어요.", "sources": cost_ids[2:3], "years": [2026]}]
sec(base, "생활")["summary"] = [{"text": "기숙사는 합격 직후 신청해야 해요.", "sources": life_ids[:1], "years": [2025]}]
sec(base, "배운점")["summary"] = [{"text": "합친 배운점", "sources": ["R149-1-1"], "years": [2025]}]
sec(base, "팁")["summary"] = [{"text": "근거 없는 문장", "sources": [], "years": []}]
sec(base, "지원").pop("summary", None)  # #188 이후 notes.json에 지원 summary가 있어 시험 안에서 뺀다

# 1) 인터뷰 문장이 없을 때
n = notes.getNote(ME, {"id": NID})
expect("비용: summary 그대로 + newLines 0", sec(n, "비용")["summary"] == sec(base, "비용")["summary"]
       and sec(n, "비용")["newLines"] == 0)
expect("원문 lines는 그대로(접기용)", len(sec(n, "비용")["lines"]) == len(cost_ids))
expect("배운점은 summary 없음(원문 인용)", "summary" not in sec(n, "배운점") and "newLines" not in sec(n, "배운점"))
expect("sources 없는 요약 문장은 버림 → 다 빠지면 summary·newLines 생략",
       "summary" not in sec(n, "팁") and "newLines" not in sec(n, "팁"))
expect("summary 없는 칸은 newLines도 없음", "summary" not in sec(n, "지원") and "newLines" not in sec(n, "지원"))

# 2) 인터뷰로 새 문장 2개 → 생활 newLines 2, lines 끝 2개가 새 문장
with store.lock():
    rows = store.load("noteLines", [])
    for i, t in enumerate(["기숙사 대신 WG에 살았어요.", "첫 달은 행정 처리로 바빴어요."]):
        rows.append({"noteId": NID, "program": PROGRAM, "section": "생활", "text": t,
                     "sourceId": f"I-90{i}", "semester": "2026-1", "at": f"2026-11-23T10:0{i}"})
    store.save("noteLines")
n = notes.getNote(ME, {"id": NID})
life = sec(n, "생활")
expect("생활: newLines 2 = lines 끝 2개가 인터뷰 문장", life["newLines"] == 2
       and [ln["sourceId"] for ln in life["lines"][-2:]] == ["I-900", "I-901"])
expect("문단은 다시 만들지 않음", life["summary"] == sec(base, "생활")["summary"])
expect("비용은 newLines 0 그대로", sec(n, "비용")["newLines"] == 0)

# 3) 요약 근거 문장을 신고하면 그 요약 문장만 빠진다
with store.lock():
    store.load("reported", {})["L-" + cost_ids[2]] = {"reason": "기타"}
    store.save("reported")
n = notes.getNote(ME, {"id": NID})
expect("신고한 문장을 근거로 든 요약 문장은 빠짐", [s["text"] for s in sec(n, "비용")["summary"]] == ["한 달 생활비는 110만~140만 원 사이였어요."])
with store.lock():
    store.load("reported", {})["L-" + life_ids[0]] = {"reason": "기타"}
    store.save("reported")
n = notes.getNote(ME, {"id": NID})
expect("요약 문장이 다 빠지면 summary·newLines 생략(원문 목록)", "summary" not in sec(n, "생활") and "newLines" not in sec(n, "생활"))
expect("사전 생성 노트(메모리)는 그대로", len(sec(base, "비용")["summary"]) == 2)

# 4) mock(common/mock-data.json) 마르부르크도 같은 모양
mock = json.loads((Path(__file__).resolve().parent.parent / "common" / "mock-data.json").read_text(encoding="utf-8"))
m = mock["getNote"][NID]
with_summary = [s for s in m["sections"] if s.get("summary")]
expect("mock: summary 칸 1개 이상, 배운점 없음", with_summary and all(s["name"] != "배운점" for s in with_summary))
expect("mock: 요약 문장마다 sources(노트 sources에 있음)·years",
       all(x["sources"] and all(sid in m["sources"] for sid in x["sources"]) and x["years"]
           for s in with_summary for x in s["summary"]))
expect("mock: newLines ≤ lines 수, 끝 N개는 인터뷰 문장",
       all(0 <= s["newLines"] <= len(s["lines"])
           and all(m["sources"][ln["sourceId"]]["docType"] == "인터뷰" for ln in s["lines"][len(s["lines"]) - s["newLines"]:])
           for s in with_summary))

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
