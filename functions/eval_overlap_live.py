# eval_overlap_live.py — 겹쳐 돌리기(작업 35 · #278 3-3) 실제 호출 전후 시간 비교 (미리, AI 비용 있음)
#   python -X utf8 functions/eval_overlap_live.py            # 대상 10문항 × 끔/켬 = askBoo 20번(예상 약 $1, HCX 0회)
#   python -X utf8 functions/eval_overlap_live.py --list     # 대상 문항만 보여 줌(AI 안 부름)
# 대상: 90문항 중 앞 대화 없음 + 학교 이름이 글자로 잡혀 겹쳐 돌리기가 시작되는 질문, 기대결과 「답변」, 학교가 서로 다르게.
# 프롬프트 캐시가 두 번째 실행을 빠르게 하므로 앞 5문항은 끔→켬, 뒤 5문항은 켬→끔 순서로 돌린다.
# 단계별 ms: callAI를 감싸 작업별 시작·끝을 잰다(응답·글은 남기지 않음). save=False(질문함·askLog에 안 남김).
# 결과: 질문별 한 줄(끔·켬 총초, 질문정리·답쓰기·답검사 ms, status 끔/켬) + 중앙값. --out이면 JSON.
import argparse
import json
import os
import statistics as st
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
sys.path.insert(0, str(ROOT / "tools"))
os.environ["VCC_ASK_FULL"] = "1"
import askboo  # noqa: E402
import run_eval  # noqa: E402


def targets(n=10):
    rows = run_eval.read_questions(ROOT / "data" / "eval-questions.csv") \
        + run_eval.read_questions(ROOT / "data" / "eval-questions-multi.csv")
    out, seen = [], set()
    for r in rows:
        if r["기대결과"] != "답변" or run_eval.read_history(r.get("이전대화")):
            continue
        q = r["질문"]
        progs = askboo.match_programs(q)
        if not progs or askboo.is_official(q) or askboo.is_compare(q) or progs[0] in seen:
            continue
        if not askboo.full_evidence(q, progs)[0]:
            continue
        seen.add(progs[0])
        out.append(r)
        if len(out) >= n:
            break
    return out


real = askboo.callAI
spans, lock = [], threading.Lock()


def timed(작업명, messages, system=None, **kw):
    t = time.perf_counter()
    try:
        return real(작업명, messages, system=system, **kw)
    finally:
        with lock:
            spans.append((작업명, t, time.perf_counter()))


def one(q, flag):
    os.environ["VCC_ASK_OVERLAP"] = flag
    spans.clear()
    trace = {}
    t0 = time.perf_counter()
    res = askboo._answer("eval", {"question": q, "history": []}, False, trace)
    total = time.perf_counter() - t0
    sp = trace.get("overlap")
    if sp:
        sp["future"].result()
    with lock:
        s = list(spans)
    ms = {}
    for name, a, b in s:
        if b - t0 > total + 0.05:   # 응답 뒤에 끝난 호출(버린 답쓰기)은 단계 시간에 넣지 않는다
            name += "(응답 뒤)"
        ms.setdefault(name, []).append(round((b - a) * 1000))
    return {"total": round(total, 2), "status": res.get("status"), "lines": len(res.get("lines") or []),
            "used": None if sp is None else sp.get("used"), "ms": ms}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    rows = targets(a.n)
    for r in rows:
        print(r["번호"], r["질문"], "→", askboo.match_programs(r["질문"])[0])
    if a.list:
        return 0
    askboo.callAI = timed
    result = []
    for i, r in enumerate(rows):
        order = ("0", "1") if i < len(rows) / 2 else ("1", "0")
        got = {f: one(r["질문"], f) for f in order}
        result.append({"번호": r["번호"], "order": "".join(order), "off": got["0"], "on": got["1"]})
        o, n = got["0"], got["1"]
        print(f"{r['번호']:>3} 순서 {'끔→켬' if order[0] == '0' else '켬→끔'} · 끔 {o['total']:.2f}s {o['status']}/{o['lines']}줄"
              f" · 켬 {n['total']:.2f}s {n['status']}/{n['lines']}줄 쓰임={n['used']} · 차이 {o['total'] - n['total']:+.2f}s"
              f" · 끔 {o['ms']} · 켬 {n['ms']}", flush=True)
    off = [x["off"]["total"] for x in result]
    on = [x["on"]["total"] for x in result]
    d = [x["off"]["total"] - x["on"]["total"] for x in result]
    same = sum(1 for x in result if x["off"]["status"] == x["on"]["status"])
    print(f"중앙값 끔 {st.median(off):.2f}s · 켬 {st.median(on):.2f}s · 단축 중앙 {st.median(d):+.2f}s 평균 {st.mean(d):+.2f}s"
          f" · status 같음 {same}/{len(result)}")
    if a.out:
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    os.environ.pop("VCC_ASK_OVERLAP", None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
