# try_web_search.py — 작업 99 웹 검색(C안) 로컬 시험 (수정: 미리)
#
# 「바깥 정보」 질문 10개를 callAI("외부정보")로 부르고 답·출처·시간·비용을 기록한다.
# 실서버에 올리지 않는다. askboo.py는 이 길을 부르지 않는다(의도 「외부정보」는 docs/조사/99_*.md 초안만).
#
#   python -X utf8 try_web_search.py --gate-only        # AI 없이 가르기(규정·인물 막기)만 확인 — 비용 0
#   python -X utf8 try_web_search.py --mode open        # 막는 목록(blocked_domains)만 둔 검색
#   python -X utf8 try_web_search.py --mode official    # 허용 목록(allowed_domains)만 검색
#   python -X utf8 try_web_search.py --mode open --only 1,2 --dynamic   # 동적 필터링 켠 비교
#
# 결과: docs/조사/99_웹검색_시험기록_<mode>.json (작업 폴더 안). 예상 비용: 질문 1개 $0.02~0.08.

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "조사"

# ── 시험 질문 10개 (작업 99: 환율 2·대학 순위 2·기업 정보 2·비교과 보도 2·특강자 2) + 길 점검용 규정 2개 ──
QUESTIONS = [
    {"id": 1, "유형": "환율", "q": "오늘 원/유로 환율이 얼마예요? 독일 교환 가기 전에 환전하려고요."},
    {"id": 2, "유형": "환율", "q": "요즘 엔화 환율로 일본 생활비 한 달 15만 엔이면 원화로 얼마쯤이에요?"},
    {"id": 3, "유형": "대학 순위", "q": "QS 세계대학순위 최신판에서 독일 마르부르크 대학교는 몇 위예요?"},
    {"id": 4, "유형": "대학 순위", "q": "THE 세계대학순위에서 한국외국어대학교는 몇 위권이에요?"},
    {"id": 5, "유형": "기업 정보", "q": "KOTRA는 어떤 일을 하는 기관이고 본사는 어디에 있어요? 인턴 지원 전에 알아 두려고요."},
    {"id": 6, "유형": "기업 정보", "q": "삼성전자 2025년 연간 매출액이 얼마였어요?"},
    {"id": 7, "유형": "비교과 보도", "q": "한국외대 비교과 프로그램이 최근 언론에 소개된 적 있어요?"},
    {"id": 8, "유형": "비교과 보도", "q": "한국외대 학생 창업 지원 프로그램 관련 기사 있어요?"},
    {"id": 9, "유형": "특강자", "q": "한국외대에서 이번 학기에 열린 진로 특강 연사가 누구였어요?"},
    {"id": 10, "유형": "특강자", "q": "외대 특강에 왔던 유명 연사 개인 인스타나 연락처 알려 주세요."},
    {"id": 11, "유형": "규정(점검)", "q": "교환학생 지원하려면 학점이 몇 점 이상이어야 해요?"},
    {"id": 12, "유형": "규정(점검)", "q": "휴학 중에 한 인턴도 학점 인정돼요?"},
]

# ── 가르기: AI를 부르기 전에 코드가 먼저 막는다 ──────────────────────
# 규정(학사·장학·지원 자격)은 웹으로 보내지 않고 공식 안내로. 학교 규정은 해마다 바뀌고 웹 글(블로그)이 옛 기준이 많다.
규정_말 = ["학점", "졸업", "학칙", "장학", "등록금", "휴학", "복학", "수강", "지원 자격", "지원자격", "선발 기준",
          "선발기준", "인정", "규정", "신청 기간", "신청기간", "성적 기준", "어학 성적", "어학성적"]
# 실존 인물: 연락처·SNS·사생활·평판을 묻는 말은 막는다. 공개 행사 정보(일시·주제·연사 이름·소속)는 공식 공지 출처로만.
인물_말 = ["연락처", "전화번호", "번호 알려", "이메일", "메일 주소", "인스타", "sns", "SNS", "페이스북", "트위터",
          "집안", "가족", "연봉", "재산", "사생활", "결혼", "나이", "고향", "평판", "논란", "어디 살"]


def 가르기(질문):
    """→ ("규정"|"인물"|"외부", 이유). 규정·인물은 AI를 부르지 않는다."""
    for w in 인물_말:
        if w in 질문:
            return "인물", f"실존 인물 개인 정보('{w}')"
    for w in 규정_말:
        if w in 질문:
            return "규정", f"학사 규정('{w}') → 공식 안내"
    return "외부", ""


GATE_REPLY = {
    "규정": "학교 규정은 해마다 바뀌어서 BOO가 웹에서 찾아 답하지 않아요. 국제교류팀·학사 공지의 공식 안내를 확인해 주세요.",
    "인물": "실제 사람의 연락처나 개인 정보는 알려 드릴 수 없어요. 특강 일시·주제는 학교 공지에서 확인할 수 있어요.",
}

SYSTEM = """너는 한국외대 학생을 돕는 BOO다. 웹 검색 결과로만 짧게 답한다.
- 2~4문장, 해요체. 문장마다 검색 결과에 근거한다. 검색 결과에 없는 숫자·이름은 쓰지 않는다.
- 환율·순위·매출처럼 바뀌는 숫자는 기준일(또는 발표 연도)을 함께 쓴다.
- 공식 출처(발표 기관·학교·기업 자체 사이트)를 언론·블로그보다 먼저 쓴다.
- 검색 결과로 뒷받침되지 않는 문장(인사·당부·"확인해 보세요"·직접 한 계산)은 쓰지 않는다. 출처 없는 문장은 화면에서 지워진다.
- 찾지 못하면 "찾지 못했어요"라고 쓰고 지어내지 않는다.
- 실존 인물은 공개 행사 정보(이름·소속·강연 주제)만. 연락처·SNS·사생활·평판은 쓰지 않는다.
- 학교 학사 규정(학점·지원 자격·장학)은 답하지 말고 공식 안내를 확인하라고만 쓴다."""

# 막는 목록(open 모드): 위키·SNS·개인 블로그 — 인물 정보와 옛 정보가 많은 곳
BLOCKED = ["namu.wiki", "instagram.com", "facebook.com", "x.com", "twitter.com", "tiktok.com",
           "blog.naver.com", "tistory.com", "brunch.co.kr", "youtube.com"]
# 허용 목록(official 모드): 발표 기관·학교·기업·통신사/주요 일간지
ALLOWED = ["hufs.ac.kr", "bok.or.kr", "smbs.biz", "koreaexim.go.kr", "kebhana.com",
           "topuniversities.com", "timeshighereducation.com", "uni-marburg.de",
           "kotra.or.kr", "dart.fss.or.kr", "samsung.com",
           "news.naver.com", "hankyung.com", "khan.co.kr", "edaily.co.kr", "unn.net", "veritas-a.com",
           "news1.kr", "newsis.com", "mt.co.kr", "fnnews.com"]
# 11/26 시험: chosun.com·donga.com·hani.co.kr·joongang.co.kr·mk.co.kr·yna.co.kr는 Anthropic 크롤러를 막아 두어
# allowed_domains에 넣으면 요청 전체가 400("not accessible to our user agent"). 허용 목록에 넣지 않는다.
# 출처 판정: 공식(발표 기관·학교·기업) / 언론 / 기타
공식_도메인 = ["hufs.ac.kr", "bok.or.kr", "smbs.biz", "koreaexim.go.kr", "kebhana.com", "topuniversities.com",
            "timeshighereducation.com", "uni-marburg.de", "kotra.or.kr", "dart.fss.or.kr", "samsung.com",
            "go.kr", "or.kr"]
언론_도메인 = ["yna.co.kr", "news.naver.com", "hankyung.com", "mk.co.kr", "chosun.com", "donga.com", "joongang.co.kr",
            "hani.co.kr", "khan.co.kr", "edaily.co.kr", "unn.net", "veritas-a.com", "news", "times", "ilbo", "herald"]


def 출처종류(url):
    host = (urlparse(url).hostname or "").lower()
    if any(host == d or host.endswith("." + d) for d in 공식_도메인):
        return "공식"
    if any(d in host for d in 언론_도메인):
        return "언론"
    return "기타"


PRICE = {"claude-sonnet-5-5": (2.0, 10.0)}   # $/1M 입력·출력 (claude-api 스킬 11/03 표)


def 비용(model_id, usage):
    i, o = PRICE.get(model_id, (2.0, 10.0))
    return round(usage["input"] * i / 1e6 + usage["output"] * o / 1e6 + usage["searches"] * 0.01, 4)


def 설정(mode, dynamic):
    s = json.loads(json.dumps(ai.SETTINGS["외부정보"]))
    if mode == "open":
        s["web_search"]["blocked_domains"] = BLOCKED
    else:
        s["web_search"]["allowed_domains"] = ALLOWED
    if dynamic:
        s["web_search"].pop("allowed_callers", None)   # 기본값 = 코드 실행 안에서 검색(동적 필터링)
        s["web_search"]["response_inclusion"] = "excluded"
    return s


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _nums(t):
    return {n.replace(",", "") for n in _NUM.findall(t or "")}


def 문장_거르기(segments, 질문, results=()):
    """글 조각 → 문장. 출처 조각이 하나도 안 걸친 문장은 버리고(번호 없는 문장 규칙),
    근거(이 답의 인용 글 전체·인용 제목·검색 결과 제목과 날짜·질문)에 없는 숫자가 든 문장도 버린다(근거에 없는 숫자 규칙).
    인용 글(cited_text)은 150자까지라 같은 문장의 인용만 보면 맞는 숫자도 버려져서 답 전체로 넓혔다.
    → (남은 [{"text", "sources"}], 버린 [{"text", "이유"}])"""
    full, spans, pos = "", [], 0
    근거숫자 = _nums(질문)
    for r in results:
        근거숫자 |= _nums(r.get("title")) | _nums(r.get("page_age"))
    for s in segments:
        spans.append((pos, pos + len(s["text"]), s["sources"]))
        full += s["text"]
        pos += len(s["text"])
        for src in s["sources"]:
            근거숫자 |= _nums(src.get("cited_text")) | _nums(src.get("title"))
    kept, dropped = [], []
    for m in re.finditer(r"[^\n]*?(?:[.!?](?=\s|$)|\n|$)", full):   # 1,472.72 같은 소수점은 문장 끝이 아니다
        a, b = m.start(), m.end()
        text = full[a:b].strip()
        if not text:
            continue
        srcs = []
        for sa, sb, ss in spans:
            if sa < b and sb > a:
                srcs += ss
        if not srcs:
            if "찾지 못했" in text and not _nums(text) - _nums(질문):   # 「못 찾음」은 지우면 뜻이 바뀐다(11/26 4번: THE 대신 QS만 남음)
                kept.append({"text": text, "sources": []})
            else:
                dropped.append({"text": text, "이유": "출처 없음"})
            continue
        없는 = sorted(n for n in _nums(text) if n not in 근거숫자 and len(n) > 1)   # 한 자리(1유로·2~4문장)는 보지 않는다
        if 없는:
            dropped.append({"text": text, "이유": f"근거에 없는 숫자 {', '.join(없는)}"})
            continue
        uniq = list({x["url"]: x for x in srcs}.values())
        kept.append({"text": text, "sources": uniq})
    return kept, dropped


def 채우기(질문, segments, results):
    """걸러진 답 + 출처. 다 버려지면 폴백: 인용이 있으면 공식 출처 인용 원문 한 줄, 없으면 「찾지 못했어요」+ 검색된 공식 링크."""
    kept, dropped = 문장_거르기(segments, 질문, results)
    답 = " ".join(s["text"] for s in kept).strip()
    urls = []
    for s in kept:
        for src in s["sources"]:
            if src["url"] not in urls:
                urls.append(src["url"])
    폴백 = ""
    if not 답:
        인용 = [src for s in segments for src in s["sources"]]
        인용.sort(key=lambda x: 출처종류(x["url"]) != "공식")
        if 인용:
            폴백 = "인용"
            답 = f"「{인용[0]['cited_text'].strip()}」 — {인용[0]['title']}"
            urls = [인용[0]["url"]]
        else:
            폴백 = "찾지 못함"
            답 = "찾지 못했어요. 아래 공식 사이트에서 확인해 주세요." if any(출처종류(r["url"]) == "공식" for r in results) \
                else "찾지 못했어요."
            urls = [r["url"] for r in results if 출처종류(r["url"]) == "공식"][:2]
    return {"답": 답, "폴백": 폴백, "버린문장": dropped, "출처": [{"url": u, "종류": 출처종류(u)} for u in urls]}


def run_one(item, mode, dynamic):
    길, 이유 = 가르기(item["q"])
    row = {**item, "길": 길}
    if 길 != "외부":
        row.update({"이유": 이유, "답": GATE_REPLY[길], "AI": False, "초": 0, "비용": 0})
        return row
    s = 설정(mode, dynamic)
    시작 = time.time()
    out = ai.callAI("외부정보", [{"role": "user", "content": item["q"]}], system=SYSTEM, 측정설정=s)
    초 = round(time.time() - 시작, 1)
    row.update({"AI": True, "초": 초, "ok": out["ok"]})
    if not out["ok"]:
        row["error"] = out.get("error")
        return row
    row.update(채우기(item["q"], out["segments"], out["sources"]))
    usage = out["usage"]
    row.update({
        "원문": out["text"], "segments": out["segments"], "results": out["sources"],
        "검색결과수": len(out["sources"]), "검색": usage["searches"],
        "입력토큰": usage["input"], "출력토큰": usage["output"],
        "비용": 비용(ai.claude_model_id("sonnet"), usage),
    })
    return row


def main():
    p = argparse.ArgumentParser(description="작업 99 웹 검색 로컬 시험")
    p.add_argument("--mode", choices=["open", "official"], default="open")
    p.add_argument("--only", help="질문 번호 쉼표(예: 1,3)")
    p.add_argument("--dynamic", action="store_true", help="동적 필터링 켬(기본은 direct)")
    p.add_argument("--gate-only", action="store_true", help="AI 없이 가르기만")
    p.add_argument("--refilter", action="store_true", help="AI 없이 저장된 기록의 segments를 다시 걸러 답·출처만 고침")
    a = p.parse_args()

    if a.refilter:
        f = OUT_DIR / f"99_웹검색_시험기록_{a.mode + ('-dynamic' if a.dynamic else '')}.json"
        rows = json.loads(f.read_text(encoding="utf-8"))
        for r in rows:
            if r.get("segments") is not None:
                r.update(채우기(r["q"], r["segments"], r.get("results", [])))
            print(f"{r['id']:>2} {r.get('폴백', '') or '-':<5} {(r.get('답') or '')[:200]}")
        f.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0

    items = QUESTIONS
    if a.only:
        ids = {int(x) for x in a.only.split(",")}
        items = [q for q in QUESTIONS if q["id"] in ids]
    if a.gate_only:
        for q in items:
            길, 이유 = 가르기(q["q"])
            print(f"{q['id']:>2} {q['유형']:<8} {길:<3} {이유}")
        return 0

    rows = []
    for q in items:
        r = run_one(q, a.mode, a.dynamic)
        rows.append(r)
        print(f"{r['id']:>2} {r['유형']:<8} {r['길']} {r['초']:>5}초 ${r.get('비용', 0):.4f} "
              f"출처 {len(r.get('출처', []))} 검색 {r.get('검색', 0)} {'' if r.get('ok', True) else 'ERR ' + str(r.get('error'))}")
        print("    " + (r.get("답") or "")[:300].replace("\n", " "))
    tag = a.mode + ("-dynamic" if a.dynamic else "")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"99_웹검색_시험기록_{tag}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    ai_rows = [r for r in rows if r.get("AI")]
    if ai_rows:
        print(f"합계 ${sum(r.get('비용', 0) for r in rows):.3f} · 평균 {sum(r['초'] for r in ai_rows) / len(ai_rows):.1f}초 "
              f"· 최대 {max(r['초'] for r in ai_rows)}초 → {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
