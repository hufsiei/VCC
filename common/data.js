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
const KIND_BY_FIELD = { 국제교류: "교환", 현장실습: "인턴", 비교과: "비교과" };
const QUESTION_SECTION = "후배 질문";
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
  const progress = { filled: sections.filter((s) => answered.has(s)).length, total: frame["칸"].length };
  const order = [...sections.filter((s) => s !== LAST_SECTION), ...sections.filter((s) => s === LAST_SECTION)];
  const next = order.find((s) => !answered.has(s));
  if (!next) return { done: true, progress };
  const short = (info["별칭"] || [])[0] || p.program;
  const template = iv.questions[next] || iv.questions["*"];
  return { done: false, section: next, question: template.replaceAll("{p}", short).replaceAll("{s}", next), progress, pendingQuestions: 0 };
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
      if (/평점|장학금|몇\s*학점|선발\s*(인원|기준)|휴학|등록금|초과학기|인정\s*신청|인정받을 수/.test(p.question || "")) return m.askBoo.official; // 규정 질문 (명세 4장)
      return /교환|파견|독일|마르부르크/.test(p.question || "") ? m.askBoo.exchange : m.askBoo.hold;
    case "interviewNext":
      return mockInterview(m, p); // 고른 경험(program)에 맞는 노트 틀로 묻는다
    case "getNote":
      return m.getNote[p.id] || m.getNote["N-marburg"];
    case "scrapNote":
      return { ok: true, noteId: p.noteId, scrapped: p.scrap !== false }; // mock은 기억하지 않는다(목록·노트의 scrapped는 고정값)
    case "checkMessage":
      return /\d{8,}/.test(p.text || "") ? m.checkMessage.blocked : m.checkMessage.ok;
    case "getAdminOverview":
    case "getAdminSuggestions":
    case "getReportSettings":
      return m[name][!p.dept || p.dept === "ALL" ? "ALL" : "D01"]; // mock은 전체·국제교류팀 두 벌(PRD 7장)
    case "respondRequest":
      return p.cancel ? m.cancelRequest : m.respondRequest; // 요청 취소(cancelRequest)도 같은 서버 함수
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
export const askBoo = (question) => call("askBoo", { question });
export const interviewNext = (program, answers) => call("interviewNext", { program, answers });
export const summarizeInterview = (program, transcript) => call("summarizeInterview", { program, transcript });
export const saveConsent = (draftId, edits) => call("saveConsent", { draftId, edits, consent: true });
export const listNotes = (filter) => call("listNotes", { filter });
export const getNote = (id) => call("getNote", { id });
// 스크랩 켜기(scrap=true, 기본)·끄기(false) → { ok, noteId, scrapped }. 카드·노트의 scrapped, 내 보관함 scraps에 반영(spec 4장)
export const scrapNote = (noteId, scrap = true) => call("scrapNote", { noteId, scrap });
export const reportStatement = (lineId, reason) => call("reportStatement", { lineId, reason });
// more=true면 3명씩 더해 최대 9명. 응답의 hasMore가 false면 「비슷한 선배를 모두 보여드렸어요」(spec 4장)
export const recommendSeniors = (noteId, more) => call("recommendSeniors", more ? { noteId, more: true } : { noteId });
export const checkMessage = (text) => call("checkMessage", { text });
export const previewNickname = (to) => call("previewNickname", { to });
export const sendMessage = (to, text) => call("sendMessage", { to, text });
export const getMessages = () => call("getMessages");
export const respondRequest = (threadId, accept) => call("respondRequest", { threadId, accept });
// 보낸 사람이 수락 대기(waiting) 요청을 거둔다 → status "cancelled". 서버 함수는 respondRequest 하나(spec 4장)
export const cancelRequest = (threadId) => call("respondRequest", { threadId, cancel: true });
export const getInbox = () => call("getInbox");
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
