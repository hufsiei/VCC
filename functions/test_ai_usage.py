# test_ai_usage.py — 오늘 내 AI 사용액 한 줄 (ai_usage.py, 11/24)
# 실행: cd functions && python test_ai_usage.py
# 가짜 로그만 쓴다. 실제 AI 호출·.env 읽기 없음.
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import ai_usage

fails = []


def expect(name, cond):
    print(("ok   " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


def row(at, model, tin, tout, ok=True):
    return json.dumps({"at": at, "작업": "시험", "모델": model, "입력토큰": tin, "출력토큰": tout,
                       "ms": 1, "ok": ok}, ensure_ascii=False)


DAY = "2026-11-24"
lines = [
    row("2026-11-24T09:00:00", "claude-sonnet-5-5", 1_000_000, 0),        # $2.00
    row("2026-11-24T09:01:00", "claude-sonnet-5-5", 0, 100_000),          # $1.00
    row("2026-11-24T09:02:00", "claude-opus-5-5", 500_000, 50_000),       # $2.00 + $1.00
    row("2026-11-24T09:03:00", "HCX-005", 1200, 34),
    row("2026-11-24T09:04:00", "HCX-005", 800, 0, ok=False),
    row("2026-11-23T23:59:59", "claude-opus-5-5", 9_000_000, 9_000_000),  # 어제 — 빼야 함
    "{깨진 줄",
    "",
    json.dumps(["목록"]),
]

s = ai_usage.summarize(lines, DAY)
expect("Claude 금액 = 2+1+3 = $6.00", abs(s["usd"] - 6.0) < 1e-9)
expect("Claude 회수 3 (어제 줄 제외)", s["claude_calls"] == 3)
expect("HCX 회수 2 (실패 호출도 셈)", s["hcx_calls"] == 2)
expect("HCX 토큰 = 입력+출력 2034", s["hcx_tokens"] == 2034)
expect("HCX 단가 없음 → 금액 없음", s["hcx_usd"] is None)
expect("한 줄 모양", ai_usage.line(s) == "오늘 내 AI $6.00 (Claude 3회) · HCX 2회 2,034토큰")

# 로그가 없는 PC → $0.00
empty = ai_usage.summarize(ai_usage.read_log(Path(tempfile.mkdtemp()) / "없음.jsonl"), DAY)
expect("로그 없음 → $0.00", ai_usage.line(empty) == "오늘 내 AI $0.00 (Claude 0회) · HCX 0회 0토큰")

# 단가 모르는 Claude 모델은 회수에 넣고 따로 표시
s2 = ai_usage.summarize([row("2026-11-24T10:00:00", "claude-haiku-5-5", 100, 100)], DAY)
expect("단가 모름 표시", s2["claude_calls"] == 1 and "단가 모름 1회(claude-haiku-5-5)" in ai_usage.line(s2))

# HCX 단가를 채우면 금액에 더한다
old = ai_usage.HCX_PRICE
ai_usage.HCX_PRICE = (1.0, 5.0)
s3 = ai_usage.summarize([row("2026-11-24T10:00:00", "HCX-005", 1_000_000, 200_000)], DAY)
ai_usage.HCX_PRICE = old
expect("HCX 단가 있으면 $2.00 더함", abs(s3["usd"] - 2.0) < 1e-9 and ai_usage.line(s3).endswith("HCX 1회 1,200,000토큰 $2.00"))

# 일지 줄 읽기·팀 합계
expect("parse_line 왕복", ai_usage.parse_line("- 오늘 AI: " + ai_usage.line(s))
       == {"usd": 6.0, "claude_calls": 3, "hcx_calls": 2, "hcx_tokens": 2034})
expect("parse_line 줄 없음 → None", ai_usage.parse_line("오늘은 AI 안 씀") is None)
total, missing = ai_usage.team_total([
    ("미리", "오늘 AI: 오늘 내 AI $1.25 (Claude 10회) · HCX 4회 1,000토큰"),
    ("원우", "## 오늘 AI\n오늘 내 AI $0.50 (Claude 2회) · HCX 0회 0토큰"),
    ("민지", "일지에 줄을 안 씀"),
])
expect("팀 합계 금액·회수", abs(total["usd"] - 1.75) < 1e-9 and total["claude_calls"] == 12 and total["hcx_tokens"] == 1000)
expect("줄 없는 일지 이름", missing == ["민지"])

# 명령줄: 가짜 로그 파일로
tmp = Path(tempfile.mkdtemp())
log = tmp / "ai-calls.jsonl"
log.write_text("\n".join(lines), encoding="utf-8")
here = Path(__file__).resolve().parent
r = subprocess.run([sys.executable, "-X", "utf8", str(here / "ai_usage.py"), "--log", str(log), "--date", DAY],
                   capture_output=True, text=True, encoding="utf-8")
expect("명령줄 출력", r.returncode == 0 and r.stdout.strip() == "오늘 내 AI $6.00 (Claude 3회) · HCX 2회 2,034토큰")
(tmp / "a.md").write_text("오늘 AI: 오늘 내 AI $1.00 (Claude 1회) · HCX 1회 10토큰", encoding="utf-8")
(tmp / "b.md").write_text("없음", encoding="utf-8")
r = subprocess.run([sys.executable, "-X", "utf8", str(here / "ai_usage.py"), "--journals", str(tmp / "a.md"), str(tmp / "b.md")],
                   capture_output=True, text=True, encoding="utf-8")
expect("명령줄 팀 합계", r.stdout.strip() == "오늘 팀 AI $1.00 (Claude 1회) · HCX 1회 10토큰 — 일지 1/2개 (「오늘 AI」 줄 없음: b.md)")

# --live (/token): 네트워크 없이 — 키 없음 분기와 가짜 응답
out = ai_usage.live_lines(env={})
expect("--live 키 없음: Anthropic 로그 추정", out[0].startswith("Anthropic: Admin 키 없음 — 이 PC 로그 추정: 오늘 내 AI $"))
expect("--live 키 없음: NCP", out[1] == "NCP: NCP 키 없음")
expect("--live NCP 키 하나만 있어도 키 없음", ai_usage.live_lines(env={"NCP_OS_ACCESS_KEY": "x"})[1] == "NCP: NCP 키 없음")

seen_headers = []


def fake_anthropic(url, headers):
    seen_headers.append(headers)
    if "/api_keys" in url:
        return {"data": [{"id": "apikey_1", "name": "vcc-dev(ww)"}]}
    if "/analytics/cost" in url:      # 11/25 실제 응답 모양
        return {"data": [{"group": {"api_key_id": "apikey_1", "model": None}, "cost": {"currency": "USD", "amount": "150.5"}},
                         {"group": {"api_key_id": None}, "cost": {"currency": "USD", "amount": "49.5"}}]}
    return {"data": [{"group": {"api_key_id": "apikey_1"},
                      "usage": {"uncached_input_tokens": 1000, "output_tokens": 200, "total_tokens": 1210,
                                "cache_creation": {"ephemeral_5m_input_tokens": 10}}}]}


a = ai_usage.anthropic_lines("sk-ant-admin-가짜", today="2026-11-25", get=fake_anthropic)
expect("Anthropic 금액: 센트 → $2.00", a[0].startswith("Anthropic: 오늘 $2.00 · 이번 달 $2.00"))
expect("Anthropic 키별(이름, 금액 큰 순, total_tokens만)", [l.strip() for l in a[1:]] ==
       ["vcc-dev(ww): 오늘 $1.50 · 1,210토큰", "키 없음(콘솔 등): 오늘 $0.49 · 0토큰"])
expect("Anthropic beta 헤더", all(h.get("anthropic-beta") == ai_usage.ANALYTICS_BETA for h in seen_headers))


def fail_get(url, headers):
    raise RuntimeError("HTTP 401")


expect("Anthropic 실패 한 줄", ai_usage.anthropic_lines("k", get=fail_get) == ["Anthropic: 조회 실패 — HTTP 401"])
expect("Anthropic 실패에 키 값 없음", "비밀키값" not in ai_usage.anthropic_lines("비밀키값", get=fail_get)[0])


def fake_ncp(url, headers):
    assert "x-ncp-apigw-signature-v2" in headers
    if "getProductDemandCostList" in url:
        return {"getProductDemandCostListResponse": {"productDemandCostList": [
            {"productDemandType": {"codeName": "CLOVA Studio"}, "useAmount": 1200},
            {"productDemandType": {"codeName": "API Gateway"}, "useAmount": 180}]}}
    return {"getDemandCostListResponse": {"demandCostList": [{"creditDiscountAmount": 1260}]}}


n = ai_usage.ncp_lines("ak", "sk", month="202611", get=fake_ncp)
expect("NCP 금액·크레딧", n == ["NCP: 이번 달 이용 ₩1,380 (CLOVA Studio ₩1,200) · 크레딧 차감 ₩1,260(202611~) "
                              "→ 대회 크레딧 남은 약 ₩498,740 (추정, 청구 반영은 늦을 수 있음)"])
expect("NCP 실패 한 줄", ai_usage.ncp_lines("ak", "sk", get=fail_get) == ["NCP: 조회 실패 — HTTP 401"])
expect("NCP 응답 모양 다름", ai_usage.ncp_lines("ak", "sk", get=lambda u, h: {}) == ["NCP: 응답 모양이 예상과 다름"])

# ── 질문 1건당 원가 (--since, 작업 55) ──
def call(at, task, model, tin, tout, ms, ok=True):
    return json.dumps({"at": at, "작업": task, "모델": model, "입력토큰": tin, "출력토큰": tout,
                       "ms": ms, "ok": ok}, ensure_ascii=False)


S, O, H = "claude-sonnet-5-5", "claude-opus-5-5", "HCX-005"
cl = [
    # 건 1 (10:00:00~10:00:09): 정리 → 고르기(HCX) → 쓰기 → 검사
    call("2026-11-29T10:00:02", "정리", S, 1_000, 100, 2000),        # $0.002 + $0.001
    call("2026-11-29T10:00:03", "고르기", H, 2_000, 10, 1000),
    call("2026-11-29T10:00:06", "쓰기", S, 3_000, 500, 3000),        # $0.006 + $0.005
    call("2026-11-29T10:00:09", "검사", O, 4_000, 50, 3000),         # $0.016 + $0.001
    # 건 2 (10:05:00~): 같은 구성, 고르기 실패 1번 뒤 다시
    call("2026-11-29T10:05:02", "정리", S, 3_000, 300, 2000),        # $0.006 + $0.003
    call("2026-11-29T10:05:03", "고르기", H, None, None, 1000, ok=False),
    call("2026-11-29T10:05:04", "고르기", H, 4_000, 30, 1000),
    call("2026-11-29T10:05:07", "쓰기", S, 5_000, 700, 3000),        # $0.010 + $0.007
    call("2026-11-29T10:05:10", "검사", O, 6_000, 150, 3000),        # $0.024 + $0.003
    # 건 3 (11:00): 정리만(대화 — 쓰기·검사 없음)
    call("2026-11-29T11:00:02", "정리", S, 2_000, 200, 2000),        # $0.004 + $0.002
    # 기간 밖
    call("2026-11-28T23:59:59", "정리", S, 9_000_000, 9_000_000, 1),
    call("2026-11-30T00:00:00", "정리", S, 9_000_000, 9_000_000, 1),
    "{깨진 줄",
]
day0, day1 = ai_usage.parse_when("2026-11-29"), ai_usage.parse_when("2026-11-29", end=True)
expect("parse_when 날짜 끝 = 23:59:59", day1.isoformat() == "2026-11-29T23:59:59")
rep = ai_usage.cost_report(cl, day0, day1, [ai_usage.parse_per("물어보기 1건=정리,고르기,쓰기,검사")], gap=3)
t = {(r["작업"], r["모델"]): r for r in rep["tasks"]}
expect("기간 안 성공 9건 · 실패 1건", rep["calls"] == 9 and rep["failed"] == 1)
expect("작업별 평균: 정리 3회 입력 2,000 출력 200", t[("정리", S)]["호출"] == 3
       and t[("정리", S)]["tin"] == 2000 and t[("정리", S)]["tout"] == 200)
expect("작업별 평균 금액: 정리 $0.006", abs(t[("정리", S)]["usd"] - 0.006) < 1e-12)
expect("작업별 평균 ms: 쓰기 3000", t[("쓰기", S)]["ms"] == 3000)
expect("실패 호출 제외: 고르기 2회 평균 입력 3,000, 실패 1", t[("고르기", H)]["호출"] == 2
       and t[("고르기", H)]["tin"] == 3000 and t[("고르기", H)]["실패"] == 1)
expect("HCX 단가 없음 → 금액 0, 토큰만", t[("고르기", H)]["usd"] == 0 and t[("고르기", H)]["unpriced_tokens"] == 3020)
expect("HCX 금액 칸은 – + 토큰", ai_usage.money(t[("고르기", H)]) == "– + HCX-005 3,020토큰(단가 없음)")

b = rep["per"][0]
# 정리 0.006 + 쓰기 (0.011+0.017)/2=0.014 + 검사 (0.017+0.027)/2=0.022 = 0.042
expect("--per 묶음 합계 $0.042", abs(b["usd"] - 0.042) < 1e-12)
expect("--per 묶음 토큰 = 작업 평균의 합", b["tin"] == 2000 + 3000 + 4000 + 5000 and b["tout"] == 200 + 20 + 600 + 100)
expect("--per 묶음 HCX 토큰 따로", b["unpriced_tokens"] == 3020 and b["unpriced"] == [H])
p2 = ai_usage.per_bundle(ai_usage.load_calls(cl, day0, day1)[0], "들려주기(칸 6개)", ai_usage.parse_per("x=쓰기*6,없는작업")[1])
expect("--per 횟수 *6 · 기록 없는 작업 표시", abs(p2["usd"] - 0.084) < 1e-12 and p2["missing"] == ["없는작업"])
expect("parse_per 모양", ai_usage.parse_per("a = 정리, 요약:6 ,검사×2") == ("a", [("정리", 1), ("요약", 6), ("검사", 2)]))
try:
    ai_usage.parse_per("이름만")
    expect("parse_per '=' 없으면 오류", False)
except ValueError:
    expect("parse_per '=' 없으면 오류", True)

sh = rep["shapes"]
expect("시각 묶음: 구성 2가지", len(sh) == 2)
expect("시각 묶음: 4단계 구성 2건(실패 고르기는 구성에서 빠짐)", sh[0]["건"] == 2
       and sh[0]["구성"] == "정리 1 + 고르기 1 + 쓰기 1 + 검사 1")
expect("시각 묶음: 1건 평균 금액 $0.042", abs(sh[0]["usd"] - (0.003 + 0.011 + 0.017 + 0.009 + 0.017 + 0.027) / 2) < 1e-12)
expect("시각 묶음: 1건 소요 = (9+10)/2초", abs(sh[0]["wall_s"] - 9.5) < 1e-9)
expect("시각 묶음: 정리만 1건", sh[1]["구성"] == "정리 1" and sh[1]["건"] == 1)
sh300 = ai_usage.cost_report(cl, day0, day1, gap=300)["shapes"]
expect("gap 300 → 건 1·2가 한 건으로", sh300[0]["구성"] == "정리 2 + 고르기 2 + 쓰기 2 + 검사 2" and len(sh300) == 2)
expect("gap 없으면 시각 묶음 없음", ai_usage.cost_report(cl, day0, day1)["shapes"] is None)

txt = "\n".join(ai_usage.report_lines(rep))
expect("출력에 '추정' 문구", "금액은 추정" in txt and "HCX 단가 미확인" in txt)
md = ai_usage.report_lines(rep, md=True, krw=1400)
expect("--md 표 머리", "| 작업 | 모델 | 호출 | 실패 | 평균 입력 | 평균 출력 | 평균 금액(추정) | 평균 ms |" in md)
expect("--krw ₩ 표시", any("$0.0420 (₩58.8)" in l for l in md))

old = ai_usage.HCX_PRICE
ai_usage.HCX_PRICE = (1.0, 5.0)
rep_h = ai_usage.cost_report(cl, day0, day1, [ai_usage.parse_per("q=고르기")])
ai_usage.HCX_PRICE = old
expect("HCX 단가 채우면 자동으로 금액에: 고르기 평균 $0.0031", abs(rep_h["per"][0]["usd"] - (3000 * 1 + 20 * 5) / 1e6) < 1e-12
       and rep_h["per"][0]["unpriced_tokens"] == 0)

log2 = tmp / "cost.jsonl"
log2.write_text("\n".join(cl), encoding="utf-8")
r = subprocess.run([sys.executable, "-X", "utf8", str(here / "ai_usage.py"), "--log", str(log2), "--since", "2026-11-29",
                    "--until", "2026-11-29", "--gap", "3", "--per", "물어보기 1건=정리,고르기,쓰기,검사", "--md"],
                   capture_output=True, text=True, encoding="utf-8")
expect("명령줄 --since --md", r.returncode == 0 and "## AI 호출 원가 — 2026-11-29T00:00:00 ~ 2026-11-29T23:59:59" in r.stdout
       and "### 물어보기 1건 — 정의: 정리 1 + 고르기 1 + 쓰기 1 + 검사 1" in r.stdout)
r = subprocess.run([sys.executable, "-X", "utf8", str(here / "ai_usage.py"), "--log", str(log2), "--since", "2026-11-29",
                    "--per", "잘못"], capture_output=True, text=True, encoding="utf-8")
expect("명령줄 --per 모양 틀리면 종료코드 2", r.returncode == 2)

print(f"\n{len(fails)} fail" if fails else "\nall ok")
sys.exit(1 if fails else 0)
