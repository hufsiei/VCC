// 내 보관함 · 쪽지 탭 (11/24 닮은선배 · 내 쪽지에서 옮김, 작업 28)
//   1단계 탭: 받은 요청(수락·거절) → 대화 → 보낸 요청(수락 대기·요청 취소, 취소함·응답 없음은 맨 아래)
//   2단계: 익명 쪽지 대화(?tab=messages&thread=T-…, 5초 폴링) → ⋮ 신고·차단 시트 → 차단이면 확인 시트를 한 번 더
// 기준: docs/design-rules.md 7-⑥·5-9·5-10·8절(기다리는 요청·받은 쪽지 요청·익명 쪽지 대화),
//       docs/spec-v1.md 4장 getMessages(read)·checkMessage·sendMessage·respondRequest·cancelRequest·reportThread
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
// 학번(withId)은 화면과 주소에 쓰지 않는다 — 대화는 threadId로만.
// questions.js가 setupMessages({go, goBack, onChange})로 화면 이동을 넘겨 준다.

import { getMessages, checkMessage, sendMessage, respondRequest, cancelRequest, reportThread } from "../../common/data.js";
import { markThreadRead, unreadOf, localRequests, rememberRequest, forgetRequests, refreshBell } from "./bell.js";

const POLL_MS = 5000; // 대화창 새 쪽지 확인 간격(실시간 채팅은 하지 않음 — 작업 28 비고)

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트, 날짜
// ---------------------------------------------------------------------------

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const child of [].concat(children)) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}
const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });
const statusLabel = (kind, iconName, text) =>
  el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, el("span", { text })]);
const skeletons = (n, cls) => Array.from({ length: n }, () => el("div", { className: `skeleton ${cls}`, attrs: { "aria-hidden": "true" } }));

function toast(text, iconName = "check") {
  const host = document.getElementById("toastHost");
  host.replaceChildren(el("span", { className: "toast" }, [icon(iconName), el("span", { text })]));
  drawIcons();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.replaceChildren(), 3000);
}

function errorBox(onRetry) {
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", onRetry);
  return el("div", { className: "state-box" }, [
    statusLabel("error", "circle-alert", "불러오지 못했어요"),
    el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]);
}

// "2026-11-20T11:30:00+09:00" → 오늘이면 「오전 11:30」, 아니면 「11월 20일」
function shortTime(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay ? d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" }) : `${d.getMonth() + 1}월 ${d.getDate()}일`;
}
function fullTime(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return "";
  return `${d.getMonth() + 1}월 ${d.getDate()}일 ${d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" })}`;
}
// 「로/으로」: 마지막 글자에 받침이 있고 그 받침이 ㄹ이 아니면 「으로」(수달 → 수달로, 고래 → 고래로, 곰 → 곰으로)
function josaRo(word) {
  const code = String(word || "").trim().slice(-1).charCodeAt(0) - 0xac00;
  if (code < 0 || code > 11171) return "(으)로";
  const jong = code % 28;
  return jong === 0 || jong === 8 ? "로" : "으로";
}
// retryAt(다시 보낼 수 있는 시각, ISO KST — spec [11/24]) → 아직 그 시각 전이면 「11월 30일부터 다시 보낼 수 있어요」
function retryText(iso) {
  const at = iso ? new Date(iso) : null;
  if (!at || Number.isNaN(at.getTime()) || at.getTime() <= Date.now()) return null;
  const kst = new Date(at.getTime() + 9 * 3600 * 1000);
  return `${kst.getUTCMonth() + 1}월 ${kst.getUTCDate()}일부터 다시 보낼 수 있어요`;
}

// ---------------------------------------------------------------------------
// 2. 상태 — 화면 이동은 questions.js가 넘겨 준다
// ---------------------------------------------------------------------------

let nav = { go: () => {}, goBack: () => {}, onChange: () => {} };
export function setupMessages(ctx) {
  nav = { ...nav, ...ctx };
}

let threads = [];            // getMessages.threads(내가 보낸 것·받은 것 모두)
let waitingCount = 0;
let waitingLimit = 3;
let threadsLoaded = false;
export const allThreads = () => threads;

// 이 화면에서 바꾼 대화 상태(요청 취소·수락·거절·차단). 서버가 아직 「수락 대기」로 주면 이 값을 쓴다
// (진짜 서버는 바뀐 상태를 바로 돌려주지만 mock은 기억하지 않아서 필요)
const localStatus = new Map(); // threadId → status
const localRetry = new Map();  // threadId → retryAt(이 화면에서 취소한 요청)
const localSent = new Map();   // threadId → [{from:"me", text, at}] 대화창에서 보낸 쪽지

// 서버 목록에 이 화면에서 보낸 쪽지·바꾼 상태를 합친다(서버에 이미 보이면 지역 사본은 버린다)
function mergeLocal(t) {
  const changed = localStatus.get(t.threadId);
  // 차단은 수락된 대화에도 걸린다 — 서버가 아직 blocked로 안 주면(mock) 이 화면에서 한 차단을 쓴다
  if (changed === "blocked" && t.status !== "blocked") t = { ...t, status: "blocked", blockedByMe: true };
  else if (changed && t.status === "waiting") t = { ...t, status: changed };
  else if (changed) localStatus.delete(t.threadId);
  if (t.status === "cancelled" && !t.retryAt && localRetry.has(t.threadId)) t = { ...t, retryAt: localRetry.get(t.threadId) };
  const extra = localSent.get(t.threadId);
  if (!extra || !extra.length) return t;
  const seen = new Set((t.messages || []).filter((m) => m.from === "me").map((m) => m.text));
  const left = extra.filter((m) => !seen.has(m.text));
  localSent.set(t.threadId, left);
  return left.length ? { ...t, messages: [...(t.messages || []), ...left] } : t;
}

// read: 대화창을 열 때 그 threadId — 서버가 그 대화만 읽음으로 바꾼다(spec [11/23 읽음])
export async function loadThreads(read) {
  try {
    const res = await getMessages(read);
    if (!res || res.error) throw new Error((res && res.error) || "쪽지 없음");
    const server = Array.isArray(res.threads) ? res.threads : [];
    threads = server.map(mergeLocal);
    // 닮은선배에서 이 탭으로 보낸 요청(서버 목록에 아직 없음)도 남겨 둔다. 서버에 보이면 지역 사본은 버린다
    const ids = new Set(server.map((t) => t.threadId));
    const local = localRequests();
    forgetRequests(local.filter((t) => ids.has(t.threadId)).map((t) => t.threadId));
    for (const t of local) if (!ids.has(t.threadId)) threads.push(mergeLocal(t));
    const localWaiting = threads.filter((t) => t.role === "asker" && t.status === "waiting").length;
    waitingCount = Math.max(Number.isFinite(res.waitingCount) ? res.waitingCount : 0, localWaiting);
    if (Number.isFinite(res.waitingLimit)) waitingLimit = res.waitingLimit;
    threadsLoaded = true;
    refreshBell({ threads });
    nav.onChange(threads);
    return true;
  } catch (err) {
    console.error(err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// 3. 쪽지 탭 목록 — 받은 요청 → 대화 → 보낸 요청(취소함·응답 없음은 맨 아래)
//    8절: 받은 요청 카드에 학과는 보이지 않는다(학과 + 학년이면 특정하기 쉬움)
// ---------------------------------------------------------------------------

const STATUS_LABEL = {
  waiting: () => statusLabel("neutral", "clock", "수락 대기"),
  cancelled: () => statusLabel("neutral", "x", "취소함"),
  expired: () => statusLabel("neutral", "hourglass", "응답 없음"),
  declined: () => statusLabel("neutral", "minus", "수락되지 않았어요"),
  blocked: () => statusLabel("neutral", "ban", "차단됨"),
};

const lastMessage = (t) => (t.messages && t.messages.length ? t.messages[t.messages.length - 1] : null);
const askerInfoText = (info) => {
  if (!info) return "";
  const parts = [];
  if (Number.isFinite(info.학년)) parts.push(`${info.학년}학년`);
  if (Array.isArray(info.관심) && info.관심.length) parts.push(`관심: ${info.관심.join(", ")}`);
  if (info.시기) parts.push(`시기: ${info.시기}`);
  return parts.join(" · ");
};
const threadQuery = (t) => `thread=${encodeURIComponent(t.threadId)}`;

function threadRow(t, { muted = false } = {}) {
  const last = lastMessage(t);
  const unread = unreadOf(t);
  const row = el("a", { className: `card thread-row${muted ? " thread-row--muted" : ""}`, attrs: { href: `?tab=messages&${threadQuery(t)}` } }, [
    el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
    el("div", { className: "thread-row__body" }, [
      el("div", { className: "thread-row__name" }, [
        el("span", { text: t.nickname || "상대" }),
        unread > 0 ? el("span", { className: "count-badge", text: unread, attrs: { "aria-label": `안 읽은 쪽지 ${unread}개` } }) : null,
        STATUS_LABEL[t.status] && t.status !== "accepted" ? STATUS_LABEL[t.status]() : null,
      ]),
      last ? el("p", { className: "thread-row__last", text: `${last.from === "me" ? "나: " : ""}${last.text}` }) : null,
      el("span", { className: "thread-row__time", text: shortTime((last && last.at) || t.requestedAt) }),
    ]),
  ]);
  row.addEventListener("click", (e) => {
    e.preventDefault();
    nav.go(threadQuery(t));
  });
  return row;
}

// 받은 쪽지 요청(선배 쪽): 「용감한 수달 · 2학년 · 관심: 교환학생·독일」 + 요청 문장 + 수락 / 거절
function requestCard(t) {
  const first = lastMessage(t);
  const accept = el("button", { className: "btn btn--primary", text: "수락", attrs: { type: "button" } });
  const decline = el("button", { className: "btn btn--outline", text: "거절", attrs: { type: "button" } });
  accept.addEventListener("click", () => respond(t, true, [accept, decline]));
  decline.addEventListener("click", () => respond(t, false, [accept, decline]));
  return el("article", { className: "card request-card" }, [
    el("div", { className: "senior-card__top" }, [
      el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
      el("div", {}, [
        el("p", { className: "request-card__who", text: t.nickname || "후배" }),
        el("p", { className: "sub", text: askerInfoText(t.askerInfo) }),
      ]),
    ]),
    first ? el("p", { className: "request-card__text", text: first.text }) : null,
    el("span", { className: "thread-row__time", text: fullTime(t.requestedAt) }),
    el("div", { className: "btn-row" }, [decline, accept]),
  ]);
}

// 보낸 요청(보낸 쪽): 수락 대기 + 「요청 취소」(확인 시트)
function sentCard(t) {
  const row = threadRow(t, { muted: t.status !== "waiting" });
  if (t.status !== "waiting") return row;
  const cancel = el("button", { className: "btn btn--outline btn--block", text: "요청 취소", attrs: { type: "button" } });
  cancel.addEventListener("click", () => confirmCancel(t));
  return el("div", { className: "msg-group" }, [row, cancel]);
}

let tabPanel = null;
export async function renderMessagesTab(panel) {
  tabPanel = panel;
  panel.setAttribute("aria-busy", "true");
  if (!threadsLoaded) panel.replaceChildren(...skeletons(2, "inbox-skeleton"));
  const ok = await loadThreads();
  if (tabPanel !== panel || panel.getAttribute("aria-labelledby") !== "tab-messages") return; // 그 사이 다른 탭으로 감
  if (!ok && !threadsLoaded) {
    panel.setAttribute("aria-busy", "false");
    panel.replaceChildren(errorBox(() => renderMessagesTab(panel)));
    drawIcons();
    return;
  }
  const received = threads.filter((t) => t.role === "senior" && t.status === "waiting");
  const talking = threads.filter((t) => t.status === "accepted" || t.status === "blocked")
    .sort((a, b) => String((lastMessage(b) || {}).at || "").localeCompare(String((lastMessage(a) || {}).at || "")));
  const sentWaiting = threads.filter((t) => t.role === "asker" && t.status === "waiting");
  const sentDone = threads.filter((t) => t.role === "asker" && ["cancelled", "expired", "declined"].includes(t.status)); // 맨 아래

  const children = [];
  if (!threads.length) {
    children.push(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 주고받은 쪽지가 없어요" }),
      el("p", { className: "sub", text: "닮은선배에게 쪽지를 요청해 보세요." }),
      el("a", { className: "btn btn--secondary", text: "닮은선배 보기", attrs: { href: "../senior/" } }),
    ]));
  }
  if (received.length) {
    children.push(el("h2", { className: "section-title", text: `받은 요청 ${received.length}건` }), el("div", { className: "msg-group" }, received.map(requestCard)));
  }
  if (talking.length) {
    children.push(el("h2", { className: "section-title", text: "대화" }), el("div", { className: "msg-group" }, talking.map((t) => threadRow(t))));
  }
  if (sentWaiting.length || sentDone.length) {
    children.push(
      el("h2", { className: "section-title", text: "보낸 요청" }),
      el("p", { className: "sub", text: `답을 기다리는 쪽지 ${waitingCount}/${waitingLimit}건` }),
      el("div", { className: "msg-group" }, [...sentWaiting, ...sentDone].map(sentCard)),
    );
  }
  panel.setAttribute("aria-busy", "false");
  panel.replaceChildren(...children);
  drawIcons();
}
// 목록이 지금 보이면 다시 그린다(수락·거절·취소 뒤)
function rerenderTab() {
  if (tabPanel && tabPanel.isConnected && !tabPanel.closest("[hidden]") && tabPanel.getAttribute("aria-labelledby") === "tab-messages") renderMessagesTab(tabPanel);
}

async function respond(t, accept, buttons) {
  for (const b of buttons) b.disabled = true;
  try {
    const res = await respondRequest(t.threadId, accept);
    if (!res || res.error || res.ok === false) throw new Error((res && (res.message || res.error)) || "응답 실패");
    t.status = res.status || (accept ? "accepted" : "declined");
    localStatus.set(t.threadId, t.status);
    toast(accept ? "요청을 수락했어요. 대화가 열렸어요" : "요청을 거절했어요");
    if (accept) nav.go(threadQuery(t));
    else if (currentThreadId === t.threadId) openThread(t.threadId, { reuse: true });
    else rerenderTab();
  } catch (err) {
    console.error(err);
    for (const b of buttons) b.disabled = false;
    toast("처리하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
}

// ---------------------------------------------------------------------------
// 4. 확인 시트(5-10) — 요청 취소·차단
// ---------------------------------------------------------------------------

const confirmSheet = document.getElementById("confirmSheet");
let confirmAction = null;
let confirmFocus = null;

function openConfirm({ title, text, okText, danger = false, onOk }) {
  confirmFocus = document.activeElement;
  document.getElementById("confirmTitle").textContent = title;
  document.getElementById("confirmText").textContent = text;
  const ok = document.getElementById("confirmOk");
  ok.textContent = okText;
  ok.className = `btn ${danger ? "btn--danger" : "btn--primary"} btn--block`;
  ok.disabled = false;
  confirmAction = onOk;
  confirmSheet.hidden = false;
  document.body.classList.add("sheet-open");
  confirmSheet.querySelector(".sheet").focus();
}
function closeConfirm() {
  confirmSheet.hidden = true;
  document.body.classList.remove("sheet-open");
  confirmAction = null;
  if (confirmFocus && confirmFocus.isConnected) confirmFocus.focus();
}
document.getElementById("confirmOk").addEventListener("click", async (e) => {
  if (!confirmAction) return;
  e.currentTarget.disabled = true;
  const action = confirmAction;
  await action();
  closeConfirm();
});
document.getElementById("confirmCancel").addEventListener("click", closeConfirm);
confirmSheet.querySelector(".sheet-scrim").addEventListener("click", closeConfirm);
confirmSheet.addEventListener("keydown", (e) => { if (e.key === "Escape") closeConfirm(); });

function confirmCancel(t) {
  openConfirm({
    title: `${t.nickname || "선배"}에게 보낸 요청을 취소할까요?`,
    text: "취소하면 이 선배에게는 7일 뒤에 다시 요청할 수 있어요.",
    okText: "요청 취소",
    danger: true,
    onOk: async () => {
      try {
        const res = await cancelRequest(t.threadId);
        if (!res || res.error || res.ok === false) throw new Error((res && (res.message || res.error)) || "취소 실패");
        t.status = res.status || "cancelled";
        localStatus.set(t.threadId, t.status);
        if (res.retryAt) { t.retryAt = res.retryAt; localRetry.set(t.threadId, res.retryAt); } // 카드·대화창에 바로 날짜가 보이게
        // 닮은선배에서 이 탭으로 보낸 요청이면 기억해 둔 사본도 바꾼다(닮은선배 카드가 「요청 보냄」으로 남지 않게 — mock용)
        const mine = localRequests().find((x) => x.threadId === t.threadId);
        if (mine) rememberRequest({ ...mine, status: t.status, retryAt: t.retryAt });
        waitingCount = Math.max(0, waitingCount - 1);
        toast("요청을 취소했어요");
        if (currentThreadId === t.threadId) openThread(t.threadId, { reuse: true });
        else rerenderTab();
      } catch (err) {
        console.error(err);
        toast("취소하지 못했어요. 다시 시도해 주세요", "circle-alert");
      }
    },
  });
}

// ---------------------------------------------------------------------------
// 5. 익명 쪽지 대화(2단계, 8절) — 상대 이름은 보는 사람에 따라 다르다(후배 화면 「독일어과 선배 A」, 선배 화면 「용감한 수달」)
//    열 때와 5초마다 getMessages(threadId)로 새 쪽지 확인 + 그 대화 읽음, 보내기 전 연락처·학번 검사(checkMessage)
// ---------------------------------------------------------------------------

const threadChat = document.getElementById("threadChat");
const threadTop = document.getElementById("threadTop");
const threadDock = document.getElementById("threadDock");
let currentThreadId = null;
let pollTimer = null;
let lastRenderedKey = "";

export function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
  currentThreadId = null;
}

function messageBubble(t, m) {
  if (m.from === "me") {
    return el("div", { className: "msg msg--user" }, [
      el("div", { className: "msg__body" }, [el("p", { className: "msg__bubble", text: m.text }), el("span", { className: "msg__time", text: shortTime(m.at) })]),
    ]);
  }
  return el("div", { className: "msg msg--ai msg--them" }, [
    el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
    el("div", { className: "msg__body" }, [
      el("span", { className: "msg__sender", text: t.nickname || "상대" }),
      el("p", { className: "msg__bubble", text: m.text }),
      el("span", { className: "msg__time", text: shortTime(m.at) }),
    ]),
  ]);
}

function renderThreadTop(t) {
  const items = [];
  if (t.role === "asker" && t.myNickname) items.push(statusLabel("info", "info", `선배에게는 '${t.myNickname}'${josaRo(t.myNickname)} 보여요`));
  if (t.role === "senior" && t.askerInfo) items.push(el("p", { className: "sub", text: askerInfoText(t.askerInfo) }));
  if (STATUS_LABEL[t.status] && t.status !== "accepted") items.push(STATUS_LABEL[t.status]());
  threadTop.replaceChildren(el("div", { className: "thread-top" }, items));
}

// 입력줄 자리: 대화 중이면 입력칸, 아니면 상태에 맞는 안내(차단 문구는 11/23 미리님 결정)
function renderDock(t) {
  if (t.status === "accepted") {
    const input = el("input", { className: "input", attrs: { id: "threadInput", autocomplete: "off", maxlength: "300", "aria-label": "쪽지 입력", placeholder: "쪽지를 입력하세요" } });
    const send = el("button", { className: "send-btn", attrs: { type: "submit", "aria-label": "보내기", disabled: "" } }, [icon("arrow-up")]);
    const err = el("p", { className: "field__error", attrs: { role: "alert" } });
    err.hidden = true;
    const warn = el("div", { className: "check-warn", attrs: { role: "alert" } }); // 연락처·학번·비방 주의 라벨 자리(입력창 위)
    warn.hidden = true;
    const form = el("form", { className: "composer" }, [input, send]);
    input.addEventListener("input", () => {
      send.disabled = input.value.trim() === "";
      err.hidden = true;
      warn.hidden = true;
      input.removeAttribute("aria-invalid");
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      sendInThread(t, input, send, err, warn);
    });
    threadDock.replaceChildren(warn, err, form);
  } else if (t.status === "blocked") {
    threadDock.replaceChildren(el("div", { className: "dock-note" }, [
      el("p", { className: "btn-reason" }, [icon("ban"), el("span", { text: t.blockedByMe ? "차단한 대화예요" : "더 이어 갈 수 없는 대화예요" })]),
    ]));
  } else if (t.status === "waiting" && t.role === "asker") {
    const cancel = el("button", { className: "btn btn--outline btn--block", text: "요청 취소", attrs: { type: "button" } });
    cancel.addEventListener("click", () => confirmCancel(t));
    threadDock.replaceChildren(el("div", { className: "dock-note" }, [
      el("p", { className: "btn-reason" }, [icon("clock"), el("span", { text: "선배가 수락하면 대화가 열려요" })]),
      cancel,
    ]));
  } else if (t.status === "waiting" && t.role === "senior") {
    const accept = el("button", { className: "btn btn--primary", text: "수락", attrs: { type: "button" } });
    const decline = el("button", { className: "btn btn--outline", text: "거절", attrs: { type: "button" } });
    accept.addEventListener("click", () => respond(t, true, [accept, decline]));
    decline.addEventListener("click", () => respond(t, false, [accept, decline]));
    threadDock.replaceChildren(el("div", { className: "btn-row" }, [decline, accept]));
  } else {
    const retry = t.status === "cancelled" ? retryText(t.retryAt) : null;
    const text = { cancelled: retry ? `취소한 요청이에요. ${retry}` : "취소한 요청이에요", expired: "선배가 아직 못 봤어요. 다른 선배에게 보내 볼까요?", declined: "선배가 이번에는 대화를 열지 않았어요" }[t.status] || "더 이어 갈 수 없는 대화예요";
    // 받은 쪽(선배)이 거절한 대화에는 닮은선배로 가는 버튼이 필요 없다
    const back = t.role === "asker" ? el("a", { className: "btn btn--outline btn--block", text: "닮은선배 보기", attrs: { href: "../senior/" } }) : null;
    threadDock.replaceChildren(el("div", { className: "dock-note" }, [el("p", { className: "btn-reason" }, [icon("info"), el("span", { text })]), back]));
  }
  drawIcons();
}

function renderThread(t, { keepDock = false } = {}) {
  document.getElementById("threadTitle").textContent = t.nickname || "쪽지";
  document.title = `${t.nickname || "쪽지"} · 내 보관함`;
  setThreadMenu(t);
  renderThreadTop(t);
  const key = `${t.status}|${(t.messages || []).length}|${(lastMessage(t) || {}).at || ""}`;
  if (key !== lastRenderedKey) {
    const nearBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 120;
    threadChat.replaceChildren(...(t.messages || []).map((m) => messageBubble(t, m)));
    if (nearBottom || !lastRenderedKey) window.scrollTo(0, document.body.scrollHeight);
    lastRenderedKey = key;
  }
  if (!keepDock || !threadDock.querySelector("#threadInput")) renderDock(t);
  drawIcons();
}

// 연 대화는 읽음: 서버는 getMessages(threadId)로, mock은 bell.js가 기억한다. 종 점도 바로 다시 그린다
function readNow(t) {
  markThreadRead(t);
  refreshBell({ threads });
  nav.onChange(threads);
}

export async function openThread(threadId, { reuse = false } = {}) {
  const firstOpen = currentThreadId !== threadId || !reuse;
  currentThreadId = threadId;
  if (firstOpen) {
    lastRenderedKey = "";
    setThreadMenu(null); // 대화를 받기 전에는 ⋮을 숨긴다
    threadTop.replaceChildren();
    threadDock.replaceChildren();
    threadChat.replaceChildren(...skeletons(2, "detail-skeleton"));
  }
  const local = threads.find((x) => x.threadId === threadId);
  if (local && reuse) renderThread(local);
  const ok = await loadThreads(threadId);
  if (currentThreadId !== threadId) return; // 그 사이 다른 화면으로 감
  const t = threads.find((x) => x.threadId === threadId);
  if (!t) {
    threadChat.replaceChildren(ok ? el("div", { className: "state-box" }, [
      el("p", { className: "state-box__title", text: "대화를 찾지 못했어요" }),
      el("p", { className: "sub", text: "내 보관함 쪽지 탭에서 다시 골라 주세요." }),
    ]) : errorBox(() => openThread(threadId)));
    threadDock.replaceChildren();
    drawIcons();
    return;
  }
  renderThread(t);
  readNow(t);
  // 5초마다 새 쪽지 확인 — 이 화면을 떠나면 멈춘다
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (document.hidden || currentThreadId !== threadId) return;
    if (await loadThreads(threadId)) {
      const fresh = threads.find((x) => x.threadId === threadId);
      if (fresh && currentThreadId === threadId) {
        renderThread(fresh, { keepDock: fresh.status === "accepted" });
        readNow(fresh);
      }
    }
  }, POLL_MS);
}

// ---------------------------------------------------------------------------
// 5-1. 대화 ⋮ 메뉴 → 신고·차단(spec reportThread [11/23 차단])
//   사유(선택) + 「차단도 하기」(선택) — 둘 중 하나는 있어야 보낸다. 차단은 되돌릴 수 없어서 확인 시트를 한 번 더(5-10).
//   신고만 하면 대화는 그대로 이어지고, 차단하면 입력줄이 「차단한 대화예요」로 바뀐다. 상대에게는 알리지 않는다.
//   취소함·응답 없음 대화는 ⋮을 두지 않는다(선배 쪽은 서버가 「볼 수 없는 기록」으로 막음).
// ---------------------------------------------------------------------------

const THREAD_REASONS = ["불쾌한 표현이 있어요", "연락처·개인 정보를 물어요", "광고·홍보예요", "기타"];
const threadMenu = document.getElementById("threadMenu");
const threadMenuSpacer = document.getElementById("threadMenuSpacer");
const reportSheet = document.getElementById("reportSheet");
const reportReasons = document.getElementById("reportReasons");
const reportBlock = document.getElementById("reportBlock");
const reportBlockRow = document.getElementById("reportBlockRow");
const reportSubmit = document.getElementById("reportSubmit");
const reportHint = document.getElementById("reportHint");
let reportTarget = null;
let reportChoice = null;
let reportFocus = null;

function setThreadMenu(t) {
  const show = !!t && !["cancelled", "expired"].includes(t.status);
  threadMenu.hidden = !show;
  threadMenuSpacer.hidden = show; // 제목이 가운데에 있게 빈 자리와 번갈아 보인다
}

function updateReportSubmit() {
  const block = reportBlock.checked;
  reportSubmit.disabled = !reportChoice && !block;
  reportSubmit.textContent = reportChoice && block ? "신고하고 차단하기" : block ? "차단하기" : "신고하기";
  reportHint.hidden = !reportSubmit.disabled;
}

function openReportSheet() {
  const t = threads.find((x) => x.threadId === currentThreadId);
  if (!t) return;
  reportTarget = t;
  reportChoice = null;
  reportFocus = document.activeElement;
  reportReasons.replaceChildren(...THREAD_REASONS.map((r) => {
    const chip = el("button", { className: "choice-chip", text: r, attrs: { type: "button", "aria-pressed": "false" } });
    chip.addEventListener("click", () => {
      reportChoice = reportChoice === r ? null : r; // 한 번 더 누르면 고른 것을 푼다
      for (const c of reportReasons.children) c.setAttribute("aria-pressed", String(c === chip && reportChoice === r));
      updateReportSubmit();
    });
    return chip;
  }));
  reportBlock.checked = false;
  reportBlockRow.hidden = t.status === "blocked"; // 이미 차단된 대화는 신고만
  updateReportSubmit();
  reportSheet.hidden = false;
  document.body.classList.add("sheet-open");
  reportSheet.querySelector(".sheet").focus();
}

function closeReportSheet({ keepTarget = false } = {}) {
  reportSheet.hidden = true;
  document.body.classList.remove("sheet-open");
  if (!keepTarget) {
    reportTarget = null;
    if (reportFocus && reportFocus.isConnected) reportFocus.focus();
  }
}

async function sendReport(t, reason, block) {
  try {
    const res = await reportThread(t.threadId, reason || undefined, block);
    if (!res || res.error || res.ok === false) throw new Error((res && (res.message || res.error)) || "신고 실패");
    if (block) {
      if (t.status === "waiting" && t.role === "asker") waitingCount = Math.max(0, waitingCount - 1); // 서버도 한도에서 뺀다
      t.status = "blocked";
      t.blockedByMe = true;
      localStatus.set(t.threadId, "blocked");
    }
    toast(reason && block ? "신고하고 차단했어요" : block ? "차단했어요" : "신고했어요. 담당자가 확인해요");
    if (currentThreadId === t.threadId) renderThread(t);
  } catch (err) {
    console.error(err);
    toast(block ? "차단하지 못했어요. 다시 시도해 주세요" : "신고하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
}

reportSubmit.addEventListener("click", async () => {
  const t = reportTarget;
  if (!t || reportSubmit.disabled) return;
  const reason = reportChoice;
  const block = reportBlock.checked && t.status !== "blocked";
  if (!block) {
    reportSubmit.disabled = true;
    await sendReport(t, reason, false);
    closeReportSheet();
    return;
  }
  // 차단은 되돌릴 수 없다 → 확인 시트(5-10). 신고 시트는 닫고 확인 시트만 띄운다
  closeReportSheet({ keepTarget: true });
  openConfirm({
    title: "이 대화를 차단할까요?",
    text: "차단하면 두 사람 모두 이 대화에서 더 쪽지를 보낼 수 없어요. 차단은 풀 수 없어요.",
    okText: reason ? "신고하고 차단하기" : "차단하기",
    danger: true,
    onOk: () => sendReport(t, reason, true),
  });
});
threadMenu.addEventListener("click", openReportSheet);
document.getElementById("reportCancel").addEventListener("click", () => closeReportSheet());
reportSheet.querySelector(".sheet-scrim").addEventListener("click", () => closeReportSheet());
reportSheet.addEventListener("keydown", (e) => { if (e.key === "Escape") closeReportSheet(); });
reportBlock.addEventListener("change", updateReportSubmit);

// 쪽지 검사(checkMessage)에 걸렸을 때: 주의 라벨(짧은 이유) + 그 아래 서버 문구. 전송은 하지 않는다.
// 한도 초과·네트워크 실패 같은 진짜 오류는 빨간 오류 문구(field__error)로 둔다.
const CHECK_LABEL = { 연락처: "연락처가 있어요", 학번: "학번이 있어요", 비방: "보낼 수 없는 표현이 있어요" };
function showCheckWarning(box, check) {
  box.replaceChildren(
    statusLabel("warning", "triangle-alert", check.label || CHECK_LABEL[check.reason] || "보낼 수 없는 내용이 있어요"),
    el("p", { className: "check-warn__text", text: check.message || "이 내용은 쪽지로 보낼 수 없어요. 고쳐서 다시 보내 주세요." }),
  );
  box.hidden = false;
  drawIcons();
}

async function sendInThread(t, input, send, err, warn) {
  const text = input.value.trim();
  if (!text) return;
  send.disabled = true;
  input.disabled = true;
  const fail = (message) => {
    err.replaceChildren(icon("circle-alert"), el("span", { text: message }));
    err.hidden = false;
    input.setAttribute("aria-invalid", "true");
    drawIcons();
  };
  try {
    const check = await checkMessage(text);
    if (check && check.ok === false) {
      showCheckWarning(warn, check); // 입력창 위 주의 라벨 + 문구(8절 익명 쪽지 대화)
      return;
    }
    const res = await sendMessage(t.withId, text);
    if (!res || res.error || res.ok === false) {
      fail((res && (res.message || res.error)) || "쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
      if (res && res.reason === "차단") { t.status = "blocked"; renderDock(t); }
      return;
    }
    const msg = { from: "me", text, at: res.at || new Date().toISOString() };
    const list = localSent.get(t.threadId) || [];
    list.push(msg);
    localSent.set(t.threadId, list);
    t.messages = [...(t.messages || []), msg];
    input.value = "";
    renderThread(t, { keepDock: true });
    readNow(t);
  } catch (e) {
    console.error(e);
    fail("쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
  } finally {
    input.disabled = false;
    send.disabled = input.value.trim() === "";
    input.focus();
  }
}
