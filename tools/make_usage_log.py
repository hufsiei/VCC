# 사용 로그 시드 생성기 (원우 담당, 작업 65) — PRD 6-3
# 사용: python tools/make_usage_log.py            → data/usage-log.json 생성 후 점검
#       python tools/make_usage_log.py --check    → 생성하지 않고 기존 파일 점검만(같은 seed로 다시 만들어 비교)
# 원칙: 실제 학생 정보·실제 후기 문장을 쓰지 않는다. 모든 질문 문장은 아래 템플릿 × 프로그램 이름 치환.
#       같은 seed면 결과가 한 글자도 같다(생성 시각 같은 값은 넣지 않는다).
#
# 질문 행 모양 = functions/runtime_fns.py add_question()이 쌓는 questions.json + PRD 6-3의 분야·근거수
#   {id, at, colreg_no, crs_nm, regst_grad, 프로그램명|null, 분야|null, 칸|null, status ok|hold|official, 질문, 근거수, noteId(null), 운영부서코드|null}
# 상태는 askBoo 규칙과 맞춘다: 규정 표현(OFFICIAL_RE)이면 official, 근거가 있으면 ok, 없으면 hold
#   (노트 없는 프로그램·보고서에 칸이 없는 주제·인턴 근무조건 → hold)
#
# [결정] PRD는 '프로그램 비중 = 이수 인원 비례'지만, 분야를 가리지 않고 비례하면 비교과(이수 2,240건)가 질문의 약 76%가
#   되고 비교과는 노트가 없어 전부 hold라 보류율 28%를 맞출 수 없다. 그래서 분야 몫(국제교류 55·현장실습 20·비교과 15·
#   분류 안 됨 10%)을 먼저 정하고 분야 안에서 이수 인원에 비례시킨다. 시연 프로그램(마르부르크필립스대학교)은 ×6 가중(콘솔 질문 순위 1위가 되게).
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 20261120
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "usage-log.json"
KST = timezone(timedelta(hours=9))
START, END = datetime(2025, 9, 1, tzinfo=KST), datetime(2026, 11, 30, 23, 59, tzinfo=KST)
DEMO = {"H0143", "H0469", "H0745"}          # 시연 인물은 로그에 넣지 않는다(내 보관함이 시연 대본과 섞이지 않게)
MARBURG = "마르부르크필립스대학교"

# askBoo(functions/askboo.py)와 같은 규정 질문 판별식 — 템플릿이 이 규칙과 어긋나지 않는지 점검에 쓴다
OFFICIAL_RE = re.compile(r"평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수")
INTERVIEW_ONLY_INTERN = re.compile(r"월급|급여|시급|페이|보수|연봉|근무\s*시간|근무\s*조건|복지|휴가|정규직|채용\s*전환")

TOTAL = 1200
# 분야별 건수와 그 안의 상태 건수(합계: hold 336 = 28%, official 120 = 규정성 키워드 질문 200건의 60%)
PLAN = {
    "국제교류": {"total": 660, "official": 60, "hold": 51, "kw_ok": 60},
    "현장실습": {"total": 240, "official": 15, "hold": 30, "kw_ok": 20},
    "비교과":   {"total": 180, "official": 20, "hold": 160, "kw_ok": 0},
    None:       {"total": 120, "official": 25, "hold": 95, "kw_ok": 0},
}
COUNTS = {"interviews": 40, "consents": 32, "reports": 12, "requests": 60, "accepted": 38}

# official 템플릿은 모두 학점·장학·선발 중 하나를 넣는다(PRD: 이 키워드 질문의 60%가 official)
# ── 질문 템플릿(평가 질문 4유형: 동의어=경험 질문 / 범위밖 / 함정(분류 안 됨) / 규정오해=규정성) ──────────
EX_OK = {   # 국제교류 경험 질문: 칸 → 템플릿. 보고서 문항(evidence 칸)과 이어진다
    "지원": ["{p} 지원 서류는 뭘 준비해요?", "{p} 비자는 어떻게 받았어요?", "{p} 가기 전에 챙길 준비물 있어요?",
            "{p} 유학생 보험은 어떻게 했어요?", "{p} 입학허가서 받을 때 주의할 점은요?"],
    "학점": ["{p} 수강신청은 어떻게 해요?", "{p} 수업 따라갈 만해요?", "{p} 어학 수업 어때요?", "{p} 세미나 과제 많아요?"],
    "비용": ["{p} 한 달 생활비 얼마 들어요?", "{p} 물가 어때요?", "{p} 가면 예산 얼마 잡아야 해요?"],
    "생활": ["{p} 기숙사 구하기 어려워요?", "{p} 공항에서 학교까지 어떻게 가요?", "{p} 버디 프로그램 있어요?",
            "{p} 치안은 괜찮아요?", "{p} 숙소는 어떻게 구했어요?"],
    "팁":   ["{p} 다녀온 선배 조언 듣고 싶어요", "{p} 후기 알려 주세요", "{p} 경험담 있어요?"],
}
EX_KW_OK = {"학점": ["{p} 학점 인정 받을 때 주의할 점은요?", "{p}에서 들은 수업 학점 인정 잘 됐어요?"]}   # 키워드는 있지만 경험 질문
EX_OUT = ["{p} 가서 아르바이트 할 수 있어요?", "{p} 다녀오면 취업에 도움 돼요?", "{p} 현지에서 인턴 구할 수 있어요?",
          "{p} 근처 여행 코스 추천해 주세요", "{p} 졸업 후 대학원 진학한 선배 있어요?"]               # 보고서에 칸이 없는 주제
EX_OFF = [("{p} 선발되려면 평점 몇 점 필요해요?", "지원"), ("{p} 선발 인원은 몇 명이에요?", "지원"),
          ("{p} 가면 장학금 받을 수 있어요?", "비용"), ("{p} 학점 인정 신청은 언제 해요?", "학점"),
          ("{p} 파견 기간 등록금도 장학금으로 돼요?", "비용"), ("{p} 다녀오면 몇 학점까지 인정돼요?", "학점")]

IN_OK = {"업무내용": ["{p} 실습 가면 무슨 일 해요?", "{p} 하루 일과 어때요?", "{p} 실습 분위기 어때요?"],
         "지원·선발": ["{p} 실습 지원할 때 뭘 준비했어요?", "{p} 실습 전에 공부해 가면 좋은 거 있어요?"],
         "배운점": ["{p} 실습하면서 뭘 배웠어요?", "{p} 실습 해 보니 어땠어요?"]}
IN_KW_OK = {"지원·선발": ["{p} 선발 면접 분위기 어땠어요?", "{p} 서류 선발 때 뭘 봤던 것 같아요?"]}
IN_HOLD = ["{p} 실습 월급 얼마예요?", "{p} 근무 시간은 어떻게 돼요?", "{p} 정규직 전환도 돼요?", "{p} 실습 복지 어때요?"]   # 근무조건
IN_OFF = [("{p} 현장실습 하면 몇 학점 인정돼요?", "지원·선발"), ("{p} 실습 선발 기준이 뭐예요?", "지원·선발"),
          ("{p} 실습 학점 인정 신청은 어떻게 해요?", "지원·선발")]

BI_HOLD = {"활동내용": ["{p} 들을 만해요?", "{p} 어떤 활동 해요?", "{p} 과제 많아요?", "{p} 신청하면 뭐가 좋아요?"],
           "배운점": ["{p} 이수하고 뭐가 달라졌어요?", "{p} 진로에 도움 됐어요?"]}
BI_OFF = [("{p} 이수하면 장학금 있어요?", "활동내용"), ("{p} 선발 기준이 뭐예요?", "활동내용")]

UN_HOLD = [("교환학생 어디가 제일 좋아요?", "국제교류", None), ("유럽 교환 생활비 평균 얼마예요?", "국제교류", "비용"),
           ("리옹 대학 기숙사 어때요?", "국제교류", "생활"), ("소르본 교환 후기 있어요?", "국제교류", "팁"),
           ("무역 쪽 인턴 어디가 좋아요?", "현장실습", None), ("방학 때 할 만한 현장실습 추천해 주세요", "현장실습", None),
           ("영어로 수업 듣는 학교 어디예요?", "국제교류", "학점"), ("취업 특강 중에 들을 만한 거 있어요?", "비교과", None),
           ("특교원 프로그램 뭐가 좋아요?", "비교과", None), ("교환이랑 인턴 둘 다 해 본 선배 있어요?", None, None)]
UN_OFF = [("교환학생 선발 때 평점 몇 점이어야 해요?", "국제교류", "지원"), ("휴학하고 교환 가도 학점 인정돼요?", "국제교류", "학점"),
          ("교환 가면 장학금 나와요?", "국제교류", "비용"), ("초과학기 장학금도 있어요?", None, None),
          ("현장실습 몇 학점 인정받을 수 있어요?", "현장실습", "지원·선발")]

REPORT_REASONS = ["사실과 달라요", "개인 정보가 들어 있어요", "오래된 정보예요", "공식 안내와 달라요"]
REPORT_STATUS = ["숨김 중"] * 7 + ["공식 안내 연결됨"] * 3 + ["복구"] * 2

# 월별 질문 비중(학기 초 3·9월, 수강신청 2·8월, 교환 지원 3~4·9~10월, 인턴 모집 5~6·11~12월에 봉우리)
MONTH_W = {"국제교류": {1: 2, 2: 4, 3: 8, 4: 6, 5: 3, 6: 2, 7: 2, 8: 4, 9: 8, 10: 7, 11: 4, 12: 2},
           "현장실습": {1: 2, 2: 2, 3: 3, 4: 4, 5: 7, 6: 6, 7: 3, 8: 2, 9: 3, 10: 4, 11: 7, 12: 6},
           "비교과":   {1: 1, 2: 3, 3: 8, 4: 5, 5: 4, 6: 2, 7: 1, 8: 3, 9: 8, 10: 5, 11: 4, 12: 2},
           None:       {1: 2, 2: 4, 3: 6, 4: 4, 5: 3, 6: 2, 7: 2, 8: 4, 9: 6, 10: 5, 11: 4, 12: 2}}
HOUR_W = {h: w for h, w in zip(range(24), [2, 1, 1, 0, 0, 0, 0, 1, 2, 3, 4, 4, 5, 4, 4, 4, 4, 5, 5, 6, 7, 8, 7, 4])}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def display_name(p, aliases, rnd):
    """질문에 쓰는 이름: 별칭이 있으면 30% 별칭, ㈜·(유)·[특교원] 같은 꾸밈은 뺀다(학생이 그렇게 쓰지 않음)."""
    if aliases.get(p) and rnd.random() < 0.3:
        return rnd.choice(aliases[p])
    s = re.sub(r"^\[[^\]]+\]\s*", "", p).replace("\xad", "")
    s = re.sub(r"㈜|\(주\)|\(유\)", "", s).strip()
    if len(s) > 18:   # 긴 비교과 공식 명칭은 학생이 줄여 쓴다: 콜론·꺾쇠·괄호 앞까지
        s = re.split(r"\s*[:<(]", s)[0].strip() or s
    return s


def build(seed=SEED):
    rnd = random.Random(seed)
    programs = {p["프로그램명"]: p for p in load("programs.json")}
    aliases = {k: v["별칭"] for k, v in programs.items() if v.get("별칭")}
    students = [s for s in load("students.json") if str(s.get("colreg_no", "")).startswith("H")]
    evidence = load("evidence.json")
    extra = load("extracurricular.json")
    interns = load("internships.json")

    # 이수자(그 프로그램에 대해 묻지 않는 사람) — 국제교류 = 파견대학, 현장실습 = 후기 업체, 비교과 = 이수 기록
    done = defaultdict(set)
    for s in students:
        if s.get("파견대학"):
            done[s["파견대학"]].add(s["colreg_no"])
    for r in interns:
        done[r["업체명"]].add(r["학번"])
    for r in extra:
        done[r["프로그램명"]].add(r["가상학번"])

    ev_by = defaultdict(list)                      # (프로그램, 칸) → 근거 수
    for e in evidence:
        ev_by[(e["프로그램명"], e["칸"] or None)].append(e)
        ev_by[(e["프로그램명"], "*")].append(e)
    noted = {p for (p, k) in ev_by if k == "*"}

    by_field = defaultdict(list)
    for p, v in programs.items():
        by_field[v["분야"]].append(p)
    weight = {p: max(len(done[p]), 1) * (6 if p == MARBURG else 1) for p in programs}

    def pick_program(field, only_noted=False, need=None):
        cands = [p for p in sorted(by_field[field]) if (not only_noted or p in noted) and (need is None or need(p))]
        return rnd.choices(cands, weights=[weight[p] for p in cands])[0]

    grade_w = {"국제교류": {1: 3, 2: 4, 3: 3, 4: 1}, "현장실습": {1: 1, 2: 3, 3: 4, 4: 4},
               "비교과": {1: 3, 2: 3, 3: 3, 4: 2}, None: {1: 2, 2: 3, 3: 3, 4: 2}}
    by_grade = defaultdict(list)
    for s in students:
        if s["colreg_no"] not in DEMO and s.get("regst_grad"):
            by_grade[s["regst_grad"]].append(s)

    def pick_asker(field, program):
        while True:
            g = rnd.choices(list(grade_w[field]), weights=list(grade_w[field].values()))[0]
            s = rnd.choice(by_grade[g])
            if program is None or s["colreg_no"] not in done[program]:
                return s

    months = []
    d = START
    while d <= END:
        months.append((d.year, d.month))
        d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)

    def pick_time(field):
        y, m = rnd.choices(months, weights=[MONTH_W[field][mm] * (1 + 0.04 * i) for i, (yy, mm) in enumerate(months)])[0]
        nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=KST)
        days = (min(nxt, END + timedelta(minutes=1)) - datetime(y, m, 1, tzinfo=KST)).days
        h = rnd.choices(list(HOUR_W), weights=list(HOUR_W.values()))[0]
        return datetime(y, m, 1 + rnd.randrange(days), h, rnd.randrange(60), rnd.randrange(60), tzinfo=KST)

    # ── 질문 슬롯: 분야 × 종류를 정확한 건수로 만든 뒤 채운다 ──
    slots = []
    for field, pl in PLAN.items():
        ok = pl["total"] - pl["official"] - pl["hold"]
        slots += [(field, "official")] * pl["official"] + [(field, "hold")] * pl["hold"] \
            + [(field, "kw_ok")] * pl["kw_ok"] + [(field, "ok")] * (ok - pl["kw_ok"])
    rnd.shuffle(slots)

    rows = []
    for field, kind in slots:
        prog, sec, text, status, n_ev = None, None, None, kind if kind in ("official", "hold") else "ok", 0
        if field == "국제교류":
            if kind == "official":
                prog = pick_program(field)
                t, sec = rnd.choice(EX_OFF)
            elif kind == "hold":
                prog = pick_program(field)
                if prog in noted:
                    t = rnd.choice(EX_OUT)
                else:                                            # 노트(보고서) 없는 학교는 무엇을 물어도 hold
                    sec = rnd.choice(list(EX_OK))
                    t = rnd.choice(EX_OK[sec])
            else:
                pool = EX_KW_OK if kind == "kw_ok" else EX_OK
                sec = rnd.choice(list(pool))
                prog = pick_program(field, need=lambda p, s=sec: bool(ev_by.get((p, s))))
                t = rnd.choice(pool[sec])
                n_ev = len(ev_by[(prog, sec)])
        elif field == "현장실습":
            prog = pick_program(field, only_noted=True)
            if kind == "official":
                t, sec = rnd.choice(IN_OFF)
            elif kind == "hold":
                t, sec = rnd.choice(IN_HOLD), "근무조건"
            else:
                pool = IN_KW_OK if kind == "kw_ok" else IN_OK
                sec = rnd.choice(list(pool))
                t = rnd.choice(pool[sec])
                n_ev = len(ev_by[(prog, "*")])                   # 현장실습 후기는 칸이 없어 전체 문단이 후보(askBoo와 같음)
        elif field == "비교과":
            prog = pick_program(field)
            if kind == "official":
                t, sec = rnd.choice(BI_OFF)
            else:
                sec = rnd.choice(list(BI_HOLD))
                t = rnd.choice(BI_HOLD[sec])
        else:                                                    # 분류 안 됨: 프로그램 없음
            text, f2, sec = rnd.choice(UN_OFF if kind == "official" else UN_HOLD)
        if text is None:
            text = t.format(p=display_name(prog, aliases, rnd))
        asker = pick_asker(field, prog)
        rows.append({
            "id": None, "at": pick_time(field), "colreg_no": asker["colreg_no"], "crs_nm": asker.get("crs_nm"),
            "regst_grad": asker.get("regst_grad"), "프로그램명": prog,
            "분야": programs[prog]["분야"] if prog else (f2 if field is None else field),
            "칸": sec, "status": status, "질문": text, "근거수": n_ev, "noteId": None,
            "운영부서코드": programs[prog]["운영부서코드"] if prog else None,
        })
    rows.sort(key=lambda r: (r["at"], r["colreg_no"]))
    for i, r in enumerate(rows, 1):
        r["id"] = f"UQ-{i:04d}"
        r["at"] = r["at"].isoformat(timespec="seconds")

    # ── 인터뷰 40 · 공개 동의 32 · 신고 12 · 쪽지 요청 60(수락 38) ──
    def completer(p):
        ids = sorted(done[p] - DEMO)
        return rnd.choice(ids) if ids else None

    interviews = []
    mix = ["국제교류"] * 22 + ["현장실습"] * 10 + ["비교과"] * 8
    rnd.shuffle(mix)
    for field in mix:
        prog = pick_program(field, need=lambda p: bool(done[p] - DEMO))
        at = pick_time(field)
        n = rnd.randint(4, 9)
        interviews.append({"id": None, "at": at, "colreg_no": completer(prog), "프로그램명": prog, "분야": field,
                           "문장수": n, "후배질문답": rnd.randint(0, 2)})
    interviews.sort(key=lambda r: r["at"])
    for i, r in enumerate(interviews, 1):
        r["id"] = f"UI-{i:03d}"
    consents = []
    for r in rnd.sample(interviews, COUNTS["consents"]):
        removed = rnd.choice([0, 0, 0, 1, 1, 2])
        consents.append({"id": None, "at": r["at"] + timedelta(minutes=rnd.randint(3, 40)), "interviewId": r["id"],
                         "colreg_no": r["colreg_no"], "프로그램명": r["프로그램명"],
                         "공개문장수": r["문장수"] - removed, "제외문장수": removed})
    consents.sort(key=lambda r: r["at"])
    for i, r in enumerate(consents, 1):
        r["id"] = f"UC-{i:03d}"
    for r in interviews:
        r["at"] = r["at"].isoformat(timespec="seconds")

    reports = []
    status_list = REPORT_STATUS[:]
    rnd.shuffle(status_list)
    pool = [e for e in evidence]
    for st in status_list:
        e = rnd.choice(pool)
        p = e["프로그램명"]
        who = pick_asker(programs[p]["분야"], p)
        reports.append({"id": None, "at": pick_time(programs[p]["분야"]), "colreg_no": who["colreg_no"], "프로그램명": p,
                        "lineId": f"L-{e['id']}", "sourceId": e["id"], "사유": rnd.choice(REPORT_REASONS), "status": st})
    reports.sort(key=lambda r: r["at"])
    for i, r in enumerate(reports, 1):
        r["id"] = f"UR-{i:03d}"
        r["at"] = r["at"].isoformat(timespec="seconds")

    requests = []
    st = ["accepted"] * COUNTS["accepted"] + ["declined"] * 12 + ["pending"] * (COUNTS["requests"] - COUNTS["accepted"] - 12)
    rnd.shuffle(st)
    for s in st:
        field = rnd.choices(["국제교류", "현장실습", "비교과"], weights=[6, 3, 1])[0]
        prog = pick_program(field, need=lambda p: bool(done[p] - DEMO))
        frm = pick_asker(field, prog)
        requests.append({"id": None, "at": pick_time(field), "from": frm["colreg_no"], "to": completer(prog),
                         "프로그램명": prog, "status": s})
    requests.sort(key=lambda r: r["at"])
    for i, r in enumerate(requests, 1):
        r["id"] = f"UM-{i:03d}"
        r["at"] = r["at"].isoformat(timespec="seconds")
    for r in consents:
        r["at"] = r["at"].isoformat(timespec="seconds")

    return {
        "meta": {"seed": seed, "기간": [START.date().isoformat(), END.date().isoformat()],
                 "생성": "tools/make_usage_log.py (작업 65) — 템플릿 생성, 실제 학생·후기 문장 없음",
                 "건수": {"questions": len(rows), "interviews": len(interviews), "consents": len(consents),
                          "reports": len(reports), "requests": len(requests)}},
        "questions": rows, "interviews": interviews, "consents": consents, "reports": reports, "requests": requests,
    }


def check(log):
    """완료 기준(작업내역 65 [11/19 보강]) + PRD 6-3 수치 점검. 문제 목록을 돌려준다."""
    bad = []
    programs = {p["프로그램명"]: p for p in load("programs.json")}
    staff = {s["colreg_no"] for s in load("students.json") if not str(s["colreg_no"]).startswith("H")}
    q = log["questions"]
    if json.dumps(build(log["meta"]["seed"]), ensure_ascii=False) != json.dumps(log, ensure_ascii=False):
        bad.append("같은 seed로 다시 만들면 결과가 다름")
    want = {"questions": TOTAL, "interviews": COUNTS["interviews"], "consents": COUNTS["consents"],
            "reports": COUNTS["reports"], "requests": COUNTS["requests"]}
    for k, n in want.items():
        if len(log[k]) != n:
            bad.append(f"{k} {len(log[k])}건(기대 {n})")
    if sum(r["status"] == "accepted" for r in log["requests"]) != COUNTS["accepted"]:
        bad.append("쪽지 요청 수락 건수 틀림")
    people = [r["colreg_no"] for k in ("questions", "interviews", "consents", "reports") for r in log[k]] \
        + [x for r in log["requests"] for x in (r["from"], r["to"])]
    if staff & set(people):
        bad.append(f"직원 행 포함: {staff & set(people)}")
    if DEMO & set(people):
        bad.append(f"시연 인물 포함: {DEMO & set(people)}")
    names = [r["프로그램명"] for k in ("questions", "interviews", "consents", "reports", "requests") for r in log[k] if r["프로그램명"]]
    if set(names) - set(programs):
        bad.append(f"programs.json에 없는 프로그램명: {set(names) - set(programs)}")
    by_dept = Counter(r["운영부서코드"] for r in q)
    if sum(v for k, v in by_dept.items() if k) + by_dept[None] != len(q):
        bad.append("부서별 합계 + 분류 안 됨 ≠ 전체")
    if any(r["프로그램명"] and r["운영부서코드"] != programs[r["프로그램명"]]["운영부서코드"] for r in q):
        bad.append("운영부서코드가 programs.json과 다름")
    st = Counter(r["status"] for r in q)
    if st["hold"] != round(TOTAL * 0.28):
        bad.append(f"hold {st['hold']}건 ≠ 28%")
    for r in q:
        off = bool(OFFICIAL_RE.search(r["질문"]))
        if (r["status"] == "official") != off:
            bad.append(f"규정 판별과 상태 불일치: {r['id']} {r['status']} {r['질문']}")
        if r["status"] == "ok" and r["근거수"] <= 0:
            bad.append(f"ok인데 근거 0: {r['id']}")
        if r["status"] != "ok" and r["근거수"]:
            bad.append(f"{r['status']}인데 근거 있음: {r['id']}")
        if r["분야"] == "현장실습" and r["status"] == "ok" and INTERVIEW_ONLY_INTERN.search(r["질문"]):
            bad.append(f"근무조건 질문이 ok: {r['id']}")
        if not (START.isoformat() <= r["at"] <= END.isoformat()):
            bad.append(f"기간 밖: {r['id']} {r['at']}")
    kw = [r for r in q if re.search(r"학점|장학|선발", r["질문"])]
    off_ratio = sum(r["status"] == "official" for r in kw) / max(len(kw), 1)
    if abs(off_ratio - 0.6) > 0.02:
        bad.append(f"학점·장학·선발 키워드 질문 중 official 비율 {off_ratio:.0%}(기대 60%)")
    done = defaultdict(set)
    for s in load("students.json"):
        if s.get("파견대학"):
            done[s["파견대학"]].add(s["colreg_no"])
    for r in load("internships.json"):
        done[r["업체명"]].add(r["학번"])
    for r in load("extracurricular.json"):
        done[r["프로그램명"]].add(r["가상학번"])
    if any(r["프로그램명"] and r["colreg_no"] in done[r["프로그램명"]] for r in q):
        bad.append("질문자가 그 프로그램 이수자")
    if any(r["from"] in done[r["프로그램명"]] or r["to"] not in done[r["프로그램명"]] for r in log["requests"]):
        bad.append("쪽지 요청: 보낸 사람이 이수자이거나 받는 사람이 미이수자")
    if any(r["colreg_no"] not in done[r["프로그램명"]] for r in log["interviews"]):
        bad.append("인터뷰한 사람이 그 프로그램 미이수자")
    ev_ids = {e["id"] for e in load("evidence.json")}
    if any(r["sourceId"] not in ev_ids for r in log["reports"]):
        bad.append("신고 근거 id가 evidence.json에 없음")
    iv = {r["id"] for r in log["interviews"]}
    if any(c["interviewId"] not in iv for c in log["consents"]) or len({c["interviewId"] for c in log["consents"]}) != len(log["consents"]):
        bad.append("공개 동의의 인터뷰 id가 없거나 중복")
    return bad


def summary(log):
    q = log["questions"]
    st = Counter(r["status"] for r in q)
    print(f"질문 {len(q)}건: ok {st['ok']} · hold {st['hold']}({st['hold'] / len(q):.0%}) · official {st['official']}")
    print("분야:", dict(Counter(r["분야"] or "없음" for r in q)))
    print("부서:", dict(sorted(Counter(r["운영부서코드"] or "분류 안 됨" for r in q).items())))
    print("칸:", dict(Counter(r["칸"] or "없음" for r in q).most_common()))
    print("월:", dict(sorted(Counter(r["at"][:7] for r in q).items())))
    print("프로그램 Top 5:", Counter(r["프로그램명"] for r in q if r["프로그램명"]).most_common(5))
    print(f"인터뷰 {len(log['interviews'])} · 공개 동의 {len(log['consents'])} · 신고 {len(log['reports'])} · "
          f"쪽지 요청 {len(log['requests'])}(수락 {sum(r['status'] == 'accepted' for r in log['requests'])})")


def main():
    if "--check" in sys.argv:
        log = json.loads(OUT.read_text(encoding="utf-8"))
    else:
        log = build()
        OUT.write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"생성: {OUT.relative_to(ROOT)}")
    summary(log)
    bad = check(log)
    print(f"점검 문제 {len(bad)}건")
    for b in bad[:30]:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
