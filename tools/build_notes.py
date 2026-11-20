# 해봤노트 사전 생성 (원우 담당, 작업 26) — spec 4장 getNote [11/19], 9장 notes.json
# 사용: python tools/build_notes.py          → data/notes.json 생성 후 점검(문제 있으면 종료코드 1)
#       python tools/build_notes.py --check  → 생성하지 않고 기존 파일 점검만
# 원칙: 칸 문장 = 근거 문단 원문 그대로 1:1(text = evidence.text, sourceId = evidence.id). AI 없음.
#       서버(getNote·listNotes)는 이 파일 + runtime/noteLines.json(동의 통과 인터뷰 문장)을 합쳐 응답한다.
#
# 노트 = 국제교류(귀국보고서 있는 학교)·현장실습(후기 있는 업체)·비교과(이수 기록 있는 프로그램 전부)마다 1건.
#   비교과는 근거 문단이 없어 칸이 비어 있고(인터뷰로 채움) oneLine은 ''(화면은 '–'), 커버에 satisfaction(만족도 5점)과
#   completedCount(이수 인원)를 넣는다(11/20 결정: 해봤노트에 보여 주는 용도만). 교환·인턴은 둘 다 null.
# id    : 'N-' + 프로그램명 해시 6자리(데이터가 바뀌어도 그대로 — noteLines가 noteId로 묶이므로). 시연 학교만 'N-marburg'.
# type  : 국제교류는 그 학교 경험자 중 교환학생이 1명이라도 있으면 '교환', 없으면 '파견'(두 틀은 칸이 같다). 현장실습은 '인턴'.
# 인턴  : 후기는 칸이 없는 자유 서술이다. 작업 50(문장 자동 분류)의 결과 data/intern-sections.json({sourceId: 칸})이 있으면
#         그 칸에 넣고 autoClassified: true, 없으면 노트의 'unclassified' 목록에 둔다(화면은 쓰지 않음, evidenceCount엔 셈).
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "notes.json"
FIXED_IDS = {"마르부르크필립스대학교": "N-marburg"}          # spec 4장·mock-data와 같은 id
_TERM = {"1": 1, "여름": 2, "2": 3, "겨울": 4}
# 규정성 진술(학점 인정·장학금·자격 요건·선발 기준). '학점 걱정을 덜었다'처럼 경험만 말한 문장은 잡지 않게 좁힌다
OFFICIAL_RE = re.compile(r"학점\s*인정|인정\s*(신청|서류|받)|전공\s*인정|교양\s*인정|변환\s*성적|몇\s*학점|장학|선발|자격|평점|등록금")
FILLER_RE = re.compile(r"^(?:(?:참고로|경험상|사실|개인적으로|하나 꼽자면|하나 더,|미리 말해 두면|제 경우엔|지나고 보니|확실히|그리고|또|"
                       r"진짜|체감상|한국과 비교하면|그 시기엔|저 같은 경우|돌이켜 보면|지금 생각해도|솔직히 말하면|덧붙이자면)\s*)+")


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def note_id(program):
    return FIXED_IDS.get(program) or "N-" + hashlib.sha1(program.encode("utf-8")).hexdigest()[:6]


def term_key(sem):
    y, t = sem.split("-")
    return int(y), _TERM.get(t, 0)


def first_sentence(text):
    s = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    return FILLER_RE.sub("", s).strip() or s


def _grade_range(records):
    """이수 당시 학년 중 많은 순으로 60% 이상을 덮는 학년들의 범위(예: '1~2', '3')."""
    c = Counter(r["이수 당시 학년"] for r in records if r.get("이수 당시 학년"))
    if not c:
        return "전"
    got, total, acc = [], sum(c.values()), 0
    for g, n in sorted(c.items(), key=lambda x: (-x[1], x[0])):
        got.append(g)
        acc += n
        if acc / total >= 0.6:
            break
    lo, hi = min(got), max(got)
    return f"{lo}" if lo == hi else f"{lo}~{hi}"


def item_key(e):
    """보고서 문항 순서(1-1 < 1-2 < … < 2-7 < 3 < 4), 같은 문항이면 최근 학기 먼저, 그다음 id."""
    head = e["문항"].split(".")[0]
    nums = tuple(int(x) for x in head.split("-") if x.isdigit())
    y, t = term_key(e["semester"])
    return nums, -y, -t, e["id"]


def build():
    programs = load("programs.json")
    frames = load("frames.json")
    evidence = load("evidence.json")
    students = load("students.json")
    interns = load("internships.json")
    cls_path = DATA / "intern-sections.json"
    classified = json.loads(cls_path.read_text(encoding="utf-8")) if cls_path.exists() else {}

    ev_by = defaultdict(list)
    for e in evidence:
        ev_by[e["프로그램명"]].append(e)
    exch = defaultdict(Counter)
    for s in students:
        if s.get("파견대학"):
            exch[s["파견대학"]][s.get("해외경험 유형")] += 1
    job = defaultdict(Counter)
    for r in interns:
        job[r["업체명"]][r["직군"]] += 1
    taken = defaultdict(list)                                # 비교과 이수 기록(학기·이수 당시 학년)
    for r in load("extracurricular.json"):
        taken[r["프로그램명"]].append(r)
    sat = {r["프로그램명"]: r for r in load("extracurricular-satisfaction.json")}

    notes = []
    for p in programs:
        name = p["프로그램명"]
        rows = ev_by.get(name, [])
        satisfaction = completed = None
        if p["분야"] == "국제교류" and rows:
            ntype = "교환" if exch[name].get("교환학생") else "파견"
            for_whom = f"{p['세부']}권 {ntype}을 생각하는 1~2학년"
        elif p["분야"] == "현장실습" and rows:
            ntype = "인턴"
            for_whom = f"{job[name].most_common(1)[0][0]} 분야 현장실습을 생각하는 2~3학년"
        elif p["분야"] == "비교과" and taken.get(name):
            # 비교과는 근거 문단이 없다 → 칸은 비워 두고 인터뷰로 채운다. 커버에 만족도·이수 인원(11/20 결정: 보여 주는 용도만)
            ntype = "비교과"
            for_whom = f"{_grade_range(taken[name])}학년이 많이 이수한 비교과"
            satisfaction = p.get("만족도(5점)")
            completed = sat.get(name, {}).get("이수 인원(가상)", len(taken[name]))
        else:
            continue
        frame = frames[ntype]
        lines_by = defaultdict(list)
        unclassified = []
        sources = {}
        for e in sorted(rows, key=item_key):
            line = {"text": e["text"], "sourceId": e["id"], "lineId": f"L-{e['id']}", "official": bool(OFFICIAL_RE.search(e["text"]))}
            sources[e["id"]] = {"docType": e["docType"], "program": name, "semester": e["semester"]}
            sec = e["칸"] or classified.get(e["id"])
            if ntype == "인턴" and not e["칸"] and sec:
                line["autoClassified"] = True
            if sec in frame["칸"] and sec not in frame["인터뷰로만"]:
                lines_by[sec].append(line)
            else:
                unclassified.append(line)
        sections = [{"name": s, "interviewOnly": s in frame["인터뷰로만"], "lines": lines_by.get(s, [])} for s in frame["칸"]]
        biggest = max(sections, key=lambda s: len(s["lines"]))       # 같으면 틀 순서상 앞 칸
        one_src = biggest["lines"][0]["text"] if biggest["lines"] else (unclassified[0]["text"] if unclassified else "")
        sems = [e["semester"] for e in rows] or [r["semester"] for r in taken[name]]
        note = {
            "id": note_id(name), "program": name, "type": ntype,
            "oneLine": first_sentence(one_src) if one_src else "", "forWhom": for_whom,
            "evidenceCount": len(rows), "lastSemester": max(sems, key=term_key),
            "satisfaction": satisfaction, "completedCount": completed,
            "sections": sections, "sources": sources,
        }
        if unclassified:
            note["unclassified"] = unclassified
        notes.append(note)
    return notes


def check(notes):
    bad = []
    evidence = {e["id"]: e for e in load("evidence.json")}
    frames = load("frames.json")
    names = {p["프로그램명"] for p in load("programs.json")}
    ex_names = {p["프로그램명"] for p in load("programs.json") if p["분야"] == "비교과"}
    comp, last_ex = Counter(), defaultdict(list)
    for r in load("extracurricular.json"):
        comp[r["프로그램명"]] += 1
        last_ex[r["프로그램명"]].append(r["semester"])
    if {n["program"] for n in notes if n["type"] == "비교과"} != ex_names:
        bad.append("비교과 노트가 비교과 프로그램 전부와 다름")
    seen = Counter()
    if json.dumps(build(), ensure_ascii=False) != json.dumps(notes, ensure_ascii=False):
        bad.append("다시 만들면 결과가 다름 — data/가 바뀌었으면 인자 없이 다시 생성")
    ids = [n["id"] for n in notes]
    if len(ids) != len(set(ids)):
        bad.append("노트 id 중복")
    if len({n["program"] for n in notes}) != len(notes):
        bad.append("한 프로그램에 노트가 여러 개")
    for n in notes:
        if n["program"] not in names:
            bad.append(f"programs.json에 없는 프로그램: {n['program']}")
        frame = frames[n["type"]]
        if [s["name"] for s in n["sections"]] != frame["칸"]:
            bad.append(f"칸 순서·이름이 frames.json과 다름: {n['id']}")
        all_lines = [l for s in n["sections"] for l in s["lines"]] + n.get("unclassified", [])
        for s in n["sections"]:
            if s["interviewOnly"] != (s["name"] in frame["인터뷰로만"]):
                bad.append(f"interviewOnly 틀림: {n['id']} {s['name']}")
            if s["interviewOnly"] and s["lines"]:
                bad.append(f"인터뷰로만 칸에 사전 문장이 있음: {n['id']} {s['name']}")
        for l in all_lines:
            e = evidence.get(l["sourceId"])
            seen[l["sourceId"]] += 1
            if not e or l["text"] != e["text"] or e["프로그램명"] != n["program"]:
                bad.append(f"원문 1:1이 아님: {n['id']} {l['sourceId']}")
            if l["lineId"] != f"L-{l['sourceId']}" or l["sourceId"] not in n["sources"]:
                bad.append(f"lineId·sources 틀림: {n['id']} {l['sourceId']}")
        for s in n["sections"]:
            for l in s["lines"]:
                e = evidence[l["sourceId"]]
                if e["칸"] and e["칸"] != s["name"]:
                    bad.append(f"근거 칸과 노트 칸이 다름: {l['sourceId']} {e['칸']} → {s['name']}")
        if n["evidenceCount"] != len(all_lines):
            bad.append(f"evidenceCount ≠ 문장 수: {n['id']}")
        if all_lines:
            if n["lastSemester"] != max((n["sources"][l["sourceId"]]["semester"] for l in all_lines), key=term_key):
                bad.append(f"lastSemester 틀림: {n['id']}")
            if not n["oneLine"]:
                bad.append(f"근거가 있는데 oneLine 빈 칸: {n['id']}")
        elif n["type"] != "비교과" or n["oneLine"]:
            bad.append(f"근거 없는 노트는 비교과만, oneLine은 빈 값(화면은 '–'): {n['id']}")
        if not n["forWhom"]:
            bad.append(f"forWhom 빈 칸: {n['id']}")
        if n["type"] == "비교과":
            if not isinstance(n["satisfaction"], (int, float)) or not n["completedCount"]:
                bad.append(f"비교과 노트에 만족도·이수 인원 없음: {n['id']}")
            if n["completedCount"] != comp.get(n["program"]):
                bad.append(f"이수 인원이 비교과 기록 수와 다름: {n['id']}")
            if n["lastSemester"] != max(last_ex[n["program"]], key=term_key):
                bad.append(f"비교과 lastSemester 틀림: {n['id']}")
        elif n["satisfaction"] is not None or n["completedCount"] is not None:
            bad.append(f"교환·인턴 노트에 만족도·이수 인원이 있음: {n['id']}")
    missing = set(evidence) - set(seen)
    if missing:
        bad.append(f"노트에 안 들어간 근거 {len(missing)}건(예: {sorted(missing)[:3]})")
    if any(v > 1 for v in seen.values()):
        bad.append("한 근거가 두 번 들어감")
    m = next((n for n in notes if n["program"] == "마르부르크필립스대학교"), None)
    if not m or m["id"] != "N-marburg":
        bad.append("시연 노트 N-marburg 없음")
    return bad


def summary(notes):
    t = Counter(n["type"] for n in notes)
    lines = sum(len(s["lines"]) for n in notes for s in n["sections"])
    unc = sum(len(n.get("unclassified", [])) for n in notes)
    off = sum(l["official"] for n in notes for s in n["sections"] for l in s["lines"])
    print(f"노트 {len(notes)}개: {dict(t)} · 칸에 들어간 문장 {lines} · 칸 분류 전 {unc} · official 표시 {off}")


def main():
    if "--check" in sys.argv:
        notes = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        notes = build()
        OUT.write_text(json.dumps(notes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"생성: {OUT.relative_to(ROOT)}")
    summary(notes)
    bad = check(notes)
    print(f"점검 문제 {len(bad)}건")
    for b in bad[:20]:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
