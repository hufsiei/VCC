# notes.py — 해봤노트 읽기 (작업 26 미리 몫·74, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 getNote·listNotes·askBoo [11/19] 근거 풀 · PRD 4-2 ③⑤
#   노트 = data/notes.json(사전 생성, 원우 build_notes.py) + runtime/noteLines.json(공개 동의를 통과한 인터뷰 문장)
#   쓰는 쪽은 runtime_fns.saveConsent(noteLines에 쌓기·질문 answered·알림). 여기는 읽기만 한다.
#
#   getNote(me, {id})          — 칸 뒤에 인터뷰 문장을 붙인다. 「후배 질문」 칸은 Q(asked)·A(text) 쌍, 질문별로 모아 원문 인용
#   listNotes(me, {filter})    — 카드 목록. evidenceCount·lastSemester에 인터뷰 문장을 더한다
#   interview_lines(program)   — askBoo 근거 풀에 더할 인터뷰 문장(후배 질문 A 포함)
#   scrapNote(me, {noteId, scrap}) — 스크랩 켜기·끄기(runtime/scraps.json). 카드·노트의 scrapped, getInbox.scraps
#   카드·노트의 country = 국제교류 프로그램의 programs.json 「세부」(국가). 인턴·비교과는 null
#
# 원문 인용만 한다: 선배가 동의한 문장 그대로 붙이고, 여러 선배의 답을 합치거나 요약하지 않는다(HCX 원칙 v2). AI 없음.
# 응답에 선배 학번(owner)·내 경험노트 id는 넣지 않는다.
import copy
import hashlib
import json
import re
from pathlib import Path

import store

DATA = Path(__file__).resolve().parent.parent / "data"
QUESTION_SECTION = "후배 질문"
INTERVIEW = "인터뷰"
FIXED_IDS = {"마르부르크필립스대학교": "N-marburg"}   # tools/build_notes.py note_id()와 같은 규칙
KIND_BY_FIELD = {"국제교류": "교환", "현장실습": "인턴", "비교과": "비교과"}
SUMMARY_KEYS = ("id", "program", "type", "oneLine", "forWhom", "evidenceCount", "lastSemester",
                "satisfaction", "completedCount")


def _json(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


NOTES = {n["id"]: n for n in _json("notes.json", []) if isinstance(n, dict) and n.get("id")}
ID_BY_PROGRAM = {n.get("program"): i for i, n in NOTES.items()}
PROGRAMS = {p["프로그램명"]: p for p in _json("programs.json", [])}
DEPTS = {d["부서코드"]: d for d in _json("departments.json", [])}
FRAMES = _json("frames.json", {})


def note_id(program):
    """프로그램 → 노트 id. notes.json에 있으면 그 id, 없으면 build_notes.py와 같은 해시 규칙(나중에 생성돼도 같은 id)."""
    return ID_BY_PROGRAM.get(program) or FIXED_IDS.get(program) or \
        "N-" + hashlib.sha1(program.encode("utf-8")).hexdigest()[:6]


# ── 선배가 그 경험을 한 학기 (출처 칩 연도용) ───────────────────────────
_semesters = None


def experience_semester(colreg_no, program):
    """보고서·후기·비교과 이수 기록에서 찾는다. 없으면 None(화면은 「–」)."""
    global _semesters
    if _semesters is None:
        _semesters = {}
        rows = [(e.get("학번"), e.get("프로그램명"), e.get("semester")) for e in _json("evidence.json", [])]
        rows += [(r.get("학번"), r.get("업체명"), r.get("semester")) for r in _json("internships.json", [])]
        rows += [(r.get("가상학번"), r.get("프로그램명"), r.get("semester")) for r in _json("extracurricular.json", [])]
        for who, name, sem in rows:
            if who and name and sem:
                key = (who, name)
                _semesters[key] = max(_semesters.get(key, ""), str(sem))
    return _semesters.get((colreg_no, program))


# ── noteLines 읽기 ────────────────────────────────────────────────────
def _visible_lines(nid=None, program=None):
    """동의 통과 인터뷰 문장 중 신고로 숨겨지지 않은 것."""
    with store.lock():
        rows = list(store.load("noteLines", []))
        hidden = set(store.load("reported", {}))
    return [r for r in rows
            if (nid is None or r.get("noteId") == nid) and (program is None or r.get("program") == program)
            and "L-" + r.get("sourceId", "") not in hidden]


def _out_line(r):
    line = {"text": r["text"], "sourceId": r["sourceId"], "lineId": "L-" + r["sourceId"], "official": bool(r.get("official"))}
    if r.get("section") == QUESTION_SECTION and r.get("answersQuestionId"):
        line = {"asked": r.get("asked", ""), "answersQuestionId": r["answersQuestionId"], **line}
    return line


def _question_pairs(rows):
    """「후배 질문」 칸: 같은 질문의 답을 붙여 둔다(질문이 처음 답해진 순서, 답은 동의 순서). 합치지 않는다."""
    order = []
    for r in rows:
        key = r.get("answersQuestionId") or r.get("asked") or r["sourceId"]
        if key not in order:
            order.append(key)
    return sorted(rows, key=lambda r: (order.index(r.get("answersQuestionId") or r.get("asked") or r["sourceId"]),
                                       r.get("at", "")))


def _kind(program):
    return KIND_BY_FIELD.get(PROGRAMS.get(program, {}).get("분야"), "교환")


def _empty_note(nid, program):
    """notes.json에 없는 프로그램(보고서·후기 없음)에 인터뷰 문장만 있을 때의 노트 틀."""
    kind = _kind(program)
    frame = FRAMES.get(kind) or {"칸": [], "인터뷰로만": []}
    return {"id": nid, "program": program, "type": kind, "oneLine": "", "forWhom": "",
            "evidenceCount": 0, "lastSemester": None, "satisfaction": None, "completedCount": None,
            "sections": [{"name": s, "interviewOnly": s in frame["인터뷰로만"], "lines": []} for s in frame["칸"]],
            "sources": {}}


def _country(program):
    """국제교류 프로그램의 국가(programs.json 「세부」). 카드 띠 「교환학생 · 독일」용. 인턴·비교과는 None."""
    info = PROGRAMS.get(program, {})
    return info.get("세부") if info.get("분야") == "국제교류" else None


def _my_scraps(me):
    """내가 스크랩한 노트 id 목록(스크랩한 순서)."""
    with store.lock():
        return list(store.load("scraps", {}).get(me, []))


def _official_url(program):
    code = PROGRAMS.get(program, {}).get("운영부서코드")
    return DEPTS.get(code, {}).get("공식안내URL", "")


def _merge(nid, rows):
    """사전 생성 노트 + 인터뷰 문장. rows는 이 노트의 보이는 noteLines."""
    base = NOTES.get(nid)
    if base is None and not rows:
        return None
    note = copy.deepcopy(base) if base else _empty_note(nid, rows[0].get("program", ""))
    with store.lock():
        hidden = set(store.load("reported", {}))
    for sec in note["sections"]:   # 신고로 숨긴 보고서 문장도 뺀다
        sec["lines"] = [ln for ln in sec.get("lines", []) if ln.get("lineId") not in hidden]

    by_section = {}
    for r in sorted(rows, key=lambda r: r.get("at", "")):
        by_section.setdefault(r.get("section"), []).append(r)
    for name, items in by_section.items():
        sec = next((s for s in note["sections"] if s["name"] == name), None)
        if sec is None:   # 틀에 없는 칸(틀이 바뀐 경우)은 맨 뒤에 둔다
            sec = {"name": name, "interviewOnly": True, "lines": []}
            note["sections"].append(sec)
        if name == QUESTION_SECTION:
            items = _question_pairs(items)
        sec["lines"] += [_out_line(r) for r in items]
        for r in items:
            note.setdefault("sources", {})[r["sourceId"]] = {"docType": INTERVIEW, "program": note["program"],
                                                             "semester": r.get("semester")}

    note["evidenceCount"] = (note.get("evidenceCount") or 0) + len(rows)
    sems = [s for s in [note.get("lastSemester"), *(r.get("semester") for r in rows)] if s]
    note["lastSemester"] = max(sems) if sems else None
    if not note.get("officialUrl"):
        note["officialUrl"] = _official_url(note["program"])
    return note


# ── 서버 함수 ─────────────────────────────────────────────────────────
def getNote(me, p):
    nid = (p.get("id") or "").strip()
    note = _merge(nid, _visible_lines(nid=nid)) if nid else None
    if not note:
        return {"error": "노트를 찾지 못했어요"}
    note["country"] = _country(note["program"])
    note["scrapped"] = nid in _my_scraps(me)
    return note


def _norm(s):
    return re.sub(r"\s+", "", s or "").lower()


def listNotes(me, p):
    f = p.get("filter") or {}
    kind, q = f.get("type"), _norm(f.get("q"))
    rows = _visible_lines()
    count, last, program_of = {}, {}, {}
    for r in rows:
        nid = r.get("noteId")
        count[nid] = count.get(nid, 0) + 1
        program_of.setdefault(nid, r.get("program", ""))
        if r.get("semester"):
            last[nid] = max(last.get(nid, ""), r["semester"])
    ids = list(NOTES) + [nid for nid in program_of if nid not in NOTES]
    scrapped = set(_my_scraps(me))
    out = []
    for nid in ids:
        n = NOTES.get(nid) or _empty_note(nid, program_of[nid])
        card = {k: n.get(k) for k in SUMMARY_KEYS}
        card["evidenceCount"] = (card["evidenceCount"] or 0) + count.get(nid, 0)
        sems = [s for s in (card["lastSemester"], last.get(nid)) if s]
        card["lastSemester"] = max(sems) if sems else None
        if kind and card["type"] != kind:
            continue
        if q:
            words = [card["program"], *PROGRAMS.get(card["program"], {}).get("별칭", []), card["oneLine"], card["forWhom"]]
            if not any(q in _norm(w) for w in words if w):
                continue
        card["country"] = _country(card["program"])
        card["scrapped"] = nid in scrapped
        out.append(card)
    return {"notes": out}


def _note_exists(nid):
    return nid in NOTES or bool(_visible_lines(nid=nid))


def scrapNote(me, p):
    """스크랩 켜기(scrap 생략·true)·끄기(false). 같은 상태로 다시 불러도 ok(멱등)."""
    nid = (p.get("noteId") or "").strip()
    if not nid or not _note_exists(nid):
        return {"error": "노트를 찾지 못했어요"}
    on = p.get("scrap", True) is not False
    with store.lock():
        mine = store.load("scraps", {}).setdefault(me, [])
        if on and nid not in mine:
            mine.append(nid)
        elif not on and nid in mine:
            mine.remove(nid)
        store.save("scraps")
    return {"ok": True, "noteId": nid, "scrapped": on}


def inbox_scraps(me):
    """getInbox.scraps — 최근 스크랩이 위. 지금 없는 노트는 뺀다."""
    out = []
    for nid in reversed(_my_scraps(me)):
        program = (NOTES.get(nid) or {}).get("program")
        if program is None:
            rows = _visible_lines(nid=nid)
            program = rows[0].get("program") if rows else None
        if program:
            out.append({"noteId": nid, "program": program})
    return out


def interview_lines(program):
    """askBoo 근거 풀용. evidence.json 행과 같은 열 이름으로 돌려준다(+ 칸·후배 질문 원문)."""
    return [{"id": r["sourceId"], "docType": INTERVIEW, "프로그램명": program, "semester": r.get("semester"),
             "칸": r.get("section"), "text": r["text"], "asked": r.get("asked")}
            for r in sorted(_visible_lines(program=program), key=lambda r: r.get("at", ""), reverse=True)]


ROUTES = {"getNote": getNote, "listNotes": listNotes, "scrapNote": scrapNote}
