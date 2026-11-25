# notes.py — 해봤노트 읽기 (작업 26 미리 몫·74, 작성: 미리)
#
# 기준: docs/spec-v1.md 4장 getNote·listNotes·askBoo [11/19] 근거 풀 · PRD 4-2 ③⑤
#   노트 = data/notes.json(사전 생성, 원우 build_notes.py) + runtime/noteLines.json(공개 동의를 통과한 인터뷰 문장)
#   쓰는 쪽은 runtime_fns.saveConsent(noteLines에 쌓기·질문 answered·알림). 여기는 읽기만 한다.
#
#   getNote(me, {id})          — 칸 뒤에 인터뷰 문장을 붙인다. [v2 작업 89] 「후배 질문」 칸은 없다 — 후배 질문에 답한
#                                문장은 질문의 칸에 일반 문장으로 들어가고 answersQuestionId·asked만 붙는다(화면 라벨용)
#   listNotes(me, {filter})    — 카드 목록. evidenceCount·lastSemester에 인터뷰 문장을 더한다
#   interview_lines(program)   — askBoo 근거 풀에 더할 인터뷰 문장(후배 질문 답도 그 칸 문장으로)
#   scrapNote(me, {noteId, scrap}) — 스크랩 켜기·끄기(runtime/scraps.json). 카드·노트의 scrapped, getInbox.scraps
#   saveQuestion(me, {noteId, section}) — [11/22] 「질문함에 담기」: 그 칸을 질문함에 hold로(다음 인터뷰가 먼저 묻는다)
#   카드·노트의 country = 국제교류 프로그램의 programs.json 「세부」(국가). 인턴·비교과는 null
#   [11/23 주제별] 카드·노트의 kind = 인턴 프로그램의 「세부」(기관유형). listNotes는 groups(나라·기관유형 칩)와
#   filter.country·filter.kind를 받고, 비교과 카드는 이수 인원(completedCount) 많은 순
#   getNote 배운점 문장의 senior = 「선배 A」(노트 안에서만 쓰는 글자, 학과 없음 — PRD 9-1)
#   [11/23 작업 78] getNote 칸별 summary(notes.json 사전 생성 요약 문단)를 넘기고 newLines(그 뒤 붙은 인터뷰 문장 수)를 붙인다
#   [11/25 작업 33] 요약 문장마다 lineId(「S-…」, summary_line_id)를 붙이고, reportStatement로 신고된 요약 문장은 뺀다
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
QUESTION_SECTION = "후배 질문"   # [v2 작업 89] 없어진 칸. frames.json·옛 noteLines에 남아 있으면 걸러 낸다
INTERVIEW = "인터뷰"
# 후배 질문의 칸을 모를 때(칸이 없거나 틀 밖) 넣는 칸 — spec 4장 interviewNext [v2]
FALLBACK_SECTION = {"교환": "팁", "*": "배운점"}
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


# ── 노트 틀 [v2 작업 89] ──────────────────────────────────────────────
def _kind(program):
    return KIND_BY_FIELD.get(PROGRAMS.get(program, {}).get("분야"), "교환")


def frame_sections(kind):
    """그 종류의 노트 틀 칸(「후배 질문」 빼고). frames.json에서 원우가 지우기 전후 모두 같은 값."""
    return [s for s in (FRAMES.get(kind) or {}).get("칸", []) if s != QUESTION_SECTION]


def fallback_section(program):
    """후배 질문의 칸을 모를 때 넣는 칸: 교환·파견 「팁」, 인턴·비교과 「배운점」(틀에 없으면 틀의 마지막 칸)."""
    kind = _kind(program)
    names = frame_sections(kind)
    s = FALLBACK_SECTION.get(kind, FALLBACK_SECTION["*"])
    return s if s in names or not names else names[-1]


def section_for_question(program, q):
    """질문함 행의 칸이 그 프로그램 틀 안에 있으면 그 칸, 아니면 None(부르는 쪽이 정한다)."""
    s = (q or {}).get("칸")
    return s if s in frame_sections(_kind(program)) else None


# ── noteLines 읽기 ────────────────────────────────────────────────────
def _legacy_section(r, questions):
    """11/23 이전에 「후배 질문」 칸으로 쌓인 문장 → 질문의 칸(없으면 fallback_section). 저장된 행은 바꾸지 않는다."""
    if r.get("section") != QUESTION_SECTION:
        return r
    program = r.get("program", "")
    s = section_for_question(program, questions.get(r.get("answersQuestionId"))) or fallback_section(program)
    return {**r, "section": s}


def _visible_lines(nid=None, program=None):
    """동의 통과 인터뷰 문장 중 신고로 숨겨지지 않은 것. 옛 「후배 질문」 칸 문장은 질문의 칸으로 읽는다."""
    with store.lock():
        rows = list(store.load("noteLines", []))
        hidden = set(store.load("reported", {}))
        questions = {q.get("id"): q for q in store.load("questions", [])} \
            if any(r.get("section") == QUESTION_SECTION for r in rows) else {}
    return [_legacy_section(r, questions) for r in rows
            if (nid is None or r.get("noteId") == nid) and (program is None or r.get("program") == program)
            and "L-" + r.get("sourceId", "") not in hidden]


def _out_line(r):
    line = {"text": r["text"], "sourceId": r["sourceId"], "lineId": "L-" + r["sourceId"], "official": bool(r.get("official"))}
    if r.get("answersQuestionId"):   # [v2] 화면은 중립 라벨 「후배 질문에 답한 문장」만(Q는 질문자 보관함에서)
        line = {"asked": r.get("asked", ""), "answersQuestionId": r["answersQuestionId"], **line}
    return line


def _empty_note(nid, program):
    """notes.json에 없는 프로그램(보고서·후기 없음)에 인터뷰 문장만 있을 때의 노트 틀."""
    kind = _kind(program)
    frame = FRAMES.get(kind) or {"칸": [], "인터뷰로만": []}
    return {"id": nid, "program": program, "type": kind, "oneLine": "", "forWhom": "",
            "evidenceCount": 0, "lastSemester": None, "satisfaction": None, "completedCount": None,
            "sections": [{"name": s, "interviewOnly": s in frame.get("인터뷰로만", []), "lines": []}
                         for s in frame_sections(kind)],
            "sources": {}}


def _country(program):
    """국제교류 프로그램의 국가(programs.json 「세부」). 카드 띠 「교환학생 · 독일」용. 인턴·비교과는 None."""
    info = PROGRAMS.get(program, {})
    return info.get("세부") if info.get("분야") == "국제교류" else None


def _org_kind(program):
    """[11/23 주제별] 인턴(현장실습) 프로그램의 기관유형(programs.json 「세부」). 묶음 칩 「공공기관」용. 국제교류·비교과는 None."""
    info = PROGRAMS.get(program, {})
    return info.get("세부") if info.get("분야") == "현장실습" else None


def _groups(cards, key):
    """묶음 칩 목록: 값별 노트 수, 많은 순(같으면 가나다순). 값이 없는 카드는 뺀다."""
    count = {}
    for c in cards:
        if c.get(key):
            count[c[key]] = count.get(c[key], 0) + 1
    return [{"name": k, "count": v} for k, v in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))]


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
    # [v2] 사전 생성 노트에 남은 「후배 질문」 칸은 뺀다(인터뷰 문장은 _visible_lines가 질문의 칸으로 옮겨 둠)
    note["sections"] = [s for s in note["sections"] if s.get("name") != QUESTION_SECTION]
    hidden_sources = set()
    for sec in note["sections"]:   # 신고로 숨긴 보고서 문장도 뺀다
        hidden_sources |= {ln.get("sourceId") for ln in sec.get("lines", []) if ln.get("lineId") in hidden}
        sec["lines"] = [ln for ln in sec.get("lines", []) if ln.get("lineId") not in hidden]

    by_section = {}
    for r in sorted(rows, key=lambda r: r.get("at", "")):
        by_section.setdefault(r.get("section"), []).append(r)
    for name, items in by_section.items():
        sec = next((s for s in note["sections"] if s["name"] == name), None)
        if sec is None:   # 틀에 없는 칸(틀이 바뀐 경우)은 맨 뒤에 둔다
            sec = {"name": name, "interviewOnly": True, "lines": []}
            note["sections"].append(sec)
        sec["lines"] += [_out_line(r) for r in items]
        for r in items:
            note.setdefault("sources", {})[r["sourceId"]] = {"docType": INTERVIEW, "program": note["program"],
                                                             "semester": r.get("semester")}
    _section_summary(note, by_section, hidden_sources, hidden)

    note["evidenceCount"] = (note.get("evidenceCount") or 0) + len(rows)
    sems = [s for s in [note.get("lastSemester"), *(r.get("semester") for r in rows)] if s]
    note["lastSemester"] = max(sems) if sems else None
    if not note.get("officialUrl"):
        note["officialUrl"] = _official_url(note["program"])
    return note


# ── 칸별 요약 문단 [v2 작업 78] ────────────────────────────────────────
def summary_line_id(nid, section, text):
    """[11/25 작업 33] 요약 문장 id — 노트·칸·문장 글의 해시라 문단 순서가 바뀌어도 같고, 문장을 다시 만들면(글이 바뀌면)
    새 id가 된다(옛 신고가 다른 문장을 숨기지 않게). 원문 문장 id(「L-…」)와 겹치지 않게 「S-」로 시작한다."""
    return "S-" + hashlib.sha1(f"{nid}|{section}|{text}".encode("utf-8")).hexdigest()[:10]


def find_line(line_id):
    """신고 기록에 남길 문장 정보 {kind: "summary"|"line", noteId, program, section, text} 또는 None.
    요약 문장(S-…)은 notes.json의 칸 summary에서, 원문 문장(L-…)은 notes.json 칸 문장·noteLines에서 찾는다."""
    if not line_id:
        return None
    if line_id.startswith("S-"):
        for nid, n in NOTES.items():
            for sec in n.get("sections", []):
                for s in sec.get("summary") or []:
                    if summary_line_id(nid, sec.get("name"), s.get("text", "")) == line_id:
                        return {"kind": "summary", "noteId": nid, "program": n.get("program"),
                                "section": sec.get("name"), "text": s.get("text", "")}
        return None
    for nid, n in NOTES.items():
        for sec in n.get("sections", []):
            for ln in sec.get("lines", []):
                if ln.get("lineId") == line_id:
                    return {"kind": "line", "noteId": nid, "program": n.get("program"),
                            "section": sec.get("name"), "text": ln.get("text", "")}
    with store.lock():
        rows = list(store.load("noteLines", []))
    for r in rows:
        if "L-" + r.get("sourceId", "") == line_id:
            return {"kind": "line", "noteId": r.get("noteId"), "program": r.get("program"),
                    "section": r.get("section"), "text": r.get("text", "")}
    return None


def _section_summary(note, by_section, hidden_sources, hidden=()):
    """notes.json(원우 build_notes.py)의 칸별 summary를 그대로 넘긴다. 서버는 AI를 부르지 않는다.
    - 배운점은 요약하지 않는다(선배별 원문 인용) → 있어도 뺀다
    - [11/25 작업 33] 요약 문장마다 lineId(summary_line_id)를 붙인다. 신고된 요약 문장(hidden)은 뺀다
    - 신고로 숨긴 문장을 근거로 든 요약 문장은 뺀다. 다 빠지면 summary 생략(화면은 원문 목록)
    - newLines = 요약을 만든 뒤 인터뷰로 새로 붙은 문장 수 = 그 칸 lines 끝 N개(문단은 다시 만들지 않는다)"""
    for sec in note["sections"]:
        summ = sec.pop("summary", None)
        if not summ or sec["name"] == LESSON_SECTION:
            continue
        summ = [{**s, "lineId": summary_line_id(note["id"], sec["name"], s.get("text", ""))} for s in summ
                if s.get("sources") and not hidden_sources.intersection(s["sources"])]
        summ = [s for s in summ if s["lineId"] not in hidden]
        if summ:
            sec["summary"] = summ
            sec["newLines"] = len(by_section.get(sec["name"], []))


# ── 배운점 선배 글자 [11/22] ──────────────────────────────────────────
# 배운점은 선배별 원문 인용이라(디자인 규칙 8절) 문장마다 「선배 A」를 붙인다. 글자는 **이 노트 안에서만** 쓰는 것:
# PRD 9-1에 따라 학과는 넣지 않고, 닮은선배의 nickname(학과 포함)과도 잇지 않는다(이으면 학과가 드러남).
LESSON_SECTION = "배운점"
_who_by_source = None


def _source_owner(sid):
    """보고서·후기 문장 id → 쓴 사람(evidence.json 학번). 화면으로는 내보내지 않는다."""
    global _who_by_source
    if _who_by_source is None:
        _who_by_source = {e["id"]: e.get("학번") for e in _json("evidence.json", []) if e.get("id")}
    return _who_by_source.get(sid)


def _label_lesson_seniors(note, rows):
    owner = {r["sourceId"]: r.get("owner") for r in rows}
    letters = {}
    for sec in note.get("sections", []):
        if sec.get("name") != LESSON_SECTION:
            continue
        for ln in sec.get("lines", []):
            who = owner.get(ln.get("sourceId")) or _source_owner(ln.get("sourceId"))
            if not who:
                continue
            if who not in letters:
                i = len(letters)
                letters[who] = f"선배 {chr(ord('A') + i)}" if i < 26 else f"선배 {i + 1}"
            ln["senior"] = letters[who]


# ── 서버 함수 ─────────────────────────────────────────────────────────
def getNote(me, p):
    nid = (p.get("id") or "").strip()
    rows = _visible_lines(nid=nid) if nid else []
    note = _merge(nid, rows) if nid else None
    if not note:
        return {"error": "노트를 찾지 못했어요"}
    _label_lesson_seniors(note, rows)
    note["country"] = _country(note["program"])
    note["kind"] = _org_kind(note["program"])
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
        card["kind"] = _org_kind(card["program"])
        card["scrapped"] = nid in scrapped
        out.append(card)
    # [11/23 주제별] 비교과는 이수 인원 많은 순(없으면 뒤). 다른 종류 카드의 자리·순서는 그대로
    extra = iter(sorted((c for c in out if c["type"] == "비교과"), key=lambda c: -(c["completedCount"] or -1)))
    out = [next(extra) if c["type"] == "비교과" else c for c in out]
    # 묶음 칩은 type·q로 거른 뒤, country·kind로 거르기 전 카드로 센다(칩을 눌러도 다른 칩이 사라지지 않게)
    groups = {"country": _groups(out, "country"), "kind": _groups(out, "kind")}
    country, org = (f.get("country") or "").strip(), (f.get("kind") or "").strip()
    out = [c for c in out if (not country or c["country"] == country) and (not org or c["kind"] == org)]
    return {"notes": out, "groups": groups}


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


QUESTION_TEXT = "{section} 이야기를 최근 경험으로 듣고 싶어요."


def saveQuestion(me, p):
    """[11/22] 「질문함에 담기」(디자인 규칙 6-1·6-2, PRD ⑧): 노트의 한 칸을 질문함에 hold로 넣는다.
    다음 선배 인터뷰(interviewNext)가 이 질문을 먼저 묻는다. 글은 서버가 정한다(자유 입력 없음 → 검사·AI 없음).
    같은 사람·노트·칸의 hold 질문이 이미 있으면 새로 만들지 않는다(멱등)."""
    import runtime_fns   # runtime_fns가 notes를 import하므로 여기서 부른다
    nid = (p.get("noteId") or "").strip()
    section = (p.get("section") or "").strip()
    note = _merge(nid, _visible_lines(nid=nid)) if nid else None
    if not note:
        return {"error": "노트를 찾지 못했어요"}
    names = [s["name"] for s in note.get("sections", [])]
    if section not in names or section == QUESTION_SECTION:
        return {"error": "담을 수 없는 칸이에요"}
    with store.lock():
        same = next((q for q in store.load("questions", [])
                     if q.get("colreg_no") == me and q.get("noteId") == nid and q.get("칸") == section
                     and q.get("status") == "hold"), None)
    if same:
        qid, already = same["id"], True
    else:
        qid = runtime_fns.add_question(me, QUESTION_TEXT.format(section=section), program=note["program"],
                                       section=section, note_id=nid)
        already = False
    return {"ok": True, "questionId": qid, "already": already,
            "message": "질문함에 담았어요. 다음 선배 인터뷰 때 먼저 물어볼게요."}


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


ROUTES = {"getNote": getNote, "listNotes": listNotes, "scrapNote": scrapNote, "saveQuestion": saveQuestion}
