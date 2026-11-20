# score.py — 닮은 선배 점수·이유·후보·정렬 (원우 담당, 작업 22). AI 없음.
# 규칙: docs/spec-v1.md 4장 recommendSeniors [11/20 개정]
#   후보 = 그 노트(희망 프로그램)의 경험자 전부. 점수 하한 없음. 직원 행·본인은 뺀다.
#   점수(순서용) = 학과 일치 5 · 이중전공 일치 4 · 단과대 일치 3 · 공통 비교과 2(여러 개여도 한 번)
#   정렬 = 점수 ↓ → 동점이면 ① 수락 대기 요청이 적은 선배 ② 최근 학기에 다녀온 선배 → (③ 학번, 결과 고정용)
#   reasons 맨 앞은 항상 「희망 프로그램을 경험했어요」, 겹치는 점이 있으면 뒤에 더한다.
#   받는 한도: 수락 대기 요청이 5건이면 requestsFull.
# 이 파일은 계산만 한다. 목록 9명 보관·글자(A·B…)·재계산 시점은 recommendSeniors(runtime)가 맡는다.
#
# 쓰는 법:
#   from score import rank_seniors
#   rank_seniors("H0143", "마르부르크필립스대학교", waiting={"H0469": 1})
#   → [{"studentId", "score", "reasons", "requestsFull", "waiting", "semester"}, ...]  (정렬된 전체 후보)
# 시험: cd functions && python test_score.py
import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
WEIGHTS = {"학과": 5, "이중전공": 4, "단과대": 3, "공통 비교과": 2}   # 바꾸면 spec 4장·PRD 4-1도 함께
REQUEST_LIMIT = 5                                                  # 받는 선배당 수락 대기 요청 한도
FIRST_REASON = "희망 프로그램을 경험했어요"
_TERM = {"1": 1, "여름": 2, "2": 3, "겨울": 4}                      # 학기 순서: 1학기 < 여름 < 2학기 < 겨울
_TERM_NAME = {1: "1", 2: "여름", 3: "2", 4: "겨울"}


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _data():
    """학생·경험 기록을 한 번만 읽어 둔다. 데이터 파일이 바뀌면 reload()."""
    students = {s["colreg_no"]: s for s in _load("students.json") if str(s.get("colreg_no", "")).startswith("H")}
    extra = {}                                          # 학번 → 비교과 프로그램(기록 순서 유지, 중복 없음)
    exp = {}                                            # 프로그램 → {학번: (연도, 학기 코드)}
    for r in _load("extracurricular.json"):
        extra.setdefault(r["가상학번"], [])
        if r["프로그램명"] not in extra[r["가상학번"]]:
            extra[r["가상학번"]].append(r["프로그램명"])
        term = (int(r["이수학년도"]), int(r["이수학기(1~4)"]))
        cur = exp.setdefault(r["프로그램명"], {}).get(r["가상학번"])
        exp[r["프로그램명"]][r["가상학번"]] = max(cur, term) if cur else term
    reports = {r["학번"]: (int(r["학년도"]), int(r["학기"])) for r in _load("reports.json")}
    for h, s in students.items():                       # 국제교류: 파견대학. 학기는 귀국보고서, 없으면 입학년도·파견시기로 계산
        if s.get("파견대학"):
            term = reports.get(h) or _term_from_grade(s)
            exp.setdefault(s["파견대학"], {})[h] = term
    for r in _load("internships.json"):                 # 현장실습: 후기의 업체명·semester
        y, t = r["semester"].split("-")
        exp.setdefault(r["업체명"], {})[r["학번"]] = (int(y), _TERM[t])
    return students, extra, exp


def _term_from_grade(s):
    """'3학년 1학기' + 입학년도 → (연도, 학기 코드). 귀국보고서가 없는 20명용."""
    try:
        g, t = s["파견시기"].replace("학년", "").replace("학기", "").split()
        return int(s["입학년도"]) + int(g) - 1, 1 if t == "1" else 3
    except (KeyError, ValueError, AttributeError, TypeError):
        return (0, 0)


def reload():
    _data.cache_clear()


def experienced(program):
    """그 프로그램 경험자 학번 목록(직원 제외)."""
    students, _, exp = _data()
    return sorted(h for h in exp.get(program, {}) if h in students)


def score_senior(me, senior):
    """보는 사람(me)과 선배(senior, 둘 다 colreg_no)의 점수와 겹치는 점.
    돌려주는 값: {"score": int, "reasons": [...]} — reasons에는 맨 앞 「희망 프로그램…」을 넣지 않는다(rank_seniors가 붙인다)."""
    students, extra, _ = _data()
    a, b = students.get(me, {}), students.get(senior, {})
    score, reasons = 0, []
    if a.get("univ_nm") and a.get("univ_nm") == b.get("univ_nm"):
        score += WEIGHTS["단과대"]
        reasons.append(f"같은 {b['univ_nm']}")
    if a.get("crs_nm") and a.get("crs_nm") == b.get("crs_nm"):
        score += WEIGHTS["학과"]
        reasons.append(f"같은 {b['crs_nm']}")
    if a.get("dbl_mjr_nm") and a.get("dbl_mjr_nm") == b.get("dbl_mjr_nm"):
        score += WEIGHTS["이중전공"]
        reasons.append(f"이중전공 {b['dbl_mjr_nm']} 같음")
    common = [p for p in extra.get(senior, []) if p in set(extra.get(me, []))]
    if common:
        score += WEIGHTS["공통 비교과"]
        reasons.append(f"{common[0]} 함께 이수" if len(common) == 1 else f"{common[0]} 외 {len(common) - 1}개 함께 이수")
    return {"score": score, "reasons": reasons}


def rank_seniors(me, program, waiting=None):
    """희망 프로그램 경험자 전부를 정렬해 돌려준다(점수 하한 없음, 본인·직원 제외).
    waiting: {선배 학번: 수락 대기 요청 수} — runtime messages.json에서 센 값(없으면 0)."""
    _, _, exp = _data()
    waiting = waiting or {}
    out = []
    for h in experienced(program):
        if h == me:
            continue
        s = score_senior(me, h)
        y, t = exp[program][h]
        w = int(waiting.get(h, 0))
        out.append({"studentId": h, "score": s["score"], "reasons": [FIRST_REASON] + s["reasons"],
                    "requestsFull": w >= REQUEST_LIMIT, "waiting": w,
                    "semester": f"{y}-{_TERM_NAME.get(t, t)}" if y else None})
    # 점수 ↓, 대기 요청 ↑, 최근 학기 ↓, 학번 ↑
    out.sort(key=lambda r: (-r["score"], r["waiting"], tuple(-x for x in exp[program][r["studentId"]]), r["studentId"]))
    return out
