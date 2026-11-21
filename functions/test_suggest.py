# test_suggest.py — 개선 제안·리포트 요약 사후 검증 (작업 67)
# 실행: cd functions && python test_suggest.py
# AI는 가짜로 바꿔 돈을 쓰지 않는다. 하나라도 틀리면 종료코드 1.
import json
import sys
import tempfile
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import admin
import suggest

fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def fake(obj):
    text = json.dumps(obj, ensure_ascii=False)
    return lambda *a, **k: {"ok": True, "text": text, "json": obj, "model": "fake"}


PROG, SEC = "마르부르크필립스대학교", "학점"
QS = [{"at": f"2026-10-0{i}T10:00:00+09:00", "질문": f"{PROG} 학점 인정 신청은 언제 해요?"} for i in range(1, 4)]

# ── 1. 제안 검증 ──────────────────────────────────────────────────────
good = {"유형": "안내 보강", "제목": f"{PROG} 학점 인정 절차 안내", "제안": "학점 인정 신청 시기를 묻는 질문이 반복돼요. 공식 안내에 절차를 정리해 주세요."}
r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(good))
expect("정상 출력은 그대로 통과", r["제목"] == good["제목"] and r["제안"] == good["제안"] and r["유형"] == "안내 보강" and not r["problems"])
expect("id는 admin과 같은 규칙", r["id"] == admin._suggestion_id(PROG, SEC))

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제안="신청은 3월 15일까지예요. 안내를 보강해 주세요.")))
expect("입력에 없는 숫자 → 제안만 버림, 제목은 남김", r["제안"] == "" and r["제목"] == good["제목"] and "제안" in r["problems"])

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제안="https://evil.example 에 안내를 올려 주세요.")))
expect("URL → 제안 버림", r["제안"] == "" and "URL·HTML" in r["problems"]["제안"])

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제목="<img src=x onerror=alert(1)>")))
expect("HTML 태그 → 제목 버림(화면은 템플릿)", r["제목"] == "")

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제안="토플 점수 기준도 함께 안내해 주세요.")))
expect("입력에 없는 고유명사(시험명) → 제안 버림", r["제안"] == "" and any("고유명사" in p for p in r["problems"]["제안"]))

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제안="Erasmus 교환 안내를 보강해 주세요.")))
expect("입력에 없는 영문 → 제안 버림", r["제안"] == "")

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 유형="아무거나")))
expect("목록 밖 유형은 비움(admin이 코드 유형 사용)", r["유형"] == "")

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=lambda *a, **k: {"ok": False, "json": None, "model": "fake", "error": "시간 초과"})
expect("호출 실패 → 전부 비움", r["제목"] == "" and r["제안"] == "" and "호출" in r["problems"])

r = suggest.generate_one(PROG, SEC, "안내 보강", QS, call=fake(dict(good, 제안="가" * 200)))
expect("너무 긴 제안 → 버림", r["제안"] == "")

expect("숫자는 통째로 대조(입력 「2023」 안의 3은 통과 못 함)",
       suggest.check_generated("제안이 3건이에요.", "기간: 2023년") == ["숫자 3"])
expect("일반 낱말 FAQ는 허용", suggest.check_generated("FAQ로 정리해 주세요.", "프로그램: x") == [])

# ── 2. 캐시 → 콘솔 카드 ─────────────────────────────────────────────────
sid = admin._suggestion_id(PROG, SEC)
admin.SUGGESTION_TEXT[sid] = {"id": sid, "유형": "안내 보강", "제목": "캐시 제목", "제안": "캐시 제안"}
admin.USAGE["questions"] += [{"id": f"T{i}", "at": q["at"], "colreg_no": "H0100", "crs_nm": "독일어과", "프로그램명": PROG, "칸": SEC,
                              "status": "official", "질문": q["질문"], "운영부서코드": "D01"} for i, q in enumerate(QS)]
cards = admin.getAdminSuggestions("staff01", {"dept": "D01", "period": {"type": "semester", "value": "2026-2"}})["suggestions"]
card = next(c for c in cards if c["id"] == sid)
expect("콘솔 카드가 캐시 제목·제안을 씀", card["제목"] == "캐시 제목" and card["제안"] == "캐시 제안")
admin.SUGGESTION_TEXT[sid] = {"id": sid, "유형": "", "제목": "", "제안": ""}
card = next(c for c in admin.getAdminSuggestions("staff01", {"dept": "D01", "period": {"type": "semester", "value": "2026-2"}})["suggestions"] if c["id"] == sid)
expect("캐시가 비면 템플릿 제목·코드 유형", card["제목"] and card["제안"] == "" and card["유형"] in suggest.KINDS)

# ── 3. 리포트 요약 ─────────────────────────────────────────────────────
ov = admin._overview("D01", {"type": "semester", "value": "2026-2"})
ov["deptName"] = "국제교류팀"
n = ov["kpi"]["questions"]["value"]
text, src = suggest.ai_summary(ov, {"suggestions": cards}, call=fake({"요약": f"이번 학기 국제교류팀 질문은 {n}건이에요."}))
expect("입력 숫자만 쓴 요약은 통과", src == "ai" and str(n) in text)
text, src = suggest.ai_summary(ov, {"suggestions": cards}, call=fake({"요약": "질문이 지난 학기보다 37% 늘었어요."}))
expect("새로 계산한 숫자가 있으면 탈락 → 템플릿", text is None and src is None)
text, src = suggest.ai_summary(ov, {"suggestions": cards}, call=fake({"요약": "<script>alert(1)</script>"}))
expect("HTML이면 탈락", text is None)

suggest.callAI = fake({"요약": "질문이 지난 학기보다 37% 늘었어요."})
r = admin.issueReport("staff01", {"dept": "D01", "period": {"type": "semester", "value": "2026-2"}})
expect("issueReport: AI 요약 탈락 → 템플릿 요약", r["summarySource"] == "template" and r["summary"] == admin._summary(ov))
suggest.callAI = fake({"요약": f"이번 학기 국제교류팀 질문은 {n}건이에요."})
r = admin.issueReport("staff01", {"dept": "D01", "period": {"type": "semester", "value": "2026-2"}})
expect("issueReport: AI 요약 통과 → html에 들어감", r["summarySource"] == "ai" and f"{n}건이에요" in r["html"])

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
