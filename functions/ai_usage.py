# ai_usage.py — 오늘 내 AI 사용액 한 줄 (11/24 미리 결정)
#
# 팀원마다 미리 계정에서 따로 발급한 키(Claude vcc-dev(ww)·vcc-dev(minji), CLOVA)를 쓰고, 키별 한도가 없다.
# 그래서 각자 이 PC의 호출 기록(functions/logs/ai-calls.jsonl, ai.py가 씀)으로 오늘 사용액을 매번 본다.
#   python -X utf8 functions/ai_usage.py                → 오늘 내 AI $0.12 (Claude 5회) · HCX 3회 1,234토큰
#   python -X utf8 functions/ai_usage.py --date 2026-11-23
#   python -X utf8 functions/ai_usage.py --journals <일지.md> <일지.md> ...   → 팀 합계(milend)
# 쓰는 곳: .claude/hooks/session_start.py의 [VCC] 줄, PR 올릴 때 마지막 답, 작업일지 「오늘 AI」 줄.
# 금액은 로그 토큰 × 아래 단가로 낸 추정이다. 실제 청구는 Claude 콘솔(키별 비용)·NCP 이용 요금과 대조한다.
# AI를 부르지 않고 .env도 읽지 않는다.
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import paths

LOG_FILE = paths.LOGS / "ai-calls.jsonl"

# Claude 단가: $ per 1M 토큰 (입력, 출력). 로그의 "모델" 값(모델 ID) 기준.
CLAUDE_PRICES = {
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
# HCX 단가: 아직 확인 못 함(11/24). NCP 요금표를 확인하면 $ per 1M 토큰 (입력, 출력)으로 환산해 채운다.
# None이면 HCX는 금액에 넣지 않고 회수·토큰만 보여 준다. CLOVA는 11/24부터 대회 크레딧에서 차감.
HCX_PRICE = None


def _is_hcx(model):
    return str(model).lower().startswith("hcx")


def summarize(lines, day):
    """로그 줄(문자열) 중 day(YYYY-MM-DD) 줄만 센다. 깨진 줄·다른 날 줄은 건너뛴다."""
    s = {"date": day, "usd": 0.0, "claude_calls": 0, "hcx_calls": 0, "hcx_tokens": 0,
         "hcx_usd": None, "unpriced": {}}
    hcx_in = hcx_out = 0
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(d, dict) or not str(d.get("at", "")).startswith(day):
            continue
        model = d.get("모델", "")
        tin, tout = int(d.get("입력토큰") or 0), int(d.get("출력토큰") or 0)
        if _is_hcx(model):
            s["hcx_calls"] += 1
            hcx_in += tin
            hcx_out += tout
            continue
        s["claude_calls"] += 1
        price = CLAUDE_PRICES.get(model)
        if price is None:
            s["unpriced"][model] = s["unpriced"].get(model, 0) + 1
            continue
        s["usd"] += (tin * price[0] + tout * price[1]) / 1_000_000
    s["hcx_tokens"] = hcx_in + hcx_out
    if HCX_PRICE is not None:
        s["hcx_usd"] = (hcx_in * HCX_PRICE[0] + hcx_out * HCX_PRICE[1]) / 1_000_000
        s["usd"] += s["hcx_usd"]
    return s


def read_log(path=None):
    path = Path(path) if path else LOG_FILE
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:                       # 로그가 없는 PC(아직 AI를 안 부름)
        return []


def line(s, who="내"):
    """오늘 내 AI $0.12 (Claude 5회) · HCX 3회 1,234토큰"""
    text = f"오늘 {who} AI ${s['usd']:.2f} (Claude {s['claude_calls']}회)"
    text += f" · HCX {s['hcx_calls']}회 {s['hcx_tokens']:,}토큰"
    if s["hcx_usd"] is not None:
        text += f" ${s['hcx_usd']:.2f}"
    if s["unpriced"]:
        n = sum(s["unpriced"].values())
        text += f" · 단가 모름 {n}회({', '.join(sorted(s['unpriced']))})"
    return text


def today_line(day=None, path=None):
    day = day or date.today().isoformat()
    return line(summarize(read_log(path), day))


# ── 팀 합계 (milend) ── 작업일지의 「오늘 AI」 줄(위 line() 모양)을 읽어 더한다.
_LINE = re.compile(r"오늘 \S+ AI \$([\d.]+) \(Claude ([\d,]+)회\) · HCX ([\d,]+)회 ([\d,]+)토큰")


def parse_line(text):
    """글에서 첫 「오늘 … AI $x (Claude n회) · HCX m회 k토큰」을 찾아 dict로. 없으면 None."""
    m = _LINE.search(text)
    if not m:
        return None
    num = lambda g: int(g.replace(",", ""))
    return {"usd": float(m.group(1)), "claude_calls": num(m.group(2)),
            "hcx_calls": num(m.group(3)), "hcx_tokens": num(m.group(4))}


def team_total(texts):
    """[(이름, 일지 글)] → (합계 dict, 줄을 못 찾은 이름 목록)"""
    total = {"usd": 0.0, "claude_calls": 0, "hcx_calls": 0, "hcx_tokens": 0,
             "hcx_usd": None, "unpriced": {}}
    missing = []
    for name, text in texts:
        p = parse_line(text)
        if p is None:
            missing.append(name)
            continue
        for k in ("usd", "claude_calls", "hcx_calls", "hcx_tokens"):
            total[k] += p[k]
    return total, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="오늘 내 AI 사용액 한 줄 (ai-calls.jsonl × 단가)")
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)")
    ap.add_argument("--log", help="로그 파일 (기본: 본 저장소 functions/logs/ai-calls.jsonl)")
    ap.add_argument("--json", action="store_true", help="숫자를 JSON으로")
    ap.add_argument("--journals", nargs="+", metavar="일지", help="작업일지들의 「오늘 AI」 줄을 더해 팀 합계")
    a = ap.parse_args(argv)
    if a.journals:
        texts = []
        for f in a.journals:
            try:
                texts.append((Path(f).name, Path(f).read_text(encoding="utf-8-sig")))
            except OSError:
                texts.append((Path(f).name, ""))
        total, missing = team_total(texts)
        out = line(total, who="팀") + f" — 일지 {len(texts) - len(missing)}/{len(texts)}개"
        if missing:
            out += f" (「오늘 AI」 줄 없음: {', '.join(missing)})"
        print(json.dumps({**total, "missing": missing}, ensure_ascii=False) if a.json else out)
        return 0
    s = summarize(read_log(a.log), a.date or date.today().isoformat())
    print(json.dumps(s, ensure_ascii=False) if a.json else line(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
