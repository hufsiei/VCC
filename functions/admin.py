# admin.py — 관리자 콘솔 집계 함수 (작업 66, PRD 5장·7장). AI 없음.
#
# 함수 모양: 함수(me, payload) -> dict  (me = X-Token으로 확인한 colreg_no, local_fn.py가 넣어 준다)
#   getDepartments · getAdminOverview · getAdminSuggestions · setSuggestionStatus
#   getReportSettings · saveReportSettings · issueReport · listIssuedReports  (+ getIssuedReport, getDeptReport)
#
# 집계 = data/usage-log.json(시드) + runtime/questions.json(시연 중 질문, add_question이 같은 모양으로 쌓음).
# 부서 = 질문의 프로그램 → programs.json의 운영부서코드. 프로그램이 안 잡힌 질문은 「전체」에만 들어가고 unclassified로 센다.
#   → 「전체」 = 부서별 합 + unclassified (PRD 5-5)
# 권한(PRD 7장): 직원(staff…)만. 총괄(crs_nm 「전체」)은 모든 부서, 부서 담당자는 서버가 dept를 자기 부서로 고정하고
#   saveReportSettings·issueReport를 거절한다. 학생이 부르면 {"error": "볼 수 없는 기록이에요"}.
# 개선 제안 묶음은 시드 로그로만 만든다(제안 문장은 작업 67이 data/suggestions.json에 미리 만들어 둔다 — 없으면 제목만).
#   시연 중 새로 생긴 보류·규정 질문은 pendingNew로만 센다(「새 질문 N건 — 다음 집계 때 제안 생성」).
# 리포트 요약은 issueReport 때 AI 1회(suggest.ai_summary, 실패하면 템플릿). 그래서 issueReport는 local_fn의 AI_ROUTES에 든다.
# 리포트는 서버 함수가 불릴 때 예정일이 지났으면 그 자리에서 자동 발행한다(스케줄러 없음, PRD 5-4).
import calendar
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import notes
import store
import suggest
from runtime_fns import now, student

DATA = Path(__file__).resolve().parent.parent / "data"
DENY = {"error": "볼 수 없는 기록이에요"}
SECTIONS = ["지표", "프로그램 순위", "미답변 질문", "개선 제안", "신고 진술"]   # 리포트 포함 항목(PRD 5-4)
STATUSES = ["새로 옴", "검토 중", "반영됨", "보류"]                              # 개선 제안 상태(PRD 5-3)
BUNDLE_MIN = 3                                                                  # 묶음이 되는 질문 수
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _json(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


DEPTS = _json("departments.json", [])
DEPT_BY_CODE = {d["부서코드"]: d for d in DEPTS}
PROGRAMS = {p["프로그램명"]: p for p in _json("programs.json", [])}
USAGE = _json("usage-log.json", {})
SUGGESTION_TEXT = {s.get("id"): s for s in _json("suggestions.json", []) if isinstance(s, dict)}   # 작업 67


# ---------- 권한 ----------
def _staff(me):
    """직원이면 (권한, 부서코드) — 총괄은 ("총괄", None). 직원이 아니면 None."""
    if not me or not str(me).startswith("staff"):
        return None
    dept = student(me).get("crs_nm") or ""
    if dept == "전체":
        return "총괄", None
    code = next((d["부서코드"] for d in DEPTS if d.get("부서명") == dept), None)
    return ("부서", code) if code else None


def _scope(me, p):
    """요청의 dept를 권한에 맞게 고친다. 돌려주는 값: (dept 코드 또는 "ALL", 권한) / 거절이면 (None, None)."""
    who = _staff(me)
    if not who:
        return None, None
    role, own = who
    if role == "부서":
        return own, role
    dept = p.get("dept") or "ALL"
    return (dept if dept == "ALL" or dept in DEPT_BY_CODE else None), role


# ---------- 기간 ----------
def _parse_period(period):
    """{type: semester|month, value} → (시작일, 끝 다음날, 정규화한 period). 없으면 지금 학기."""
    period = period or {}
    kind, value = period.get("type") or "semester", str(period.get("value") or "")
    today = datetime.fromisoformat(now()).date()
    try:
        if kind == "month":
            y, m = map(int, (value or f"{today.year}-{today.month}").split("-"))
            start = date(y, m, 1)
            end = date(y + (m == 12), m % 12 + 1, 1)
            return start, end, {"type": "month", "value": f"{y}-{m:02d}"}
        if not value:
            y = today.year if today.month >= 3 else today.year - 1
            value = f"{y}-{1 if 3 <= today.month <= 8 else 2}"
        y, t = map(int, value.split("-"))
        if t == 1:
            return date(y, 3, 1), date(y, 9, 1), {"type": "semester", "value": f"{y}-1"}
        return date(y, 9, 1), date(y + 1, 3, 1), {"type": "semester", "value": f"{y}-2"}
    except (ValueError, TypeError):
        return None, None, None


def _previous(period):
    kind, value = period["type"], period["value"]
    y, n = map(int, value.split("-"))
    if kind == "month":
        return {"type": "month", "value": f"{y - (n == 1)}-{(n - 2) % 12 + 1:02d}"}
    return {"type": "semester", "value": f"{y - 1}-2" if n == 1 else f"{y}-1"}


def _label(period):
    y, n = period["value"].split("-")
    return f"{y}년 {int(n)}월" if period["type"] == "month" else f"{y}년 {n}학기"


def _in(at, start, end):
    d = str(at or "")[:10]
    return start.isoformat() <= d < end.isoformat()


def _delta(cur, prev):
    """전 기간 대비 증감 %(정수). 전 기간이 0이면 None(화면은 배지를 숨김)."""
    return None if not prev else round((cur - prev) / prev * 100)


# ---------- 질문 모으기 ----------
def _dept_of(program):
    return (PROGRAMS.get(program) or {}).get("운영부서코드")


def _questions(start, end, seed_only=False):
    """기간 안 질문. 시드 로그 + (seed_only가 아니면) 시연 중 질문. 학생 행만(직원 제외)."""
    rows = [dict(q, _seed=True) for q in USAGE.get("questions", [])]
    if not seed_only:
        for q in store.load("questions", []):
            prog = q.get("프로그램명")
            rows.append(dict(q, 운영부서코드=q.get("운영부서코드") or _dept_of(prog),
                             분야=q.get("분야") or (PROGRAMS.get(prog) or {}).get("분야"), _seed=False))
    return [q for q in rows if _in(q.get("at"), start, end) and str(q.get("colreg_no", "")).startswith("H")]


def _filter(rows, dept, key="운영부서코드"):
    return rows if dept == "ALL" else [r for r in rows if r.get(key) == dept]


def _filter_program(rows, dept, key="프로그램명"):
    return rows if dept == "ALL" else [r for r in rows if _dept_of(r.get(key)) == dept]


# ---------- 노트 칸이 비었는지 ----------
def _section_lines(program, section):
    nid = notes.note_id(program)
    note = notes.NOTES.get(nid)
    n = 0
    if note:
        n += sum(len(s.get("lines", [])) for s in note.get("sections", []) if s.get("name") == section)
    n += sum(1 for r in store.load("noteLines", []) if r.get("noteId") == nid and r.get("section") == section)
    return n, bool(note)


def _gap(program, section):
    """노트가 없거나 그 칸이 비었으면 True(신규 수요 조건)."""
    lines, has_note = _section_lines(program, section)
    return not has_note or (section is not None and lines == 0)


# ---------- 묶음(신규 수요·개선 제안) ----------
def _bundles(rows):
    """보류·규정 질문을 프로그램·칸으로 묶는다. 3건 이상 묶음만. 프로그램 없는 질문은 묶지 않는다."""
    groups = defaultdict(list)
    for q in rows:
        if q.get("status") in ("hold", "official") and q.get("프로그램명"):
            groups[(q["프로그램명"], q.get("칸"))].append(q)
    return {k: v for k, v in groups.items() if len(v) >= BUNDLE_MIN}


def _suggestion_id(program, section):
    return "S-" + hashlib.sha1(f"{program}|{section}".encode("utf-8")).hexdigest()[:6]


def _new_demand(rows):
    return sum(1 for (prog, sec), qs in _bundles(rows).items()
               if sum(q["status"] == "hold" for q in qs) >= BUNDLE_MIN and _gap(prog, sec))


def _kind(program, section, qs):
    holds = sum(q["status"] == "hold" for q in qs)
    if holds >= BUNDLE_MIN and _gap(program, section):
        return "신규 수요"
    if holds * 2 < len(qs):            # 규정 질문이 더 많음
        return "안내 보강"
    return "검토 필요"


def _title(kind, program, section):
    short = ((PROGRAMS.get(program) or {}).get("별칭") or [program])[0]
    where = f"{short} {section}" if section else short
    return {"신규 수요": f"{where} 경험이 아직 없어요",
            "안내 보강": f"{where} 공식 안내를 보강해 주세요",
            "검토 필요": f"{where} 질문이 반복돼요"}[kind]


def _suggestions(dept, start, end):
    status = store.load("suggestionStatus", {})
    out = []
    for (prog, sec), qs in _bundles(_filter(_questions(start, end, seed_only=True), dept)).items():
        sid = _suggestion_id(prog, sec)
        kind = _kind(prog, sec, qs)
        cached = SUGGESTION_TEXT.get(sid) or {}
        qs = sorted(qs, key=lambda q: q["at"], reverse=True)
        out.append({"id": sid, "유형": cached.get("유형") or kind, "제목": cached.get("제목") or _title(kind, prog, sec),
                    "제안": cached.get("제안") or "", "부서코드": _dept_of(prog), "프로그램명": prog, "칸": sec,
                    "count": len(qs), "lastAt": qs[0]["at"], "status": status.get(sid, {}).get("status", "새로 옴"),
                    "questions": [{"at": q["at"], "학과": q.get("crs_nm"), "칸": q.get("칸"), "질문": q.get("질문")}
                                  for q in qs]})
    out.sort(key=lambda s: (s["status"] != "새로 옴", -s["count"], s["id"]))
    return out


# ---------- 탭1 수요 현황 ----------
def _overview(dept, period):
    start, end, period = _parse_period(period)
    if not period:
        return {"error": "기간을 확인해 주세요"}
    pstart, pend, _ = _parse_period(_previous(period))
    every = _questions(start, end)
    rows = _filter(every, dept)
    prev = _filter(_questions(pstart, pend), dept)

    def kpi(qs):
        hold = sum(q.get("status") == "hold" for q in qs)
        return len(qs), hold

    n, hold = kpi(rows)
    pn, phold = kpi(prev)
    nd, pnd = _new_demand(rows), _new_demand(prev)
    imp = sum(s["status"] == "새로 옴" for s in _suggestions(dept, start, end))
    pimp = sum(s["status"] == "새로 옴" for s in _suggestions(dept, pstart, pend))

    by_prog = defaultdict(list)
    for q in rows:
        if q.get("프로그램명"):
            by_prog[q["프로그램명"]].append(q)
    programs = sorted(({"프로그램명": p, "분야": (PROGRAMS.get(p) or {}).get("분야"), "questions": len(qs),
                        "hold": sum(q.get("status") == "hold" for q in qs),
                        "sections": dict(Counter(q.get("칸") for q in qs if q.get("칸")))}
                       for p, qs in by_prog.items()), key=lambda r: (-r["questions"], r["프로그램명"]))

    # [11/25 PR #236] 분야별 칸 수. 분야 = 질문의 분야(없으면 programs.json 「분야」). 분야를 모르는 질문은 넣지 않는다
    by_field = defaultdict(Counter)
    for q in rows:
        field = q.get("분야") or (PROGRAMS.get(q.get("프로그램명")) or {}).get("분야")
        if field and q.get("칸"):
            by_field[field][q["칸"]] += 1

    by_dept = defaultdict(list)
    for q in rows:
        by_dept[q.get("crs_nm") or "–"].append(q)
    colleges = sorted(({"학과": k, "questions": len(v), "holdRate": round(sum(q.get("status") == "hold" for q in v) / len(v) * 100)}
                       for k, v in by_dept.items()), key=lambda r: (-r["questions"], r["학과"]))
    if len(colleges) > 8:
        rest = [q for c in colleges[8:] for q in by_dept[c["학과"]]]
        colleges = colleges[:8] + [{"학과": "그 외", "questions": len(rest),
                                    "holdRate": round(sum(q.get("status") == "hold" for q in rest) / len(rest) * 100)}]

    weekly = defaultdict(lambda: [0, 0])
    for q in rows:
        d = date.fromisoformat(q["at"][:10])
        wk = (d - timedelta(days=d.weekday())).isoformat()
        weekly[wk][0] += 1
        weekly[wk][1] += q.get("status") == "hold"

    return {
        "dept": dept, "period": period, "label": _label(period),
        "kpi": {"questions": {"value": n, "delta": _delta(n, pn)},
                "unanswered": {"value": hold, "delta": _delta(hold, phold), "holdRate": round(hold / n * 100) if n else 0},
                "newDemand": {"value": nd, "delta": _delta(nd, pnd)},
                "improvements": {"value": imp, "delta": _delta(imp, pimp)}},
        "programs": programs,
        "sections": dict(Counter(q.get("칸") for q in rows if q.get("칸"))),
        "sectionsByField": {f: dict(c) for f, c in sorted(by_field.items())},
        "colleges": colleges,
        "notes": _note_stats(dept, start, end),
        "weekly": [{"week": k, "questions": v[0], "hold": v[1]} for k, v in sorted(weekly.items())],
        "unclassified": sum(1 for q in every if not q.get("운영부서코드")) if dept == "ALL" else 0,
        "computedAt": now(),
    }


def _note_stats(dept, start, end):
    mine = [n for n in notes.NOTES.values() if dept == "ALL" or _dept_of(n.get("program")) == dept]
    interviews = _filter_program([r for r in USAGE.get("interviews", []) if _in(r.get("at"), start, end)], dept)
    consents = _filter_program([r for r in USAGE.get("consents", []) if _in(r.get("at"), start, end)], dept)
    live = [v for v in store.load("myNotes", {}).values() if _in(v.get("updatedAt"), start, end)
            and (dept == "ALL" or _dept_of(v.get("program")) == dept)]
    n_int = len(interviews) + len(live)
    n_con = len(consents) + sum(1 for v in live if v.get("share") in ("shared", "partial"))
    return {"count": len(mine), "evidence": sum(n.get("evidenceCount", 0) for n in mine),
            "interviews": n_int, "consentRate": round(n_con / n_int * 100) if n_int else 0}


def getDepartments(me, p):
    if not _staff(me):
        return DENY
    role, own = _staff(me)
    depts = [d for d in DEPTS if role == "총괄" or d["부서코드"] == own]
    return {"departments": [{k: d.get(k) for k in ("부서코드", "부서명", "담당분야")} for d in depts],
            "role": role, "fixed": own}


def getAdminOverview(me, p):
    dept, _ = _scope(me, p)
    return _overview(dept, p.get("period")) if dept else DENY


def getDeptReport(me, p):
    """옛 이름(spec 4장). 내부에서 getAdminOverview를 부른다(PRD 7장)."""
    return getAdminOverview(me, p)


# ---------- 탭2 개선 제안 ----------
def _reported(dept, start, end):
    lines = {}
    for n in notes.NOTES.values():
        for s in n.get("sections", []):
            for ln in s.get("lines", []):
                lines[ln.get("lineId")] = (n, ln)
    rows = []
    for r in USAGE.get("reports", []):
        rows.append({"lineId": r.get("lineId"), "at": r.get("at"), "reason": r.get("사유"), "status": r.get("status")})
    for line_id, r in store.load("reported", {}).items():
        rows.append({"lineId": line_id, "at": r.get("at"), "reason": r.get("reason"), "status": r.get("status"),
                     "saved": r})
    out = []
    for r in rows:
        n, ln = lines.get(r["lineId"], (None, None))
        saved = r.get("saved") or {}
        summary = saved.get("kind") == "summary"
        if n is None and saved.get("noteId"):   # [11/25 작업 33] 요약 문장·인터뷰 문장 신고는 기록에 남긴 글·노트로
            n = {"id": saved["noteId"], "program": saved.get("program")}
            ln = {"text": saved.get("text")}
        program = n.get("program") if n else None
        if not _in(r["at"], start, end) or (dept != "ALL" and _dept_of(program) != dept):
            continue
        out.append({"lineId": r["lineId"], "text": ln.get("text") if ln else None,
                    # 노트 문장 = 근거 원문 1:1(작업 26). 요약 문장은 원문이 아니라 AI 문단의 한 문장 → sourceText 없음
                    "sourceText": ln.get("text") if ln and not summary else None,
                    "kind": "summary" if summary else "line",
                    "reason": r["reason"], "noteId": n.get("id") if n else None, "program": program,
                    "status": r["status"] or "숨김 중", "at": r["at"]})
    return sorted(out, key=lambda r: r["at"], reverse=True)


def getAdminSuggestions(me, p):
    dept, _ = _scope(me, p)
    if not dept:
        return DENY
    start, end, period = _parse_period(p.get("period"))
    if not period:
        return {"error": "기간을 확인해 주세요"}
    live = _filter([q for q in _questions(start, end) if not q["_seed"]], dept)
    return {"dept": dept, "period": period, "suggestions": _suggestions(dept, start, end),
            "reported": _reported(dept, start, end),
            "pendingNew": sum(q.get("status") in ("hold", "official") for q in live)}


def setSuggestionStatus(me, p):
    who = _staff(me)
    sid, status = p.get("id"), p.get("status")
    if not who:
        return DENY
    if status not in STATUSES:
        return {"error": "상태를 확인해 주세요"}
    # 부서 담당자는 자기 부서 제안만 바꾼다. 제안 id = 프로그램·칸 해시이므로 시드 묶음 전체에서 찾는다
    found = next(((prog, sec) for (prog, sec) in _bundles(_questions(date(2000, 1, 1), date(2100, 1, 1), seed_only=True))
                  if _suggestion_id(prog, sec) == sid), None)
    if not found:
        return {"error": "제안을 찾지 못했어요"}
    if who[0] == "부서" and _dept_of(found[0]) != who[1]:
        return DENY
    with store.lock():
        store.load("suggestionStatus", {})[sid] = {"status": status, "by": me, "at": now()}
        store.save("suggestionStatus")
    return {"ok": True}


# ---------- 탭3 리포트 발행 ----------
def _default_settings(dept):
    mail = (DEPT_BY_CODE.get(dept) or {}).get("대표메일(가상)")
    return {"period": "monthly", "day": 1, "recipients": [mail] if mail else [], "sections": list(SECTIONS),
            "saved": False, "savedAt": None}


def _settings(dept):
    return store.load("reportSettings", {}).get(dept) or _default_settings(dept)


def _last_issued(dept):
    rows = [r for r in store.load("issuedReports", []) if r["dept"] == dept]
    return max((r["issuedAt"] for r in rows), default=None)


def _next_issue(dept, s):
    """다음 발행 예정일(YYYY-MM-DD). 월간 = 매월 day일, 학기당 = 학기 끝(2월 말·8월 말) 뒤 day일.
    기준 = 마지막 발행 시각, 없으면 설정 저장 시각(그 뒤 첫 예정일)."""
    base = (_last_issued(dept) or s.get("savedAt") or now())[:10]
    b = date.fromisoformat(base)
    if s["period"] == "monthly":
        y, m = b.year, b.month
        for _ in range(13):
            d = date(y, m, min(s["day"], calendar.monthrange(y, m)[1]))
            if d > b:
                return d.isoformat()
            y, m = y + (m == 12), m % 12 + 1
    for y in (b.year - 1, b.year, b.year + 1):
        for end in (date(y, 3, 1) - timedelta(days=1), date(y, 8, 31)):
            d = end + timedelta(days=s["day"])
            if d > b:
                return d.isoformat()
    return None


def _auto_issue(dept):
    """예정일이 지났으면 이번에 발행한다(저장된 설정이 있을 때만). 지난 기간(전월·전 학기)을 집계."""
    s = _settings(dept)
    if not s.get("saved"):
        return
    due = _next_issue(dept, s)
    if due and due <= now()[:10]:
        cur = _parse_period({"type": "month" if s["period"] == "monthly" else "semester"})[2]
        _issue(dept, _previous(cur), "auto")


def getReportSettings(me, p):
    dept, _ = _scope(me, p)
    if not dept:
        return DENY
    with store.lock():
        _auto_issue(dept)
        s = _settings(dept)
        return {"dept": dept, "period": s["period"], "day": s["day"], "recipients": s["recipients"],
                "sections": s["sections"], "nextIssueAt": _next_issue(dept, s) if s.get("saved") else None,
                "lastIssuedAt": _last_issued(dept)}


def saveReportSettings(me, p):
    dept, role = _scope(me, p)
    if not dept:
        return DENY
    if role != "총괄":
        return {"error": "리포트 설정은 총괄 관리자만 바꿀 수 있어요"}
    s = p.get("settings") or {}
    period = s.get("period")
    if period not in ("monthly", "semester"):
        return {"error": "주기를 확인해 주세요"}
    try:
        day = int(s.get("day"))
    except (TypeError, ValueError):
        return {"error": "발행일을 확인해 주세요"}
    if not (1 <= day <= 28 if period == "monthly" else 0 <= day <= 60):
        return {"error": "발행일을 확인해 주세요"}
    recipients = [str(r).strip() for r in (s.get("recipients") or []) if str(r).strip()]
    bad = [r for r in recipients if not EMAIL.match(r)]
    if bad:
        return {"error": f"이메일 형식을 확인해 주세요: {bad[0]}"}
    if not recipients or len(recipients) > 10:
        return {"error": "받는 사람은 1명 이상 10명 이하예요"}
    sections = [x for x in (s.get("sections") or []) if x in SECTIONS]
    if not sections:
        return {"error": "포함 항목을 하나 이상 골라 주세요"}
    with store.lock():
        new = {"period": period, "day": day, "recipients": recipients, "sections": sections,
               "saved": True, "savedAt": now(), "by": me}
        store.load("reportSettings", {})[dept] = new
        store.save("reportSettings")
        return {"ok": True, "nextIssueAt": _next_issue(dept, new)}


def _summary(ov):
    """리포트 요약 한 단락(템플릿). AI 요약(작업 67)이 생기면 실패 시 이 문장으로 대체한다."""
    k = ov["kpi"]
    top = [r["프로그램명"] for r in ov["programs"][:3]]
    text = (f"{ov['label']} 질문은 {k['questions']['value']}건이고 미답변은 {k['unanswered']['value']}건"
            f"(보류율 {k['unanswered']['holdRate']}%)이에요.")
    if top:
        text += f" 질문이 많은 프로그램은 {', '.join(top)}이에요."
    if k["newDemand"]["value"]:
        text += f" 노트가 비어 있는 신규 수요 묶음이 {k['newDemand']['value']}개 있어요."
    return text


def _render(dept, ov, sugg, settings, summary):
    """메일 본문과 같은 HTML(디자인 MD 7-⑤ 순서). 모든 글자는 escape. 색은 화면(style.css)이 rpt- 클래스로 입힌다."""
    e = lambda x: html.escape(str(x if x is not None else "–"))
    name = "전체" if dept == "ALL" else (DEPT_BY_CODE.get(dept) or {}).get("부서명", dept)
    k = ov["kpi"]
    inc = set(settings["sections"])
    parts = [f'<article class="rpt"><header class="rpt-head"><p class="rpt-period">{e(ov["label"])}</p>'
             f'<h1 class="rpt-dept">{e(name)} 해봤노트 리포트</h1></header>']
    if "지표" in inc:
        cards = [("질문 수", k["questions"]["value"]), ("미답변 질문", k["unanswered"]["value"]),
                 ("신규 수요", k["newDemand"]["value"]), ("개선 요청", k["improvements"]["value"])]
        parts.append('<section class="rpt-kpi">' + "".join(
            f'<div class="rpt-card"><p class="rpt-card-label">{e(a)}</p><p class="rpt-card-value">{e(b)}</p></div>'
            for a, b in cards) + "</section>")
    if "프로그램 순위" in inc:
        parts.append('<section class="rpt-rank"><h2>프로그램별 질문 순위</h2><ol>' + "".join(
            f"<li>{e(r['프로그램명'])} · {e(r['questions'])}건</li>" for r in ov["programs"][:5]) + "</ol></section>")
    if "개선 제안" in inc and sugg["suggestions"]:
        parts.append('<section class="rpt-insight"><h2>주요 인사이트</h2><ul>' + "".join(
            f"<li>[{e(s['유형'])}] {e(s['제목'])} · 근거 질문 {e(s['count'])}건</li>" for s in sugg["suggestions"][:3])
            + "</ul></section>")
    if "미답변 질문" in inc:
        holds = [q for s in sugg["suggestions"] for q in s["questions"]][:5]
        if holds:
            parts.append('<section class="rpt-hold"><h2>미답변 질문</h2><ul>' + "".join(
                f"<li>{e(q['질문'])}</li>" for q in holds) + "</ul></section>")
    if "신고 진술" in inc and sugg["reported"]:
        parts.append(f'<section class="rpt-reported"><h2>신고된 진술 {len(sugg["reported"])}건</h2></section>')
    parts.append(f'<section class="rpt-summary"><h2>요약</h2><p>{e(summary)}</p></section>')
    url = (DEPT_BY_CODE.get(dept) or {}).get("공식안내URL")
    if url:
        parts.append(f'<footer class="rpt-foot"><a href="{e(url)}">공식 안내 보기</a></footer>')
    return "".join(parts) + "</article>"


def _issue(dept, period, mode):
    start, end, period = _parse_period(period)
    ov = _overview(dept, period)
    sugg = {"suggestions": _suggestions(dept, start, end), "reported": _reported(dept, start, end)}
    settings = _settings(dept)
    # AI 요약 한 단락(작업 67). 입력에 없는 숫자·고유명사·URL이 있거나 실패하면 템플릿 문장
    ov["deptName"] = "전체" if dept == "ALL" else (DEPT_BY_CODE.get(dept) or {}).get("부서명", dept)
    text, source = suggest.ai_summary(ov, sugg)
    summary = text or _summary(ov)
    rid = store.next_id("R")
    at = now()
    store.load("reportHtml", {})[rid] = _render(dept, ov, sugg, settings, summary)
    store.save("reportHtml")
    store.load("issuedReports", []).append({"reportId": rid, "issuedAt": at, "dept": dept, "period": period,
                                            "mode": mode, "recipients": len(settings["recipients"]), "summary": summary,
                                            "summarySource": source or "template"})
    store.save("issuedReports")
    return {"reportId": rid, "issuedAt": at, "html": store.load("reportHtml", {})[rid], "summary": summary,
            "summarySource": source or "template"}


def issueReport(me, p):
    dept, role = _scope(me, p)
    if not dept:
        return DENY
    if role != "총괄":
        return {"error": "리포트 발행은 총괄 관리자만 할 수 있어요"}
    if not _parse_period(p.get("period"))[2]:
        return {"error": "기간을 확인해 주세요"}
    with store.lock():
        return _issue(dept, p.get("period"), "manual")


def listIssuedReports(me, p):
    dept, _ = _scope(me, p)
    if not dept:
        return DENY
    with store.lock():
        _auto_issue(dept)
        rows = [r for r in store.load("issuedReports", []) if dept == "ALL" or r["dept"] == dept]
        rows = sorted(rows, key=lambda r: r["issuedAt"], reverse=True)
        return {"reports": [{"reportId": r["reportId"], "issuedAt": r["issuedAt"], "dept": r["dept"],
                             "period": r["period"], "label": _label(r["period"]), "mode": r["mode"],
                             "recipients": r["recipients"], "url": None} for r in rows]}


def getIssuedReport(me, p):
    """발행 이력의 「열기」. 화면은 html을 iframe srcdoc(sandbox)로 보여 준다 — innerHTML 금지."""
    dept, role = _scope(me, p)
    if not dept:
        return DENY
    r = next((x for x in store.load("issuedReports", []) if x["reportId"] == p.get("reportId")), None)
    if not r or (role == "부서" and r["dept"] != dept):
        return DENY
    return {"reportId": r["reportId"], "issuedAt": r["issuedAt"], "summary": r["summary"],
            "html": store.load("reportHtml", {}).get(r["reportId"], "")}


ROUTES = {"getDepartments": getDepartments, "getAdminOverview": getAdminOverview,
          "getAdminSuggestions": getAdminSuggestions, "setSuggestionStatus": setSuggestionStatus,
          "getReportSettings": getReportSettings, "saveReportSettings": saveReportSettings,
          "issueReport": issueReport, "listIssuedReports": listIssuedReports,
          "getIssuedReport": getIssuedReport, "getDeptReport": getDeptReport}
