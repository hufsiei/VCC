# test_report_log.py — 요약 문장 신고 · askBoo 답 기록 · 기록 내보내기 (작업 33, 11/25)
# 실행: cd functions && python test_report_log.py
# AI는 가짜로 바꿔 돈을 쓰지 않는다. 기록은 임시 폴더에 쓴다(data/runtime·드라이브를 건드리지 않음). 하나라도 틀리면 종료코드 1.
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import admin
import askboo
import export_runtime
import notes
import runtime_fns
from runtime_fns import reportStatement

fails = []


def expect(name, ok):
    print(("통과 " if ok else "실패 ") + name)
    if not ok:
        fails.append(name)


def sec(note, name):
    return next((s for s in note["sections"] if s["name"] == name), None)


NID, PROGRAM, ME, OTHER = "N-marburg", "마르부르크필립스대학교", "H0143", "H0745"
base = notes.NOTES[NID]
cost_ids = [ln["sourceId"] for ln in sec(base, "비용")["lines"]]
for s in base["sections"]:   # 사전 생성 summary 대신 아래 가짜 값으로 시험
    s.pop("summary", None)
sec(base, "비용")["summary"] = [
    {"text": "한 달 생활비는 110만~140만 원 사이였어요.", "sources": cost_ids[:2], "years": [2025, 2026]},
    {"text": "정착 초기 비용은 따로 들어요.", "sources": cost_ids[2:3], "years": [2026]}]

# 1) 요약 문장 id
n = notes.getNote(ME, {"id": NID})
summ = sec(n, "비용")["summary"]
ids = [s.get("lineId") for s in summ]
expect("요약 문장마다 lineId(S-…), 서로 다름", len(ids) == 2 and all(i and i.startswith("S-") for i in ids) and ids[0] != ids[1])
expect("다시 읽어도 같은 id", [s["lineId"] for s in sec(notes.getNote(OTHER, {"id": NID}), "비용")["summary"]] == ids)
expect("사전 생성 노트(메모리)에는 lineId를 쓰지 않음", all("lineId" not in s for s in sec(base, "비용")["summary"]))

# 2) 사유가 없으면 신고를 받지 않는다(요약·원문 모두)
for reason in (None, "", "   "):
    r = reportStatement(ME, {"lineId": ids[0], "reason": reason})
    expect(f"사유 {reason!r} → error", r == {"error": "신고 사유를 적어 주세요"})
expect("원문 문장도 사유 없으면 error", reportStatement(ME, {"lineId": "L-" + cost_ids[0]}) == {"error": "신고 사유를 적어 주세요"})
expect("사유 없는 신고는 기록·숨김 없음", not store.load("reported", {})
       and len(sec(notes.getNote(ME, {"id": NID}), "비용")["summary"]) == 2)
expect("lineId 없으면 error", "error" in reportStatement(ME, {"reason": "기타"}))
expect("없는 요약 문장 id는 error", "error" in reportStatement(ME, {"lineId": "S-0000000000", "reason": "기타"}))

# 3) 요약 문장 신고 → 그 문장만 바로 빠진다
r = reportStatement(ME, {"lineId": ids[0], "reason": "사실과 달라요. 연락은 010-1234-5678"})
expect("신고 응답", r == {"ok": True, "hidden": True})
after = sec(notes.getNote(OTHER, {"id": NID}), "비용")
expect("신고한 요약 문장만 빠짐", [s["lineId"] for s in after["summary"]] == ids[1:])
expect("원문 lines는 그대로", len(after["lines"]) == len(cost_ids))
rec = store.load("reported", {})[ids[0]]
expect("기록: 문장 글·noteId·칸·사유·시각", rec["text"] == summ[0]["text"] and rec["noteId"] == NID and rec["section"] == "비용"
       and rec["kind"] == "summary" and rec["reason"].startswith("사실과") and rec["at"] and rec["status"] == "숨김 중")
reportStatement(ME, {"lineId": ids[1], "reason": "기타"})
expect("요약 문장이 다 빠지면 summary 생략", "summary" not in sec(notes.getNote(ME, {"id": NID}), "비용"))

# 4) 기존 원문 문장 신고도 그대로
reportStatement(OTHER, {"lineId": "L-" + cost_ids[0], "reason": "기타"})
n = notes.getNote(ME, {"id": NID})
expect("원문 문장 신고 → 노트에서 숨김", all(ln["sourceId"] != cost_ids[0] for ln in sec(n, "비용")["lines"]))
expect("원문 신고 기록에도 글·칸", store.load("reported", {})["L-" + cost_ids[0]].get("section") == "비용")
expect("사유는 100자까지", len(store.load("reported", {})[ids[0]]["reason"]) <= runtime_fns.REASON_MAX)

# 5) 콘솔 집계(getAdminSuggestions.reported)에 요약 문장 신고가 든다
rep = admin.getAdminSuggestions("staff01", {})   # 기간 없음 = 지금 학기
mine = [x for x in rep.get("reported", []) if x["lineId"] == ids[0]]
expect("콘솔 집계에 요약 문장 신고", len(mine) == 1 and mine[0]["noteId"] == NID and mine[0]["program"] == PROGRAM
       and mine[0]["text"] == summ[0]["text"] and mine[0]["kind"] == "summary" and mine[0]["sourceText"] is None)
expect("콘솔 집계: 원문 신고는 kind line", any(x["lineId"] == "L-" + cost_ids[0] and x["kind"] == "line" for x in rep["reported"]))


# 6) askBoo 답 기록
def fake_call(작업명, messages, system=None):
    return {"ok": False, "text": "", "json": None, "model": "fake"}   # AI 실패 → 정규식 경로(v1)로 답한다


askboo.callAI = fake_call
r = askboo.askBoo(ME, {"question": "휴학하고 교환학생 가도 되나요? 제 번호는 010-9999-8888"})
log = store.load("askLog", [])
expect("규정 질문 → official 한 줄 기록", r["status"] == "official" and len(log) == 1 and log[0]["status"] == "official")
expect("응답에 기록용 칸(_program)이 새지 않음", "_program" not in r)
expect("기록 칸: 시각·질문·답 문장·프로그램·안내 문구", set(log[0]) == {"at", "status", "question", "lines", "programs", "noteId", "message"}
       and log[0]["at"] and log[0]["message"] == r["message"])
expect("기록에 사람 칸 없음(학번·questionId)", ME not in json.dumps(log, ensure_ascii=False) and "questionId" not in log[0])
expect("기록의 질문은 가려짐", "010-9999" not in log[0]["question"] and "[연락처]" in log[0]["question"])
r = askboo.askBoo(ME, {"question": "마르부르크 기숙사 어땠어요?", "force": "hold"})
expect("hold도 기록", r["status"] == "hold" and len(log) == 2 and log[1]["status"] == "hold" and log[1]["lines"] == [])
askboo.askBoo("eval", {"question": "마르부르크 기숙사 어땠어요?", "force": "hold"}, save=False)
expect("평가(save=False)는 남기지 않음", len(store.load("askLog", [])) == 2)
expect("빈 질문(error)은 남기지 않음", "error" in askboo.askBoo(ME, {"question": " "}) and len(store.load("askLog", [])) == 2)
askboo._log_answer("답이 있는 질문", {"status": "ok", "noteId": NID, "sources": {"R1": {"program": PROGRAM}},
                               "lines": [{"text": "기숙사는 일찍 신청해요.", "cites": ["R1"], "sourceId": "R1", "lineId": "L-A1-1"}]})
expect("ok 답: 문장·cites·프로그램", log[2]["lines"] == [{"text": "기숙사는 일찍 신청해요.", "cites": ["R1"]}] and log[2]["programs"] == [PROGRAM])
saved = json.loads((store.RUNTIME / "askLog.json").read_text(encoding="utf-8"))
expect("askLog.json에 저장됨", len(saved) == 3)

# 7) 내보내기 --dry: 시트 4개, 글은 가려지고 학번이 없다
with store.lock():
    store.load("messages", {})["T-0001"] = {
        "asker": ME, "senior": "H0469", "askerNickname": "차분한 수달", "status": "accepted", "createdAt": "2026-11-25T10:00",
        "messages": [{"from": ME, "text": "안녕하세요, 메일 abc@hufs.ac.kr 로 연락 주세요", "at": "2026-11-25T10:00"},
                     {"from": "H0469", "text": "=1+1 네 좋아요", "at": "2026-11-25T10:05"}], "lastRead": {}}
    store.save("messages")
    store.load("threadReports", []).append({"threadId": "T-0001", "by": "H0469", "role": "senior", "reason": "광고",
                                            "block": True, "at": "2026-11-25T10:06"})
    store.save("threadReports")
    store.load("noteLines", []).append({"noteId": NID, "program": PROGRAM, "section": "생활", "text": "학번 201912345 선배예요. WG에 살았어요.",
                                        "sourceId": "I-0901", "semester": "2026-1", "official": False, "owner": "H0469",
                                        "myNoteId": "M-0001", "draftLineId": "D1", "at": "2026-11-25T09:00"})
    store.save("noteLines")
    store.load("myNotes", {})["M-0001"] = {"owner": "H0469", "program": PROGRAM, "myNote": {"sections": [
        {"name": "생활", "lines": [{"text": "나만 보는 문장 비밀"}]}]}}
    store.save("myNotes")
sheets = export_runtime.build_sheets(store.load)
expect("시트 4개", list(sheets) == ["신고", "물어보기", "들려주기", "쪽지"])
expect("행 수: 신고 4(문장 3 + 쪽지 1)·물어보기 3·들려주기 1·쪽지 2",
       [len(v) - 1 for v in sheets.values()] == [4, 3, 1, 2])
flat = json.dumps(sheets, ensure_ascii=False)
expect("학번·학번 칸 없음", not any(x in flat for x in ("H0143", "H0469", "H0745", "colreg_no", "201912345")))
expect("연락처·메일 가려짐", not any(x in flat for x in ("010-1234", "010-9999", "abc@hufs")) and "[메일]" in flat and "[연락처]" in flat)
expect("쪽지는 역할만", [row[3] for row in sheets["쪽지"][1:]] == ["선배", "후배"] and "수달" not in flat)
expect("나만 보기 문장은 싣지 않음", "비밀" not in flat)
expect("요약 문장 신고 행", any(row[1] == "요약 문장" and row[5] == summ[0]["text"] and row[4] == "비용" for row in sheets["신고"][1:]))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    code = export_runtime.main(["--dry", "--local"])
out = buf.getvalue()
expect("--dry: 종료코드 0, 시트 이름 4개 출력", code == 0 and all(f"[{k}]" in out for k in sheets))
expect("--dry 출력도 가려짐·학번 없음", not any(x in out for x in ("H0143", "H0469", "010-1234", "abc@hufs")))
expect("--dry는 파일을 쓰지 않음", not list(store.RUNTIME.parent.rglob("*.xlsx")))

# 8) 엑셀 쓰기(임시 폴더): 「=」로 시작하는 글이 수식이 되지 않는다
# openpyxl은 requirements.txt(배포 zip)에 없다. 없는 PC는 엑셀을 여는 검사(8번·9번 끝)만 건너뛴다.
try:
    import openpyxl
except ImportError:
    openpyxl = None
    print("openpyxl 없음 — 엑셀 검사 건너뜀(python -m pip install openpyxl)")

xlsx = store.RUNTIME.parent / "out.xlsx"
if openpyxl:
    export_runtime.write_xlsx(sheets, xlsx)
    wb = openpyxl.load_workbook(xlsx)
    cell = next(c for row in wb["쪽지"].iter_rows(min_row=2) for c in row if str(c.value or "").startswith("=1+1"))
    expect("엑셀: 시트 4개 + 수식 아님", wb.sheetnames == list(sheets) and cell.data_type == "s")

# 9) askLog는 최근 ASK_LOG_MAX건만 남고, 잘려 나간 앞 기록은 엑셀 물어보기 시트에 이어 남는다
askboo.ASK_LOG_MAX, askboo.ASK_LOG_SLACK = 5, 2
for i in range(10):
    askboo._log_answer(f"질문 {i}", {"status": "hold", "lines": [], "message": "보류"})
log = store.load("askLog", [])
expect("askLog 상한: 최근 것만(5~7건), 마지막이 가장 최근", 5 <= len(log) <= 7 and log[-1]["question"] == "질문 9"
       and all(r["question"] != "답이 있는 질문" for r in log)
       and len(json.loads((store.RUNTIME / "askLog.json").read_text(encoding="utf-8"))) == len(log))
if openpyxl:
    merged = export_runtime.keep_old_rows(export_runtime.build_sheets(store.load), xlsx)
    asked = [row[2] for row in merged["물어보기"][1:]]
    expect("내보내기: 잘린 앞 기록도 시트에 남고 겹치지 않음", "답이 있는 질문" in asked and "질문 9" in asked and len(asked) == len(set(asked))
           and len(asked) == len(log) + 3)

print(f"\n{len(fails)}건 실패" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
