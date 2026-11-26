// 인터BOO 화면 (작업 20) — 물어보기 · 들려주기 · AI 요약 미리보기
// 기준: docs/design-rules.md 7-①·7-②·5-7·6-1·6-2, docs/spec-v1.md 4장(askBoo·interviewNext·summarizeInterview)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import {
  currentUser, logout, getMe, askBoo, interviewNext, summarizeInterview,
  saveInterviewDraft, getInterviewDraft, demandNext, saveDemand,
} from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");

// 노트 틀 칸 이름. 원본은 data/frames.json — 화면은 data/를 직접 읽지 않으므로(fetch 금지) 같은 값을 둔다.
// data.js에 칸 목록을 주는 함수가 생기면 이 표를 지우고 그 함수를 쓴다.
const FRAMES = {
  교환: ["지원", "학점", "비용", "생활", "팁", "배운점"],
  파견: ["지원", "학점", "비용", "생활", "팁", "배운점"],
  인턴: ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건"],
  비교과: ["활동내용", "배운점"],
};
const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" }; // note.js와 같은 값
const FIELD_TYPE = { 국제교류: "교환", 현장실습: "인턴", 비교과: "비교과" }; // chat 칩 payload.field → 해봤노트 ?type=

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs, on } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null && v !== false) node.setAttribute(k, v === true ? "" : String(v));
  if (on) for (const [k, fn] of Object.entries(on)) node.addEventListener(k, fn);
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

// node.append(null)은 「null」 글자를 붙이므로, 빈 자리(null·undefined·false)는 빼고 붙인다
const appendAll = (parent, ...children) => parent.append(...children.filter(Boolean));

const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });

function statusLabel(kind, iconName, text) {
  return el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, text]);
}

const toastHost = document.getElementById("toastHost");
let toastTimer = null;
function toast(text, iconName = "check") {
  clearTimeout(toastTimer);
  toastHost.replaceChildren(el("span", { className: "toast" }, [icon(iconName), text]));
  drawIcons();
  toastTimer = setTimeout(() => toastHost.replaceChildren(), 3000);
}

// 대화 복원(9절) 중에는 그때 저장해 둔 시각을 쓴다
let replayAt = null;
const timeText = () => replayAt || new Date().toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });

// 학기 표기(1-2절): "2024-1" → "2024-1학기", "2025-여름" → "2025 하계방학"
function semesterText(sem) {
  const [year, part] = String(sem || "").split("-");
  if (!year) return "–";
  if (part === "여름") return `${year} 하계방학`;
  if (part === "겨울") return `${year} 동계방학`;
  return part ? `${year}-${part}학기` : year;
}
const SEM_ORDER = { 1: 1, 여름: 2, 2: 3, 겨울: 4 };
const semesterKey = (sem) => {
  const [year, part] = String(sem || "").split("-");
  return Number(year || 0) * 10 + (SEM_ORDER[part] || 0);
};

// 안전한 링크만(공식 안내 URL 등): http·https만 허용
function safeUrl(url) {
  try {
    const u = new URL(url, location.href);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// 2. 말풍선
// ---------------------------------------------------------------------------

function booMessage({ wide = false } = {}) {
  const body = el("div", { className: `msg__body${wide ? " msg__body--wide" : ""}` }, [el("span", { className: "msg__sender", text: "BOO" })]);
  const msg = el("div", { className: "msg msg--ai" }, [
    el("img", { className: "msg__avatar", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
    body,
  ]);
  return { msg, body };
}

function booText(text, opts) {
  const { msg, body } = booMessage(opts);
  body.append(el("p", { className: "msg__bubble", text }), el("span", { className: "msg__time", text: timeText() }));
  return msg;
}

function userText(text) {
  return el("div", { className: "msg msg--user" }, [
    el("div", { className: "msg__body" }, [
      el("p", { className: "msg__bubble", text }),
      el("span", { className: "msg__time", text: timeText() }),
    ]),
  ]);
}

function typingMessage() {
  const { msg, body } = booMessage();
  body.append(el("div", { className: "msg__bubble", attrs: { "aria-label": "BOO가 입력 중" } }, [
    el("span", { className: "typing" }, [el("span"), el("span"), el("span")]),
  ]));
  return msg;
}

function addTo(chat, node) {
  chat.append(node);
  drawIcons();
  scrollToLatest();
  return node;
}

// 마지막 말풍선이 고정 입력줄 위에 보이도록 화면을 맨 아래까지 내린다
// (본문 아래 여백 = 입력줄 높이라서, 맨 아래까지 내리면 가려지지 않음)
function scrollToLatest() {
  requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" }));
}

// ---------------------------------------------------------------------------
// 3. 근거/출처 블록 (6-1, 6-2)
// ---------------------------------------------------------------------------

const DOC_LABEL = { 귀국보고서: "보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };

function evidenceBlock(sources) {
  const list = Object.values(sources || {});
  if (list.length === 0) return emptyEvidence();

  const reports = list.filter((s) => s.docType !== "인터뷰").length;
  const interviews = list.length - reports;
  const latest = list.map((s) => s.semester).sort((a, b) => semesterKey(b) - semesterKey(a))[0];
  const num = (n) => (n > 0 ? el("span", { className: "evidence__num", text: n }) : "–");

  const details = el("details", { className: "evidence" }, [
    el("summary", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", num(list.length), "건 · 보고서 ", num(reports), " · 선배 인터뷰 ", num(interviews), ` · 최근 ${semesterText(latest)}`]),
      ]),
      el("span", { className: "evidence__side" }, [
        el("span", { className: "evidence__toggle" }, [
          el("span", { className: "evidence__toggle-closed", text: "펼치기" }),
          el("span", { className: "evidence__toggle-open", text: "접기" }),
          icon("chevron-down"),
        ]),
      ]),
    ]),
    // 출처 한 줄: 종류 | 연도만(v4.3) — 학과·학기·이름 넣지 않음
    el("ul", { className: "evidence__list" }, list
      .slice()
      .sort((a, b) => semesterKey(b.semester) - semesterKey(a.semester))
      .map((s) => el("li", { className: "evidence__item" }, [
        DOC_LABEL[s.docType] || s.docType,
        " ", el("span", { className: "evidence__sep", text: "|" }), " ",
        String(s.semester || "–").split("-")[0],
      ]))),
  ]);
  return details;
}

function emptyEvidence(bodyChildren) {
  return el("div", { className: "evidence evidence--empty" }, [
    el("div", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), "건 · 보고서 – · 선배 인터뷰 – · 최근 –"]),
      ]),
    ]),
    bodyChildren ? el("div", { className: "evidence__empty-body" }, bodyChildren) : null,
  ]);
}

// ---------------------------------------------------------------------------
// 4. 모드 전환 (들려주기 / 물어보기) — 같은 화면 안 전환이라 하단 탭은 그대로(5-2)
// ---------------------------------------------------------------------------

const tabTell = document.getElementById("tabTell");
const tabAsk = document.getElementById("tabAsk");
const panelTell = document.getElementById("panelTell");
const panelAsk = document.getElementById("panelAsk");
const modeDesc = document.getElementById("modeDesc");
const summaryArea = document.getElementById("summaryArea");
const composer = document.getElementById("composer");
const composerInput = document.getElementById("composerInput");
const sendBtn = document.getElementById("sendBtn");

let mode = new URLSearchParams(location.search).get("mode") === "tell" ? "tell" : "ask";

function setMode(next) {
  mode = next;
  const isTell = mode === "tell";
  tabTell.setAttribute("aria-selected", String(isTell));
  tabAsk.setAttribute("aria-selected", String(!isTell));
  panelTell.hidden = !isTell;
  panelAsk.hidden = isTell;
  summaryArea.hidden = !isTell || !tell.program; // AI 요약 바는 들려주기에만(7-①), 경험을 고른 뒤
  modeDesc.textContent = isTell
    ? "BOO에게 경험을 들려주면 노트로 정리해 드려요."
    : "선배들의 해봤노트를 근거로 답해 드려요.";
  const url = new URL(location.href);
  url.searchParams.set("mode", mode);
  history.replaceState(history.state, "", url);
  updateComposer();
  measureDock();
  saveKeep(); // 돌아왔을 때 보던 모드로(9절)
  if (isTell) startTell();
}

tabTell.addEventListener("click", () => setMode("tell"));
tabAsk.addEventListener("click", () => setMode("ask"));

// 예시 문구(11/24): 입력창의 흐린 예시를 PC에서는 Tab으로 채운다. 휴대폰은 질문 아래 예시 칩을 누른다(Tab 키가 없음).
// 「…」로 끝나는 말머리 예시(「가장 크게 배운 건 …」)는 「…」를 지우고 이어 쓰게 채운다 — 바로 보내지 않는다(디자인 규칙 5-7).
const ASK_EXAMPLE = "마르부르크 생활비 얼마예요?"; // 360px 휴대폰에서도 잘리지 않게 짧게(14px, #132 생활비 질문)
const canTab = !!(window.matchMedia && window.matchMedia("(pointer: fine)").matches); // 마우스·키보드 기기에서만 「Tab」 안내
const exampleFill = (ex) => String(ex).replace(/\s*…\s*$/, " ");
function currentExamples() {
  if (mode === "ask") {
    if (!demand.active) return [ASK_EXAMPLE];
    return demandTyping() && Array.isArray(demand.step.examples) ? demand.step.examples.slice(0, 3) : [];
  }
  const step = tell.step;
  if (!step || step.done || !Array.isArray(step.examples)) return [];
  return step.examples.slice(0, 3);
}
function fillExample(ex) {
  composerInput.value = exampleFill(ex);
  updateComposer();
  composerInput.focus();
  const end = composerInput.value.length;
  composerInput.setSelectionRange(end, end); // 말머리 뒤에 바로 이어 쓰게
}

// 입력줄: 모드별 안내 문구, 보낼 수 있을 때만 전송 버튼 활성
function updateComposer() {
  // 질문이 끝난 뒤에도 칸을 고르면 이어서 쓸 수 있다
  const tellReady = mode === "tell" && tell.step && !tell.busy && (!tell.step.done || tell.extra);
  // 궁금한 것 정리하기 중에는 입력줄이 정리 답변 칸이다. 칩을 고르는 단계·끝난 뒤에는 위에서 고르게 막는다
  const askReady = !ask.busy && !demand.busy && (!demand.active || demandTyping());
  const enabled = mode === "ask" ? askReady : tellReady;
  composerInput.disabled = !enabled;
  const examples = currentExamples();
  const tabHint = canTab && examples.length ? " · Tab" : "";
  composerInput.placeholder = mode === "ask"
    ? demand.active
      ? demandTyping()
        ? (examples.length ? `예: ${exampleFill(examples[0]).trim()}${tabHint}` : "답을 적어 주세요")
        : "위에서 골라 주세요"
      : `예: ${ASK_EXAMPLE}${tabHint}`
    : tell.step && tell.step.done
      ? (tell.extra ? `「${tell.extra}」에 이어서 쓰기` : "위 칸을 골라 이어서 써 주세요")
      : examples.length ? `예: ${exampleFill(examples[0]).trim()}${tabHint}` : "경험을 들려주세요";
  sendBtn.disabled = !enabled || composerInput.value.trim() === "";
}
composerInput.addEventListener("input", updateComposer);

// PC: 입력창이 비었을 때 Tab → 첫 예시, 예시를 채운 상태에서 Tab → 다음 예시. 마지막 예시에서 Tab·Shift+Tab·직접 쓴 글이 있으면
// 원래대로 다음 칸으로 넘어간다(키보드로 빠져나갈 수 있게). 한글 조합 중(isComposing)에는 건드리지 않는다
composerInput.addEventListener("keydown", (e) => {
  if (e.key !== "Tab" || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey || e.isComposing || composerInput.disabled) return;
  const list = currentExamples();
  if (!list.length) return;
  const now = composerInput.value;
  const at = list.findIndex((ex) => exampleFill(ex) === now);
  if (now.trim() !== "" && at < 0) return;       // 직접 쓴 글이 있으면 그대로
  if (at === list.length - 1) return;             // 마지막 예시까지 채웠으면 다음 칸으로
  e.preventDefault();
  fillExample(list[at + 1]);
});

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = composerInput.value.trim();
  if (!text) return;
  composerInput.value = "";
  if (mode === "ask") {
    if (demandTyping()) sendDemandAnswer(text);
    else sendQuestion(text);
  } else sendAnswer(text);
  updateComposer();
});

// 고정 입력줄 높이만큼 본문 아래 여백(마지막 말풍선이 가리지 않게)
function measureDock() {
  for (const [viewId, dockId] of [["viewMain", "mainDock"], ["viewSummary", "summaryDock"]]) {
    const dock = document.getElementById(dockId);
    document.getElementById(viewId).style.setProperty("--dock-h", `${dock.offsetHeight}px`);
  }
  // 토스트는 고정 영역(입력줄·하단 버튼) 바로 위 16px에 — 입력창을 가리지 않게
  const visibleDock = document.getElementById(viewSummary && !viewSummary.hidden ? "summaryDock" : "mainDock");
  const rect = visibleDock.getBoundingClientRect();
  toastHost.style.bottom = `${Math.max(0, window.innerHeight - rect.top) + 16}px`;
}
window.addEventListener("resize", measureDock);

// 「맨 위로」(디자인 규칙 5-8, 11/25 민지): 한 화면보다 더 내려가면 입력줄 위 오른쪽에 보이고, 누르면 맨 위로.
// 대화가 길어지면 위쪽 안내·세그먼트(들려주기/물어보기)·처음 질문으로 돌아가기 어렵기 때문.
const toTopBtn = document.getElementById("toTopBtn");
let toTopTick = false;
function updateToTop() {
  toTopTick = false;
  toTopBtn.hidden = window.scrollY < window.innerHeight;
}
window.addEventListener("scroll", () => {
  if (!toTopTick) { toTopTick = true; requestAnimationFrame(updateToTop); }
}, { passive: true });
toTopBtn.addEventListener("click", () => {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  // 버튼이 사라지면 포커스가 갈 곳이 없어지므로 화면 제목으로 옮긴다(키보드 사용자)
  const title = document.querySelector("#viewMain .page-title");
  if (title) { title.setAttribute("tabindex", "-1"); title.focus({ preventScroll: true }); }
});

// ---------------------------------------------------------------------------
// 5. 물어보기 — askBoo: ok / hold / official / notes / chat / error
// ---------------------------------------------------------------------------

const askChat = document.getElementById("askChat");
// turns: 서버에 보내는 최근 대화(spec 4장 [v2] history). 서버는 기억하지 않으므로 화면이 쌓아서 보낸다.
// log: 화면에 그린 질문·답(9절 대화 보존 — 다른 메뉴에 갔다 와도 다시 그린다)
const ask = { busy: false, turns: [], log: [] };
const HISTORY_TURNS = 4;
const MAX_ASK_LOG = 60; // 궁금한 것 정리하기 말풍선(한 번에 20개 안팎)도 같은 log에 남는다

addTo(askChat, booText("궁금한 경험을 물어보세요. 선배들의 보고서와 인터뷰를 근거로 답해 드려요. 근거가 없으면 지어내지 않고 질문함에 담아 둘게요."));

// withHistory: false면 앞 대화 없이 묻는다(chat 칩 「질문함에 담기」 — 브리프 4-②)
// force: "hold" = chat 칩 「질문함에 담기」 — 답을 찾지 않고 바로 질문함에 담는다(spec 4장 askBoo force, PR #179)
async function sendQuestion(question, { withHistory = true, force } = {}) {
  ask.busy = true;
  updateComposer();
  const at = timeText();
  addTo(askChat, userText(question));
  const typing = addTo(askChat, typingMessage());
  const res = await askBoo(question, withHistory ? ask.turns.slice(-HISTORY_TURNS) : [], force ? { force } : {});
  typing.remove();
  ask.busy = false;
  updateComposer();
  rememberTurn(question, res);
  addTo(askChat, renderAnswer(res, question));
  // 오류 답은 남기지 않는다(돌아와서 「다시 시도」가 엉뚱하게 남지 않게)
  if (res && !res.error) {
    ask.log.push({ q: question, at, res, resAt: timeText() });
    if (ask.log.length > MAX_ASK_LOG) ask.log.shift();
    saveKeep();
  }
}

// history 한 턴 = {question, status, program}. program은 답의 근거 프로그램.
// chat은 프로그램을 바꾸지 않으므로 바로 앞 턴의 프로그램을 이어 받는다(「아까는 ○○ 이야기였어요」가 계속 맞게).
function rememberTurn(question, res) {
  if (!res || res.error || typeof res.status !== "string") return;
  const fromSources = Object.values(res.sources || {})[0]?.program;
  const last = ask.turns[ask.turns.length - 1];
  const program = typeof fromSources === "string" && fromSources
    ? fromSources
    : res.status === "chat" && last ? last.program : "";
  ask.turns.push({ question, status: res.status, program });
  if (ask.turns.length > HISTORY_TURNS) ask.turns.shift();
}

function renderAnswer(res, question) {
  if (!res || res.error) return renderError(res && res.error, () => sendQuestion(question));

  if (res.status === "chat") return renderChat(res);

  if (res.status === "hold") {
    // 근거 없음: 답을 지어내지 않는다(6-2) — 안내 + 0건 블록 + 닮은선배 보기 + 토스트
    if (!replayAt) toast("질문함에 담았어요"); // 복원할 때는 다시 띄우지 않는다
    const { msg, body } = booMessage({ wide: true });
    body.append(
      el("div", { className: "hold-box" }, [
        el("p", { className: "hold-box__text", text: res.message || "이 부분은 아직 경험한 선배가 없어요. 질문함에 담아 두었어요." }),
        emptyEvidence(),
        // [11/23 노트] 노트는 있는데 이 내용만 없으면 서버가 noteId를 준다 → 그 해봤노트로 가는 링크
        res.noteId
          ? el("div", { className: "evidence-after" }, [
              el("a", { className: "link-more", text: "해봤노트 보기 ›", attrs: { href: noteHref(res.noteId) } }),
            ])
          : null,
        // [작업 92] 보류된 내 질문 → 궁금한 것 정리하기(질문·프로그램·칸은 미리 채워짐, spec demandNext fromQuestionId)
        res.questionId ? holdDemandButton(res.questionId) : null,
        res.suggestSenior !== false
          ? el("a", { className: "btn btn--secondary btn--block", text: "닮은선배 보기", attrs: { href: "../senior/" } })
          : null,
      ]),
      el("span", { className: "msg__time", text: timeText() }),
    );
    return msg;
  }

  if (res.status === "official") {
    // 규정 질문: 선배 경험으로 답하지 않고 공식 안내로(6-1 마지막 줄)
    const { msg, body } = booMessage({ wide: true });
    const url = safeUrl(res.officialUrl);
    body.append(
      el("p", { className: "msg__bubble", text: res.message || "학교 규정에 관한 질문이라 공식 안내에서 확인해 주세요." }),
      el("div", { className: "evidence-after" }, [
        statusLabel("info", "info", "공식 안내"),
        url ? el("a", { className: "link-more", text: "공식 안내 보기 ›", attrs: { href: url, target: "_blank", rel: "noopener" } }) : null,
      ]),
      el("span", { className: "msg__time", text: timeText() }),
    );
    return msg;
  }

  if (res.status === "notes") {
    // [11/23 노트] 사람 찾기·나라만 말한 질문: 답이 아니라 해봤노트 길 안내(spec 4장).
    // 답이 아니므로 근거 블록은 두지 않는다.
    const { msg, body } = booMessage({ wide: true });
    const cards = (res.notes || []).filter((n) => n && n.noteId);
    // 현장실습을 나라로 물으면 카드 대신 기관 유형(kinds) — spec 4장 [v2] notes
    const kinds = (Array.isArray(res.kinds) ? res.kinds : []).filter((k) => typeof k === "string" && k.trim());
    // 고를 것(카드·유형)이 없을 때 「골라 보세요」라고 하지 않는다
    const fallback = cards.length || kinds.length ? "궁금한 해봤노트를 골라 보세요." : "지금은 보여 드릴 해봤노트가 없어요. 궁금한 내용을 물어보셔도 돼요.";
    appendAll(body,
      el("p", { className: "msg__bubble", text: res.message || fallback }),
      cards.length ? el("div", { className: "note-links" }, cards.map(noteLinkCard)) : null,
      kinds.length ? kindChips(kinds) : null,
      res.suggestSenior !== false
        ? el("a", { className: "btn btn--secondary btn--block", text: "닮은선배 보기", attrs: { href: "../senior/" } })
        : null,
      el("span", { className: "msg__time", text: timeText() }),
    );
    return msg;
  }

  // 화면이 모르는 새 상태: 답이 아니므로 빈 말풍선·「근거 0건」을 그리지 않고 문구만 보인다
  if (res.status !== "ok") {
    const { msg, body } = booMessage({ wide: true });
    body.append(
      el("p", { className: "msg__bubble", text: res.message || "다른 말로 다시 물어봐 주세요." }),
      el("span", { className: "msg__time", text: timeText() }),
    );
    return msg;
  }

  // ok: 문장 + 근거 블록 + 관련 해봤노트 링크
  const { msg, body } = booMessage({ wide: true });
  const bubble = el("div", { className: "msg__bubble" });
  for (const line of res.lines || []) {
    const p = el("p", { text: line.text });
    // 사후 검증에 걸려 근거 원문을 그대로 보여 준 줄(spec 4장 lines[].fallback)
    if (line.fallback) p.append(el("span", { className: "status-label status-label--neutral line-fallback", text: "근거 원문" }));
    bubble.append(p);
  }
  const program = Object.values(res.sources || {})[0]?.program;
  appendAll(body,
    bubble,
    evidenceBlock(res.sources),
    res.noteId
      ? el("div", { className: "evidence-after" }, [
          el("a", {
            className: "link-more",
            text: `${program ? program + " " : ""}해봤노트 보기 ›`,
            attrs: { href: noteHref(res.noteId) },
          }),
        ])
      : null,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

const noteHref = (noteId) => `../note/?id=${encodeURIComponent(noteId)}`;

// notes 응답의 노트 카드(공통 부품 .note-card): 분야 띠 · 노트명 · 근거 N건, 누르면 해봤노트 상세.
// 분야 띠는 해봤노트 화면(note.js noteCover)과 같은 규칙: CATEGORY[type] 띠 + 「교환학생 · 독일」(#173 type).
// type이 없거나 모르는 값이면 띠를 짐작하지 않고 뺀다.
function noteLinkCard(n) {
  const count = Number.isFinite(n.evidenceCount) ? n.evidenceCount : 0;
  const cat = CATEGORY[n.type];
  const band = cat
    ? el("div", { className: "note-card__band" }, [
        el("span", { className: "category-tag", text: CATEGORY_NAME[cat] }),
        el("span", { className: "note-card__kind", text: kindText(n) }),
      ])
    : null;
  return el("article", { className: `note-card${cat ? ` cat-${cat}` : ""}` }, [
    band,
    el("a", { className: "note-card__body", attrs: { href: noteHref(n.noteId) } }, [
      el("span", { className: "note-card__title", text: n.program || "–" }),
      // 커버 한 줄(oneLine) — 해봤노트 목록 카드와 같은 부품, 최대 2줄. 없으면 줄을 뺀다
      n.oneLine ? el("span", { className: "note-card__summary", text: n.oneLine }) : null,
      el("span", { className: "note-card__meta", text: `근거 ${count}건` }),
    ]),
  ]);
}

// 「교환학생 · 독일」 — note.js kindText와 같은 규칙(비교과는 세부 종류 없음)
function kindText(n) {
  const kind = KIND_NAME[n.type] ?? "";
  return n.country ? [kind, n.country].filter(Boolean).join(" · ") : kind;
}

// chat: 질문이 아닌 말(「아까 말한 거 말고요」)에 서버가 주는 고정 문구 + 다음 행동 칩(spec 4장 [v2]).
// 답이 아니므로 근거 블록·토스트가 없다(질문함에 저장되지 않음).
function renderChat(res) {
  const { msg, body } = booMessage({ wide: true });
  const chips = (Array.isArray(res.chips) ? res.chips : [])
    .filter((c) => c && typeof c.label === "string" && c.label.trim() && CHAT_ACTIONS.has(c.action));
  appendAll(body,
    el("p", { className: "msg__bubble", text: res.message || "어떤 경험이 궁금한지 다시 물어봐 주세요." }),
    chips.length ? chatChips(chips) : null,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

// save(질문함에 담기)는 askBoo force: "hold"로 바로 hold가 된다 — 「○○ 말고 …」가 chat으로 되풀이되지 않는다(#179)
const CHAT_ACTIONS = new Set(["notes", "save", "ask"]);

// 칩 동작(브리프 4-②): notes → 해봤노트 목록(그 분야 필터), save → 질문함에 담기, ask → 닮은선배.
// 한 번 누른 칩 줄은 끈다(기관 유형 칩과 같은 규칙).
function chatChips(chips) {
  const row = el("div", { className: "chip-row" });
  for (const chip of chips) {
    const payload = chip.payload && typeof chip.payload === "object" ? chip.payload : {};
    // 「질문함에 담기」는 외곽선 버튼(디자인 규칙 5-4), 나머지는 보조 버튼
    const button = el("button", { className: chip.action === "save" ? "btn btn--outline" : "btn btn--secondary", text: chip.label, attrs: { type: "button" } });
    button.addEventListener("click", () => {
      if (ask.busy) return;
      for (const b of row.querySelectorAll("button")) b.disabled = true;
      if (chip.action === "notes") {
        const type = FIELD_TYPE[payload.field];
        location.href = type ? `../note/?type=${encodeURIComponent(type)}` : "../note/";
      } else if (chip.action === "ask") {
        location.href = "../senior/";
      } else {
        // save: 질문함에 담기 — 답을 찾지 않고 hold로(spec 4장 chat 칩 save)
        const question = typeof payload.question === "string" && payload.question.trim() ? payload.question.trim() : "";
        if (question) sendQuestion(question, { withHistory: false, force: "hold" });
        else for (const b of row.querySelectorAll("button")) b.disabled = false;
      }
    });
    row.append(button);
  }
  return row;
}

// 기관 유형 칩: 누르면 「{유형} 인턴 어디 있어요?」로 BOO에게 바로 다시 묻는다(11/23 민지 결정, PR #168).
// 한 번 고르면 같은 줄의 칩은 끈다(들려주기 예시답 칩과 같은 모양 .chip-row).
function kindChips(kinds) {
  const row = el("div", { className: "chip-row" });
  for (const kind of kinds) {
    row.append(el("button", {
      className: "btn btn--secondary",
      text: kind,
      attrs: { type: "button" },
      on: {
        click: () => {
          if (ask.busy) return;
          for (const b of row.querySelectorAll("button")) b.disabled = true;
          sendQuestion(`${kind} 인턴 어디 있어요?`);
        },
      },
    }));
  }
  return row;
}

// 화면 안 오류(6-5): 오류 라벨 + 문구 + 다시 시도(외곽선)
function renderError(message, retry) {
  const { msg, body } = booMessage({ wide: true });
  body.append(el("div", { className: "hold-box" }, [
    statusLabel("error", "circle-alert", "불러오지 못했어요"),
    el("p", { className: "hold-box__text", text: message || "잠시 뒤에 다시 시도해 주세요." }),
    retry ? el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" }, on: { click: (e) => { e.currentTarget.disabled = true; retry(); } } }) : null,
  ]));
  return msg;
}

// ---------------------------------------------------------------------------
// 5-1. 궁금한 것 정리하기 (작업 92, spec 4장 demandNext·saveDemand [11/22 열림], PRD 3-2 시연 0:40)
//      AI 없음 — 칩과 규칙만. 서버는 기억하지 않으므로 화면이 응답의 state를 들고 다니다 고른 값·쓴 답을 넣어 다시 보낸다.
//      말풍선은 물어보기 대화(askChat)에 이어 그리고 ask.log에 남긴다(9절 — 갔다 와도 이어서).
//      ① 잠겼을 때 물어보기 위 카드 ② 보류 답 아래 버튼(fromQuestionId) 두 곳에서 시작한다.
// ---------------------------------------------------------------------------

const DEMAND_TEXT_STEPS = new Set(["situation", "question", "hope", "more"]); // 입력줄로 쓰는 단계(나머지는 칩)
// active: 정리하는 중 · busy: 서버 응답 기다리는 중 · step: 마지막 demandNext 응답(done 포함)
// from: 보류 질문에서 시작했으면 그 질문 id · sent: 이미 전한 보류 질문 id(그 버튼을 다시 켜지 않게)
const demand = { active: false, busy: false, step: null, from: null, sent: [] };
let demandCard = null;

const demandTyping = () => demand.active && !!demand.step && !demand.step.done && DEMAND_TEXT_STEPS.has(demand.step.step);

function logAsk(item) {
  ask.log.push({ ...item, at: timeText() });
  if (ask.log.length > MAX_ASK_LOG) ask.log.shift();
  saveKeep();
}
function demandUser(text) {
  logAsk({ t: "d-user", text });
  addTo(askChat, userText(text));
}
function demandBoo(text) {
  logAsk({ t: "d-boo", text });
  addTo(askChat, booText(text));
}

// 지나간 단계의 칩·버튼은 끈다(한 번에 한 단계만 답한다)
function disableDemandButtons() {
  for (const b of askChat.querySelectorAll("[data-demand] button")) b.disabled = true;
}

// ① 잠김 카드(6-6): 선배 추천이 아직 안 열렸을 때만 물어보기 맨 위에. 열려 있으면 만들지 않는다
async function showDemandCard() {
  if (demandCard || demand.active) return;
  const info = await getMe();
  const rec = info && !info.error ? info.recommend : null;
  if (!rec || rec.ready !== false || demandCard || demand.active) return;
  demandCard = el("section", { className: "card demand-invite" }, [
    el("h2", { className: "demand-invite__title", text: "궁금한 것 정리하기" }),
    el("p", { className: "sub", text: "BOO와 함께 궁금한 것을 정리해 선배와 담당 부서에 전해 보세요." }),
    el("button", { className: "btn btn--primary btn--block", text: "궁금한 것 정리하기", attrs: { type: "button" }, on: { click: () => startDemand() } }),
    el("p", { className: "btn-reason" }, [icon("lock"), "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요"]),
  ]);
  panelAsk.insertBefore(demandCard, askChat);
  drawIcons();
}
function hideDemandCard() {
  if (demandCard) demandCard.remove();
  demandCard = null;
}

// ② 보류 답 아래: 「이 질문을 선배에게 전하고 선배 추천 받기」
function holdDemandButton(questionId) {
  const sent = demand.sent.includes(questionId);
  return el("button", {
    className: "btn btn--primary btn--block",
    text: "이 질문을 선배에게 전하고 선배 추천 받기",
    attrs: { type: "button", disabled: sent, "data-from": questionId },
    on: {
      click: (e) => {
        if (demand.active) return toast("지금 정리하던 것을 먼저 마쳐 주세요", "info");
        e.currentTarget.disabled = true;
        startDemand(questionId);
      },
    },
  });
}

async function startDemand(fromQuestionId) {
  if (demand.active || demand.busy || ask.busy) return;
  Object.assign(demand, { active: true, step: null, from: fromQuestionId || null });
  hideDemandCard();
  demandBoo(fromQuestionId
    ? "좋아요. 선배가 답하기 좋게 몇 가지만 더 물어볼게요."
    : "좋아요. 선배가 답하기 좋게 궁금한 것을 함께 정리해 볼게요.");
  await nextDemand(fromQuestionId ? { fromQuestionId } : {});
}

async function nextDemand(state) {
  demand.busy = true;
  updateComposer();
  const typing = addTo(askChat, typingMessage());
  const res = await demandNext(state);
  typing.remove();
  demand.busy = false;
  if (!res || res.error || (!res.done && !res.step)) {
    // 오류(6-5): 정리를 멈추고 다시 시도하면 같은 state로 이어 간다
    demand.active = false;
    demand.step = null;
    updateComposer();
    addTo(askChat, renderError(res && res.error, () => {
      demand.active = true;
      nextDemand(state);
    }));
    return;
  }
  showDemandStep(res);
}

function showDemandStep(res) {
  disableDemandButtons();
  demand.step = res;
  logAsk({ t: "d-step", step: res });
  addTo(askChat, demandStepMessage(res));
  updateComposer();
  if (demandTyping()) composerInput.focus({ preventScroll: true });
}

// 한 단계 말풍선: (다시 묻기 문구) + 질문 + 칩 또는 예시 칩 + 「답변 n/3」 + 넘어가기·그만두기
function demandStepMessage(res) {
  if (res.done) return demandSummaryMessage(res);
  const { msg, body } = booMessage({ wide: true });
  msg.dataset.demand = "step";
  const progress = res.progress || {};
  const typing = DEMAND_TEXT_STEPS.has(res.step);
  const actions = el("div", { className: "msg__actions" }, [
    res.canSkip ? el("button", { className: "btn btn--text", text: "넘어가기", attrs: { type: "button" }, on: { click: () => skipDemandMore(res) } }) : null,
    el("button", { className: "btn btn--text", text: "정리 그만두기", attrs: { type: "button" }, on: { click: () => stopDemand(res) } }),
  ]);
  appendAll(body,
    // 유효 답변이 아니면 같은 단계를 다시 묻는다 — 입력 오류(5-9): 아이콘 + 14px 문구
    res.retry ? el("p", { className: "demand-retry" }, [icon("triangle-alert"), res.retry]) : null,
    el("p", { className: "msg__bubble", text: res.question || "" }),
    !typing && Array.isArray(res.options) && res.options.length ? demandOptions(res) : null,
    typing && Array.isArray(res.examples) && res.examples.length
      ? el("div", { className: "chip-row" }, res.examples.slice(0, 3).map((ex) => el("button", {
          className: "btn btn--secondary", text: ex, attrs: { type: "button" }, on: { click: () => fillExample(ex) }, // 바로 보내지 않음(5-7)
        })))
      : null,
    el("div", { className: "demand-foot" }, [
      statusLabel("neutral", null, `답변 ${Number(progress.answered) || 0}/${Number(progress.need) || 3}`),
      actions,
    ]),
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

// 칩 단계: 옵션은 문자열 또는 {value, label}(detail — 「아직 정하지 않았어요」는 value: null)
function demandOptions(res) {
  const row = el("div", { className: "chip-row" });
  for (const opt of res.options) {
    const isObj = opt && typeof opt === "object";
    const label = String(isObj ? opt.label ?? "" : opt ?? "");
    if (!label) continue;
    const value = isObj ? (opt.value ?? null) : opt;
    row.append(el("button", {
      className: "btn btn--secondary", text: label, attrs: { type: "button" },
      on: { click: () => pickDemand(res, value, label) },
    }));
  }
  return row;
}

function pickDemand(res, value, label) {
  if (!demand.active || demand.busy || demand.step !== res) return;
  disableDemandButtons();
  demandUser(label);
  const state = { ...res.state };
  if (res.step === "explore") state.explore = label; // 「잘 모르겠어요」 → 고민 칩(field는 그대로)
  else state[res.step] = value;
  nextDemand(state);
}

function sendDemandAnswer(text) {
  const res = demand.step;
  if (!demandTyping() || demand.busy) return;
  disableDemandButtons();
  demandUser(text);
  const state = { ...res.state };
  if (res.step === "more") {
    // 더 궁금한 것(최대 2개): 다시 묻는 중이면 방금 틀린 문장을 새 문장으로 바꾼다
    const more = Array.isArray(state.more) ? [...state.more] : [];
    if (res.retry && more.length) more[more.length - 1] = text;
    else more.push(text);
    state.more = more;
  } else {
    state[res.step] = text;
  }
  nextDemand(state);
}

function skipDemandMore(res) {
  if (!demand.active || demand.busy || demand.step !== res) return;
  disableDemandButtons();
  demandUser("넘어가기");
  nextDemand({ ...res.state, moreDone: true });
}

function stopDemand(res) {
  if (!demand.active || demand.busy || demand.step !== res) return;
  disableDemandButtons();
  // 보류 질문에서 시작했으면 그 버튼을 다시 켠다(질문함에는 이미 담겨 있다)
  if (demand.from) for (const b of askChat.querySelectorAll(`button[data-from="${CSS.escape(demand.from)}"]`)) b.disabled = false;
  Object.assign(demand, { active: false, step: null, from: null });
  demandBoo("알겠어요. 궁금한 게 생기면 언제든 다시 정리할 수 있어요.");
  updateComposer();
  showDemandCard();
}

// 끝(done): 「내가 궁금한 것」 카드 + 동의 문구 + Primary 「선배와 담당 부서에 전하기」(spec saveDemand)
// AI가 만든 글이 아니라 내가 고르고 쓴 것이므로 MINT가 아닌 SOFT BLUE 머리(3-1 AI 표시색 규칙)
function demandSummaryMessage(res) {
  const s = res.summary || {};
  const questions = (Array.isArray(s.questions) ? s.questions : []).filter((q) => typeof q === "string" && q.trim());
  const rows = [
    ["관심", s.interest],
    ["프로그램", s.program || "아직 정하지 않았어요"],
    ["궁금한 칸", s.section],
    ["시기", s.when],
    ["선배에게 묻고 싶은 것", questions],
    ["지금 내 상황", s.situation],
    ["얻고 싶은 것", s.hope],
  ];
  const card = el("article", { className: "summary-card demand-card" }, [
    el("div", { className: "summary-card__head" }, [icon("list-checks"), "내가 궁금한 것"]),
  ]);
  for (const [name, value] of rows) {
    const row = el("div", { className: "summary-row" }, [el("span", { className: "summary-row__name", text: name })]);
    const list = Array.isArray(value) ? value : [value];
    if (!list.length || list.every((v) => !v)) row.append(el("p", { className: "summary-row__empty", text: "–" }));
    else for (const v of list) if (v) row.append(el("p", { text: v }));
    card.append(row);
  }

  const { msg, body } = booMessage({ wide: true });
  msg.dataset.demand = "summary";
  const sendBtn = el("button", { className: "btn btn--primary btn--block", text: "선배와 담당 부서에 전하기", attrs: { type: "button" } });
  sendBtn.addEventListener("click", () => sendDemand(res, sendBtn));
  appendAll(body,
    el("p", { className: "msg__bubble", text: "정리했어요. 이 질문을 선배와 담당 부서에 전해도 될까요?" }),
    card,
    el("p", { className: "sub", text: "선배에게는 질문만 전해져요. 지금 내 상황과 얻고 싶은 것은 선배에게 보내지 않아요." }),
    el("div", { className: "dock__buttons" }, [
      sendBtn,
      el("button", { className: "btn btn--text", text: "정리 그만두기", attrs: { type: "button" }, on: { click: () => stopDemand(res) } }),
    ]),
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

async function sendDemand(res, button) {
  if (!demand.active || demand.busy || demand.step !== res) return;
  demand.busy = true;
  button.disabled = true;
  updateComposer();
  const out = await saveDemand(res.state);
  demand.busy = false;
  if (!out || out.error) {
    button.disabled = false;
    updateComposer();
    toast((out && out.error) || "전하지 못했어요. 잠시 뒤에 다시 시도해 주세요.", "circle-alert");
    return;
  }
  if (out.ok === false) {
    // 서버가 다시 검사해 아직 덜 끝났다고 하면 그 단계부터 다시
    demandBoo(out.message || "아직 정리가 끝나지 않았어요");
    if (out.next && (out.next.done || out.next.step)) showDemandStep(out.next);
    else updateComposer();
    return;
  }
  disableDemandButtons();
  if (demand.from) demand.sent.push(demand.from);
  Object.assign(demand, { active: false, step: null, from: null });
  logAsk({ t: "d-sent", res: out });
  addTo(askChat, demandSentMessage(out));
  hideDemandCard();
  updateComposer();
  toast(out.unlocked ? "선배 추천이 열렸어요" : "선배와 담당 부서에 전했어요");
}

function demandSentMessage(out) {
  const { msg, body } = booMessage({ wide: true });
  const ready = !!(out.recommend && out.recommend.ready);
  appendAll(body,
    el("p", { className: "msg__bubble", text: "선배와 담당 부서에 전했어요. 질문은 질문함에 담겨 있고, 선배가 경험을 들려줄 때 이 질문을 먼저 물어볼게요." }),
    ready ? statusLabel("success", "check", "선배 추천이 열렸어요") : null,
    ready ? el("a", { className: "btn btn--secondary btn--block", text: "닮은선배 보기", attrs: { href: "../senior/" } }) : null,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

// ---------------------------------------------------------------------------
// 6. 들려주기 — 내 경험 고르기 → interviewNext → AI 요약 바
// ---------------------------------------------------------------------------

const tellChat = document.getElementById("tellChat");
const tellNotice = document.getElementById("tellNotice");
const chipsBox = document.getElementById("chips");
const summaryBtn = document.getElementById("summaryBtn");
const summaryCount = document.getElementById("summaryCount");
const summaryReason = document.getElementById("summaryReason");

const tell = {
  started: false,
  busy: false,
  program: null,   // { name, kind }
  answers: [],     // spec: [{section, question, answer, questionId?, skipped?}]
  step: null,      // 마지막 interviewNext 응답
  pending: 0,      // pendingQuestions
  covered: [],     // [v2] 보고서가 이미 채워 묻지 않은 칸(interviewNext covered)
  extra: null,     // 질문이 끝난 뒤 「이어서 쓰기」로 고른 칸 이름
  experiences: [], // 이수 기록에서 고를 수 있는 경험(9절 복원 때 선택 말풍선을 다시 그림)
  log: [],         // 화면에 그린 말풍선 [{t: "choose"|"user"|"boo"|"step", text?, step?, at}]
  waiting: false,  // interviewNext 응답을 아직 못 받음(돌아오면 다시 부른다)
  summarized: false, // AI 요약이 끝남 — 노트에 저장됐으니 이 탭 보존·서버 초안을 더 남기지 않는다(9절)
};
const EXTRA_QUESTION = "더 들려주고 싶은 이야기";
const DONE_TEXT = "지금 물을 건 다 물었어요. 더 들려줄 칸을 고르거나 AI 요약을 눌러 주세요.";

// 들려주기 말풍선은 그리면서 log에 남긴다(9절)
function tellUser(text) {
  tell.log.push({ t: "user", text, at: timeText() });
  return addTo(tellChat, userText(text));
}
function tellBoo(text) {
  tell.log.push({ t: "boo", text, at: timeText() });
  return addTo(tellChat, booText(text));
}
function stepMessage(step) {
  if (step.done) return booText(DONE_TEXT);
  return step.junior ? juniorQuestion(step) : interviewQuestion(step);
}

// 답이 바뀔 때마다: 이 탭(sessionStorage) + 미완성 초안 7일(서버, spec saveInterviewDraft — 기다리지 않음)
function keepAnswers() {
  saveKeep();
  if (!tell.summarized) saveInterviewDraft(tell.program.name, tell.answers);
}

// getMe의 이수 기록에서 들려줄 수 있는 경험 목록을 만든다(국제교류 → 현장실습 → 비교과)
function myExperiences(meInfo) {
  const list = [];
  const seen = new Set();
  const add = (name, kind) => {
    if (!name || seen.has(name)) return;
    seen.add(name);
    list.push({ name, kind });
  };
  for (const r of meInfo["귀국보고서"] || []) add(r["대학명"], meInfo["해외경험 유형"] === "교환학생" ? "교환" : "파견");
  if (meInfo["해외경험"] === "있음") add(meInfo["파견대학"], meInfo["해외경험 유형"] === "교환학생" ? "교환" : "파견");
  for (const r of meInfo["현장실습후기"] || []) add(r["업체명"], "인턴");
  if (meInfo["현장실습·인턴십"] === "있음") add(meInfo["기관명(가상)"], "인턴");
  for (const r of meInfo["비교과이수내역"] || []) add(r["프로그램명"], "비교과");
  return list;
}

async function startTell() {
  if (tell.started) return;
  tell.started = true;
  const loading = addTo(tellChat, el("div", { className: "skeleton", attrs: { style: "height: 96px", "aria-label": "불러오는 중" } }));
  const meInfo = await getMe();
  loading.remove();

  if (!meInfo || meInfo.error) {
    tell.started = false;
    addTo(tellChat, renderError(meInfo && meInfo.error, () => startTell()));
    return;
  }

  const experiences = myExperiences(meInfo);
  if (experiences.length === 0) {
    // 빈 화면(6-4): BOO 80px → 제목 → 설명 → 버튼 1개
    tellChat.append(el("div", { className: "empty" }, [
      el("img", { className: "boo-illust boo-illust--sm", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "empty__title", text: "아직 들려줄 경험 기록이 없어요" }),
      el("p", { className: "sub", text: "교환·파견, 현장실습, 비교과를 이수하면 경험을 들려줄 수 있어요." }),
      el("button", { className: "btn btn--secondary", text: "물어보기로 가기", attrs: { type: "button" }, on: { click: () => setMode("ask") } }),
    ]));
    return;
  }

  tell.experiences = experiences;
  if (experiences.length === 1) return chooseProgram(experiences[0]);

  tell.log.push({ t: "choose", at: timeText() });
  addTo(tellChat, chooserMessage(experiences, null));
}

// 경험 고르기 말풍선. picked가 있으면(복원) 고른 칩만 눌린 채 모두 끈다
function chooserMessage(experiences, picked) {
  const { msg, body } = booMessage({ wide: true });
  body.append(el("p", { className: "msg__bubble", text: "어떤 경험을 들려줄까요? 이수 기록에 있는 경험이에요." }));
  const choices = el("div", { className: "choice-list" });
  for (const exp of experiences) {
    const cat = CATEGORY[exp.kind];
    choices.append(el("button", {
      className: "choice-chip",
      attrs: { type: "button", "aria-pressed": String(!!picked && picked === exp.name), disabled: !!picked },
      on: {
        click: (e) => {
          if (tell.program) return;
          e.currentTarget.setAttribute("aria-pressed", "true");
          for (const b of choices.querySelectorAll("button")) b.disabled = true;
          chooseProgram(exp);
        },
      },
    }, [el("span", { className: `category-tag cat-${cat}`, text: CATEGORY_NAME[cat] }), exp.name]));
  }
  body.append(choices, el("span", { className: "msg__time", text: timeText() }));
  return msg;
}

function chooseProgram(exp) {
  tell.program = exp;
  tellUser(exp.name);
  chipsBox.hidden = false;
  summaryArea.hidden = false;
  renderChips();
  continueTell();
}

// 경험을 고른 직후(또는 그때 다른 메뉴로 갔다가 돌아온 때): 지난번 미완성 초안(7일)이 있으면 이어서 할지 묻는다
async function continueTell() {
  tell.busy = true;
  updateComposer();
  const draft = tell.answers.length ? null : await getInterviewDraft(tell.program.name);
  tell.busy = false;
  const prev = (draft && Array.isArray(draft.answers) ? draft.answers : []).filter((a) => a && a.section);
  // 지난 답이 모두 「경험이 없어요」면 묻지 않고 바로 시작한다(「0개 들려줬어요」가 되지 않게)
  if (prev.some((a) => !a.skipped)) addTo(tellChat, draftOffer(prev));
  else askNext();
}

// 「지난번 이야기를 이어서 할까요?」 — 이어서 하기(답을 불러와 다시 보임) / 처음부터(초안을 지움)
function draftOffer(prev) {
  const { msg, body } = booMessage();
  const told = prev.filter((a) => !a.skipped).length;
  const done = () => { for (const b of actions.querySelectorAll("button")) b.disabled = true; };
  const actions = el("div", { className: "msg__actions" }, [
    el("button", {
      className: "btn btn--secondary",
      text: "이어서 하기",
      attrs: { type: "button" },
      on: {
        click: () => {
          if (tell.step || tell.busy) return;
          done();
          tellUser("이어서 할게요");
          // 불러온 지난 답은 지금 시각이 아니라 「지난번」으로 보인다(서버 초안에 시각이 없음, 디자인 규칙 5-8)
          replayAt = "지난번";
          for (const a of prev) {
            tellBoo(a.asked || a.question || `${a.section} 이야기`);
            tellUser(a.skipped ? "경험이 없어요" : a.answer);
          }
          replayAt = null;
          tell.answers = prev;
          saveKeep();
          askNext();
        },
      },
    }),
    el("button", {
      className: "btn btn--text",
      text: "처음부터 할게요",
      attrs: { type: "button" },
      on: {
        click: () => {
          if (tell.step || tell.busy) return;
          done();
          tellUser("처음부터 할게요");
          saveInterviewDraft(tell.program.name, []); // 빈 answers = 초안 지우기(spec)
          askNext();
        },
      },
    }),
  ]);
  body.append(
    el("p", { className: "msg__bubble", text: `지난번에 이 경험을 ${told}개 들려줬어요. 이어서 할까요?` }),
    actions,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

// 진행 칩(5-7): 내 이야기로 채워짐(MINT ✓) / 보고서로 채워짐(중립색) / 지금 질문 중(NAVY) / 비어 있음 — 번호 없음
// [v2] 「후배 질문」 칸은 없다 — 후배 질문의 답은 그 질문의 칸(section)에 담긴다(spec interviewNext junior)
function filledSections() {
  const set = new Set();
  for (const a of tell.answers) if (!a.skipped && a.section) set.add(a.section);
  return set;
}

function renderChips() {
  const frame = FRAMES[tell.program.kind] || FRAMES["교환"];
  const filled = filledSections();
  const covered = new Set(tell.covered);
  const picking = Boolean(tell.step && tell.step.done); // 질문이 끝나면 칩을 눌러 칸을 골라 이어서 쓴다
  const current = picking ? tell.extra : tell.step ? tell.step.section : null;
  chipsBox.classList.toggle("progress-chips--pick", picking);
  chipsBox.replaceChildren(...frame.map((name) => {
    const isCurrent = name === current;
    const isFilled = !isCurrent && filled.has(name);
    const isCovered = !isCurrent && !isFilled && covered.has(name);
    const canPick = picking;
    const state = isCurrent ? " progress-chip--current" : isFilled ? " progress-chip--filled" : isCovered ? " progress-chip--covered" : "";
    const chip = el(canPick ? "button" : "span", {
      className: `progress-chip${state}`,
      attrs: canPick ? { type: "button", "aria-pressed": String(isCurrent), "aria-label": `${name}${isCovered ? "(보고서로 채워짐)" : ""}에 이어서 쓰기` } : null,
      on: canPick ? { click: () => pickExtra(name) } : null,
    }, [isFilled ? icon("check") : isCovered ? icon("file-text") : null, name,
      isCovered ? el("span", { className: "progress-chip__note", text: "보고서" }) : null]);
    // 후배 질문을 묻는 중이면 지금 칩에 남은 후배 질문 수
    if (isCurrent && !picking && tell.step && tell.step.junior && tell.pending > 0) chip.append(el("span", { className: "progress-chip__badge", text: tell.pending }));
    if (isCurrent && !picking) chip.setAttribute("aria-current", "step");
    return chip;
  }));
  drawIcons();
  // 지금 칸이 칩 줄 가운데 오게 — 칩 줄만 가로로 움직이고 화면은 세로로 움직이지 않게
  const currentChip = chipsBox.querySelector(".progress-chip--current");
  if (currentChip) chipsBox.scrollLeft = currentChip.offsetLeft - (chipsBox.clientWidth - currentChip.offsetWidth) / 2;

  // AI 요약 바(spec [v2] 진행률): 「내 이야기 N칸 · 보고서 M칸」 — 보고서 칸은 내가 답하지 않은 covered 칸만
  const n = frame.filter((name) => filled.has(name)).length;
  const m = frame.filter((name) => !filled.has(name) && covered.has(name)).length;
  summaryCount.textContent = `내 이야기 ${n}칸 · 보고서 ${m}칸`;
  summaryBtn.disabled = n === 0 || tell.busy;
  summaryReason.hidden = n > 0;
  measureDock();
}

async function askNext() {
  tell.busy = true;
  tell.waiting = true;
  saveKeep();
  updateComposer();
  const typing = addTo(tellChat, typingMessage());
  const res = await interviewNext(tell.program.name, tell.answers);
  typing.remove();
  tell.busy = false;

  if (!res || res.error) {
    addTo(tellChat, renderError(res && res.error, () => askNext()));
    updateComposer();
    return;
  }

  tell.step = res;
  tell.waiting = false;
  // 지나간 질문의 버튼(「경험이 없어요」·예시답 칩)은 끈다
  for (const b of tellChat.querySelectorAll(".msg__actions button, .chip-row button")) b.disabled = true;
  if (typeof res.pendingQuestions === "number") tell.pending = res.pendingQuestions;
  if (Array.isArray(res.covered)) tell.covered = res.covered;
  renderNotice();

  tell.log.push({ t: "step", step: res, at: timeText() });
  addTo(tellChat, stepMessage(res));
  saveKeep();
  renderChips();
  updateComposer();
  if (!res.done) composerInput.focus({ preventScroll: true });
}

// 첫 화면 안내(7-①): pendingQuestions ≥ 1이면 「후배 N명이 이 경험을 기다리고 있어요」
function renderNotice() {
  tellNotice.replaceChildren(
    tell.pending > 0 && tell.answers.length === 0
      ? statusLabel("info", "info", `후배 ${tell.pending}명이 이 경험을 기다리고 있어요`)
      : "",
  );
  drawIcons();
}

// 후배 질문 말풍선(5-7): 머리말 + 원문 인용 + 「경험이 없어요」(건너뛰기)
function juniorQuestion(step) {
  const { msg, body } = booMessage();
  const actions = el("div", { className: "msg__actions" }, [
    el("button", {
      className: "btn btn--text",
      text: "경험이 없어요",
      attrs: { type: "button" },
      on: {
        click: (e) => {
          if (tell.busy || tell.step !== step) return;
          e.currentTarget.disabled = true;
          tellUser("경험이 없어요");
          // 질문은 hold로 남아 다른 선배에게 다시 나간다(spec interviewNext)
          tell.answers.push({ section: step.section, question: step.asked, questionId: step.questionId, skipped: true });
          keepAnswers();
          askNext();
        },
      },
    }),
  ]);
  body.append(
    el("p", { className: "msg__bubble" }, [
      el("span", { className: "msg__lead", text: "후배가 이렇게 물었어요" }),
      el("span", { className: "msg__quote", text: step.asked || "" }),
      "경험이 있으면 들려주세요.",
    ]),
    actions,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
}

// 일반 질문 말풍선 + (P1-여건) 예시답 칩: 탭하면 입력창에 채우고 바로 보내지 않는다
function interviewQuestion(step) {
  const { msg, body } = booMessage();
  body.append(el("p", { className: "msg__bubble", text: step.question }));
  if (Array.isArray(step.examples) && step.examples.length) {
    body.append(el("div", { className: "chip-row" }, step.examples.slice(0, 3).map((ex) => el("button", {
      className: "btn btn--secondary",
      text: ex,
      attrs: { type: "button" },
      on: { click: () => fillExample(ex) }, // 「…」 말머리는 「…」를 지우고 이어 쓰게(바로 보내지 않음)
    }))));
  }
  body.append(el("span", { className: "msg__time", text: timeText() }));
  return msg;
}

// 질문이 끝난 뒤 칩을 눌러 칸 고르기
function pickExtra(name) {
  if (tell.busy) return;
  tell.extra = name;
  saveKeep();
  renderChips();
  updateComposer();
  composerInput.focus({ preventScroll: true });
}

function sendAnswer(text) {
  const step = tell.step;
  if (!step || tell.busy) return;

  if (step.done) {
    // 이어서 쓰기: 고른 칸의 답으로 더한다(서버를 다시 부르지 않음 — 요약할 때 함께 보낸다)
    if (!tell.extra) return;
    tellUser(text);
    tell.answers.push({ section: tell.extra, question: EXTRA_QUESTION, answer: text });
    tellBoo(`「${tell.extra}」에 더했어요.`);
    keepAnswers();
    renderChips();
    return;
  }

  tellUser(text);
  const answer = { section: step.section, question: step.junior ? step.asked : step.question, answer: text };
  if (step.questionId) answer.questionId = step.questionId;
  tell.answers.push(answer);
  keepAnswers();
  askNext();
}

// ---------------------------------------------------------------------------
// 7. AI 요약 미리보기 (2단계) — 요약 = 내 경험노트 자동 저장, 공유는 선택(7-②)
// ---------------------------------------------------------------------------

const viewMain = document.getElementById("viewMain");
const viewSummary = document.getElementById("viewSummary");
const summaryStatus = document.getElementById("summaryStatus");
const summaryBody = document.getElementById("summaryBody");
const shareBtn = document.getElementById("shareBtn");
const laterBtn = document.getElementById("laterBtn");
let summaryResult = null;
let mainScrollY = 0;

function showView(name) {
  const summary = name === "summary";
  if (summary) mainScrollY = window.scrollY;
  viewMain.hidden = summary;
  viewSummary.hidden = !summary;
  measureDock();
  window.scrollTo(0, summary ? 0 : mainScrollY); // 돌아오면 스크롤 위치 유지(5-2)
}

// 휴대폰 뒤로가기도 같은 동작: 요약 화면은 history 한 칸으로 둔다
window.addEventListener("popstate", () => showView(history.state && history.state.view === "summary" ? "summary" : "main"));
document.getElementById("summaryBack").addEventListener("click", () => history.back());
document.getElementById("continueBtn").addEventListener("click", () => history.back());

summaryBtn.addEventListener("click", () => {
  history.pushState({ view: "summary" }, "", location.href);
  showView("summary");
  runSummary();
});

async function runSummary() {
  summaryResult = null;
  shareBtn.disabled = true;
  laterBtn.disabled = true;
  summaryStatus.replaceChildren(statusLabel("ai", "sparkles", "대화 정리하는 중…"));
  summaryBody.replaceChildren(el("div", { className: "skeleton", attrs: { style: "height: 240px", "aria-label": "정리하는 중" } }));
  drawIcons();

  const transcript = tell.answers
    .filter((a) => !a.skipped)
    .map(({ section, question, answer }) => ({ section, question, answer }));
  const res = await summarizeInterview(tell.program.name, transcript);

  if (!res || res.error) {
    summaryStatus.replaceChildren(statusLabel("error", "circle-alert", "요약하지 못했어요"));
    summaryBody.replaceChildren(el("div", { className: "hold-box" }, [
      el("p", { className: "hold-box__text", text: (res && res.error) || "잠시 뒤에 다시 시도해 주세요." }),
      el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" }, on: { click: runSummary } }),
    ]));
    drawIcons();
    return;
  }

  summaryResult = res;
  // 요약이 끝나면 이 탭의 들려주기 보존을 지운다 — 돌아와서 같은 요약을 다시 눌러 노트(고친 문장 포함)를 덮어쓰지 않게
  tell.summarized = true;
  saveKeep();
  shareBtn.textContent = "해봤노트에 공유";
  // 요약이 끝나면 항상 내 경험노트에 저장됨(서버 saved: true)
  summaryStatus.replaceChildren(res.saved
    ? statusLabel("success", "check", "요약 완료 · 내 경험노트에 저장됨")
    : statusLabel("warning", "triangle-alert", "요약은 됐지만 저장하지 못했어요"));
  summaryBody.replaceChildren(summaryCard(res));
  shareBtn.disabled = !res.saved;
  laterBtn.disabled = !res.saved;
  drawIcons();
  measureDock();
}

// 요약 카드 = 내 경험노트 원본(myNote). 노트 틀 순서, 이야기하지 않은 칸은 「–」
// 같은 질문(asked)에 답한 문장이 이어지면 첫 문장에만 Q 인용을 붙인다(common/consent.js와 같은 규칙)
function firstOfQuestion(lines, i) {
  const asked = lines[i].asked;
  return Boolean(asked) && (i === 0 || lines[i - 1].asked !== asked);
}

function summaryCard(res) {
  const frame = FRAMES[tell.program.kind] || FRAMES["교환"];
  const sections = new Map(((res.myNote && res.myNote.sections) || []).map((s) => [s.name, s.lines || []]));
  const card = el("article", { className: "summary-card" }, [
    el("div", { className: "summary-card__head" }, [icon("sparkles"), `${res.program || tell.program.name} 경험노트 (요약 초안)`]),
  ]);
  for (const name of frame) {
    const lines = sections.get(name) || [];
    const row = el("div", { className: "summary-row" }, [el("span", { className: "summary-row__name", text: name })]);
    if (lines.length === 0) row.append(el("p", { className: "summary-row__empty", text: "–" }));
    lines.forEach((line, i) => {
      // 후배 질문에 답한 문장(asked가 붙음): Q(후배 질문 원문, 인용) + A(내 답) — 그 질문의 칸 안에.
      // [11/26 #295] Q는 같은 질문이 이어지는 문장의 첫 문장에만(common/consent.js firstOfQuestion과 같은 규칙)
      if (firstOfQuestion(lines, i)) row.append(el("span", { className: "msg__quote", text: `Q. ${line.asked}` }));
      row.append(el("p", { text: line.asked ? `A. ${line.text}` : line.text }));
    });
    card.append(row);
  }
  return card;
}

// 「해봤노트에 공유」 → 공개 동의 시트(consent.js, 작업 70)
shareBtn.addEventListener("click", () => {
  if (!summaryResult) return;
  document.dispatchEvent(new CustomEvent("open-consent", { detail: summaryResult }));
});

// 공유가 끝나면(common/consent.js가 알림): 토스트 + 공유 상태 라벨 + 버튼은 「공유 범위 바꾸기」(7-②, 8절)
// 「반영 중」은 없다 — saveConsent가 그 자리에서 해봤노트에 반영한다(spec 4장 getInbox [11/22])
document.addEventListener("consent-saved", (event) => {
  if (!summaryResult || event.detail.draftId !== summaryResult.draftId) return;
  shareBtn.textContent = "공유 범위 바꾸기";
  // 서버가 문장을 모두 거절해 실제로 들어간 문장이 없으면 라벨·토스트를 띄우지 않는다
  if (event.detail.shared === 0) return;
  summaryStatus.querySelector(".status-label--neutral, .status-label--shared")?.remove();
  const label = event.detail.removed.length
    ? statusLabel("neutral", "share-2", `${event.detail.shared}문장 공유`)
    : statusLabel("success", "check", "해봤노트 공유됨");
  label.classList.add("status-label--shared");
  summaryStatus.append(" ", label);
  measureDock();
  // [작업 92] 이번 공유로 선배 추천이 처음 열렸으면 함께 알린다(spec saveConsent unlocked)
  toast(event.detail.result && event.detail.result.unlocked ? "해봤노트에 반영됐어요 · 선배 추천이 열렸어요" : "해봤노트에 반영됐어요");
});

// 「나중에 할게요」 → 내 보관함 · 내 경험노트 탭(토스트는 보관함 화면이 from=later를 보고 띄운다)
laterBtn.addEventListener("click", () => {
  location.href = "../questions/?tab=notes&from=later";
});

// ---------------------------------------------------------------------------
// 8. 헤더 — 직원 계정이면 콘솔 버튼, 메뉴는 로그아웃
// ---------------------------------------------------------------------------

if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;
document.getElementById("menuBtn").addEventListener("click", () => {
  if (confirm("로그아웃할까요?")) {
    try { sessionStorage.removeItem(KEEP_KEY); } catch { /* 보존 없이 */ }
    logout();
    location.replace("../login/");
  }
});

// ---------------------------------------------------------------------------
// 9. 대화 보존 — 다른 메뉴에 갔다 와도 두 모드의 대화를 다시 그린다(spec 4장 saveInterviewDraft 1단계)
//    이 탭의 sessionStorage에만(탭마다 따로 — 두 창 시연), 사람별 키. 탭을 닫으면 사라지고,
//    들려주기 답은 서버 미완성 초안(7일, keepAnswers)으로 다시 이어 쓸 수 있다.
// ---------------------------------------------------------------------------

const KEEP_KEY = `talkKeep:${me ? me.colreg_no : ""}`;
let restoring = false;

function saveKeep() {
  if (restoring) return;
  try {
    const t = tell.program && !tell.summarized
      ? {
          program: tell.program, answers: tell.answers, step: tell.step, pending: tell.pending, covered: tell.covered,
          extra: tell.extra, experiences: tell.experiences, log: tell.log, waiting: tell.waiting,
        }
      : null;
    const d = { active: demand.active, step: demand.active ? demand.step : null, from: demand.from, sent: demand.sent };
    sessionStorage.setItem(KEEP_KEY, JSON.stringify({ mode, ask: { turns: ask.turns, log: ask.log, demand: d }, tell: t }));
  } catch {
    // 저장 공간이 없거나 막혀 있으면 보존 없이 그대로 쓴다
  }
}

function loadKeep() {
  try {
    const kept = JSON.parse(sessionStorage.getItem(KEEP_KEY) || "null");
    return kept && typeof kept === "object" ? kept : null;
  } catch {
    return null;
  }
}

function restoreAsk(kept) {
  ask.turns = Array.isArray(kept.turns) ? kept.turns.slice(-HISTORY_TURNS) : [];
  ask.log = Array.isArray(kept.log) ? kept.log.slice(-MAX_ASK_LOG) : [];
  const d = kept.demand && typeof kept.demand === "object" ? kept.demand : {};
  demand.sent = Array.isArray(d.sent) ? d.sent : []; // 보류 답의 버튼을 그리기 전에
  for (const item of ask.log) {
    replayAt = item.at;
    // 궁금한 것 정리하기 말풍선(5-1)
    if (item.t === "d-user") addTo(askChat, userText(item.text));
    else if (item.t === "d-boo") addTo(askChat, booText(item.text));
    else if (item.t === "d-step" && item.step) addTo(askChat, demandStepMessage(item.step));
    else if (item.t === "d-sent" && item.res) addTo(askChat, demandSentMessage(item.res));
    else if (!item.t) {
      addTo(askChat, userText(item.q));
      replayAt = item.resAt;
      addTo(askChat, renderAnswer(item.res, item.q));
    }
  }
  replayAt = null;
  disableDemandButtons(); // 지나간 단계는 끄고, 정리하던 중이면 아래에 그 단계를 다시
  for (const b of askChat.querySelectorAll("button[data-from]")) b.disabled = demand.sent.includes(b.dataset.from);
  if (d.active && d.step && (d.step.done || d.step.step)) {
    Object.assign(demand, { active: true, step: d.step, from: d.from || null });
    for (const b of askChat.querySelectorAll(`button[data-from="${CSS.escape(String(demand.from))}"]`)) b.disabled = true;
    addTo(askChat, booText("아까 정리하던 것을 이어서 할게요."));
    addTo(askChat, demandStepMessage(d.step));
  }
}

function restoreTell(kept) {
  if (!kept.program || !kept.program.name) return;
  Object.assign(tell, {
    started: true, program: kept.program, step: kept.step || null, pending: kept.pending || 0,
    answers: Array.isArray(kept.answers) ? kept.answers : [], covered: Array.isArray(kept.covered) ? kept.covered : [],
    extra: kept.extra || null, experiences: Array.isArray(kept.experiences) ? kept.experiences : [],
    log: Array.isArray(kept.log) ? kept.log : [], waiting: !!kept.waiting,
  });
  for (const item of tell.log) {
    replayAt = item.at;
    if (item.t === "choose") addTo(tellChat, chooserMessage(tell.experiences, tell.program.name));
    else if (item.t === "user") addTo(tellChat, userText(item.text));
    else if (item.t === "boo") addTo(tellChat, booText(item.text));
    else if (item.t === "step" && item.step) addTo(tellChat, stepMessage(item.step));
  }
  replayAt = null;
  // 지나간 말풍선의 버튼은 모두 끄고, 이어서 할 자리는 아래에 새로 보인다
  for (const b of tellChat.querySelectorAll(".msg__actions button, .chip-row button")) b.disabled = true;
  chipsBox.hidden = false;
  renderNotice();
  renderChips();

  if (tell.waiting) return askNext();           // 질문을 받기 전에 떠났다
  if (!tell.step) return continueTell();        // 경험만 고르고 떠났다
  addTo(tellChat, resumeMessage());
  if (!tell.step.done) addTo(tellChat, stepMessage(tell.step)); // 마지막 질문을 다시(버튼·예시 칩이 살아 있게)
  updateComposer();
}

// 「아까 이야기를 이어서 할게요」(spec) + 다른 경험으로 바꾸기
// [11/26] 다 물은 뒤(done)면 바로 위 done 안내와 겹치지 않게 「이어서 쓸 수 있어요. …」(spec 9장 1단계)
function resumeMessage() {
  const { msg, body } = booMessage();
  body.append(el("p", {
    className: "msg__bubble",
    text: tell.step.done ? "이어서 쓸 수 있어요. 더 들려줄 칸을 고르거나 AI 요약을 눌러 주세요." : "아까 이야기를 이어서 할게요.",
  }));
  if (tell.experiences.length > 1) {
    body.append(el("div", { className: "msg__actions" }, [
      el("button", { className: "btn btn--text", text: "다른 경험 들려주기", attrs: { type: "button" }, on: { click: restartTell } }),
    ]));
  }
  body.append(el("span", { className: "msg__time", text: timeText() }));
  return msg;
}

// 다른 경험 고르기: 이 탭의 들려주기 대화만 비운다(지금 경험의 답은 서버 초안 7일에 남아 다시 고르면 이어서 할 수 있다)
function restartTell() {
  if (tell.busy) return;
  Object.assign(tell, {
    started: false, program: null, answers: [], step: null, pending: 0, covered: [], extra: null, log: [], waiting: false, summarized: false,
  });
  tellChat.replaceChildren();
  chipsBox.hidden = true;
  summaryArea.hidden = true;
  renderNotice();
  saveKeep();
  updateComposer();
  startTell();
}

// ---------------------------------------------------------------------------
// 시작
// ---------------------------------------------------------------------------

const kept = loadKeep();
if (kept) {
  restoring = true;
  if (kept.ask) restoreAsk(kept.ask);
  restoring = false;
  // 주소에 mode가 없으면(하단 탭으로 돌아옴) 떠날 때 보던 모드로
  if (!new URLSearchParams(location.search).get("mode") && (kept.mode === "tell" || kept.mode === "ask")) mode = kept.mode;
  if (kept.tell) restoreTell(kept.tell);
}

history.replaceState({ view: "main" }, "", location.href);
setMode(mode);
showDemandCard(); // ① 선배 추천이 잠겼을 때만 물어보기 맨 위 카드(작업 92)
drawIcons();
measureDock();
