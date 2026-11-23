# 규정 질문·주제어·별칭 빈틈 점검 (원우 담당, 작업 30 보조, 11/23)
# 사용: python tools/rule_probe.py
#
# 왜: askBoo의 코드 단계(규정 질문 판별 OFFICIAL_RE · 칸 주제어 TOPICS_EXCHANGE · 프로그램 대조)는 개발 질문을 보고 만들어서
#   개발 70·사용 로그는 다 맞히지만 다른 표현에 약하다. 봉인 1차(11/23)에서 틀린 7개도 모두 이 단계의 보류였다.
#   봉인 문항은 보지 않고, spec 정의로 새로 쓴 질문(아래 목록)으로 빈틈을 재고 넓힌 규칙을 시험한다.
#   - 규정 질문(OFFICIAL_POS): 학교가 정하는 기준·금액·기한·자격·절차(spec 4장 [11/19] 규정 질문 판별)
#   - 경험 질문(OFFICIAL_NEG): 비슷한 말이 있지만 선배 경험을 묻는 것 — 공식 안내로 가면 안 됨(spec 5·15번 예)
# 이 목록은 개발 70·봉인 30과 겹치지 않게 새로 썼다. 측정 세트가 아니라 규칙 점검용이다.
import csv, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))

OFFICIAL_POS = [
    "교환학생 지원 자격이 어떻게 돼요?", "교환 지원 신청 마감이 언제예요?", "파견 신청 기간 알려 주세요",
    "교환학생 어학 성적 기준이 몇 점이에요?", "토플 몇 점 이상이어야 지원할 수 있어요?", "교환학생 선발 인원이 몇 명이에요?",
    "파견 기간을 한 학기 연장할 수 있어요?", "교환 중에 휴학해도 돼요?", "교환학생 학비는 어디에 내요?",
    "교환 가면 본교 등록금 내야 해요?", "현장실습 하면 몇 학점 받아요?", "현장실습 참여 자격 조건이 뭐예요?",
    "인턴 지원 마감일 언제예요?", "학점 인정 신청서는 어디에 제출해요?", "교환학생 중복 지원 가능해요?",
    "교환 포기하면 불이익 있어요?", "파견 취소하면 페널티 있어요?", "졸업 학기에도 교환 지원 가능해요?",
    "4학년도 교환 지원할 수 있어요?", "교환학생 장학금 신청 방법 알려 주세요", "학점 인정 최대 몇 학점까지 돼요?",
    "어학 점수 유효 기간이 있어요?", "교환학생 면접 일정이 언제예요?", "비교과 들으면 마일리지 몇 점 줘요?",
    "이수증 발급 기준이 뭐예요?", "출석 몇 번 빠지면 수료 못 해요?", "현장실습 지원금 얼마 나와요?",
    "교환학생 체재비 지원 금액이 얼마예요?", "성적 환산 기준표 어디서 봐요?", "교환 지원서 접수 기간이 언제까지예요?",
]
OFFICIAL_NEG = [
    "학점 인정 받을 때 주의할 점 있어요?", "챙길 서류 있어요?", "지원 서류 준비 언제부터 했어요?",
    "어학 점수 어떻게 준비했어요?", "면접 분위기 어땠어요?", "기숙사 신청 언제 했어요?",
    "마르부르크 생활비 얼마 들어요?", "수강신청 어떻게 해요?", "현장실습 지원할 때 뭘 준비했어요?",
    "인턴 끝나고 뭐가 달라졌어요?", "교환 가서 학점 잘 받는 팁 있어요?", "파견 기간이 짧게 느껴졌어요?",
    "출석 엄격한 편이에요?", "성적 평가 방식 어땠어요?", "마감 직전에 서류 내도 괜찮았어요?",
    "교환 포기하고 싶었던 적 있어요?", "면접 질문 뭐 나왔어요?", "토플 공부 얼마나 했어요?",
    "비교과 들으면서 뭘 배웠어요?", "비자 연장 어떻게 했어요?",
]

# 확인용 질문 — 아래 제안 표현을 다 만든 뒤에 새로 썼고, 이 결과를 보고 표현을 고치지 않는다(제안이 위 목록에만 맞았는지 보는 값).
HOLDOUT_POS = [
    "교환학생 몇 학년부터 지원할 수 있어요?", "파견 신청 서류 제출 기한 알려 주세요", "IELTS 몇 점 필요해요?",
    "교환 지원하려면 평균 학점 기준이 있나요?", "현장실습 참여하면 지원금 나오나요?", "교환 합격 발표가 언제예요?",
    "교환 중에 한 학기 더 연장 신청할 수 있나요?", "비교과 수료 기준이 어떻게 돼요?", "교환학생 선발 기준이 뭐예요?",
    "파견 확정 후에 취소하면 어떻게 돼요?", "교환 다녀오면 학점 몇 학점까지 인정돼요?", "교환학생 모집 기간이 언제예요?",
    "인턴십 신청 자격이 있나요?", "교환 갈 때 본교 학비 감면 있어요?", "어학 성적표 제출 마감이 언제까지예요?",
]
HOLDOUT_NEG = [
    "교환 지원할 때 자기소개서 어떻게 썼어요?", "학점 인정 받느라 힘들었던 점 있어요?", "합격 발표 기다릴 때 뭐 했어요?",
    "현장실습 하면서 받은 돈은 어디에 썼어요?", "연장하고 싶을 만큼 좋았어요?", "수료하고 나서 뭐가 남았어요?",
    "IELTS 공부 어떻게 했어요?", "모집 공고 보고 바로 지원했어요?", "취소할까 고민한 적 있어요?",
    "비교과 출석 체크 빡빡했어요?", "선발되고 나서 제일 먼저 뭘 했어요?", "교환 가서 학비 말고 돈 많이 든 거 있어요?",
    "인턴십 끝나고 정규직 제안 받았어요?", "기한 맞추느라 힘들었던 서류 있어요?", "어학 성적 받고 바로 냈어요?",
]

# 확인용 2차 — 2차 표현을 다 만든 뒤에 새로 썼고, 이 결과를 보고 표현을 고치지 않는다.
HOLDOUT2_POS = [
    "교환학생 2차 모집 있어요?", "현장실습 신청 기한이 지났는데 받아 주나요?", "파견 대학 배정 결과 발표는 언제 나와요?",
    "교환 지원할 때 성적 기준 몇 점이에요?", "교환 다녀온 뒤 학점 인정 신청은 언제까지 해요?", "비교과 이수증은 어디서 발급받아요?",
    "교환학생 지원 가능 학년이 어떻게 돼요?", "현장실습 학점은 몇 학점으로 인정돼요?", "교환 기간 중 등록금은 어디에 납부해요?",
    "교환 선발 인원은 학교마다 달라요?", "파견 포기하면 다음 학기에 다시 지원 못 해요?", "교환학생 장학금은 누가 받을 수 있어요?",
    "인턴 참여하면 지원금 받을 수 있나요?", "어학 성적 제출 기한이 언제예요?", "파견 연장 가능한가요?",
]
HOLDOUT2_NEG = [
    "모집 공고 나오기 전에 뭘 준비했어요?", "발표 기다리는 동안 불안했어요?", "기한 안에 서류 다 못 낼 뻔한 적 있어요?",
    "성적 관리 어떻게 했어요?", "지원금으로 뭐 샀어요?", "연장하고 싶을 정도로 좋았던 점이 뭐예요?",
    "인정 안 될까 봐 걱정한 과목 있어요?", "교환 가기 전에 어학 공부 얼마나 했어요?", "학비 말고 생활비는 얼마 들었어요?",
    "포기하지 않고 버틴 비결이 뭐예요?", "선발되고 나서 제일 좋았던 점은요?", "수료하고 나서 연락하는 동기 있어요?",
    "면접 때 뭘 물어봤어요?", "장학금 받으려고 따로 준비한 거 있어요?", "현장실습 끝나고 추천서 받았어요?",
]

# 확인용 3차 — 3차 표현을 다 만든 뒤에 새로 썼고, 이 결과를 보고 표현을 고치지 않는다(최종 보고 값).
HOLDOUT3_POS = [
    "교환학생 모집 인원이 몇 명이에요?", "현장실습 지원 마감이 언제예요?", "교환 2학기 파견 신청 기간이 언제예요?",
    "교환 지원 자격에 학년 제한 있어요?", "어학 점수 기준이 학교마다 달라요?", "교환 기간 연장 신청할 수 있어요?",
    "현장실습 지원금은 얼마 나와요?", "교환 합격자 발표일이 언제예요?", "비교과 마일리지는 어디에 쓰여요?",
    "학점 인정 신청 기한이 지나면 어떻게 돼요?",
]
HOLDOUT3_NEG = [
    "모집 공고 보고 어떤 생각이 들었어요?", "기한 때문에 급하게 준비한 게 있어요?", "지원금 받아서 어디에 썼어요?",
    "발표 나고 나서 가장 먼저 한 일은요?", "연장했으면 좋았겠다 싶은 순간 있었어요?", "자격 요건 맞추느라 힘들었어요?",
    "현장실습 지원할 때 떨렸어요?", "성적 기준 넘기려고 공부 어떻게 했어요?", "교환 포기한 친구 있었어요?",
    "마일리지 모으는 재미 있었어요?",
]

# 확인용 4차 — 4차(경험 말투 예외)를 다 만든 뒤에 새로 썼고, 이 결과를 보고 고치지 않는다. **최종 보고 값.**
HOLDOUT4_POS = [
    "교환학생 지원하려면 토익 몇 점 필요해요?", "현장실습 신청 마감일 알려 주세요", "교환 파견 기간 연장 가능한가요?",
    "교환학생 지원 자격 중에 학점 조건이 있어요?", "비교과 이수 기준이 어떻게 되나요?", "교환학생 장학금 금액이 얼마예요?",
    "교환 다녀오면 최대 몇 학점 인정돼요?", "현장실습 지원금 받을 수 있어요?", "교환 모집 요강은 어디서 봐요?",
    "교환 합격 발표는 언제 나요?", "파견 취소하면 불이익이 있나요?", "교환학생 중복 지원 돼요?",
]
HOLDOUT4_NEG = [
    "토익 점수 올리려고 뭘 했어요?", "마감 때문에 밤샌 적 있었어요?", "연장하고 싶다고 느꼈어요?",
    "지원 자격 맞추려고 학점 관리 어떻게 했어요?", "이수하고 나서 뭐가 좋았어요?", "장학금 받고 기분 어땠어요?",
    "학점 인정 받는 과정이 힘들었어요?", "지원금 받은 거 어디에 썼어요?", "모집 요강 보고 고민했어요?",
    "합격 발표 났을 때 어땠어요?", "취소할까 걱정했어요?", "중복 지원한 친구 있었어요?",
]

# 넓힌 판별 표현(제안) — 지금 표현 + 자격·기한·점수 기준·연장·불이익·지원금 등. 경험 질문과 겹치는 말은 묶음으로만.
CURRENT = r"평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수"
PROPOSED = CURRENT + (
    r"|자격|참여\s*조건|지원\s*조건|신청\s*(기간|마감|방법)|접수\s*(기간|마감)|마감(이|일)|언제까지"
    r"|몇\s*점\s*(이상|넘|필요|되어야|이어야)|(어학|성적|점수)\s*기준|기준표|환산"
    r"|(파견|교환|기간)\s*(을\s*)?(한\s*학기\s*)?연장|중복\s*지원|불이익|페널티|(포기|취소)하면"
    r"|지원\s*가능|지원할\s*수\s*있|학비\s*(는|를|가)?\s*(어디|얼마|감면|면제|내)|체재비|지원금|마일리지|이수증|발급\s*기준|수료\s*(기준|못)|몇\s*번\s*빠지면"
    r"|유효\s*기간|일정이\s*언제"
)
# 2차(11/23, 확인용 질문 1차 결과를 보고 넓힘 — 그래서 확인용 1차는 더 이상 정직한 값이 아님, 확인용 2차로 잰다)
#   기한·발표·모집·기준을 묻는 말의 묶음, 연장 신청, '학비'는 내는 곳·금액·감면만(「학비 말고」 오탐)
PROPOSED += (
    r"|(제출|신청|접수|모집|지원)\s*(기한|기간|마감)|기한(이|은)?\s*(언제|지났|까지)|모집\s*(인원|일정|요강|기간|있)"
    r"|발표(가|는|일)?\s*(언제|날)|(학점|평점|성적|점수|어학)\s*기준|연장\s*(신청|가능|할\s*수)"
)
# 3차(11/23, 확인용 2차 결과를 보고 좁힘 — 확인용 2차도 더 이상 정직한 값이 아님, 확인용 3차로 잰다)
#   단어 하나만으로 잡던 「모집」「기한」은 묻는 꼴(모집 인원·기한이 언제)로, 「지원금」은 금액·받을 수 있는지로만
PROPOSED = PROPOSED.replace(r"|지원금|", r"|지원금\s*(은|이)?\s*(얼마|나와|나오|받을\s*수)|")

# 4차(11/23, 확인용 3차 결과를 보고 — 확인용 3차도 더 이상 정직한 값이 아님, 확인용 4차로 한 번만 재고 멈춘다)
#   같은 낱말이 규정 질문·경험 질문 둘 다에 나오므로 말투로 가른다: 지난 경험을 묻는 꼴(…했어요?·힘들었어요?·어땠어요?)이면
#   공식 안내로 보내지 않는다. 단 지금 표현(평점·등록금 등 CURRENT)에 걸리면 예전처럼 공식 안내(지금보다 나빠지지 않게).
EXPERIENCE_TONE = re.compile(r"(했|었|였|웠|겼|졌|냈|썼|봤|갔|왔|됐|났|셨)(어요|나요|어|니|습니까)\s*\??$|어땠|힘들|재미|느꼈|좋았|떨렸|고민|걱정")


def is_official(q, rx):
    if re.search(CURRENT, q):
        return True
    return bool(re.search(rx, q)) and not EXPERIENCE_TONE.search(q)


def judge(rx):
    pos = [q for q in OFFICIAL_POS if is_official(q, rx)]
    neg = [q for q in OFFICIAL_NEG if is_official(q, rx)]
    return pos, neg


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import askboo
    assert askboo.OFFICIAL_RE.pattern == CURRENT, "askboo.OFFICIAL_RE가 바뀌었음 — CURRENT를 맞출 것"
    errs = 0
    for name, rx in (("지금", CURRENT), ("제안", PROPOSED)):
        pos, neg = judge(rx)
        print(f"[규정 질문 판별 · {name}] 규정 질문 {len(pos)}/{len(OFFICIAL_POS)} 잡음 · 경험 질문 잘못 잡음 {len(neg)}/{len(OFFICIAL_NEG)}")
        if name == "지금":
            for q in OFFICIAL_POS:
                if q not in pos:
                    print(f"    놓침: {q}")
        for q in neg:
            print(f"    ✗ 경험 질문인데 잡음: {q}")
        if name == "제안" and neg:
            errs += 1
    hp = [q for q in HOLDOUT_POS if is_official(q, PROPOSED)]
    hn = [q for q in HOLDOUT_NEG if is_official(q, PROPOSED)]
    rc = re.compile(CURRENT)
    print(f"[확인용 질문 · 지금] 규정 {sum(bool(rc.search(q)) for q in HOLDOUT_POS)}/{len(HOLDOUT_POS)} · 경험 잘못 {sum(bool(rc.search(q)) for q in HOLDOUT_NEG)}/{len(HOLDOUT_NEG)}")
    print(f"[확인용 질문 · 제안] 규정 {len(hp)}/{len(HOLDOUT_POS)} · 경험 잘못 {len(hn)}/{len(HOLDOUT_NEG)}  (표현을 고치지 않고 잰 값)")
    for q in HOLDOUT_POS:
        if q not in hp:
            print(f"    놓침: {q}")
    for q in hn:
        print(f"    ✗ 경험 질문인데 잡음: {q}")
    hp2 = [q for q in HOLDOUT2_POS if is_official(q, PROPOSED)]
    hn2 = [q for q in HOLDOUT2_NEG if is_official(q, PROPOSED)]
    print(f"[확인용 2차 · 지금] 규정 {sum(bool(rc.search(q)) for q in HOLDOUT2_POS)}/{len(HOLDOUT2_POS)} · 경험 잘못 {sum(bool(rc.search(q)) for q in HOLDOUT2_NEG)}/{len(HOLDOUT2_NEG)}")
    print(f"[확인용 2차 · 제안] 규정 {len(hp2)}/{len(HOLDOUT2_POS)} · 경험 잘못 {len(hn2)}/{len(HOLDOUT2_NEG)}  (표현을 고치지 않고 잰 값)")
    for q in HOLDOUT2_POS:
        if q not in hp2:
            print(f"    놓침: {q}")
    for q in hn2:
        print(f"    ✗ 경험 질문인데 잡음: {q}")
    hp3 = [q for q in HOLDOUT3_POS if is_official(q, PROPOSED)]
    hn3 = [q for q in HOLDOUT3_NEG if is_official(q, PROPOSED)]
    print(f"[확인용 3차 · 지금] 규정 {sum(bool(rc.search(q)) for q in HOLDOUT3_POS)}/{len(HOLDOUT3_POS)} · 경험 잘못 {sum(bool(rc.search(q)) for q in HOLDOUT3_NEG)}/{len(HOLDOUT3_NEG)}")
    print(f"[확인용 3차 · 제안] 규정 {len(hp3)}/{len(HOLDOUT3_POS)} · 경험 잘못 {len(hn3)}/{len(HOLDOUT3_NEG)}  (3차 표현 기준이었음 — 4차는 이걸 보고 고침)")
    for q in HOLDOUT3_POS:
        if q not in hp3:
            print(f"    놓침: {q}")
    for q in hn3:
        print(f"    ✗ 경험 질문인데 잡음: {q}")
    hp4 = [q for q in HOLDOUT4_POS if is_official(q, PROPOSED)]
    hn4 = [q for q in HOLDOUT4_NEG if is_official(q, PROPOSED)]
    print(f"[확인용 4차 · 지금] 규정 {sum(bool(re.search(CURRENT, q)) for q in HOLDOUT4_POS)}/{len(HOLDOUT4_POS)} · 경험 잘못 {sum(bool(re.search(CURRENT, q)) for q in HOLDOUT4_NEG)}/{len(HOLDOUT4_NEG)}")
    print(f"[확인용 4차 · 제안] 규정 {len(hp4)}/{len(HOLDOUT4_POS)} · 경험 잘못 {len(hn4)}/{len(HOLDOUT4_NEG)}  ★ 최종 보고 값(고치지 않고 한 번만 잰 값)")
    for q in HOLDOUT4_POS:
        if q not in hp4:
            print(f"    놓침: {q}")
    for q in hn4:
        print(f"    ✗ 경험 질문인데 잡음: {q}")
    # 회귀: 개발 70·사용 로그에서 제안 표현으로 official이 새로 생기거나 사라지는지
    with open(ROOT / "data" / "eval-questions.csv", encoding="utf-8-sig") as f:
        dev = list(csv.DictReader(f))
    bad = [r for r in dev if (r["기대결과"] == "공식안내") != is_official(r["질문"], PROPOSED)]
    print(f"[개발 70] 제안 표현으로 기대결과와 어긋나는 질문 {len(bad)}개")
    for r in bad:
        print(f"    {r['번호']}({r['기대결과']}) {r['질문']}")
    log = json.loads((ROOT / "data" / "usage-log.json").read_text(encoding="utf-8"))
    log = log if isinstance(log, list) else next(v for v in log.values() if isinstance(v, list))
    moved = [r for r in log if (r["status"] == "official") != is_official(r["질문"], PROPOSED)]
    print(f"[사용 로그 {len(log)}] 시드 상태와 어긋나는 질문 {len(moved)}개")
    for r in moved[:10]:
        print(f"    {r['status']} {r['질문']}")
    errs += bool(bad)
    print(f"\n오류 {errs}건")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
