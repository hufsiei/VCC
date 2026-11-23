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
    ? "예: 마르부르크 생활비 얼마예요?" // 360px 휴대폰에서도 잘리지 않게 짧게(14px, #132 생활비 질문)
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
// 5. 물어보기 — askBoo: ok / hold / official / notes / chat / error
// ---------------------------------------------------------------------------

const askChat = document.getElementById("askChat");
// turns: 서버에 보내는 최근 대화(spec 4장 [v2] history). 서버는 기억하지 않으므로 화면이 쌓아서 보낸다.
const ask = { busy: false, turns: [] };
const HISTORY_TURNS = 4;

addTo(askChat, booText("궁금한 경험을 물어보세요. 선배들의 결과보고서와 인터뷰를 근거로 답해 드려요. 근거가 없으면 지어내지 않고 질문함에 담아 둘게요."));

// withHistory: false면 앞 대화 없이 묻는다(chat 칩 「질문함에 담기」 — 브리프 4-②)
async function sendQuestion(question, { withHistory = true } = {}) {
  ask.busy = true;
  updateComposer();
  addTo(askChat, userText(question));
  const typing = addTo(askChat, typingMessage());
  const res = await askBoo(question, withHistory ? ask.turns.slice(-HISTORY_TURNS) : []);
  typing.remove();
  ask.busy = false;
  updateComposer();
  rememberTurn(question, res);
  addTo(askChat, renderAnswer(res, question));
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
    toast("질문함에 담았어요");
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

// "save"(질문함에 담기)는 잠시 숨긴다: data.js askBoo가 force: "hold"를 아직 넘기지 않아, 다시 물으면
// payload.question(「○○ 말고 …」)이 또 chat으로 돌아와 같은 말풍선이 되풀이된다(11/23 mock 확인).
// 미리가 data.js에 force를 넣으면 "save"를 다시 넣고 아래 save 분기를 askBoo(question, [], { force: "hold" })로 바꾼다.
const CHAT_ACTIONS = new Set(["notes", "ask"]);

// 칩 동작(브리프 4-②): notes → 해봤노트 목록(그 분야 필터), save → 질문함에 담기, ask → 닮은선배.
// 한 번 누른 칩 줄은 끈다(기관 유형 칩과 같은 규칙).
function chatChips(chips) {
  const row = el("div", { className: "chip-row" });
  for (const chip of chips) {
    const payload = chip.payload && typeof chip.payload === "object" ? chip.payload : {};
    const button = el("button", { className: "btn btn--secondary", text: chip.label, attrs: { type: "button" } });
    button.addEventListener("click", () => {
      if (ask.busy) return;
      for (const b of row.querySelectorAll("button")) b.disabled = true;
      if (chip.action === "notes") {
        const type = FIELD_TYPE[payload.field];
        location.href = type ? `../note/?type=${encodeURIComponent(type)}` : "../note/";
      } else if (chip.action === "ask") {
        location.href = "../senior/";
      } else {
        // save: 지금은 CHAT_ACTIONS에서 빠져 오지 않는다(위 주석). force가 생기면 여기서 질문함에 담는다
        const question = typeof payload.question === "string" && payload.question.trim() ? payload.question.trim() : "";
        if (question) sendQuestion(question, { withHistory: false });
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
  if (Array.isArray(res.covered)) tell.covered = res.covered;
  renderNotice();

  if (res.done) {
    addTo(tellChat, booText("지금 물을 건 다 물었어요. 더 들려줄 칸을 고르거나 AI 요약을 눌러 주세요."));
  } else if (res.junior) {
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
          tell.answers.push({ section: step.section, question: step.asked, questionId: step.questionId, skipped: true });
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
  const answer = { section: step.section, question: step.junior ? step.asked : step.question, answer: text };
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
      // 후배 질문에 답한 문장(asked가 붙음): Q(후배 질문 원문, 인용) + A(내 답) — 그 질문의 칸 안에
      if (line.asked) row.append(el("span", { className: "msg__quote", text: `Q. ${line.asked}` }));
      row.append(el("p", { text: line.asked ? `A. ${line.text}` : line.text }));
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
  toast("해봤노트에 반영됐어요");
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
