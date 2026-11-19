// 모든 화면이 데이터를 읽고 쓰는 공통 통로입니다. 원본: docs/spec-v1.md
// 화면은 이 파일의 함수만 부릅니다. 응답 모양은 명세 4장을 따릅니다.
// 사용: <script type="module"> import { askBoo } from "../../common/data.js"; </script>

export const USE_MOCK = true; // true: common/mock-data.json, false: 서버 함수
const FN_BASE = "http://localhost:8787";

let mockPromise = null;
function loadMock() {
  if (!mockPromise) {
    mockPromise = fetch(new URL("mock-data.json", import.meta.url)).then((r) => r.json());
  }
  return mockPromise;
}

// 입력에 따라 다른 mock을 고르는 곳은 여기 한 곳입니다 (명세 3장).
function pickMock(m, name, p) {
  switch (name) {
    case "login":
      if (p.id === "staff01") return m.login.staff;               // 총괄 관리자
      if (String(p.id || "").startsWith("staff")) return m.login.staffDept; // 부서 담당자
      return p.pw === "1" ? m.login.student : m.login.fail;
    case "askBoo":
      return /교환|파견|독일|마르부르크/.test(p.question || "") ? m.askBoo.exchange : m.askBoo.hold;
    case "interviewNext": {
      const n = (p.answers || []).length;
      return n <= 3 ? m.interviewNext.steps[n] : m.interviewNext.done; // 11/19: steps[0]은 「후배 질문」
    }
    case "getNote":
      return m.getNote[p.id] || m.getNote["N-marburg"];
    case "checkMessage":
      return /\d{8,}/.test(p.text || "") ? m.checkMessage.blocked : m.checkMessage.ok;
    default:
      return m[name];
  }
}

async function call(name, payload = {}) {
  try {
    if (USE_MOCK) {
      const m = await loadMock();
      return structuredClone(pickMock(m, name, payload));
    }
    const headers = { "Content-Type": "application/json" };
    const me = currentUser();
    if (me && me.colreg_no) headers["X-User"] = me.colreg_no; // 서버가 누가 불렀는지 안다 (spec 2-1)
    const res = await fetch(`${FN_BASE}/${name}`, {
      method: "POST",
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

export const login = async (id, pw) => {
  const res = await call("login", { id, pw });
  if (res && res.ok && res.user) sessionStorage.setItem("me", JSON.stringify(res.user));
  return res;
};
export const logout = () => sessionStorage.removeItem("me");
export const getMe = () => call("getMe");
export const askBoo = (question) => call("askBoo", { question });
export const interviewNext = (program, answers) => call("interviewNext", { program, answers });
export const summarizeInterview = (program, transcript) => call("summarizeInterview", { program, transcript });
export const saveConsent = (draftId, edits) => call("saveConsent", { draftId, edits, consent: true });
export const listNotes = (filter) => call("listNotes", { filter });
export const getNote = (id) => call("getNote", { id });
export const reportStatement = (lineId, reason) => call("reportStatement", { lineId, reason });
export const recommendSeniors = (noteId) => call("recommendSeniors", { noteId });
export const checkMessage = (text) => call("checkMessage", { text });
export const previewNickname = (to) => call("previewNickname", { to });
export const sendMessage = (to, text) => call("sendMessage", { to, text });
export const getMessages = () => call("getMessages");
export const respondRequest = (threadId, accept) => call("respondRequest", { threadId, accept });
export const getInbox = () => call("getInbox");
export const getDeptReport = (dept) => call("getDeptReport", { dept });
