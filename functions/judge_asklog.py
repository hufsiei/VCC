# judge_asklog.py — 실사용 인터BOO 답 채점 (11/25 Q-13, 작성: 미리)
#
# 시험 중 학생이 실제로 던진 질문(runtime askLog — askboo._log_answer가 남김)을 Opus가 한 건씩 채점한다.
#   점수: 답했나(질문에 바로 답했나) · 근거(답 문장이 인용 근거에만 맞나, 답 문장이 없으면 null) · 길(보류·공식 안내·노트·대화 선택이 맞나)
#   각 1~5점 + 이유 한 줄. 프롬프트 원문은 docs/prompts/askBoo-채점.txt, 모델은 ai.py PROVIDER["채점"].
# 답할 때 실시간으로 부르지 않는다 — 하루 한 번 몰아서 돌린다(미리 PC, 11/25 결정).
# 채점 결과는 이 PC의 functions/logs/ask-judge.jsonl(.gitignore)에 쌓이고, export_runtime.py가 드라이브 로그 엑셀 「채점」 시트로 낸다.
# 이미 채점한 기록(id)은 다시 부르지 않는다 → 「새 기록만」.
#
# 실행: cd C:\dev\VCC\functions
#   python -X utf8 judge_asklog.py              새 기록 수·예상 금액·오늘 내 AI 사용액만 보여 준다(AI 안 부름)
#   python -X utf8 judge_asklog.py --run        실제 채점(최대 --max건, 기본 50)
#   python -X utf8 judge_asklog.py --local      버킷 대신 이 PC의 data/runtime/askLog.json(개발 확인용)
#   python -X utf8 judge_asklog.py --show       채점 결과 요약(평균·낮은 점수)만 — AI 안 부름
# 지키는 것: 기록은 이미 mask.py로 가려진 글이고, callAI 입구에서 한 번 더 가린다. 사람 칸(학번 등)은 기록에 없다.
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import paths

JUDGE_FILE = paths.LOGS / "ask-judge.jsonl"
STATUS_WORD = {"ok": "답함", "hold": "보류", "official": "공식 안내", "notes": "노트 안내", "chat": "대화"}
SCORES = ("답했나", "근거", "길")
# 건당 예상: 입력 ~2,000토큰(프롬프트·예시 + 기록·근거) · 출력 ~700토큰(생각 포함, effort low) × Opus 5.5 단가(ai_usage.py)
EST_IN, EST_OUT = 2000, 700
KST = timezone(timedelta(hours=9))


def key_of(row):
    """채점 열쇠: 기록 id. Q-13 전 기록(id 없음)은 시각 + 질문."""
    return row.get("id") or f"{row.get('at')}|{row.get('question')}"


def judged_keys(path=JUDGE_FILE):
    out = set()
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                out.add(json.loads(raw)["key"])
            except (ValueError, KeyError, TypeError):
                continue
    except OSError:
        pass
    return out


def read_judged(path=JUDGE_FILE):
    rows = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("key"):
                rows.append(d)
    except OSError:
        pass
    return rows


def new_rows(log, done):
    return [r for r in log if isinstance(r, dict) and r.get("question") and key_of(r) not in done]


def estimate(n):
    import ai_usage
    p_in, p_out = ai_usage.CLAUDE_PRICES["claude-opus-5-5"]
    return n * (EST_IN * p_in + EST_OUT * p_out) / 1_000_000


# ── 채점 입력 ─────────────────────────────────────────────────────────
_SOURCES = None


def source_text(sid, programs):
    """근거 id → 원문(보고서 문단 또는 동의 통과 인터뷰 문장). 못 찾으면 None."""
    global _SOURCES
    import askboo
    import notes
    if _SOURCES is None:
        _SOURCES = {e["id"]: e["text"] for rows in askboo.EVIDENCE.values() for e in rows}
    if sid in _SOURCES:
        return _SOURCES[sid]
    for p in programs or []:
        for r in notes.interview_lines(p):
            if r["id"] == sid:
                return r["text"]
    return None


def record_text(row):
    """askLog 한 건 → 채점 입력 글(프롬프트 예시와 같은 모양)."""
    prev = row.get("prev")
    head = f"후배: {prev['question']} → BOO: {STATUS_WORD.get(prev.get('status'), prev.get('status') or '?')}" \
        + (f" ({prev['program']})" if prev.get("program") else "") if prev else "(없음)"
    judge = " · ".join(f"{k}={row.get(f) or '–'}" for k, f in
                       (("길", "route"), ("의도", "intent"), ("분야", "field"), ("칸", "section")))
    out = [f"앞 턴: {head}", f"이번 질문: {row.get('question')}"]
    if row.get("asked"):
        out.append(f"정리된 질문: {row['asked']}")
    out += [f"판단: {judge}", f"결과: {STATUS_WORD.get(row.get('status'), row.get('status'))}",
            f"안내 문구: {row.get('message') or '–'}"]
    lines = row.get("lines") or []
    if lines:
        cites, out_lines = [], []
        for i, ln in enumerate(lines, 1):
            nums = []
            for c in ln.get("cites") or []:
                if c not in cites:
                    cites.append(c)
                nums.append(cites.index(c) + 1)
            tag = " (원문 인용)" if ln.get("fallback") else ""
            out_lines.append(f"{i}. {ln.get('text', '')}{tag} " + " ".join(f"[근거 {n}]" for n in nums))
        out += ["답 문장:", *out_lines, "근거:"]
        out += [f"[{i}] {source_text(c, row.get('programs')) or '(원문을 찾지 못함)'}" for i, c in enumerate(cites, 1)]
    else:
        out.append("답 문장: (없음)")
    out.append("보여 준 노트: " + (", ".join(row.get("programs") or []) or "(없음)"))
    return "\n".join(out) + "\n출력:"


def parse(j, has_lines):
    """채점 JSON 검사. 형식이 틀리면 None(그 기록은 다음에 다시)."""
    if not isinstance(j, dict):
        return None
    out = {}
    for k in SCORES:
        v = j.get(k)
        if k == "근거" and not has_lines:
            out[k] = None
            continue
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            if k == "근거" and v is None:
                out[k] = None
                continue
            return None
        out[k] = v
    why = j.get("이유")
    if not isinstance(why, str) or not why.strip():
        return None
    out["이유"] = why.strip()[:100]
    return out


def judge_one(row, call=None):
    """기록 한 건 채점 → {답했나, 근거, 길, 이유} 또는 None."""
    from ai import callAI, load_prompt
    call = call or callAI
    system, shots = load_prompt("askBoo-채점")
    r = call("채점", shots + [{"role": "user", "content": record_text(row)}], system=system)
    if not r.get("ok"):
        return None
    return parse(r.get("json"), bool(row.get("lines")))


def judged_row(row, score):
    return {"key": key_of(row), "at": row.get("at"), "judgedAt": datetime.now(KST).isoformat(timespec="seconds"),
            "question": row.get("question"), "status": row.get("status"), "route": row.get("route"),
            "intent": row.get("intent"), **score}


def run(log, limit, call=None, path=JUDGE_FILE):
    """새 기록을 오래된 것부터 limit건 채점해 path에 한 줄씩 붙인다(중간에 멈춰도 한 것은 남는다). → (성공, 실패)."""
    todo = new_rows(log, judged_keys(path))[:limit]
    ok = fail = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    for row in todo:
        score = judge_one(row, call)
        if score is None:
            fail += 1
            continue
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(judged_row(row, score), ensure_ascii=False) + "\n")
        ok += 1
    return ok, fail


def summary(rows):
    """채점 결과 요약 글."""
    if not rows:
        return "채점 결과 없음"
    out = [f"채점 {len(rows)}건"]
    for k in SCORES:
        vals = [r[k] for r in rows if isinstance(r.get(k), int)]
        if vals:
            out.append(f"{k} 평균 {sum(vals) / len(vals):.1f} (2점 이하 {sum(v <= 2 for v in vals)}건)")
    low = sorted(rows, key=lambda r: min(v for v in (r.get(k) for k in SCORES) if isinstance(v, int)))[:5]
    out.append("낮은 점수:")
    out += [f"  {r.get('question')} → {STATUS_WORD.get(r.get('status'), r.get('status'))} · "
            + "/".join(str(r.get(k) if r.get(k) is not None else "–") for k in SCORES) + f" · {r.get('이유')}" for r in low]
    return "\n".join(out)


def load_log(local):
    if not local:
        paths.load_env()
        os.environ["STORE_BACKEND"] = "ncp"
        os.environ.setdefault("NCP_OS_PREFIX", "runtime/")
    import store
    return list(store.load("askLog", []))


def main(argv):
    a = argparse.ArgumentParser(description="실사용 인터BOO 답 채점(askLog → Opus, 하루 한 번)")
    a.add_argument("--run", action="store_true", help="실제로 채점한다(AI 호출). 없으면 건수·예상 금액만")
    a.add_argument("--max", type=int, default=50, help="한 번에 채점할 최대 건수(기본 50)")
    a.add_argument("--local", action="store_true", help="버킷 대신 이 PC의 data/runtime을 읽는다")
    a.add_argument("--show", action="store_true", help="채점 결과 요약만 보여 준다")
    args = a.parse_args(argv)
    if args.show:
        print(summary(read_judged()))
        return 0
    import ai_usage
    log = load_log(args.local)
    todo = new_rows(log, judged_keys())
    n = min(len(todo), args.max)
    print(f"askLog {len(log)}건 · 새 기록 {len(todo)}건 · 이번 채점 {n}건 · 예상 ${estimate(n):.2f} (Opus 5.5, 건당 ~${estimate(1):.3f})")
    print(ai_usage.today_line())
    if not args.run:
        print("AI를 부르지 않았어요. 채점하려면 --run")
        return 0
    ok, fail = run(log, args.max)
    print(f"채점 {ok}건 · 실패 {fail}건(형식 오류·호출 실패 — 다음에 다시) → {JUDGE_FILE}")
    print(ai_usage.today_line())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
