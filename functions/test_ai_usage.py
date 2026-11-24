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

print(f"\n{len(fails)} fail" if fails else "\nall ok")
sys.exit(1 if fails else 0)
