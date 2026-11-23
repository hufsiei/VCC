# test_note_summary.py — 작업 78 칸별 요약 문단(tools/build_notes.py --summary) 코드 단계 시험. AI는 가짜(askboo._call 대신).
# 보는 것: ① 배운점·인터뷰로만·빈 칸은 AI를 부르지 않음 ② 근거 번호 없는 문장·근거에 없는 숫자·답검사 불일치는 버림
#         ③ sources = 인용 문단 id, years = 그 연도들 ④ build()가 note-summaries.json을 입히고 check()가 통과
#         ⑤ check()가 다른 칸 출처·틀린 연도·지어낸 숫자·배운점 요약을 잡음
# 실행: cd functions && python test_note_summary.py   (data/note-summaries.json은 건드리지 않는다: 임시 파일로 바꿔 씀)
import copy
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "functions"))
sys.path.insert(0, str(ROOT / "tools"))
import askboo  # noqa: E402
import build_notes  # noqa: E402

fails = []


def expect(name, cond, info=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  — {info}" if info and not cond else ""))
    if not cond:
        fails.append(name)


def ok(obj):
    from ai import first_json
    text = json.dumps(obj, ensure_ascii=False)
    return {"ok": True, "text": text, "json": first_json(text), "model": "fake"}


calls = []


def fake_call(kind, content):
    calls.append((kind, content))
    if kind == "답검사":
        return ok({"일치": "답검사에 걸릴" not in content})
    sec = re.search(r"「(.+?)」", content).group(1)
    return ok({"답": [
        {"text": f"{sec} 준비는 미리 해 두었다는 선배도 있었어요.", "근거": [1, 2]},
        {"text": "번호가 없는 문장이에요.", "근거": []},
        {"text": "비용은 98765유로였다고 해요.", "근거": [1]},          # 근거에 없는 숫자 → 코드가 버림
        {"text": "답검사에 걸릴 문장이에요.", "근거": [1]},              # 답검사 불일치 → 버림
        {"text": "반말로 끝나는 문장이다.", "근거": [1]},
    ]})


askboo._call = fake_call

notes = build_notes.build()
m = next(n for n in notes if n["id"] == "N-marburg")
got = build_notes.summarize(m)
asked = [re.search(r"「(.+?)」", c).group(1) for k, c in calls if k == "답쓰기"]
filled = [s["name"] for s in m["sections"] if s["lines"] and not s["interviewOnly"] and s["name"] not in build_notes.NO_SUMMARY]
expect("① 답쓰기는 원문 있는 일반 칸만 (배운점·인터뷰로만 제외)", asked == filled and "배운점" not in asked, asked)
expect("① 질문 없이 돈다(「칸 정리」 문구)", all("(질문 없음)" in c for k, c in calls if k == "답쓰기"))
expect("② 칸마다 통과 문장 1개만 남음", all(len(v) == 1 for v in got.values()) and set(got) == set(filled), got)
sec0 = m["sections"][0]
first = got[sec0["name"]][0]
expect("② 남은 문장은 근거 번호 있던 해요체 문장", first["text"].startswith(sec0["name"]))
cand_ids = []
for l in sec0["lines"]:
    cand_ids += [l["sourceId"]] * len({askboo._norm(askboo.clean_source(t)) for t in askboo.split_sentences(l["text"])})
expect("③ sources = 인용한 문장의 문단 id(중복 없음)", first["sources"] == list(dict.fromkeys(cand_ids[:2])), first["sources"])
expect("③ years = 그 문단들의 연도", first["years"] == sorted({int(m["sources"][i]["semester"][:4]) for i in first["sources"]}))

# ④ build()가 보존 파일을 입힘 + check 통과
tmp = Path(tempfile.mkdtemp()) / "note-summaries.json"
tmp.write_text(json.dumps({"N-marburg": got}, ensure_ascii=False), encoding="utf-8")
build_notes.SUMMARY_PATH = tmp
notes2 = build_notes.build()
m2 = next(n for n in notes2 if n["id"] == "N-marburg")
expect("④ 일반 칸에 summary가 붙음", all(s.get("summary") == got.get(s["name"]) for s in m2["sections"]))
expect("④ 다른 노트는 summary 없음", not any("summary" in s for n in notes2 if n["id"] != "N-marburg" for s in n["sections"]))
expect("④ check() 통과", build_notes.check(notes2) == [], build_notes.check(notes2)[:3])


def bad_with(mutate):
    n = copy.deepcopy(m2)
    mutate(n)
    return build_notes.check_summary(n)


other = next(s for s in m2["sections"] if s["name"] != sec0["name"] and s["lines"])["lines"][0]["sourceId"]
expect("⑤ 다른 칸 출처를 잡음", bad_with(lambda n: n["sections"][0]["summary"][0].update(sources=[other])))
expect("⑤ 틀린 연도를 잡음", bad_with(lambda n: n["sections"][0]["summary"][0].update(years=[1999])))
expect("⑤ 지어낸 숫자를 잡음", bad_with(lambda n: n["sections"][0]["summary"][0].update(text="12345유로였어요.")))
lesson = next(i for i, s in enumerate(m2["sections"]) if s["name"] == "배운점")
expect("⑤ 배운점 요약을 잡음", bad_with(lambda n: n["sections"][lesson].update(summary=[first])))

# AI가 다 실패하면 summary 없음(화면은 원문 목록)
askboo._call = lambda kind, content: {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
expect("AI 실패 → 빈 결과", build_notes.summarize(m) == {})

print(f"\n실패 {len(fails)}건" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
