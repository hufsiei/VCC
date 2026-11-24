// 모든 화면이 데이터를 읽고 쓰는 공통 통로입니다. 원본: docs/spec-v1.md
// 화면은 이 파일의 함수만 부릅니다. 응답 모양은 명세 4장을 따릅니다.
// 사용: <script type="module"> import { askBoo } from "../../common/data.js"; </script>

export const USE_MOCK = true; // 기본값. true: common/mock-data.json, false: 서버 함수
const FN_BASE = "http://localhost:8787";

// [작업 29] 함수별 스위치 — USE_MOCK과 반대로 보낼 함수만 적는다.
// 전환 순서(작업 29): login·getMe → askBoo → 들려주기 → 노트 → 닮은선배·쪽지 → 콘솔. 실패한 함수만 MOCK_FNS로 되돌린다.
const SERVER_FNS = []; // USE_MOCK = true여도 서버로 보낼 함수. 예: ["recommendSeniors", "sendMessage", "getMessages"]
const MOCK_FNS = []; //   USE_MOCK = false여도 mock으로 되돌릴 함수
// 서버 함수는 로그인 토큰(X-Token)이 있어야 하므로, 서버로 가는 함수가 하나라도 있으면 로그인도 서버로 간다.
const AUTH_FNS = ["login", "logout", "getMe"];

// 로컬 확인용(미리 PC, localhost에서만): 주소 끝에 ?server=all 또는 ?server=sendMessage,getMessages
// → 그 탭에서만 기억(sessionStorage, 두 창 시연). ?server= (빈 값)으로 해제. 공개 주소(GitHub Pages)에서는 무시한다.
function localServerFns() {
  try {
    if (!["localhost", "127.0.0.1"].includes(location.hostname)) return [];
    const q = new URLSearchParams(location.search);
    if (q.has("server")) {
      const v = q.get("server").trim();
      if (v) sessionStorage.setItem("vccServer", v);
      else sessionStorage.removeItem("vccServer");
    }
    const saved = sessionStorage.getItem("vccServer") || "";
    return saved ? saved.split(",").map((s) => s.trim()).filter(Boolean) : [];
  } catch {
    return [];
  }
}

// 이 함수를 mock으로 부를지
export function isMock(name) {
  const server = [...SERVER_FNS, ...localServerFns()];
  if (server.includes("all")) return false;
  if (!USE_MOCK) return MOCK_FNS.includes(name) && !AUTH_FNS.includes(name);
  if (server.includes(name)) return false;
  return !(server.length && AUTH_FNS.includes(name));
}

let mockPromise = null;
function loadMock() {
  if (!mockPromise) {
    // interviewNext mock이 서버처럼 프로그램 분야 → 노트 틀을 고르도록 data/의 두 파일도 함께 읽는다
    const get = (path) => fetch(new URL(path, import.meta.url)).then((r) => r.json());
    mockPromise = Promise.all([get("mock-data.json"), get("../data/programs.json"), get("../data/frames.json")])
      .then(([m, programs, frames]) => ({ ...m, _programs: programs, _frames: frames }));
  }
  return mockPromise;
}

// interviewNext mock (functions/interview.py의 순서를 흉내 낸다. AI 꼬리 질문은 없음)
// - interviewNext.byProgram에 있는 프로그램(마르부르크 시연 대본)은 답한 수대로 steps를 그대로 낸다.
// - 그 밖의 프로그램은 programs.json 분야 → frames.json 칸 순서로 아직 답하지 않은 칸을 묻고, 「배운점」은 마지막.
//   후배 질문은 mock 질문함에 없으므로 묻지 않는다(pendingQuestions 0).
// - [v2 작업 89] 「후배 질문」 칸은 없다. 마르부르크 대본 steps[0]은 junior: true·section 「생활」(질문의 칸)이고,
//   total은 「후배 질문」을 뺀 칸 수다. frames.json에 아직 남아 있어도 걸러 낸다.
const KIND_BY_FIELD = { 국제교류: "교환", 현장실습: "인턴", 비교과: "비교과" };
const QUESTION_SECTION = "후배 질문"; // 없어진 칸(frames.json에서 원우가 지우기 전까지 걸러 내는 용도)
const LAST_SECTION = "배운점";

function mockInterview(m, p) {
  const iv = m.interviewNext;
  const answers = p.answers || [];
  const script = (iv.byProgram || {})[p.program];
  if (script) return answers.length < script.steps.length ? script.steps[answers.length] : script.done;

  const info = (m._programs || []).find((x) => x["프로그램명"] === p.program) || {};
  const frame = (m._frames || {})[KIND_BY_FIELD[info["분야"]] || "교환"] || { 칸: [] };
  const sections = frame["칸"].filter((s) => s !== QUESTION_SECTION);
  const answered = new Set(answers.filter((a) => !a.skipped && a.answer).map((a) => a.section));
  const filled = sections.filter((s) => answered.has(s)).length;
  const progress = { filled, mine: filled, total: sections.length };
  const order = [...sections.filter((s) => s !== LAST_SECTION), ...sections.filter((s) => s === LAST_SECTION)];
  const next = order.find((s) => !answered.has(s));
  if (!next) return { done: true, progress };
  const short = (info["별칭"] || [])[0] || p.program;
  const template = iv.questions[next] || iv.questions["*"];
  return { done: false, section: next, question: template.replaceAll("{p}", short).replaceAll("{s}", next), progress, pendingQuestions: 0 };
}

// summarizeInterview mock: 고정 요약(교환 칸: 지원·학점·생활)과 대화한 칸이 하나도 겹치지 않으면(인턴·비교과 등)
// 그 칸이 모두 「–」로 보이므로, 대화한 답을 칸별로 그대로 옮겨 돌려준다(AI 요약 없음). 겹치면 {}(고정 요약 그대로).
function mockSummaryFromTranscript(m, transcript) {
  const answers = (transcript || []).filter((a) => a && a.section && typeof a.answer === "string" && a.answer.trim());
  const fixed = new Set(m.summarizeInterview.myNote.sections.map((s) => s.name));
  if (!answers.length || answers.some((a) => fixed.has(a.section))) return {};
  const mine = [];
  const pub = [];
  let k = 0;
  for (const a of answers) {
    let i = mine.findIndex((s) => s.name === a.section);
    if (i < 0) {
      i = mine.push({ name: a.section, lines: [] }) - 1;
      pub.push({ name: a.section, lines: [] });
    }
    k += 1;
    mine[i].lines.push({ text: a.answer.trim() });
    pub[i].lines.push({ lineId: `L-D1-${k}`, text: a.answer.trim(), match: true });
  }
  return { myNote: { sections: mine }, publicDraft: { sections: pub } };
}

// summarizeInterview append mock [v2 작업 90]: getMyNote(M-0001) 문장 뒤에 이번 요약 문장을 붙인 모양.
// 새 공개 문장은 새 draftId(D-0002)의 lineId(L-D2-k)와 new: true. 기억하지 않는다(다시 불러도 같은 모양).
function mockAppend(m, out) {
  const old = m.getMyNote;
  const draftId = "D-0002";
  let k = 0;
  const merge = (oldSecs, newSecs, mapNew) => {
    const secs = oldSecs.map((s) => ({ name: s.name, lines: [...s.lines] }));
    for (const s of newSecs) {
      let sec = secs.find((x) => x.name === s.name);
      if (!sec) secs.push((sec = { name: s.name, lines: [] }));
      sec.lines.push(...s.lines.map((ln) => ({ ...mapNew(ln), new: true })));
    }
    return { sections: secs };
  };
  // getMyNote 칸 문장은 화면용 모양(publicText·shared 등)이라 내 경험노트 문장 모양으로 줄인다
  const oldMine = old.sections.map((s) => ({ name: s.name, lines: s.lines.map(({ text, edited, answersQuestionId, asked }) =>
    ({ text, ...(edited ? { edited } : {}), ...(answersQuestionId ? { answersQuestionId, asked } : {}) })) }));
  return {
    ...out, draftId, myNoteId: old.id,
    myNote: merge(oldMine, out.myNote.sections, (ln) => ln),
    publicDraft: merge(old.publicDraft.sections, out.publicDraft.sections, (ln) => ({ ...ln, lineId: `L-D2-${++k}` })),
  };
}

// ── 선배 추천 열림 + 「궁금한 것 정리하기」 mock (functions/demand.py를 흉내 낸다, 11/22) ──
// mock 기본값은 「열림」(지금 만드는 화면이 갑자기 잠기지 않게). 잠김 화면을 보려면 주소 끝에 ?locked=1.
// ?locked=1이어도 mock saveDemand·saveConsent를 부르면 이 탭에서는 열린다(sessionStorage "mockUnlocked").
const NEED = 3;
const DEMAND = {
  fields: ["국제교류", "현장실습", "비교과"], unsure: "잘 모르겠어요", notYet: "아직 정하지 않았어요",
  fieldLabel: { 국제교류: "교환학생", 현장실습: "현장실습", 비교과: "비교과" }, detailLabel: { "1회성": "1회성 특강" },
  explore: [
    { label: "외국에서 살아 보기", field: "국제교류" }, { label: "일 경험 해 보기", field: "현장실습" },
    { label: "진로 찾기", field: "비교과", detail: "진로·취업 교육과정" }, { label: "공부 방법 찾기", field: "비교과", detail: "학습공동체·튜터링·멘토링" },
  ],
  when: ["이번 학기", "다음 학기", "1년 뒤", "아직 몰라요"],
  junk: new Set(["몰라요", "모르겠어요", "잘 모르겠어요", "없어요", "없음", "아무거나", "글쎄요", "그냥요", "딱히요", "ㅇㅇ", "네", "아니요"]),
  q: {
    explore: "괜찮아요. 요즘 가장 고민인 게 뭐예요?", field: "어떤 경험이 궁금해요?",
    detail: { 국제교류: "어느 나라가 궁금해요?", 현장실습: "어떤 곳에서 일해 보고 싶어요?", 비교과: "어떤 종류의 프로그램이 궁금해요?" },
    program: "궁금한 프로그램을 골라 주세요. 아직 정하지 않았어도 괜찮아요.", section: "그중에서 무엇이 가장 궁금해요?",
    when: "언제쯤 해 보려고 해요?", situation: "지금 어느 정도 준비됐어요? 선배가 답할 때 참고할 수 있게 지금 상황을 적어 주세요.",
    question: "{s}에 대해 무엇이 궁금해요? 선배에게 묻고 싶은 것을 한 문장으로 적어 주세요.",
    hope: "이 경험이 나에게 무엇을 남겨 줬으면 좋겠어요?", more: "더 궁금한 게 있으면 적어 주세요. 없으면 넘어가도 돼요.",
  },
  examples: { situation: ["2학년이고 어학 점수를 준비하고 있어요", "아직 아무것도 준비하지 못했어요"], hope: ["외국어로 일상을 꾸려 본 자신감", "진로를 정할 실마리"] },
};
const mockReady = () => sessionStorage.getItem("mockUnlocked") === "1" || !new URLSearchParams(location.search).has("locked");
const mockStatus = () => {
  const ready = mockReady();
  return { ready, by: ready ? "ask" : null, need: NEED, talk: { answered: 0, shared: 0 }, ask: ready };
};
const LOCKED = () => ({ locked: true, message: "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요", recommend: mockStatus() });

function answerProblem(text) {
  const t = String(text || "").trim();
  if (DEMAND.junk.has(t.replace(/[.!?~ ]+$/, ""))) return "선배가 답할 수 있게 구체적으로 적어 주세요.";
  if (t.length < 10) return "조금만 더 자세히 적어 주세요(10자 이상).";
  if (new Set(t.replace(/\s/g, "")).size <= 2) return "선배가 답할 수 있게 구체적으로 적어 주세요.";
  if (/\d{8,}|\d{2,3}-\d{3,4}-\d{4}/.test(t)) return "연락처는 넣을 수 없어요.";
  return null;
}
const countInterview = (tr) =>
  new Set((tr || []).filter((a) => a && !a.skipped && !answerProblem(a.answer)).map((a) => `${a.section}|${String(a.question || "").replace(/\s+/g, "")}`)).size;

function mockDemand(m, raw) {
  const s = { ...(raw || {}) };
  const programs = m._programs || [];
  if (s.fromQuestionId && !s._prefilled) { // mock 질문함의 보류 질문 → 마르부르크·생활로 미리 채움
    const info = programs.find((x) => x["프로그램명"] === "마르부르크필립스대학교") || {};
    Object.assign(s, { field: info["분야"], detail: info["세부"], program: info["프로그램명"], section: "생활",
      question: "마르부르크에서 학기 중 현지 인턴을 병행할 수 있어요?", _prefilled: true }, raw);
  }
  if (s.field === DEMAND.unsure && s.explore) {
    const e = DEMAND.explore.find((x) => x.label === s.explore);
    if (e) Object.assign(s, { field: e.field, explored: true }, e.detail ? { detail: e.detail } : {});
  }
  if (s.detail === DEMAND.notYet) s.detail = null;
  if (s.program === DEMAND.notYet) s.program = null;
  s.more = (s.more || []).filter((x) => typeof x === "string" && x.trim()).slice(0, 2);
  if (s.moreDone) s.more = s.more.filter((x) => !answerProblem(x));
  const valid = ["situation", "question", "hope"].filter((k) => s[k] && !answerProblem(s[k])).length + s.more.filter((x) => !answerProblem(x)).length;
  const step = (name, extra) => ({ done: false, step: name, state: s, progress: { answered: valid, need: NEED }, ...extra });

  if (s.field === DEMAND.unsure && !s.explored) return step("explore", { question: DEMAND.q.explore, options: DEMAND.explore.map((e) => e.label) });
  if (!DEMAND.fields.includes(s.field)) return step("field", { question: DEMAND.q.field, options: [...DEMAND.fields, DEMAND.unsure] });
  if (!("detail" in s)) {
    const counts = {};
    for (const x of programs) if (x["분야"] === s.field && x["세부"]) counts[x["세부"]] = (counts[x["세부"]] || 0) + 1;
    const details = Object.keys(counts).sort((a, b) => counts[b] - counts[a] || a.localeCompare(b));
    return step("detail", { question: DEMAND.q.detail[s.field],
      options: [...details.map((d) => ({ value: d, label: DEMAND.detailLabel[d] || d })), { value: null, label: DEMAND.notYet }] });
  }
  if (!("program" in s)) {
    const list = programs.filter((x) => x["분야"] === s.field && (s.detail == null || x["세부"] === s.detail)).map((x) => x["프로그램명"]).sort();
    return step("program", { question: DEMAND.q.program, options: [...list, DEMAND.notYet] });
  }
  const info = programs.find((x) => x["프로그램명"] === s.program) || { 분야: s.field };
  const frame = (m._frames || {})[KIND_BY_FIELD[info["분야"]] || "교환"] || { 칸: [] };
  const sections = frame["칸"].filter((x) => x !== QUESTION_SECTION);
  if (!sections.includes(s.section)) return step("section", { question: DEMAND.q.section, options: sections });
  if (!DEMAND.when.includes(s.when)) return step("when", { question: DEMAND.q.when, options: DEMAND.when });
  for (const k of ["situation", "question", "hope"]) {
    const bad = s[k] ? answerProblem(s[k]) : null;
    if (!s[k] || bad) return step(k, { question: DEMAND.q[k].replace("{s}", s.section), examples: DEMAND.examples[k] || [], ...(bad ? { retry: bad } : {}) });
  }
  const badMore = s.more.find((x) => answerProblem(x));
  if (!s.moreDone && (s.more.length < 2 || badMore)) return step("more", { question: DEMAND.q.more, canSkip: true, ...(badMore ? { retry: answerProblem(badMore) } : {}) });
  const label = DEMAND.fieldLabel[s.field] + (s.detail ? `·${DEMAND.detailLabel[s.detail] || s.detail}` : "");
  return { done: true, state: s, progress: { answered: valid, need: NEED },
    summary: { interest: label, program: s.program, section: s.section, when: s.when, situation: s.situation, questions: [s.question, ...s.more], hope: s.hope } };
}

// 입력에 따라 다른 mock을 고르는 곳은 여기 한 곳입니다 (명세 3장).
function pickMock(m, name, p) {
  switch (name) {
    case "login":
      // mock은 비번을 대조하지 않는다(공개 코드에 비번을 두지 않음). 시연 아이디 모양이고 비번이 비어 있지 않으면 성공
      if (!p.pw) return m.login.fail;
      if (p.id === "staff01") return m.login.staff; // 총괄 관리자
      if (p.id === "staff02") return m.login.staffDept; // 부서 담당자
      return /^H\d{4}$/.test(String(p.id || "")) ? m.login.student : m.login.fail;
    case "askBoo":
      if (p.force === "hold") return m.askBoo.holdSaved; // [v2] chat 칩 「질문함에 담기」 — 질문 내용과 상관없이 hold, 문구는 서버 HOLD_SAVED와 같게(작업 87)
      // [v2] 대화·메타(질문이 아님) → chat(고정 문구 + 칩). 질문함에 저장하지 않는다
      if (/아까|말고|그\s*말이\s*아니|그게\s*아니|데이터\s*(가|는)?\s*없|고마워/.test(p.question || "")) return m.askBoo.chat;
      if (/평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수/.test(p.question || "")) return m.askBoo.official; // 규정 질문 (명세 4장)
      // [v2] 탐색(어디 있어요·추천·어떤 게 있어요)도 주제어가 없으면 해봤노트 카드
      if (/어디\s*(에)?\s*있|추천해|어떤\s*(게|곳이|데가)\s*있/.test(p.question || "") && !/기숙사|비용|수업|서류|학점|팁|조언|어땠/.test(p.question || "")) return m.askBoo.notes;
      // [11/23] 사람을 찾는 질문(주제어 없음) → 해봤노트 카드(status "notes")
      if (/(다녀온|갔다\s*온|가\s*본|경험한)\s*(선배|사람|분)|선배\s*(있|계|없|\?|$)/.test(p.question || "") && !/기숙사|비용|수업|서류|학점|팁|조언|어땠/.test(p.question || "")) return m.askBoo.notes;
      return /교환|파견|독일|마르부르크/.test(p.question || "") ? m.askBoo.exchange : m.askBoo.hold;
    case "interviewNext":
      return mockInterview(m, p); // 고른 경험(program)에 맞는 노트 틀로 묻는다
    case "getNote":
      return m.getNote[p.id] || m.getNote["N-marburg"];
    case "scrapNote":
      return { ok: true, noteId: p.noteId, scrapped: p.scrap !== false }; // mock은 기억하지 않는다(목록·노트의 scrapped는 고정값)
    case "getMyNote":
      return { ...m.getMyNote, id: p.id || m.getMyNote.id }; // mock 경험노트는 하나뿐(M-0001)
    case "saveInterviewDraft": { // [v2 작업 79] 이 탭에서만 기억(sessionStorage mockDraft:<program>)
      if (!p.program) return { error: "들려줄 경험을 먼저 골라 주세요" };
      const key = `mockDraft:${p.program}`;
      if (!(p.answers || []).length) { sessionStorage.removeItem(key); return { ok: true, savedAt: null, expiresAt: null }; }
      const at = new Date();
      sessionStorage.setItem(key, JSON.stringify({ answers: p.answers, savedAt: at.toISOString() }));
      return { ok: true, savedAt: at.toISOString(), expiresAt: new Date(at.getTime() + 7 * 864e5).toISOString() };
    }
    case "getInterviewDraft": {
      try { return JSON.parse(sessionStorage.getItem(`mockDraft:${p.program}`)) || { answers: [] }; } catch { return { answers: [] }; }
    }
    case "deleteQuestion":
    case "updateQuestion": { // [v2 작업 91] mock은 기억하지 않는다. answered·official 질문이면 서버와 같은 error
      const verb = name === "deleteQuestion" ? "지울" : "고칠";
      const q = (m.getInbox.questions || []).find((x) => x.questionId === p.questionId);
      if (q && q.status === "answered") return { error: `선배가 답한 질문은 ${verb} 수 없어요` };
      if (q && q.status === "official") return { error: `공식 안내 질문은 ${verb} 수 없어요` };
      if (name === "deleteQuestion") return { ok: true, questionId: p.questionId, status: "deleted" };
      const text = String(p.text || "").split(/\s+/).filter(Boolean).join(" ");
      if (!text) return { error: "질문을 적어 주세요" };
      if (text.length > 300) return { error: "질문은 300자까지 쓸 수 있어요" };
      if (/\d{2,3}-?\d{3,4}-?\d{4}|@|https?:\/\/|www\./i.test(text)) return { error: "질문에 연락처·메일·링크를 넣을 수 없어요", reason: "연락처" };
      return { ok: true, questionId: p.questionId, text, editedAt: new Date().toISOString() };
    }
    case "updateMyNote": { // [11/23] mock은 기억하지 않는다 — 고친 결과 모양만 서버와 같게
      const note = structuredClone({ ...m.getMyNote, id: p.id || m.getMyNote.id });
      for (const ch of p.changed || []) {
        const line = (note.sections.find((s) => s.name === ch.section) || { lines: [] }).lines[ch.index];
        const text = String(ch.text || "").trim();
        if (!line) return { error: "고칠 문장을 찾지 못했어요" };
        if (!text) return { error: "문장을 적어 주세요", section: ch.section, index: ch.index };
        if (text !== line.text) Object.assign(line, { text, edited: true });
      }
      note.editedLines = note.sections.reduce((n, s) => n + s.lines.filter((l) => l.edited).length, 0);
      return { ok: true, ...note };
    }
    case "saveQuestion":
      return m.saveQuestion; // mock은 기억하지 않는다(내 보관함 질문함 목록은 고정값)
    case "checkMessage":
      return /\d{8,}/.test(p.text || "") ? m.checkMessage.blocked : m.checkMessage.ok;
    // ── 선배 추천 열림(11/22) ──
    case "getMe":
      return { ...m.getMe, recommend: mockStatus(), recommendable: sessionStorage.getItem("mockRecommendable") !== "0" };
    case "setRecommendable": // [11/23] 이 탭에서만 기억(mock)
      if (typeof p.on !== "boolean") return { error: "켜기·끄기를 골라 주세요" };
      sessionStorage.setItem("mockRecommendable", p.on ? "1" : "0");
      return { ok: true, recommendable: p.on };
    case "recommendSeniors":
    case "previewNickname":
      return mockReady() ? m[name] : LOCKED();
    case "sendMessage":
      return mockReady() ? m.sendMessage : { ok: false, reason: "잠김", message: LOCKED().message, recommend: mockStatus() };
    case "summarizeInterview": {
      const out = { ...m.summarizeInterview, ...mockSummaryFromTranscript(m, p.transcript), program: p.program || m.summarizeInterview.program, answered: countInterview(p.transcript), need: NEED };
      sessionStorage.removeItem(`mockDraft:${p.program}`); // [작업 79] 요약하면 미완성 초안을 지운다(서버와 같게)
      return p.append === true ? mockAppend(m, out) : out;
    }
    case "saveConsent": {
      const before = mockReady();
      sessionStorage.setItem("mockUnlocked", "1"); // mock은 답변 수를 기억하지 않으므로 공유하면 열린다고 본다
      return { ...m.saveConsent, recommend: mockStatus(), unlocked: !before };
    }
    case "demandNext":
      return mockDemand(m, p.state);
    case "saveDemand": {
      if (!p.consent) return { error: "선배와 부서에 전하는 데 동의해 주세요" };
      const next = mockDemand(m, p.state);
      if (!next.done) return { ok: false, message: "아직 정리가 끝나지 않았어요", next };
      const before = mockReady();
      sessionStorage.setItem("mockUnlocked", "1");
      return { ok: true, demandId: "R-0001", questionIds: [p.state && p.state.fromQuestionId ? p.state.fromQuestionId : "Q-0003"], recommend: mockStatus(), unlocked: !before };
    }
    case "getAdminOverview":
    case "getAdminSuggestions":
    case "getReportSettings":
      return m[name][!p.dept || p.dept === "ALL" ? "ALL" : "D01"]; // mock은 전체·국제교류팀 두 벌(PRD 7장)
    case "respondRequest":
      return p.cancel ? m.cancelRequest : m.respondRequest; // 요청 취소(cancelRequest)도 같은 서버 함수
    case "reportThread": // [11/23] mock은 기억하지 않는다(쪽지 목록은 고정값) — 응답 모양만 서버와 같게
      if (!p.reason && !p.block) return { error: "신고 사유를 골라 주세요" };
      return { ok: true, reported: !!p.reason, blocked: !!p.block, status: p.block ? "blocked" : "accepted" };
    default:
      return m[name];
  }
}

async function call(name, payload = {}) {
  try {
    if (isMock(name)) {
      const m = await loadMock();
      return structuredClone(pickMock(m, name, payload));
    }
    const headers = { "Content-Type": "application/json" };
    const me = currentUser();
    if (me && me.token) headers["X-Token"] = me.token; // 서버가 토큰으로 누가 불렀는지 안다 (spec 2-1)
    const res = await fetch(`${FN_BASE}/${name}`, {
      method: "POST",
      keepalive: true, // 로그아웃 직후 화면이 바뀌어도 요청이 끊기지 않게
      headers,
      body: JSON.stringify(payload),
    });
    return await res.json();
  } catch (e) {
    return { error: "데이터를 불러오지 못했어요: " + e.message };
  }
}

// 로그인한 사용자. 탭마다 따로(sessionStorage) — 두 창 시연용.
export function currentUser() {
  try {
    return JSON.parse(sessionStorage.getItem("me") || "null");
  } catch {
    return null;
  }
}

// 학번은 대소문자를 가리지 않는다: h0143 → H0143, STAFF01 → staff01 (mock·서버 공통)
export function normalizeId(id) {
  const s = String(id || "").trim();
  if (/^h\d{4}$/i.test(s)) return s.toUpperCase();
  if (/^staff\d+$/i.test(s)) return s.toLowerCase();
  return s;
}

export const login = async (id, pw) => {
  const res = await call("login", { id: normalizeId(id), pw });
  if (res && res.ok && res.user) sessionStorage.setItem("me", JSON.stringify(res.user));
  return res;
};
export const logout = () => {
  // 서버에서 토큰 폐기. call()이 헤더를 먼저 만든 뒤 지우므로 기다리지 않아도 토큰이 실려 간다(화면은 바로 이동).
  const done = isMock("logout") ? Promise.resolve() : call("logout");
  sessionStorage.removeItem("me");
  return done;
};
export const getMe = () => call("getMe");
// [v2] history = 최근 4턴 [{question, status, program?}]
// opts.force = "hold": chat 칩 「질문함에 담기」(save) — 답을 찾지 않고 바로 질문함에 hold로 (명세 4장)
export const askBoo = (question, history = [], { force } = {}) =>
  call("askBoo", force ? { question, history, force } : { question, history });
export const interviewNext = (program, answers) => call("interviewNext", { program, answers });
// [v2 작업 90] append = true: 이어 쓰기 — 기존 내 경험노트·공개 초안 뒤에 새 문장을 덧붙인다(새 문장 new: true, 응답은 합친 전체).
//   「더 들려주기」(../talk/?mode=tell&program=…)와 질문이 끝난 뒤 「이어서 쓰기」는 append로 부른다
export const summarizeInterview = (program, transcript, append = false) =>
  call("summarizeInterview", append ? { program, transcript, append: true } : { program, transcript });
export const saveConsent = (draftId, edits) => call("saveConsent", { draftId, edits, consent: true });
export const listNotes = (filter) => call("listNotes", { filter });
export const getNote = (id) => call("getNote", { id });
// 스크랩 켜기(scrap=true, 기본)·끄기(false) → { ok, noteId, scrapped }. 카드·노트의 scrapped, 내 보관함 scraps에 반영(spec 4장)
export const scrapNote = (noteId, scrap = true) => call("scrapNote", { noteId, scrap });
// 「질문함에 담기」: 노트의 한 칸을 질문함에 hold로 → { ok, questionId, already, message }. 다음 선배 인터뷰가 먼저 묻는다(spec 4장)
export const saveQuestion = (noteId, section) => call("saveQuestion", { noteId, section });
export const reportStatement = (lineId, reason) => call("reportStatement", { lineId, reason });
// more=true면 3명씩 더해 최대 9명. 응답의 hasMore가 false면 「비슷한 선배를 모두 보여드렸어요」(spec 4장)
export const recommendSeniors = (noteId, more) => call("recommendSeniors", more ? { noteId, more: true } : { noteId });
export const checkMessage = (text) => call("checkMessage", { text });
export const previewNickname = (to) => call("previewNickname", { to });
export const sendMessage = (to, text) => call("sendMessage", { to, text });
// [11/23] 그냥 부르면 목록만(읽음으로 바꾸지 않음). 대화창을 열 때는 getMessages(threadId) → 그 대화만 읽음
export const getMessages = (read) => call("getMessages", read ? { read } : {});
export const respondRequest = (threadId, accept) => call("respondRequest", { threadId, accept });
// 보낸 사람이 수락 대기(waiting) 요청을 거둔다 → status "cancelled". 서버 함수는 respondRequest 하나(spec 4장)
// [11/24] 응답·getMessages(취소한 대화)·recommendSeniors(그 선배 카드)에 retryAt = 다시 보낼 수 있는 시각(ISO KST, 취소 + 7일)
export const cancelRequest = (threadId) => call("respondRequest", { threadId, cancel: true });
// [11/23] 쪽지 대화 ⋮ 메뉴 신고·차단. reason만 → 신고, block: true → 차단(양쪽 다 더 못 보냄, 상대에게 알림 없음). 둘 다 가능
export const reportThread = (threadId, reason, block = false) => call("reportThread", { threadId, reason, block });
export const getInbox = () => call("getInbox");
// [v2 작업 91] 내 보관함 질문 상세의 「질문 삭제」·「질문 고치기」. 본인 hold 질문만(answered·official·남의 것은 { error })
//   deleteQuestion → { ok, questionId, status: "deleted" } (목록에서 빠짐) · updateQuestion → { ok, questionId, text, editedAt } | { error, reason? }
export const deleteQuestion = (questionId) => call("deleteQuestion", { questionId });
export const updateQuestion = (questionId, text) => call("updateQuestion", { questionId, text });
// [v2 작업 79] 들려주기 미완성 초안(다른 기기·다음 날에도 이어 쓰기). answers = interviewNext에 보내는 것과 같은 모양
//   답할 때마다 saveInterviewDraft → { ok, savedAt, expiresAt }(빈 answers면 지움) · 들어올 때 getInterviewDraft → { answers, savedAt } | { answers: [] }
//   본인만, 7일 지나면 없음, summarizeInterview가 끝나면 서버가 지운다
export const saveInterviewDraft = (program, answers) => call("saveInterviewDraft", { program, answers });
export const getInterviewDraft = (program) => call("getInterviewDraft", { program });
// [11/23] 닮은선배 추천받기 켜기·끄기(기본 켬, getMe().recommendable). 끄면 추천 후보와 새 쪽지 요청에서 빠지고, 수락한 대화는 이어진다
export const setRecommendable = (on) => call("setRecommendable", { on });
// 내 경험노트 상세(본인만) → { id, program, type, noteId, share, filled, total, sharedLines, draftId, sections[{name, lines[{text, publicText, lineId, shared}]}], publicDraft } (spec 4장)
export const getMyNote = (id) => call("getMyNote", { id });
// [11/23] 내 경험노트 문장 고치기. changed = [{ section, index, text }] (index = getMyNote 그 칸 lines 순서)
//   → { ok: true, ...getMyNote와 같은 모양(고친 문장은 edited: true) } | { error }. 해봤노트 공개 문장은 바뀌지 않는다
export const updateMyNote = (id, changed) => call("updateMyNote", { id, changed });
// ── 선배 추천 열림(11/22, spec 4장) ──
// 열림 여부는 getMe().recommend = { ready, by: "talk"|"ask"|null, need: 3, talk: {answered, shared}, ask }.
// 잠겼을 때 recommendSeniors·previewNickname은 { locked: true, message, recommend }, sendMessage(새 요청)는 { ok: false, reason: "잠김", message }.
// 「궁금한 것 정리하기」(수요 인터뷰): state를 들고 다니며 demandNext를 부르고, done이면 동의 후 saveDemand.
//   demandNext(state) → { done:false, step, question, options?, examples?, retry?, canSkip?, progress:{answered, need}, state } | { done:true, summary, state, progress }
//   물어보기에서 보류된 질문으로 시작: demandNext({ fromQuestionId: questionId })
export const demandNext = (state = {}) => call("demandNext", { state });
export const saveDemand = (state) => call("saveDemand", { state, consent: true }); // → { ok, demandId, questionIds, recommend, unlocked }
export const getDeptReport = (dept) => call("getDeptReport", { dept });

// ── 관리자 콘솔(직원 계정 전용, PRD 7장·작업 66) ──
// dept: "ALL" | 부서코드("D01"…). 부서 담당자(staff02)는 서버가 자기 부서로 고정한다.
// period: { type: "semester" | "month", value: "2026-2" | "2026-11" } — 비우면 지금 학기
export const getDepartments = () => call("getDepartments");
export const getAdminOverview = (dept, period) => call("getAdminOverview", { dept, period });
export const getAdminSuggestions = (dept, period) => call("getAdminSuggestions", { dept, period });
export const setSuggestionStatus = (id, status) => call("setSuggestionStatus", { id, status }); // 새로 옴|검토 중|반영됨|보류
export const getReportSettings = (dept) => call("getReportSettings", { dept });
export const saveReportSettings = (dept, settings) => call("saveReportSettings", { dept, settings });
export const issueReport = (dept, period) => call("issueReport", { dept, period });
export const listIssuedReports = (dept) => call("listIssuedReports", { dept });
// 이력 「열기」. html은 iframe srcdoc(sandbox)로만 보여 준다 — innerHTML 금지
export const getIssuedReport = (reportId) => call("getIssuedReport", { reportId });
