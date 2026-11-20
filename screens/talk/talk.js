// 인터BOO 화면 (작업 20) — 물어보기 · 들려주기 · AI 요약 미리보기
// 기준: docs/design-rules.md 7-①·7-②·5-7·6-1·6-2, docs/spec-v1.md 4장(askBoo·interviewNext·summarizeInterview)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import {
  currentUser, logout, getMe, askBoo, interviewNext, summarizeInterview,
} from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");

// 노트 틀 칸 이름. 원본은 data/frames.json — 화면은 data/를 직접 읽지 않으므로(fetch 금지) 같은 값을 둔다.
// data.js에 칸 목록을 주는 함수가 생기면 이 표를 지우고 그 함수를 쓴다.
const FRAMES = {
  교환: ["지원", "학점", "비용", "생활", "팁", "배운점", "후배 질문"],
  파견: ["지원", "학점", "비용", "생활", "팁", "배운점", "후배 질문"],
  인턴: ["지원동기", "업무내용", "배운점", "지원·선발", "근무조건", "후배 질문"],
  비교과: ["활동내용", "배운점", "후배 질문"],
};
const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const QUESTION_SECTION = "후배 질문";

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

const timeText = () => new Date().toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" });

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

const DOC_LABEL = { 귀국보고서: "결과보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };

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
        el("span", {}, ["근거 ", num(list.length), "건 · 결과보고서 ", num(reports), " · 선배 인터뷰 ", num(interviews), ` · 최근 ${semesterText(latest)}`]),
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
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), "건 · 결과보고서 – · 선배 인터뷰 – · 최근 –"]),
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
  if (isTell) startTell();
}

tabTell.addEventListener("click", () => setMode("tell"));
tabAsk.addEventListener("click", () => setMode("ask"));

// 입력줄: 모드별 안내 문구, 보낼 수 있을 때만 전송 버튼 활성
function updateComposer() {
  // 질문이 끝난 뒤에도 칸을 고르면 이어서 쓸 수 있다
  const tellReady = mode === "tell" && tell.step && !tell.busy && (!tell.step.done || tell.extra);
  const enabled = mode === "ask" ? !ask.busy : tellReady;
  composerInput.disabled = !enabled;
  composerInput.placeholder = mode === "ask"
    ? "예: 마르부르크 파견은 어학을 언제부터 준비해요?"
    : tell.step && tell.step.done
      ? (tell.extra ? `「${tell.extra}」에 이어서 쓰기` : "위 칸을 골라 이어서 써 주세요")
      : "경험을 들려주세요";
  sendBtn.disabled = !enabled || composerInput.value.trim() === "";
}
composerInput.addEventListener("input", updateComposer);

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = composerInput.value.trim();
  if (!text) return;
  composerInput.value = "";
  if (mode === "ask") sendQuestion(text);
  else sendAnswer(text);
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

// ---------------------------------------------------------------------------
// 5. 물어보기 — askBoo: ok / hold / official / error
// ---------------------------------------------------------------------------

const askChat = document.getElementById("askChat");
const ask = { busy: false };

addTo(askChat, booText("궁금한 경험을 물어보세요. 선배들의 결과보고서와 인터뷰를 근거로 답해 드려요. 근거가 없으면 지어내지 않고 질문함에 담아 둘게요."));

async function sendQuestion(question) {
  ask.busy = true;
  updateComposer();
  addTo(askChat, userText(question));
  const typing = addTo(askChat, typingMessage());
  const res = await askBoo(question);
  typing.remove();
  ask.busy = false;
  updateComposer();
  addTo(askChat, renderAnswer(res, question));
}

function renderAnswer(res, question) {
  if (!res || res.error) return renderError(res && res.error, () => sendQuestion(question));

  if (res.status === "hold") {
    // 근거 없음: 답을 지어내지 않는다(6-2) — 안내 + 0건 블록 + 닮은선배 보기 + 토스트
    toast("질문함에 담았어요");
    const { msg, body } = booMessage({ wide: true });
    body.append(
      el("div", { className: "hold-box" }, [
        el("p", { className: "hold-box__text", text: res.message || "이 부분은 아직 들은 선배가 없어요. 질문함에 담아 두었어요." }),
        emptyEvidence(),
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
  body.append(
    bubble,
    evidenceBlock(res.sources),
    res.noteId
      ? el("div", { className: "evidence-after" }, [
          el("a", {
            className: "link-more",
            text: `${program ? program + " " : ""}해봤노트 보기 ›`,
            attrs: { href: `../note/?id=${encodeURIComponent(res.noteId)}` },
          }),
        ])
      : null,
    el("span", { className: "msg__time", text: timeText() }),
  );
  return msg;
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
  extra: null,     // 질문이 끝난 뒤 「이어서 쓰기」로 고른 칸 이름
};
const EXTRA_QUESTION = "더 들려주고 싶은 이야기";

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

  if (experiences.length === 1) return chooseProgram(experiences[0]);

  const { msg, body } = booMessage({ wide: true });
  body.append(el("p", { className: "msg__bubble", text: "어떤 경험을 들려줄까요? 이수 기록에 있는 경험이에요." }));
  const choices = el("div", { className: "choice-list" });
  for (const exp of experiences) {
    const cat = CATEGORY[exp.kind];
    choices.append(el("button", {
      className: "choice-chip",
      attrs: { type: "button", "aria-pressed": "false" },
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
  addTo(tellChat, msg);
}

function chooseProgram(exp) {
  tell.program = exp;
  addTo(tellChat, userText(exp.name));
  chipsBox.hidden = false;
  summaryArea.hidden = false;
  renderChips();
  askNext();
}

// 진행 칩(5-7): 채워짐(MINT ✓) / 지금 질문 중(NAVY) / 비어 있음 — 번호 없음
function filledSections() {
  const set = new Set();
  for (const a of tell.answers) if (!a.skipped && a.section) set.add(a.section);
  // 「후배 질문」은 답하거나 건너뛰면 채워짐 처리(5-7)
  if (tell.answers.some((a) => a.section === QUESTION_SECTION)) set.add(QUESTION_SECTION);
  return set;
}

function renderChips() {
  const frame = FRAMES[tell.program.kind] || FRAMES["교환"];
  const filled = filledSections();
  const picking = Boolean(tell.step && tell.step.done); // 질문이 끝나면 칩을 눌러 칸을 골라 이어서 쓴다
  const current = picking ? tell.extra : tell.step ? tell.step.section : null;
  chipsBox.classList.toggle("progress-chips--pick", picking);
  chipsBox.replaceChildren(...frame.map((name) => {
    const isCurrent = name === current;
    const isFilled = !isCurrent && filled.has(name);
    const canPick = picking && name !== QUESTION_SECTION; // 후배 질문은 질문이 있어야 답할 수 있음
    const chip = el(canPick ? "button" : "span", {
      className: `progress-chip${isCurrent ? " progress-chip--current" : isFilled ? " progress-chip--filled" : ""}`,
      attrs: canPick ? { type: "button", "aria-pressed": String(isCurrent), "aria-label": `${name}에 이어서 쓰기` } : null,
      on: canPick ? { click: () => pickExtra(name) } : null,
    }, [isFilled ? icon("check") : null, name]);
    if (name === QUESTION_SECTION && tell.pending > 0) chip.append(el("span", { className: "progress-chip__badge", text: tell.pending }));
    if (isCurrent && !picking) chip.setAttribute("aria-current", "step");
    return chip;
  }));
  drawIcons();
  // 지금 칸이 칩 줄 가운데 오게 — 칩 줄만 가로로 움직이고 화면은 세로로 움직이지 않게
  const currentChip = chipsBox.querySelector(".progress-chip--current");
  if (currentChip) chipsBox.scrollLeft = currentChip.offsetLeft - (chipsBox.clientWidth - currentChip.offsetWidth) / 2;

  // AI 요약 바: 노트 틀(후배 질문 제외 칸) 채운 수 / 전체 칸
  const content = frame.filter((n) => n !== QUESTION_SECTION);
  const n = content.filter((name) => filled.has(name)).length + (filled.has(QUESTION_SECTION) && tell.answers.some((a) => a.section === QUESTION_SECTION && !a.skipped) ? 1 : 0);
  summaryCount.textContent = `노트 틀 ${n}/${frame.length} 채움`;
  summaryBtn.disabled = n === 0 || tell.busy;
  summaryReason.hidden = n > 0;
  measureDock();
}

async function askNext() {
  tell.busy = true;
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
  // 지나간 질문의 버튼(「경험이 없어요」·예시답 칩)은 끈다
  for (const b of tellChat.querySelectorAll(".msg__actions button, .chip-row button")) b.disabled = true;
  if (typeof res.pendingQuestions === "number") tell.pending = res.pendingQuestions;
  renderNotice();

  if (res.done) {
    addTo(tellChat, booText("고마워요. 노트 틀을 모두 채웠어요. 더 들려줄 이야기가 있으면 위 칸을 골라 이어서 써 주세요. 다 됐으면 아래 「AI 요약」을 눌러 정리해 보세요."));
  } else if (res.section === QUESTION_SECTION) {
    addTo(tellChat, juniorQuestion(res));
  } else {
    addTo(tellChat, interviewQuestion(res));
  }
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
          addTo(tellChat, userText("경험이 없어요"));
          // 질문은 hold로 남아 다른 선배에게 다시 나간다(spec interviewNext)
          tell.answers.push({ section: QUESTION_SECTION, question: step.asked, questionId: step.questionId, skipped: true });
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
      on: { click: () => { composerInput.value = ex; updateComposer(); composerInput.focus(); } },
    }))));
  }
  body.append(el("span", { className: "msg__time", text: timeText() }));
  return msg;
}

// 질문이 끝난 뒤 칩을 눌러 칸 고르기
function pickExtra(name) {
  if (tell.busy) return;
  tell.extra = name;
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
    addTo(tellChat, userText(text));
    tell.answers.push({ section: tell.extra, question: EXTRA_QUESTION, answer: text });
    addTo(tellChat, booText(`「${tell.extra}」에 더했어요.`));
    renderChips();
    return;
  }

  addTo(tellChat, userText(text));
  const answer = { section: step.section, question: step.section === QUESTION_SECTION ? step.asked : step.question, answer: text };
  if (step.questionId) answer.questionId = step.questionId;
  tell.answers.push(answer);
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
    for (const line of lines) {
      // 후배 질문 칸: Q(후배 질문 원문, 인용) + A(내 답)
      if (name === QUESTION_SECTION && line.asked) row.append(el("span", { className: "msg__quote", text: `Q. ${line.asked}` }));
      row.append(el("p", { text: name === QUESTION_SECTION ? `A. ${line.text}` : line.text }));
    }
    card.append(row);
  }
  return card;
}

// 「해봤노트에 공유」 → 공개 동의 시트(consent.js, 작업 70)
shareBtn.addEventListener("click", () => {
  if (!summaryResult) return;
  document.dispatchEvent(new CustomEvent("open-consent", { detail: summaryResult }));
});

// 공유가 끝나면(consent.js가 알림): 토스트 + 내 경험노트에 「반영 중」(중립) + 버튼은 「공유 범위 바꾸기」(7-②, 8절)
document.addEventListener("consent-saved", (event) => {
  if (!summaryResult || event.detail.draftId !== summaryResult.draftId) return;
  summaryStatus.querySelector(".status-label--neutral")?.remove();
  summaryStatus.append(" ", statusLabel("neutral", "clock", "반영 중"));
  shareBtn.textContent = "공유 범위 바꾸기";
  measureDock();
  toast("해봤노트에 반영하고 있어요");
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
    logout();
    location.replace("../login/");
  }
});

// ---------------------------------------------------------------------------
// 시작
// ---------------------------------------------------------------------------

history.replaceState({ view: "main" }, "", location.href);
setMode(mode);
drawIcons();
measureDock();
