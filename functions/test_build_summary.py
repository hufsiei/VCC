# test_build_summary.py — 작업 78 칸별 요약 문단(tools/build_notes.py --summary) 코드 단계 시험. AI는 가짜(askboo._call 대신).
# 보는 것: ① 배운점·인터뷰로만·빈 칸은 AI를 부르지 않음 ② 근거 번호 없는 문장·근거에 없는 숫자·답검사 불일치는 버림
#         ③ sources = 인용 문단 id, years = 그 연도들 ④ build()가 note-summaries.json을 입히고 check()가 통과
#         ⑤ check()가 다른 칸 출처·틀린 연도·지어낸 숫자·배운점 요약을 잡음
#         ⑥ [11/23] 칸 상한(근거 5건 이하 3·그 외 5문장)·앞 칸과 같은 뜻 문장 빼기·official 인용 → official: true, check()도 잡음
# 실행: cd functions && python test_build_summary.py   (data/note-summaries.json은 건드리지 않는다: 임시 파일로 바꿔 씀)
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
        {"text": DISTINCT.get(sec, f"{sec} 이야기를 들려줬어요."), "근거": [1, 2]},
        {"text": "번호가 없는 문장이에요.", "근거": []},
        {"text": "비용은 98765유로였다고 해요.", "근거": [1]},          # 근거에 없는 숫자 → 코드가 버림
        {"text": "답검사에 걸릴 문장이에요.", "근거": [1]},              # 답검사 불일치 → 버림
        {"text": "반말로 끝나는 문장이다.", "근거": [1]},
    ]})


# 칸마다 뜻이 다른 문장(같으면 ⑥ 중복 빼기에 걸린다)
DISTINCT = {"지원": "서류는 일찍 챙겼다는 선배도 있었어요.", "학점": "과목 고르기가 어려웠다고 해요.",
            "비용": "돈은 아껴 썼다고 해요.", "생활": "동네 산책이 즐거웠다고 해요.", "팁": "겁내지 말라는 선배도 있었어요."}
askboo._call = fake_call

notes = build_notes.build()
m = next(n for n in notes if n["id"] == "N-marburg")
got = build_notes.summarize(m)
asked = [re.search(r"「(.+?)」", c).group(1) for k, c in calls if k == "답쓰기"]
filled = [s["name"] for s in m["sections"] if s["lines"] and not s["interviewOnly"] and s["name"] not in build_notes.NO_SUMMARY]
expect("① 답쓰기는 원문 있는 일반 칸만 (배운점·인터뷰로만 제외)", asked == filled and "배운점" not in asked, asked)
expect("① 질문 없이 돈다(「칸 정리」 문구)", all("(질문 없음)" in c for k, c in calls if k == "답쓰기"))
caps = {s["name"]: build_notes.summary_cap(s) for s in m["sections"]}
expect("① AI에 칸 상한을 알림(근거 5건 이하 3, 그 외 5)",
       all(f"{caps[re.search(r'「(.+?)」', c).group(1)]}개 이내" in c for k, c in calls if k == "답쓰기")
       and set(caps[n] for n in filled) == {3, 5}, caps)
expect("② 칸마다 통과 문장 1개만 남음", all(len(v) == 1 for v in got.values()) and set(got) == set(filled), got)
sec0 = m["sections"][0]
first = got[sec0["name"]][0]
expect("② 남은 문장은 근거 번호 있던 해요체 문장", first["text"] == DISTINCT[sec0["name"]])
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
strip = lambda v: [{k: x[k] for k in ("text", "sources", "years")} for x in v or []]   # noqa: E731
expect("④ 일반 칸에 summary가 붙음(+ official)", all(strip(s.get("summary")) == got.get(s["name"], []) for s in m2["sections"])
       and all(isinstance(x["official"], bool) for s in m2["sections"] for x in s.get("summary", [])))
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

# ⑥ 칸 상한·중복 빼기·official (AI 없음, apply_summaries)
def sec_of(n, name):
    return next(s for s in n["sections"] if s["name"] == name)


small = next(s for s in m["sections"] if s["name"] in filled and build_notes.summary_cap(s) == 3)
big = next(s for s in m["sections"] if s["name"] in filled and build_notes.summary_cap(s) == 5)
off_sec = next((s for s in m["sections"] if s["name"] in filled and any(l["official"] for l in s["lines"])), None)
WORDS = ["사과", "기차", "노을", "바다", "연필", "우산", "모자", "시계", "구름", "편지", "호수", "등대", "들판", "창문",
         "거울", "단풍", "나비", "썰매", "풍선", "모래", "약국", "부채", "포도", "피리", "엽서", "자석"]
many = lambda s, k, o=0: [{"text": f"{WORDS[2 * (i + o)]}와 {WORDS[2 * (i + o) + 1]} 이야기예요.",   # noqa: E731 — 서로 겹치지 않는 문장
                      "sources": [s["lines"][0]["sourceId"]], "years": [2025]} for i in range(k)]
n3 = copy.deepcopy(m)
for s in n3["sections"]:
    s.pop("summary", None)
saved = {small["name"]: many(small, 6), big["name"]: many(big, 7, 6)}
build_notes.apply_summaries(n3["sections"], saved)
expect("⑥ 근거 5건 이하 칸은 3문장까지", len(sec_of(n3, small["name"])["summary"]) == 3, len(small["lines"]))
expect("⑥ 그 외 칸은 5문장까지", len(sec_of(n3, big["name"])["summary"]) == 5, len(big["lines"]))

first_name = next(s["name"] for s in m["sections"] if s["name"] in (small["name"], big["name"]))
later_name = big["name"] if first_name == small["name"] else small["name"]
dup = {"text": "마트 물가가 착해서 요리를 안 하던 사람도 하게 되고, 자취 비용이 적게 든다고 해요.", "sources": [sec_of(m, first_name)["lines"][0]["sourceId"]], "years": [2025]}
dup2 = {"text": "마트 물가가 착해서 요리를 안 하던 사람도 하게 되고 자취 비용이 적게 들었으며, 공병 보증금 제도 덕에 빈 병이 용돈이 됐어요.",
        "sources": [sec_of(m, later_name)["lines"][0]["sourceId"]], "years": [2025]}
other_txt = {"text": "기숙사 신청은 합격 직후에 했다는 선배도 있었어요.", "sources": dup2["sources"], "years": [2025]}
n4 = copy.deepcopy(m)
for s in n4["sections"]:
    s.pop("summary", None)
build_notes.apply_summaries(n4["sections"], {first_name: [dup], later_name: [dup2, other_txt]})
expect("⑥ 앞 칸과 같은 뜻 문장은 뒤 칸에서 빠짐", [x["text"] for x in sec_of(n4, later_name)["summary"]] == [other_txt["text"]]
       and sec_of(n4, first_name)["summary"][0]["text"] == dup["text"])
expect("⑥ 전하는 말투 꼬리만 같은 문장은 중복 아님",
       not build_notes.is_dup("성적 평가 방식이 과목마다 달라서 출석 비중부터 봤다는 선배도 있었어요.",
                              "한 달 비용은 선배마다 달랐는데, 월세 포함 110만 원 정도였다는 선배도 있었어요."))

if off_sec:
    oid = next(l["sourceId"] for l in off_sec["lines"] if l["official"])
    nid = next((l["sourceId"] for l in off_sec["lines"] if not l["official"]), None)
    n5 = copy.deepcopy(m)
    for s in n5["sections"]:
        s.pop("summary", None)
    items = [{"text": "가 문장이에요.", "sources": [oid], "years": [2025]}]
    if nid:
        items.append({"text": "나 다른 이야기예요.", "sources": [nid], "years": [2025]})
    build_notes.apply_summaries(n5["sections"], {off_sec["name"]: items})
    got5 = sec_of(n5, off_sec["name"])["summary"]
    expect("⑥ official 칸 문장을 인용하면 official: true, 아니면 false",
           got5[0]["official"] is True and all(x["official"] is False for x in got5[1:]))
else:
    expect("⑥ 마르부르크에 official 칸 문장이 있음(시험 전제)", False)

i0 = next(i for i, s in enumerate(m2["sections"]) if s.get("summary"))
expect("⑥ check()가 상한 초과를 잡음", any("상한" in b for b in bad_with(lambda n: n["sections"][i0].update(summary=n["sections"][i0]["summary"] * 6))))
expect("⑥ check()가 틀린 official을 잡음",
       any("official" in b for b in bad_with(lambda n: n["sections"][i0]["summary"][0].update(official=not n["sections"][i0]["summary"][0]["official"]))))
i1 = next(i for i, s in enumerate(m2["sections"]) if s.get("summary") and i > i0)
expect("⑥ check()가 칸 간 중복을 잡음",
       any("같은 뜻" in b for b in bad_with(lambda n: n["sections"][i1]["summary"].append(
           dict(n["sections"][i1]["summary"][0], text=n["sections"][i0]["summary"][0]["text"])))))

# AI가 다 실패하면 summary 없음(화면은 원문 목록)
askboo._call = lambda kind, content: {"ok": False, "text": "", "json": None, "model": "fake", "error": "x"}
expect("AI 실패 → 빈 결과", build_notes.summarize(m) == {})

print(f"\n실패 {len(fails)}건" if fails else "\n모두 통과")
sys.exit(1 if fails else 0)
