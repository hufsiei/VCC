# test_score.py — score.py 시험 (작업 22). 실행: cd functions && python test_score.py
# 완료 기준(작업내역 22): 후배1(H0143) 기준 선배1(H0469) 1위. spec 4장 [11/20] 규칙 전부. 하나라도 틀리면 종료코드 1.
import json
import sys
import time
from pathlib import Path

from score import FIRST_REASON, REQUEST_LIMIT, WEIGHTS, experienced, rank_seniors, score_senior

DATA = Path(__file__).resolve().parent.parent / "data"
MARBURG = "마르부르크필립스대학교"


def main():
    bad = []
    programs = [p["프로그램명"] for p in json.loads((DATA / "programs.json").read_text(encoding="utf-8"))]
    students = json.loads((DATA / "students.json").read_text(encoding="utf-8"))
    staff = {s["colreg_no"] for s in students if not str(s["colreg_no"]).startswith("H")}

    # 1) 시연: 후배1 → 마르부르크 → 선배1 1위 14점(학과 5 + 이중전공 4 + 단과대 3 + 공통 비교과 2)
    r = rank_seniors("H0143", MARBURG)
    if not r or r[0]["studentId"] != "H0469" or r[0]["score"] != 14:
        bad.append(f"시연 1위 틀림: {r[:1]}")
    elif r[0]["reasons"] != [FIRST_REASON, "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음",
                             "한국외국어대학교 직무탐색 집중교육 함께 이수"]:
        bad.append(f"선배1 이유 틀림: {r[0]['reasons']}")
    # 선배2(H0241) 2위 12점(학과 5 + 이중전공 4 + 단과대 3, 공통 비교과 없음)
    if len(r) < 2 or r[1]["studentId"] != "H0241" or r[1]["score"] != 12:
        bad.append(f"시연 2위 틀림: {r[1:2]}")
    elif r[1]["reasons"] != [FIRST_REASON, "같은 서양어대학", "같은 독일어과", "이중전공 경영학 같음"]:
        bad.append(f"선배2 이유 틀림: {r[1]['reasons']}")
    h745 = next((x for x in r if x["studentId"] == "H0745"), None)
    if not h745 or h745["score"] != 8:
        bad.append(f"H0745 8점 아님: {h745}")

    # 2) 모든 프로그램 × 보는 사람 몇 명: 후보·정렬·이유 규칙
    viewers = ["H0143", "H0469", "H0241", "H0745", "H0001", "H0500", "H1000"]
    t = time.time()
    n = 0
    for p in programs:
        exp = set(experienced(p))
        for me in viewers:
            out = rank_seniors(me, p)
            n += 1
            ids = [x["studentId"] for x in out]
            if set(ids) != exp - {me}:
                bad.append(f"후보 ≠ 경험자 전부(본인 제외): {p} {me}")
            if staff & set(ids) or me in ids or len(ids) != len(set(ids)):
                bad.append(f"직원·본인·중복 포함: {p} {me}")
            keys = [(-x["score"], x["waiting"]) for x in out]
            if keys != sorted(keys):
                bad.append(f"점수·대기 정렬 틀림: {p} {me}")
            for x in out:
                if x["reasons"][0] != FIRST_REASON:
                    bad.append(f"이유 맨 앞 틀림: {p} {x['studentId']}")
                s = score_senior(me, x["studentId"])
                if x["score"] != s["score"] or x["reasons"][1:] != s["reasons"]:
                    bad.append(f"score_senior와 다름: {p} {x['studentId']}")
                if not x["semester"]:
                    bad.append(f"경험 학기 없음: {p} {x['studentId']}")
    if time.time() - t > 5:
        bad.append(f"느림: {n}회 {time.time() - t:.1f}초")

    # 3) 점수 = 이유와 가중치의 합(겹치는 점마다 정확히 한 번)
    for x in rank_seniors("H0143", MARBURG):
        want = sum(WEIGHTS["단과대"] for z in x["reasons"] if z.startswith("같은 ") and z.endswith("대학")) \
            + sum(WEIGHTS["학과"] for z in x["reasons"] if z.startswith("같은 ") and not z.endswith("대학")) \
            + sum(WEIGHTS["이중전공"] for z in x["reasons"] if z.startswith("이중전공")) \
            + sum(WEIGHTS["공통 비교과"] for z in x["reasons"] if z.endswith("함께 이수"))
        if x["score"] != want:
            bad.append(f"점수와 이유 합 다름: {x}")

    # 4) 하한 없음: 0점 선배도 후보이고 이유가 비지 않는다.
    #    가상 학생은 모두 서양어대학이라 0점이 생기지 않으므로, 다른 단과대 학생을 잠시 만들어 본다
    import score as sc
    students_map = sc._data()[0]
    students_map["H9999"] = {"colreg_no": "H9999", "univ_nm": "경상대학", "crs_nm": "경영학부", "dbl_mjr_nm": None}
    try:
        zr = rank_seniors("H9999", MARBURG)
        if len(zr) != len(experienced(MARBURG)) or any(x["score"] != 0 or x["reasons"] != [FIRST_REASON] for x in zr):
            bad.append(f"하한 없음 틀림(다른 단과대 학생에게 0점 선배가 다 나와야 함): {zr[:2]}")
    finally:
        del students_map["H9999"]

    # 5) 동점 처리: 대기 요청 적은 선배 먼저 → 최근 학기 먼저. 받는 한도 5건
    base = [x for x in rank_seniors("H0143", MARBURG) if x["score"] == 8]
    if [x["semester"] for x in base] != sorted([x["semester"] for x in base], reverse=True):
        bad.append(f"동점 최근 학기 순 아님: {[(x['studentId'], x['semester']) for x in base]}")
    if len(base) >= 2:
        first = base[0]["studentId"]
        moved = [x for x in rank_seniors("H0143", MARBURG, waiting={first: 2}) if x["score"] == 8]
        if moved[-1]["studentId"] != first:
            bad.append("대기 요청이 많은 동점 선배가 뒤로 가지 않음")
    full = rank_seniors("H0143", MARBURG, waiting={"H0469": REQUEST_LIMIT})
    top = next(x for x in full if x["studentId"] == "H0469")
    if not top["requestsFull"] or full[0]["studentId"] != "H0469":
        bad.append("받는 한도 5건: requestsFull 아님 또는 점수 순서가 바뀜")
    if next(x for x in rank_seniors("H0143", MARBURG, waiting={"H0469": REQUEST_LIMIT - 1}) if x["studentId"] == "H0469")["requestsFull"]:
        bad.append("대기 4건인데 requestsFull")

    # 6) 공통 비교과 여러 개 → 2점 한 번, 「외 N개」
    multi = None
    for p in programs:
        for me in ("H0001", "H0500"):
            for x in rank_seniors(me, p):
                if any(" 외 " in z for z in x["reasons"]):
                    multi = x
                    break
            if multi:
                break
        if multi:
            break
    if multi and sum(z.endswith("함께 이수") for z in multi["reasons"]) != 1:
        bad.append(f"공통 비교과 이유가 여러 줄: {multi}")

    # 7) 같은 입력 → 같은 결과
    if rank_seniors("H0143", MARBURG) != rank_seniors("H0143", MARBURG):
        bad.append("같은 입력인데 결과가 다름")

    print(f"닮은 선배 점수 시험: 프로그램 {len(programs)} × 보는 사람 {len(viewers)} = {n}회 · 틀림 {len(bad)}건")
    for b in bad[:20]:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
