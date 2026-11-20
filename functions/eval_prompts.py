# eval_prompts.py — 작업 53 미검증 프롬프트 6종 채점 (작성: 미리)
#
# 실행:  cd C:\dev\VCC\functions
#        python eval_prompts.py                  # 6종 모두 HCX로
#        python eval_prompts.py 요약 일치검사      # 고른 종류만
#        python eval_prompts.py --sonnet 요약 일치검사   # Claude Sonnet으로 같은 사례(비교용, Anthropic 크레딧 필요)
#        python eval_prompts.py --opus 일치검사          # Claude Opus로. --claude는 CLAUDE_MODEL(기본 Sonnet)
#        결과: logs/eval-prompts-{hcx|sonnet|opus|claude}.json — 모델마다 다른 파일이라 서로 덮지 않는다
#
# 프롬프트: docs/prompts/{작업명}.txt · 사례: functions/eval53_cases.json(종류마다 정상 5·함정 5, 가상 문장)
# 채점은 첫 JSON 파싱 후 기준(HCX 원칙 v2 2절). 합격선(작업 53): 판정·분류 9/10 이상, 요약·일치 검사는 근거 밖 내용 0건.
#   충분판정·쪽지검사·문단분류 — 기대값과 같으면 정답
#   꼬리질문 — 질문 하나·50자 안·답에 없는 숫자·영문·고유명사·금지어 없음이면 정답
#   요약     — 문장마다 askboo.verify(문장, 원문)와 금지어·불확실 표현 검사. 걸린 문장 수 = 근거 밖 의심
#   일치검사 — 기대 false를 true로 놓친 수 = 근거 밖 통과(0이어야 함). 정확도도 함께
# 결과 전체는 functions/logs/eval-prompts-{모델}.json (.gitignore 대상) — 문장을 사람이 직접 훑어보는 용도.
import json
import re
import sys
from pathlib import Path

import askboo
from ai import SETTINGS, callAI, load_prompt

HERE = Path(__file__).parent
CASES = json.loads((HERE / "eval53_cases.json").read_text(encoding="utf-8"))
SECTIONS = ["지원동기", "업무내용", "배운점"]

# HCX로 잴 때 설정(원칙 v2 5절: 사실을 다루는 호출은 T=0, Max는 출력 크기에 맞게). PROVIDER가 hcx인 작업은 SETTINGS 그대로.
HCX_SETTINGS = {"요약": {"max_tokens": 300, "temperature": 0}, "일치검사": {"max_tokens": 30, "temperature": 0},
                "문단분류": {"max_tokens": 30, "temperature": 0}}
# Claude로 잴 때는 서비스와 같은 설정(ai.SETTINGS)으로 잰다. Opus 5.5는 생각을 끌 수 없고 생각 토큰도 max_tokens에 들어가므로
# 1000처럼 작게 잡으면 답이 잘려 'JSON 없음'으로 오답 처리될 수 있다. PROVIDER가 hcx인 작업(문단분류 등)은 2000/low.
CLAUDE_FALLBACK = {"max_tokens": 2000, "effort": "low"}


def claude_settings(kind):
    s = SETTINGS.get(kind, {})
    return s if "effort" in s else CLAUDE_FALLBACK


def user_text(kind, c):
    if kind == "충분판정":
        return f"칸: {c['칸']}\n질문: {c['질문']}\n답: {c['답']}\n출력:"
    if kind == "꼬리질문":
        return f"칸: {c['칸']}\n처음 질문: {c['처음 질문']}\n답: {c['답']}\n출력:"
    if kind == "요약":
        return f"칸: {c['칸']}\n답: {c['답']}\n출력:"
    if kind == "일치검사":
        return f"원문: {c['원문']}\n요약: {c['요약']}\n출력:"
    if kind == "쪽지검사":
        return f"쪽지: {c['쪽지']}\n출력:"
    if kind == "문단분류":
        return f"칸 목록: {', '.join(SECTIONS)}\n문장: {c['문장']}\n출력:"
    raise ValueError(kind)


def outside(text, source, banned=()):
    """답(원문)에 없는 숫자·영문·고유명사·금지어. 꼬리 질문용(새 낱말은 질문이라 허용)."""
    probs = [f"숫자 {n}" for n in re.findall(r"\d+", text) if n not in source]
    probs += [f"영문 {w}" for w in re.findall(r"[A-Za-z][A-Za-z\-]+", text) if w.lower() not in source.lower()]
    probs += [f"고유명사 {p}" for p in askboo.PROPER_NOUNS if askboo._norm(p) in askboo._norm(text)
              and askboo._norm(p) not in askboo._norm(source)]
    probs += [f"금지어 {b}" for b in banned if b in text]
    return probs


HEDGE = re.compile(r"아마|것 같|정도|쯤|정확하진|정확하지")


def grade(kind, c, j):
    """돌려주는 값: (정답 여부, 메모)."""
    if not isinstance(j, dict):
        return False, "JSON 없음"
    if kind == "충분판정":
        v = j.get("충분")
        return v is c["기대"], f"충분={v}"
    if kind == "쪽지검사":
        v = j.get("ok")
        ok = v is c["기대"] and (v is True or j.get("reason") == "비방")
        return ok, f"ok={v} reason={j.get('reason')}"
    if kind == "문단분류":
        v = j.get("칸")
        want = c["기대"] if isinstance(c["기대"], list) else [c["기대"]]
        return v in want and v in SECTIONS, f"칸={v}"
    if kind == "일치검사":
        v = j.get("일치")
        return v is c["기대"], f"일치={v}"
    if kind == "꼬리질문":
        q = j.get("질문")
        if not isinstance(q, str) or not q.strip():
            return False, "질문 없음"
        probs = outside(q, c["답"] + " " + c["처음 질문"] + " " + c["칸"], c.get("금지", ()))
        if len(q) > 50:
            probs.append(f"{len(q)}자")
        if q.count("?") > 1:
            probs.append("질문 여러 개")
        return not probs, f"{q} {probs or ''}"
    if kind == "요약":
        lines = j.get("문장")
        if not isinstance(lines, list) or not lines or not all(isinstance(s, str) for s in lines):
            return False, "문장 목록 없음"
        bad = []
        for s in lines:
            p = askboo.verify(s, c["답"]) + [f"금지어 {b}" for b in c.get("금지", ()) if b in s]
            if HEDGE.search(c["답"]) and re.search(r"\d", s) and not HEDGE.search(s):
                p.append("불확실 표현이 빠짐")
            if p:
                bad.append({"문장": s, "문제": p})
        return not bad, {"문장": lines, "근거 밖 의심": bad}
    raise ValueError(kind)


def run(kinds, model):
    report, summary = {}, {}
    for kind in kinds:
        system, shots = load_prompt(kind)
        rows, right, miss_outside, outside_lines = [], 0, 0, 0
        for i, c in enumerate(CASES[kind], 1):
            r = callAI(kind, shots + [{"role": "user", "content": user_text(kind, c)}], system=system,
                       측정모델=model, 측정설정=HCX_SETTINGS.get(kind) if model == "hcx" else claude_settings(kind))
            ok, memo = grade(kind, c, r.get("json")) if r["ok"] else (False, r.get("error"))
            right += ok
            if kind == "일치검사" and c["기대"] is False and r.get("json", {}) and r["json"].get("일치") is True:
                miss_outside += 1
            if kind == "요약" and isinstance(memo, dict):
                outside_lines += len(memo["근거 밖 의심"])
            print(f"  {'O' if ok else 'X'} {kind} {i:>2} [{c['유형']}] {memo if not isinstance(memo, dict) else memo['문장']}")
            if isinstance(memo, dict) and memo["근거 밖 의심"]:
                print(f"       !! {memo['근거 밖 의심']}")
            rows.append({"사례": c, "원시 출력": r.get("text"), "정답": ok, "메모": memo})
        s = {"정답": right, "전체": len(CASES[kind])}
        if kind == "일치검사":
            s["근거 밖 통과"] = miss_outside
        if kind == "요약":
            s["근거 밖 의심 문장"] = outside_lines
        summary[kind] = s
        report[kind] = rows
        print(f"== {kind}: {s}\n")
    out = HERE / "logs" / f"eval-prompts-{model}.json"
    out.parent.mkdir(exist_ok=True)
    old = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"결과": {}, "합계": {}}
    old["결과"].update(report)
    old["합계"].update(summary)
    out.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding="utf-8")
    print("합계:", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    args = sys.argv[1:]
    model = next((m for m in ("sonnet", "opus", "claude") if f"--{m}" in args), "hcx")
    kinds = [a for a in args if not a.startswith("--")] or [k for k in CASES if not k.startswith("_")]
    run(kinds, model)
