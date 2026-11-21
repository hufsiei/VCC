# suggest.py — 개선 제안 사전 생성 + 리포트 요약 (작업 67, PRD 5-3·5-4·8장)
#
# 1) 개선 제안: 시드 사용 로그의 묶음(admin._bundles, 보류·규정 질문 3건 이상)마다 AI 1회
#    → {"유형","제목","제안"} → 사후 검증 → data/suggestions.json 캐시. 시연 중에는 AI를 부르지 않는다.
#    실행: cd functions && python suggest.py            (전부 다시 만듦)
#          python suggest.py --dry                      (AI 없이 묶음·입력만 출력)
#          python suggest.py --retry                    (제목·제안 중 하나라도 버려진 묶음만 다시 부름)
# 2) 리포트 요약: issueReport 때 AI 1회 {"요약"} → 사후 검증 → 실패하면 admin._summary 템플릿.
#
# 사후 검증(코드, AI 아님): 입력에 없는 숫자·영문·고유명사, URL·HTML 태그가 있으면 그 칸을 버린다.
#   제안이 걸리면 제안만 버리고 제목은 남긴다(제목이 걸리면 화면은 템플릿 제목). 모델은 ai.py PROVIDER 「개선제안」「리포트요약」.
import json
import re
import sys
from pathlib import Path

from ai import callAI, load_prompt
from askboo import PROPER_NOUNS, _norm

DATA = Path(__file__).resolve().parent.parent / "data"
OUT = DATA / "suggestions.json"
KINDS = ("신규 수요", "안내 보강", "검토 필요")
MAX_QUESTIONS = 10                      # 묶음에서 AI에 보내는 질문 수(최근순)
LIMITS = {"제목": 40, "제안": 160, "요약": 260}
ALLOWED_EN = {"faq", "q&a"}              # 일반 낱말(기관·시험 이름이 아님) — 제안문에 써도 된다
URL_HTML = re.compile(r"https?://|www\.|<\s*/?\s*[a-zA-Z]|&lt;|javascript:", re.I)


def check_generated(text, source, kind="제안", limit=None):
    """생성 글이 입력(source)에 없는 것을 말하는지 본다. 빈 목록이면 통과."""
    problems = []
    if not isinstance(text, str) or not text.strip():
        return ["빈 글"]
    if URL_HTML.search(text):
        problems.append("URL·HTML")
    if len(text) > (limit or LIMITS.get(kind, 200)):
        problems.append("너무 김")
    allowed = set(re.findall(r"\d+(?:[.,]\d+)?", source))   # 글자 일부가 아니라 숫자 전체로 대조(「2023」 안의 3은 3이 아님)
    for num in re.findall(r"\d+(?:[.,]\d+)?", text):
        if num not in allowed:
            problems.append(f"숫자 {num}")
    low = source.lower()
    for w in re.findall(r"[A-Za-z][A-Za-z\-]+", text):
        if w.lower() not in low and w.lower() not in ALLOWED_EN:
            problems.append(f"영문 {w}")
    t, s = _norm(text), _norm(source)
    for noun in PROPER_NOUNS:
        n = _norm(noun)
        if n and n in t and n not in s:
            problems.append(f"고유명사 {noun}")
    return problems


# ---------- 1) 개선 제안 ----------
def bundle_input(program, section, kind, questions):
    qs = sorted(questions, key=lambda q: q["at"], reverse=True)[:MAX_QUESTIONS]
    lines = "\n".join(f"- {q.get('질문', '')}" for q in qs)
    return f"프로그램: {program}\n칸: {section or '(칸 없음)'}\n참고 유형: {kind}\n질문:\n{lines}"


def generate_one(program, section, kind, questions, call=None):
    """묶음 하나 → 캐시 행 {id, 유형, 제목, 제안, ...}. 검증에 걸린 칸은 빈 글자로 둔다(admin이 템플릿으로 채움)."""
    import admin
    call = call or callAI
    system, shots = load_prompt("개선제안")
    content = bundle_input(program, section, kind, questions)
    r = call("개선제안", shots + [{"role": "user", "content": content}], system=system)
    j = r.get("json") if isinstance(r.get("json"), dict) else {}
    aliases = " ".join((admin.PROGRAMS.get(program) or {}).get("별칭", []))
    source = f"{content} {aliases}"
    row = {"id": admin._suggestion_id(program, section), "프로그램명": program, "칸": section,
           "유형": "", "제목": "", "제안": "", "model": r.get("model"), "problems": {}}
    if j.get("유형") in KINDS:
        row["유형"] = j["유형"]
    for key in ("제목", "제안"):
        # 제목은 프로그램 이름을 그대로 쓰므로 긴 이름(40자 넘는 비교과)도 들어가게 한도를 늘린다
        limit = max(LIMITS[key], len(program) + 20) if key == "제목" else None
        p = check_generated(j.get(key), source, key, limit)
        if p:
            row["problems"][key] = p
        else:
            row[key] = j[key].strip()
    if not r.get("ok"):
        row["problems"]["호출"] = [r.get("error", "실패")]
    return row


def build(call=None, dry=False, retry=None):
    import admin
    from datetime import date
    rows = admin._questions(date(2000, 1, 1), date(2100, 1, 1), seed_only=True)
    bundles = admin._bundles(rows)
    out = []
    for i, ((program, section), qs) in enumerate(sorted(bundles.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")), 1):
        kind = admin._kind(program, section, qs)
        sid = admin._suggestion_id(program, section)
        if retry is not None and sid in retry:   # --retry: 통과한 행은 다시 부르지 않는다
            out.append(retry[sid])
            continue
        if dry:
            print(f"[{i}/{len(bundles)}] {program} · {section} · {kind} · {len(qs)}건")
            continue
        row = generate_one(program, section, kind, qs, call=call)
        flag = " / ".join(f"{k}: {', '.join(v)}" for k, v in row["problems"].items()) or "통과"
        print(f"[{i}/{len(bundles)}] {program} · {section} → {row['유형'] or kind} · {row['제목'] or '(템플릿)'} · {flag}")
        out.append(row)
    return out


# ---------- 2) 리포트 요약 ----------
def summary_input(ov, sugg):
    k = ov["kpi"]
    dept_name = ov.get("deptName") or ov["dept"]
    top = ", ".join(r["프로그램명"] for r in ov["programs"][:3]) or "없음"
    titles = ", ".join(s["제목"] for s in sugg.get("suggestions", [])[:3]) or "없음"
    return (f"기간: {ov['label']}\n부서: {dept_name}\n질문 수: {k['questions']['value']}\n"
            f"미답변 질문: {k['unanswered']['value']}\n보류율: {k['unanswered']['holdRate']}%\n"
            f"신규 수요 묶음: {k['newDemand']['value']}\n개선 요청: {k['improvements']['value']}\n"
            f"질문이 많은 프로그램: {top}\n개선 제안 제목: {titles}")


def ai_summary(ov, sugg, call=None):
    """돌려주는 값: (요약 글, 출처 "ai"|None). 실패·검증 탈락이면 (None, None) → 부르는 쪽이 템플릿."""
    call = call or callAI
    system, shots = load_prompt("리포트요약")
    content = summary_input(ov, sugg)
    r = call("리포트요약", shots + [{"role": "user", "content": content}], system=system)
    j = r.get("json") if isinstance(r.get("json"), dict) else {}
    text = j.get("요약")
    if not r.get("ok") or check_generated(text, content, "요약"):
        return None, None
    return text.strip(), "ai"


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    keep = None
    if "--retry" in sys.argv and OUT.exists():   # 제목·제안이 모두 통과한 행만 두고 나머지만 다시 부른다
        keep = {r["id"]: r for r in json.loads(OUT.read_text(encoding="utf-8")) if r["제목"] and r["제안"]}
    rows = build(dry=dry, retry=keep)
    if not dry:
        OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ok = sum(1 for r in rows if r["제안"])
        print(f"\n저장: {OUT.name} · 묶음 {len(rows)} · 제안 통과 {ok} · 제목 통과 {sum(1 for r in rows if r['제목'])}")
