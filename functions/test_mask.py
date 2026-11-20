# test_mask.py — mask.py 시험 (작업 72). 실행: cd functions && python test_mask.py
# 완료 기준(작업내역 72): 전화·메일·학번·URL 예시 각 3건 이상이 치환되고 원문이 남지 않음.
# 더해서: 일반 문장·data/evidence.json 근거 문단·개발 질문은 한 글자도 바뀌지 않아야 한다. 하나라도 틀리면 종료코드 1.
import csv
import json
import sys
from pathlib import Path

from mask import find, mask, mask_messages

# (입력, 기대 출력)
MASKED = [
    # 전화
    ("궁금하면 010-1234-5678로 연락 주세요.", "궁금하면 [연락처]로 연락 주세요."),
    ("번호는 01098765432예요", "번호는 [연락처]예요"),
    ("010 2222 3333 으로 문자 주세요", "[연락처] 으로 문자 주세요"),
    ("사무실 02-2173-2678, 내선 2678", "사무실 [연락처], [연락처]"),
    ("031)330-4114로 전화했어요", "[연락처]로 전화했어요"),
    ("+82 10-1234-5678 로 왓츠앱", "[연락처] 로 왓츠앱"),
    ("대표번호 1588-1234", "대표번호 [연락처]"),
    # 메일
    ("메일은 someone@example.com이에요.", "메일은 [메일]이에요."),
    ("kim.min_su+vcc@hufs.ac.kr 로 보내 주세요", "[메일] 로 보내 주세요"),
    ("abc123 (at) gmail.com 으로 연락", "[메일] 으로 연락"),
    ("담당자 메일 eac2@hufs.ac.kr", "담당자 메일 [메일]"),
    # 학번
    ("제 학번은 H0469예요.", "제 학번은 [학번]예요."),
    ("h0143이랑 같이 갔어요", "[학번]이랑 같이 갔어요"),
    ("학번 202301234 입니다", "학번 [학번] 입니다"),
    ("201912345로 로그인했어요", "[학번]로 로그인했어요"),
    # 링크
    ("https://forms.gle/Papzh2BU87a57VZR6 에서 신청", "[링크] 에서 신청"),
    ("www.hufs.ac.kr에 공지 있어요", "[링크]에 공지 있어요"),
    ("open.kakao.com/o/abcDEF 들어오세요", "[링크] 들어오세요"),
    ("블로그 blog.naver.com/hufs_kim 참고", "블로그 [링크] 참고"),
    # 주소
    ("서울특별시 동대문구 이문로 107에 살아요", "[주소]에 살아요"),
    ("경기도 용인시 처인구 모현읍 외대로 81", "[주소]"),
    ("동대문구 이문동 270-1번지 원룸", "[주소] 원룸"),
    ("우리 집은 101동 1203호예요", "우리 집은 [주소]예요"),
    # 메신저 아이디
    ("카톡 아이디 hufs_boo123 추가해 주세요", "[연락처] 추가해 주세요"),
    ("인스타 @boo.hufs 로 DM 주세요", "[연락처] 로 DM 주세요"),
]

# 바뀌면 안 되는 문장(금액·날짜·학기·수량·프로그램명 숫자)
ORDINARY = [
    "기숙사는 월 380유로였어요.", "한 달 생활비는 월 110만~150만 원이에요.", "1,200,000원 정도 들었어요.",
    "2024-1학기에 파견 갔어요.", "2025년 3월 2일에 출국했어요.", "공항에서 기차로 1시간 걸려요.",
    "리옹3 대학이랑 파리7 디드로 중에 고민했어요.", "TestDaF 4점이었어요.", "학점 인정은 6학점 받았어요.",
    "연구 주제로 3개를 골랐어요.", "활동 2개를 했어요.", "보험은 30만 원대였어요.", "토익 950점 받았어요.",
    "8주간 실습했어요.", "123456789원짜리 견적서를 정리했어요.", "총 4,500,000원이 들었어요.",
    "K-컬처랩(온라인) 실습은 화상으로 했어요.", "Celpe-Bras 대비 과정을 들었어요.", "B2 이상이 필요해요.",
    "외대 앞 이문로에서 자취했어요.", "학교 홈페이지 공지를 확인하세요.", "메일로 교수님께 문의했어요.",
    "2023-2024 학년도 기준이에요.", "5천 원이면 한 끼 먹어요.", "오후 2시부터 6시까지 근무했어요.",
]


def main():
    bad = []
    for src, want in MASKED:
        got = mask(src)
        if got != want:
            bad.append(f"치환 틀림: {src!r}\n      기대 {want!r}\n      결과 {got!r}")
    for s in ORDINARY:
        if mask(s) != s:
            bad.append(f"오탐: {s!r} → {mask(s)!r}")

    root = Path(__file__).resolve().parent.parent / "data"
    evidence = json.loads((root / "evidence.json").read_text(encoding="utf-8"))
    bad += [f"근거 오탐: {e['id']} {find(e['text'])}" for e in evidence if mask(e["text"]) != e["text"]]
    rows = list(csv.DictReader(open(root / "eval-questions.csv", encoding="utf-8-sig")))
    bad += [f"개발 질문 오탐: {r['번호']} {find(r['질문'])}" for r in rows if mask(r["질문"]) != r["질문"]]

    msgs = [{"role": "user", "content": "제 번호 010-1111-2222"}]
    out = mask_messages(msgs)
    if out[0]["content"] != "제 번호 [연락처]" or msgs[0]["content"] != "제 번호 010-1111-2222":
        bad.append(f"mask_messages 틀림: {out} / 원본 {msgs}")
    kinds = [k for k, *_ in find("H0469 010-1234-5678 a@b.com")]
    if kinds != ["학번", "연락처", "메일"]:
        bad.append(f"find 틀림: {kinds}")

    n = len(MASKED) + len(ORDINARY) + len(evidence) + len(rows)
    print(f"마스킹 시험 {n}건(치환 {len(MASKED)} · 일반 {len(ORDINARY)} · 근거 {len(evidence)} · 질문 {len(rows)}) 중 틀림 {len(bad)}건")
    for b in bad:
        print("  -", b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
