# test_admin.py — 관리자 집계 함수 8개 (작업 66, PRD 5-5 완료 기준·7장 권한)
# 실행: cd functions && python test_admin.py
# AI 없음. 기록은 임시 폴더에 쓴다(data/runtime을 건드리지 않음). 하나라도 틀리면 종료코드 1.
import sys
from collections import Counter
import tempfile
from datetime import datetime
from pathlib import Path

import store

store.RUNTIME = Path(tempfile.mkdtemp()) / "runtime"

import admin
import runtime_fns as rf
import suggest

# 리포트 요약 AI는 부르지 않는다(실패 응답 → 템플릿 요약). AI 요약 검증은 test_suggest.py
suggest.callAI = lambda *a, **k: {"ok": False, "text": "", "json": None, "model": "fake", "error": "시험"}
from runtime_fns import add_question

clock = [datetime(2026, 11, 21, 10, 0, tzinfo=rf.KST)]
admin.now = rf.now = lambda: clock[0].isoformat(timespec="seconds")

BOSS, DEPT, STUDENT = "staff01", "staff02", "H0143"
SEM = {"type": "semester", "value": "2026-2"}
MONTH = {"type": "month", "value": "2026-10"}
fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def ov(dept, period=SEM, me=BOSS):
    return admin.getAdminOverview(me, {"dept": dept, "period": period})


# ── 1. 권한 ────────────────────────────────────────────────────────────
for name in admin.ROUTES:
    if admin.ROUTES[name](STUDENT, {"dept": "ALL"}) != admin.DENY:
        expect(f"학생은 {name} 거절", False)
expect("학생은 관리자 함수 전부 거절", True)
d = admin.getDepartments(BOSS, {})
expect("총괄은 부서 9개", len(d["departments"]) == 9 and d["role"] == "총괄")
d = admin.getDepartments(DEPT, {})
expect("부서 담당자는 자기 부서 1개(혁신지원팀 D04)", [x["부서코드"] for x in d["departments"]] == ["D04"] and d["fixed"] == "D04")
expect("부서 담당자가 ALL을 달라 해도 자기 부서로 고정", ov("ALL", me=DEPT)["dept"] == "D04" and ov("D01", me=DEPT)["dept"] == "D04")
expect("없는 부서코드는 거절", ov("D99") == admin.DENY)
expect("부서 담당자는 설정 저장 거절", "error" in admin.saveReportSettings(DEPT, {"settings": {"period": "semester", "day": 1,
                                                                                   "recipients": ["a@example.com"], "sections": ["지표"]}}))
expect("부서 담당자는 발행 거절", "error" in admin.issueReport(DEPT, {"period": SEM}))

# ── 2. 「전체」 = 부서별 합 + 분류 안 됨 (학기·월 모두) ──────────────────
for label, period in (("학기", SEM), ("월", MONTH)):
    total = ov("ALL", period)
    parts = sum(ov(c, period)["kpi"]["questions"]["value"] for c in admin.DEPT_BY_CODE)
    holds = sum(ov(c, period)["kpi"]["unanswered"]["value"] for c in admin.DEPT_BY_CODE)
    uncl_hold = sum(1 for q in admin._questions(*admin._parse_period(period)[:2]) if not q.get("운영부서코드") and q["status"] == "hold")
    expect(f"{label}: 전체 질문 = 부서 합 + 분류 안 됨", total["kpi"]["questions"]["value"] == parts + total["unclassified"])
    expect(f"{label}: 전체 미답변 = 부서 합 + 분류 안 된 보류", total["kpi"]["unanswered"]["value"] == holds + uncl_hold)
    expect(f"{label}: 프로그램 순위 합 = 분류된 질문 수", sum(r["questions"] for r in total["programs"]) == parts)

o = ov("ALL")
expect("학기 기본값 = 지금 학기(2026-2)", admin.getAdminOverview(BOSS, {"dept": "ALL"})["period"] == SEM)
expect("프로그램 순위는 질문 많은 순", [r["questions"] for r in o["programs"]] == sorted((r["questions"] for r in o["programs"]), reverse=True))
expect("학과 표는 상위 8 + 그 외", len(o["colleges"]) <= 9 and (len(o["colleges"]) < 9 or o["colleges"][-1]["학과"] == "그 외"))
expect("학과 표 합 = 질문 수", sum(c["questions"] for c in o["colleges"]) == o["kpi"]["questions"]["value"])
fields = {p["분야"] for p in admin.PROGRAMS.values() if p.get("분야")}
expect("sectionsByField 분야 이름은 programs.json 「분야」 값", set(o["sectionsByField"]) <= fields and len(o["sectionsByField"]) >= 2)
expect("sectionsByField 칸 합 ≤ sections 칸 합(분야 모르는 질문은 빠짐)",
       all(sum(d.get(k, 0) for d in o["sectionsByField"].values()) <= v for k, v in o["sections"].items()))
# 프로그램이 안 잡혀도 분야만 있는 질문(「교환학생 비용은?」)이 있어 분야 합 ≥ 프로그램 합
expect("sectionsByField ⊇ 프로그램별 sections를 분야로 합친 것",
       all(o["sectionsByField"].get(f, {}).get(k, 0) >= v for f in {p["분야"] for p in o["programs"] if p["분야"]}
           for k, v in sum((Counter(p["sections"]) for p in o["programs"] if p["분야"] == f), Counter()).items()))
expect("분야 있고 프로그램 없는 질문도 sectionsByField에 들어감",
       sum(sum(d.values()) for d in o["sectionsByField"].values()) > sum(sum(p["sections"].values()) for p in o["programs"]))
expect("부서 하나(D01)도 sectionsByField 있음", "sectionsByField" in ov("D01") and isinstance(ov("D01")["sectionsByField"], dict))
expect("노트 현황: 251개·근거 4798", o["notes"]["count"] == 251 and o["notes"]["evidence"] == 4798)
expect("증감은 정수 % 또는 None", all(v["delta"] is None or isinstance(v["delta"], int) for v in o["kpi"].values()))
expect("잘못된 기간은 오류", "error" in ov("ALL", {"type": "month", "value": "abc"}))

# ── 3. 시연 중 새 보류 질문 → 미답변 +1 ─────────────────────────────────
before_all, before_d1 = ov("ALL")["kpi"]["unanswered"]["value"], ov("D01")["kpi"]["unanswered"]["value"]
pending_before = admin.getAdminSuggestions(BOSS, {"dept": "D01", "period": SEM})["pendingNew"]
add_question(STUDENT, "마르부르크에서 학기 중 현지 인턴 병행할 수 있어요?", program="마르부르크필립스대학교", status="hold")
expect("새 보류 질문 → 전체 미답변 +1", ov("ALL")["kpi"]["unanswered"]["value"] == before_all + 1)
expect("새 보류 질문 → 국제교류팀 미답변 +1(부서는 프로그램으로 찾음)", ov("D01")["kpi"]["unanswered"]["value"] == before_d1 + 1)
expect("내 보관함 질문함에서는 status hold(spec 4장 getInbox)",
       [q["status"] for q in rf.getInbox(STUDENT, {})["questions"]] == ["hold"])
expect("개선 제안 탭 pendingNew +1", admin.getAdminSuggestions(BOSS, {"dept": "D01", "period": SEM})["pendingNew"] == pending_before + 1)

# ── 4. 개선 제안 · 상태 ─────────────────────────────────────────────────
sg = admin.getAdminSuggestions(BOSS, {"dept": "ALL", "period": SEM})
expect("제안이 있고 모두 3건 이상 묶음", sg["suggestions"] and all(s["count"] >= 3 for s in sg["suggestions"]))
expect("제안 유형은 세 가지 중 하나", all(s["유형"] in ("신규 수요", "안내 보강", "검토 필요") for s in sg["suggestions"]))
expect("근거 질문 목록에 학번 없음", all("colreg_no" not in q for s in sg["suggestions"] for q in s["questions"]))
expect("개선 요청 KPI = 「새로 옴」 제안 수", o["kpi"]["improvements"]["value"] == sum(s["status"] == "새로 옴" for s in sg["suggestions"]))
first = sg["suggestions"][0]
expect("없는 상태는 거절", "error" in admin.setSuggestionStatus(BOSS, {"id": first["id"], "status": "아무거나"}))
expect("상태 바꾸기", admin.setSuggestionStatus(BOSS, {"id": first["id"], "status": "검토 중"}) == {"ok": True})
expect("상태 바꾸면 개선 요청 -1", ov("ALL")["kpi"]["improvements"]["value"] == o["kpi"]["improvements"]["value"] - 1)
other = next((s for s in sg["suggestions"] if s["부서코드"] != "D04"), None)
expect("부서 담당자는 다른 부서 제안 상태를 못 바꿈", admin.setSuggestionStatus(DEPT, {"id": other["id"], "status": "보류"}) == admin.DENY)
expect("신고 진술 목록에 노트 문장", all(r["text"] for r in sg["reported"]))

# ── 5. 리포트 설정 · 발행 · 이력 ─────────────────────────────────────────
s = admin.getReportSettings(BOSS, {"dept": "D01"})
expect("기본 설정: 학기당·대표메일·항목 5개·예정 없음", s["period"] == "semester" and s["recipients"] == ["intl@example.com"]
       and len(s["sections"]) == 5 and s["nextIssueAt"] is None)
monthly = admin.saveReportSettings(BOSS, {"dept": "D01", "settings": {"period": "monthly", "day": 1,
                                                                     "recipients": ["intl@example.com"], "sections": ["지표"]}})
expect("월간은 저장 거절", "error" in monthly)
late = admin.saveReportSettings(BOSS, {"dept": "D01", "settings": {"period": "semester", "day": 61,
                                                                  "recipients": ["intl@example.com"], "sections": ["지표"]}})
expect("발행일 61은 거절(0~60)", "error" in late)
bad = admin.saveReportSettings(BOSS, {"dept": "D01", "settings": {"period": "semester", "day": 1,
                                                                 "recipients": ["intl@example.com", "잘못된주소"], "sections": ["지표"]}})
expect("이메일 형식 검사", "error" in bad and "잘못된주소" in bad["error"])
good = admin.saveReportSettings(BOSS, {"dept": "D01", "settings": {"period": "semester", "day": 1,
                                                                  "recipients": ["intl@example.com", "boss@example.com"],
                                                                  "sections": ["지표", "프로그램 순위", "개선 제안"]}})
expect("설정 저장 → 다음 발행 2027-03-01(학기 종료 1일 뒤)", good == {"ok": True, "nextIssueAt": "2027-03-01"})
store._cache.clear()   # 서버를 껐다 켠 것처럼 메모리를 비우고 파일에서 다시 읽는다
s = admin.getReportSettings(BOSS, {"dept": "D01"})
expect("새로고침해도 설정 유지", s["recipients"] == ["intl@example.com", "boss@example.com"] and s["nextIssueAt"] == "2027-03-01")

r = admin.issueReport(BOSS, {"dept": "D01", "period": SEM})
expect("지금 발행 → html·요약", r["reportId"] and "<article" in r["html"] and "국제교류팀" in r["html"] and r["summary"])
expect("요약 숫자는 집계에서 온 것", str(ov("D01")["kpi"]["questions"]["value"]) in r["summary"])
expect("포함 항목만 들어감(신고 진술 제외)", "rpt-reported" not in r["html"] and "rpt-kpi" in r["html"])
h = admin.listIssuedReports(BOSS, {"dept": "D01"})["reports"]
expect("이력 +1(수동, 받는 사람 2명)", len(h) == 1 and h[0]["mode"] == "manual" and h[0]["recipients"] == 2)
expect("이력 열기", admin.getIssuedReport(BOSS, {"reportId": r["reportId"]})["html"] == r["html"])
expect("부서 담당자는 다른 부서 리포트를 못 엶", admin.getIssuedReport(DEPT, {"reportId": r["reportId"]}) == admin.DENY)
expect("부서 담당자 받은 리포트 목록은 자기 부서만", admin.listIssuedReports(DEPT, {"dept": "D01"})["reports"] == [])

# 예정일이 지나면 호출할 때 자동 발행(스케줄러 없음)
clock[0] = datetime(2027, 3, 1, 9, 0, tzinfo=rf.KST)
h = admin.listIssuedReports(BOSS, {"dept": "D01"})["reports"]
expect("3/1이 되면 자동 발행 1건(지난 학기 2026-2)", len(h) == 2 and h[0]["mode"] == "auto" and h[0]["period"] == SEM)
h = admin.listIssuedReports(BOSS, {"dept": "D01"})["reports"]
expect("같은 날 다시 불러도 또 발행하지 않음", len(h) == 2)
expect("다음 예정은 9/1", admin.getReportSettings(BOSS, {"dept": "D01"})["nextIssueAt"] == "2027-09-01")

# [11/27] 서버에 남은 옛 monthly 설정은 읽을 때 semester로 본다(저장값은 안 건드림)
old = {"period": "monthly", "day": 15, "recipients": ["intl@example.com"], "sections": ["지표"],
       "saved": True, "savedAt": clock[0].isoformat(), "by": BOSS}
store.load("reportSettings", {})["D02"] = old
s = admin.getReportSettings(BOSS, {"dept": "D02"})
expect("옛 monthly 저장값 → semester로 읽힘", s["period"] == "semester" and s["day"] == 15 and s["nextIssueAt"] == "2027-03-15"
       and old["period"] == "monthly")

# ── 6. 리포트 HTML은 글자를 escape ──────────────────────────────────────
evil = "<script>alert(1)</script>"
admin.USAGE["questions"] += [{"id": f"X{i}", "at": f"2026-10-0{i}T10:00:00+09:00", "colreg_no": "H0100", "crs_nm": "<img src=x onerror=alert(1)>",
                              "프로그램명": "마르부르크필립스대학교", "칸": "생활", "status": "hold", "질문": evil,
                              "운영부서코드": "D01"} for i in range(1, 10)]   # 9건 — 가장 큰 묶음이라 리포트 맨 앞에 실림
admin.saveReportSettings(BOSS, {"dept": "D01", "settings": {"period": "semester", "day": 1, "recipients": ["a@example.com"],
                                                           "sections": admin.SECTIONS}})
r = admin.issueReport(BOSS, {"dept": "D01", "period": SEM})
expect("XSS 글자는 escape(<script> 없음)", "<script>" not in r["html"] and "&lt;script&gt;" in r["html"] and "<img" not in r["html"])

# ── 7. 발행일 0일 = 학기 종료 당일 발행, 그날 끝나는 학기를 집계 (Q-120) ──────
for dept, saved, due, value in (("D03", datetime(2027, 8, 1), datetime(2027, 8, 31), "2027-1"),
                                ("D05", datetime(2028, 2, 1), datetime(2028, 2, 29), "2027-2")):
    clock[0] = saved.replace(tzinfo=rf.KST)
    admin.saveReportSettings(BOSS, {"dept": dept, "settings": {"period": "semester", "day": 0,
                                                              "recipients": ["a@example.com"], "sections": ["지표"]}})
    clock[0] = due.replace(hour=9, tzinfo=rf.KST)
    h = admin.listIssuedReports(BOSS, {"dept": dept})["reports"]
    expect(f"발행일 0: {due:%Y-%m-%d} 자동 발행은 {value} 집계",
           len(h) == 1 and h[0]["mode"] == "auto" and h[0]["period"] == {"type": "semester", "value": value})

print()
if fails:
    print(f"틀림 {len(fails)}건")
    sys.exit(1)
print("모두 통과")
