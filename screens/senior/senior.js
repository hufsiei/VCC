// 닮은선배 화면 (작업 28) — 1단계: 추천 목록 + 잠김 / 2단계: 선배 프로필 + 쪽지 요청 시트
//   내 쪽지 목록·대화·요청 취소·수락·거절·신고·차단은 내 보관함 · 쪽지 탭으로 옮겼다(11/24, screens/questions/messages.js).
//   여기서는 버튼 상태를 정하려고 getMessages 목록만 읽는다.
// 기준: docs/design-rules.md 7-④·6-6·5-5·5-8·5-9·5-10·8절(선배 프로필·익명 쪽지 요청·기다리는 요청·받은 쪽지 요청·익명 쪽지 대화),
//       docs/spec-v1.md 4장 recommendSeniors·getMe(recommend)·getInbox·listNotes·getMessages·previewNickname·checkMessage·
//       sendMessage·respondRequest·cancelRequest, PRD 4장 닮은선배 행·2-2(쿨다운·횟수 제한 UI 없음, 이름·학번 표시 없음)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
// 학번(studentId·withId)은 화면과 주소에 쓰지 않는다 — 주소의 선배는 표시명 글자(A, B…), 대화는 threadId.
// 주소: ?senior=B(프로필). 예전 주소 ?view=messages·?thread=T-0001은 내 보관함 · 쪽지 탭으로 넘긴다.

import {
  currentUser, getMe, getInbox, listNotes, recommendSeniors,
  getMessages, previewNickname, checkMessage, sendMessage,
} from "../../common/data.js";
import { rememberRequest, localRequests, forgetRequests, unreadOf } from "../questions/bell.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
// 예전 주소(알림·북마크): 내 쪽지·대화는 내 보관함 · 쪽지 탭에 있다(11/24)
{
  const old = new URLSearchParams(location.search);
  if (me && (old.has("thread") || old.get("view") === "messages")) {
    location.replace(`../questions/?tab=messages${old.get("thread") ? `&thread=${encodeURIComponent(old.get("thread"))}` : ""}`);
  }
}
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const LOCK_TEXT = "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요";
const MIN_TEXT = 5;   // 쪽지 첫 문장 최소 글자 수(빈 인사만 보내지 않게)

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
// retryAt(다시 보낼 수 있는 시각, ISO KST — spec sendMessage·recommendSeniors [11/24]) → 아직 그 시각 전이면 「11월 30일부터 다시 보낼 수 있어요」
// 시각이 지났거나 값이 없으면 null(바로 다시 보낼 수 있음). 날짜는 기기 시간대와 상관없이 한국 시간으로 읽는다
function retryText(iso) {
  const at = iso ? new Date(iso) : null;
  if (!at || Number.isNaN(at.getTime()) || at.getTime() <= Date.now()) return null;
  const kst = new Date(at.getTime() + 9 * 3600 * 1000);
  return `${kst.getUTCMonth() + 1}월 ${kst.getUTCDate()}일부터 다시 보낼 수 있어요`;
}
const NO_REQUEST_TEXT = "쪽지 요청을 받지 않는 선배예요"; // sendMessage reason 「추천 제외」(spec 4장 [11/23 추천])
const skeletons = (n, cls = "senior-skeleton") => Array.from({ length: n }, () => el("div", { className: `skeleton ${cls}`, attrs: { "aria-hidden": "true" } }));

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

// 「로/으로」: 마지막 글자에 받침이 있고 그 받침이 ㄹ이 아니면 「으로」(수달 → 수달로, 고래 → 고래로, 곰 → 곰으로)
function josaRo(word) {
  const code = String(word || "").trim().slice(-1).charCodeAt(0) - 0xac00;
  if (code < 0 || code > 11171) return "(으)로";
  const jong = code % 28;
  return jong === 0 || jong === 8 ? "로" : "으로";
}
// 「독일어과 선배 A」 → "A" (주소에 학번 대신 쓰는 글자)
const letterOf = (s) => String(s.nickname || "").trim().split(/\s+/).pop() || "";

// ---------------------------------------------------------------------------
// 2. 상태
// ---------------------------------------------------------------------------

const listArea = document.getElementById("listArea");
let notesById = new Map();
let currentCat = null;          // 고른 분야(global | practice | extra). 처음에는 아무것도 고르지 않는다(11/27)
let currentNoteId = null;       // 고른 세부 활동(노트 id). 분야만 골라서는 정해지지 않는다
let activities = [];            // 내 활동 이력(모든 분야, 최근이 앞) — [{ id, at }]
let activityError = false;      // 활동 이력을 만들 데이터(노트 목록·질문함)를 받지 못했음
let locked = null;              // 선배 추천이 잠겨 있으면 getMe.recommend(열릴 때까지 목록 대신 잠김 안내)
let profile = null;
let seniorsRes = null;          // 마지막 recommendSeniors 응답
let threads = [];               // getMessages.threads(내가 보낸 것·받은 것 모두)
let threadsByWith = new Map();  // 선배(studentId) → 내가 보낸(asker) 대화 — 버튼 상태용
let waitingCount = 0;
let waitingLimit = 3;
let loadSeq = 0;                // 추천 요청 번호 — 늦게 온 옛 응답은 버린다(8절 loadSeniors)

// ---------------------------------------------------------------------------
// 3. 관심 경험 — 분야 칩 3개 → 그 분야의 세부 활동 칩(가로 스크롤) → 고른 활동의 경험자 추천 (11/27)
//    세부 활동 = 내 이력 세 가지를 노트 id로 합친 것(같은 노트는 한 번, 이름이 비슷해도 id가 다르면 다른 활동):
//      ① 해봤노트에서 연 노트 ② 해봤노트 검색으로 찾아 연 노트 — note.js rememberViewed(이 탭 sessionStorage, 사람별, 시각 포함)
//      ③ 관심 등록 = getInbox 질문함 질문의 noteId(궁금한 것 정리하기 포함) + 스크랩(서버에 사람별로 저장)
//    정렬: 시각이 있는 기록(열람·검색·질문)은 활동별 가장 최근 시각 ↓, 시각이 없는 스크랩·예전 열람 기록은 그 뒤에 원래 순서(최근이 위)대로.
//    검색어만 치고 노트를 열지 않은 것은 활동이 아니므로 칩으로 만들지 않는다.
//    주소 ?noteId=(해봤노트·질문함의 「닮은선배 보기」)로 들어오면 그 활동의 분야와 활동을 골라 둔 채 시작한다.
//    추천은 고른 활동(노트 → 프로그램)을 실제로 경험한 선배만 — 서버 recommendSeniors(score.py, 기존 정렬 그대로).
// ---------------------------------------------------------------------------

const timeOf = (q) => String(q.answeredAt || q.askedAt || "");
const CAT_ORDER = ["global", "practice", "extra"];

// 해봤노트 상세에서 연 노트(note.js rememberViewed): [{ id, at, from: "view" | "search" }]. 예전 모양(id 문자열 목록, 최근이 앞)도 읽는다
function viewedNotes() {
  try {
    const list = JSON.parse(sessionStorage.getItem(`viewedNotes:${me ? me.colreg_no : ""}`) || "[]");
    if (!Array.isArray(list)) return [];
    return list.map((x) => (typeof x === "string" ? { id: x, at: "" } : x))
      .filter((x) => x && typeof x.id === "string").map((x) => ({ id: x.id, at: typeof x.at === "string" ? x.at : "" }));
  } catch {
    return [];
  }
}

function collectActivities(inbox, fromUrl) {
  const timed = new Map();   // id → 가장 최근 시각(ms)
  const order = [];          // 시각이 없는 기록의 순서(예전 열람 기록·스크랩)
  const add = (id, at) => {
    if (!id) return;
    const t = at ? Date.parse(at) : NaN;
    if (Number.isNaN(t)) { if (!order.includes(id)) order.push(id); return; }
    if (!timed.has(id) || timed.get(id) < t) timed.set(id, t);
  };
  if (fromUrl) add(fromUrl, new Date().toISOString()); // 방금 「닮은선배 보기」로 고른 활동이 맨 앞
  for (const v of viewedNotes()) add(v.id, v.at);
  for (const q of (inbox && inbox.questions) || []) if (q.noteId) add(q.noteId, timeOf(q));
  for (const s of (inbox && inbox.scraps) || []) add(s.noteId, "");
  const sorted = [...timed.entries()].sort((a, b) => b[1] - a[1]).map(([id, t]) => ({ id, at: new Date(t).toISOString() }));
  const rest = order.filter((id) => !timed.has(id)).map((id) => ({ id, at: "" }));
  return [...sorted, ...rest].filter((a) => notesById.has(a.id)); // 노트 목록에 없는 id(지워진 노트 등)는 뺀다
}

const activitiesOf = (cat) => activities.filter((a) => CATEGORY[notesById.get(a.id).type] === cat);

// --- 「나의 프로필 요약」(SOFT BLUE): 학과·학년·이중전공 / 관심 경험: 분야 칩 3개 / 세부 활동 칩(분야를 골랐을 때만). 이름·학번은 쓰지 않는다 ---
function renderProfile() {
  const box = document.getElementById("profileBox");
  if (!profile) { box.replaceChildren(); return; }
  const catChips = CAT_ORDER.map((cat) => {
    const chip = el("button", { className: "choice-chip interest-chip", text: CATEGORY_NAME[cat], attrs: { type: "button", "aria-pressed": String(cat === currentCat) } });
    chip.addEventListener("click", () => selectCategory(cat));
    return chip;
  });
  box.replaceChildren(el("div", { className: "profile-card" }, [
    el("span", { className: "profile-card__title", text: "나의 프로필 요약" }),
    el("div", { className: "profile-card__line" }, [
      el("span", { className: "profile-card__dept", text: profile.crs_nm || "학과 –" }),
      el("span", { text: Number.isFinite(profile.regst_grad) ? `${profile.regst_grad}학년` : "" }),
      profile.dbl_mjr_nm ? el("span", { className: "sub", text: `이중전공 ${profile.dbl_mjr_nm}` }) : null,
    ]),
    el("div", { className: "profile-card__line interest-row", attrs: { role: "group", "aria-label": "관심 경험 분야" } }, [
      el("span", { className: "interest-row__label", text: "관심 경험:" }),
      ...catChips,
    ]),
    currentCat ? activityRow() : null,
  ]));
  drawIcons();
  if (currentCat) updateArrows();
}

// 세부 활동 줄: [‹] 칩 목록(가로 스크롤, 줄바꿈 없음) [›]. 화살표는 마우스가 있는 PC에서만(CSS), 넘칠 때만 보인다
// 스크롤(스와이프·화살표)은 보이는 위치만 바꾸고, 칩을 눌러야(클릭) 활동이 바뀐다
function activityRow() {
  const list = activitiesOf(currentCat);
  if (activityError && !list.length) {
    // 데이터 없음과 구분: 못 받은 것이면 오류 라벨 + 다시 시도(6-5)
    const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
    retry.addEventListener("click", start);
    return el("div", { className: "activity-state" }, [
      statusLabel("error", "circle-alert", "활동 목록을 불러오지 못했어요"),
      retry,
    ]);
  }
  if (!list.length) {
    return el("div", { className: "activity-state" }, [
      el("p", { className: "activity-state__text", text: "아직 확인한 활동이 없어요." }),
      el("a", { className: "link-more", text: "해봤노트 둘러보기 ›", attrs: { href: "../note/" } }),
    ]);
  }
  const track = el("div", { className: "activity-track", attrs: { id: "activityTrack", role: "group", "aria-label": `${CATEGORY_NAME[currentCat]} 세부 활동` } },
    list.map((a) => {
      const name = notesById.get(a.id).program;
      // 긴 이름은 칩 최대 너비에서 말줄임 — 전체 이름은 title(PC 마우스 올림)·aria-label(화면 읽기)로
      return el("button", {
        className: "choice-chip activity-chip",
        attrs: { type: "button", "aria-pressed": String(a.id === currentNoteId), title: name, "aria-label": name, "data-id": a.id },
      }, [el("span", { className: "activity-chip__text", text: name })]);
    }));
  // 스와이프하다 손을 뗀 것은 누른 것으로 치지 않는다(8px 넘게 움직였거나 목록이 밀렸으면 클릭 무시)
  let downX = null;
  let downScroll = 0;
  track.addEventListener("pointerdown", (e) => { downX = e.clientX; downScroll = track.scrollLeft; });
  track.addEventListener("click", (e) => {
    const chip = e.target.closest(".activity-chip");
    const moved = downX !== null && e.detail > 0 && (Math.abs(e.clientX - downX) > 8 || Math.abs(track.scrollLeft - downScroll) > 8);
    downX = null;
    if (!chip || moved) return;
    selectActivity(chip.dataset.id);
  });
  track.addEventListener("scroll", updateArrows, { passive: true });
  const arrow = (dir) => {
    const b = el("button", { className: "icon-btn activity-arrow", attrs: { type: "button", "data-dir": dir, "aria-label": dir < 0 ? "이전 활동 보기" : "다음 활동 보기", "aria-controls": "activityTrack" } },
      [icon(dir < 0 ? "chevron-left" : "chevron-right")]);
    b.addEventListener("click", () => {
      const smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      track.scrollBy({ left: dir * Math.max(track.clientWidth * 0.8, 120), behavior: smooth ? "smooth" : "auto" });
    });
    return b;
  };
  return el("div", { className: "activity-row" }, [arrow(-1), track, arrow(1)]);
}

// 화살표: 맨 앞이면 ‹ 비활성, 맨 끝이면 › 비활성, 칩이 다 보이면 둘 다 숨김
function updateArrows() {
  const track = document.getElementById("activityTrack");
  if (!track) return;
  const row = track.parentElement;
  const max = track.scrollWidth - track.clientWidth;
  const overflow = max > 1;
  for (const b of row.querySelectorAll(".activity-arrow")) {
    b.hidden = !overflow;
    b.disabled = Number(b.dataset.dir) < 0 ? track.scrollLeft <= 1 : track.scrollLeft >= max - 1;
  }
}
window.addEventListener("resize", updateArrows);

// 분야를 바꾸면: 고른 활동·추천 목록을 비우고, 활동 목록은 맨 앞(왼쪽)부터
function selectCategory(cat) {
  if (cat === currentCat) return;
  currentCat = cat;
  currentNoteId = null;
  loadSeq += 1;                 // 불러오는 중이던 추천 응답은 버린다
  seniorsRes = null;
  setNoteInUrl(null);
  renderProfile();
  renderListArea();
}

// 같은 분야 안에서 다른 활동을 고르면 그 활동 기준으로 다시 추천. 이미 고른 칩을 다시 눌러도 그대로
function selectActivity(id) {
  if (!id || id === currentNoteId) return;
  const before = document.getElementById("activityTrack");
  const keep = before ? before.scrollLeft : 0;
  currentNoteId = id;
  setNoteInUrl(id);
  renderProfile();
  const track = document.getElementById("activityTrack");
  if (track) { track.scrollLeft = keep; updateArrows(); } // 다시 그려도 보던 위치 그대로
  renderListArea();
}

// 주소에도 남겨 새로고침·뒤로가기에서 같은 활동(해봤노트의 「닮은선배 보기」와 같은 모양)
function setNoteInUrl(id) {
  const url = new URL(location.href);
  if (id) url.searchParams.set("noteId", id);
  else url.searchParams.delete("noteId");
  for (const k of ["senior", "view", "thread"]) url.searchParams.delete(k);
  history.replaceState(null, "", url.pathname + url.search);
}

// 목록 자리: 잠김이면 잠김 안내, 활동을 골랐을 때만 추천 제목·카드, 그 밖에는 비워 둔다
function renderListArea() {
  if (locked) { renderLocked(locked); return; }
  if (!currentNoteId) {
    listArea.setAttribute("aria-busy", "false");
    listArea.replaceChildren();
    return;
  }
  loadSeniors(false);
}

// ---------------------------------------------------------------------------
// 4. 쪽지 상태 (getMessages) — 버튼 상태·내 쪽지 목록·대화창이 같이 쓴다
// ---------------------------------------------------------------------------

const retryWith = new Map();   // 선배 studentId → retryAt(sendMessage가 「취소」로 막으며 알려 준 값)
const optedOut = new Set();    // 선배 studentId — sendMessage가 「추천 제외」로 막은 선배(새로고침 전까지)

// 쪽지 목록(getMessages) — 버튼 상태(요청 보냄·쪽지 보기·대기 3건)와 「내 쪽지」 숫자에 쓴다
// 이 탭에서 보낸 요청(bell.js가 sessionStorage에 기억)은 서버 목록에 아직 없으면 붙여 둔다(mock은 기억하지 않아서 필요)
async function loadThreads() {
  try {
    const res = await getMessages();
    if (!res || res.error) throw new Error((res && res.error) || "쪽지 없음");
    const server = Array.isArray(res.threads) ? res.threads : [];
    const ids = new Set(server.map((t) => t.threadId));
    const local = localRequests();
    forgetRequests(local.filter((t) => ids.has(t.threadId)).map((t) => t.threadId));
    threads = [...server, ...local.filter((t) => !ids.has(t.threadId))];
    threadsByWith = new Map(threads.filter((t) => t.role === "asker").map((t) => [t.withId, t]));
    const localWaiting = threads.filter((t) => t.role === "asker" && t.status === "waiting").length;
    waitingCount = Math.max(Number.isFinite(res.waitingCount) ? res.waitingCount : 0, localWaiting);
    if (Number.isFinite(res.waitingLimit)) waitingLimit = res.waitingLimit;
    renderMessagesBadge();
    return true;
  } catch (err) {
    console.error(err); // 쪽지 상태를 못 받아도 목록은 보여 준다(보낼 때 서버가 한도를 다시 막는다)
    return false;
  }
}

// 「내 쪽지」 버튼 옆 숫자: 받은 수락 대기 요청 + 안 읽은 쪽지
const MESSAGES_URL = "../questions/?tab=messages";
const threadUrl = (t) => `${MESSAGES_URL}&thread=${encodeURIComponent(t.threadId)}`;
function renderMessagesBadge() {
  const btn = document.getElementById("myMessagesBtn");
  btn.querySelector(".count-badge")?.remove();
  const n = threads.filter((t) => t.role === "senior" && t.status === "waiting").length
    + threads.reduce((sum, t) => sum + unreadOf(t), 0);
  btn.setAttribute("aria-label", n ? `내 쪽지, 새 소식 ${n}개` : "내 쪽지");
  if (n) btn.append(el("span", { className: "count-badge", text: n > 9 ? "9+" : n, attrs: { "aria-hidden": "true" } }));
}

// 「쪽지 요청」 자리에 들어갈 것 — 카드와 프로필이 같이 쓴다
function requestControl(s, { block = false } = {}) {
  const thread = threadsByWith.get(s.studentId);
  const status = thread ? thread.status : null;
  const cls = `btn${block ? " btn--block" : ""}`;

  if (status === "waiting") {
    return el("div", { className: "request-note" }, [
      el("button", { className: cls, text: "요청 보냄", attrs: { type: "button", disabled: "" } }),
      el("p", { className: "btn-reason" }, [icon("clock"), el("span", { text: "선배가 수락하면 대화가 열려요" })]),
    ]);
  }
  if (status === "accepted") {
    return el("a", { className: `${cls} btn--primary`, text: "쪽지 보기", attrs: { href: threadUrl(thread) } }); // 내 보관함 · 쪽지 대화
  }
  if (status === "declined") {
    // 선배가 요청을 받지 않음: 다시 누를 수 없게 비활성 + 이유(5-4). 거절은 다시 보낼 수 없어 retryAt이 없다(spec recommendSeniors)
    return el("div", { className: "request-note" }, [
      el("button", { className: cls, text: "쪽지 요청", attrs: { type: "button", disabled: "" } }),
      el("p", { className: "btn-reason" }, [icon("info"), el("span", { text: "선배가 요청을 수락하지 않았어요" })]),
    ]);
  }
  if (status === "blocked") {
    return el("div", { className: "request-note" }, [
      el("button", { className: cls, text: "쪽지 요청", attrs: { type: "button", disabled: "" } }),
      el("p", { className: "btn-reason" }, [icon("ban"), el("span", { text: "더 이어 갈 수 없는 대화예요" })]),
    ]);
  }
  if (optedOut.has(s.studentId)) {
    // 추천받기를 끈 선배(보내 보니 서버가 「추천 제외」로 막음): 비활성 + 버튼 아래 이유(5-4). 주의 라벨은 요청 시트에서 보인다
    return el("div", { className: "request-note" }, [
      el("button", { className: cls, text: "쪽지 요청", attrs: { type: "button", disabled: "" } }),
      el("p", { className: "btn-reason" }, [icon("triangle-alert"), el("span", { text: NO_REQUEST_TEXT })]),
    ]);
  }
  // 내가 요청을 취소한 선배: 취소 + 7일까지 비활성 + 다시 보낼 수 있는 날(spec [11/24 retryAt]). 7일이 지나면 아래로 내려가 다시 요청할 수 있다
  const retry = retryText(s.retryAt || (thread && thread.retryAt) || retryWith.get(s.studentId));
  if (retry) {
    return el("div", { className: "request-note" }, [
      el("button", { className: cls, text: "쪽지 요청", attrs: { type: "button", disabled: "" } }),
      el("p", { className: "btn-reason" }, [icon("clock"), el("span", { text: retry })]),
    ]);
  }
  if (s.requestsFull) {
    // 받는 한도(선배 대기 5건): 쪽지 대신 질문함으로(7-④, spec recommendSeniors requestsFull)
    return el("div", { className: "request-note" }, [
      statusLabel("neutral", "clock", "지금은 요청이 많아요"),
      el("a", { className: `${cls} btn--secondary`, text: "질문함으로 묻기", attrs: { href: "../talk/?mode=ask" } }),
    ]);
  }
  if (waitingCount >= waitingLimit) {
    // 보내는 한도(대기 3건): 시트를 열지 않고 안내 + 내 보관함 · 쪽지 탭으로(8절)
    const link = el("a", { className: "btn btn--text", text: "기다리는 요청 보기", attrs: { href: MESSAGES_URL } });
    return el("div", { className: "request-note" }, [
      el("p", { className: "btn-reason" }, [icon("info"), el("span", { text: `답을 기다리는 쪽지가 ${waitingLimit}건이에요` })]),
      link,
    ]);
  }
  const b = el("button", { className: `${cls} btn--primary`, text: "쪽지 요청", attrs: { type: "button" } });
  b.addEventListener("click", () => openRequestSheet(s));
  return b;
}

// ---------------------------------------------------------------------------
// 5. 추천 목록 — 처음 3명, 「선배 더 보기」로 3명씩 최대 9명(서버가 정함), 끝나면 안내 문구
// ---------------------------------------------------------------------------

// 서버 reasons(맨 앞은 늘 「희망 프로그램을 경험했어요」) → 일치 칩(관심 경험·전공·이중전공·단과대·비교과)
function matchChips(reasons) {
  const chips = [];
  for (const r of reasons || []) {
    if (r.includes("희망 프로그램")) chips.push("관심 경험");
    // 「한국외국어대학교 … 함께 이수」는 '대학'도 들어 있어 단과대 검사보다 먼저 본다
    else if (r.includes("이수")) chips.push("비교과");
    else if (r.includes("이중전공")) chips.push("이중전공");
    else if (/과$|학부$|전공$/.test(r.replace(/^같은\s*/, ""))) chips.push("전공");
    else if (r.includes("대학")) chips.push("단과대");
  }
  // 순서는 디자인 규칙 7-④대로(관심 경험 · 전공 · 이중전공 · 단과대 · 비교과)
  const ORDER = ["관심 경험", "전공", "이중전공", "단과대", "비교과"];
  return ORDER.filter((c) => chips.includes(c));
}

// 카드의 추천 이유는 한 줄: 첫 이유 + 「외 N개」(아래 일치 칩과 겹치지 않게). 전체 이유는 프로필에서 목록으로
function reasonText(s) {
  const reasons = (s.reasons || []).filter(Boolean);
  if (!reasons.length) return "희망 프로그램을 경험했어요";
  return reasons.length > 1 ? `${reasons[0]} 외 ${reasons.length - 1}개` : reasons[0];
}

function experienceTags(note) {
  if (!note) return null;
  const cat = CATEGORY[note.type];
  return el("div", { className: "tag-row" }, [el("span", { className: `category-tag cat-${cat}`, text: CATEGORY_NAME[cat] }), el("span", { className: "sub", text: note.program })]);
}

// 카드 = 아바타·표시명 → 추천 이유 1줄 → 일치 칩 → 버튼. 분야·활동명 줄은 11/27에 뺐다(위 「나의 프로필 요약」에서 고른 활동이 보이므로)
function seniorCard(s) {
  const profileBtn = el("button", { className: "btn btn--outline", text: "프로필 보기", attrs: { type: "button" } });
  profileBtn.addEventListener("click", () => go(`senior=${encodeURIComponent(letterOf(s))}`));

  return el("article", { className: "card senior-card" }, [
    el("div", { className: "senior-card__top" }, [
      el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
      el("h3", { className: "senior-card__name", text: s.nickname || "선배" }),
    ]),
    // 추천 이유 1줄(추천이 만든 것 → MINT 표시) — 문장은 서버가 준 그대로 잇는다
    el("p", { className: "senior-card__reason" }, [
      el("span", { className: "ai-mark", attrs: { "aria-hidden": "true" } }, [icon("sparkles")]),
      el("span", { text: reasonText(s) }),
    ]),
    el("div", { className: "tag-row", attrs: { "aria-label": "일치 항목" } }, matchChips(s.reasons).map((c) => el("span", { className: "ai-chip", text: c }))),
    el("div", { className: "btn-row" }, [profileBtn, requestControl(s)]),
  ]);
}

function renderList(res) {
  seniorsRes = res;
  const seniors = res.seniors || [];
  const head = el("div", { className: "list-head" }, [
    el("h2", { className: "section-title", text: `추천 선배 ${seniors.length}명` }), // N = 실제 카드 수(7-④)
    res.newCount > 0 ? statusLabel("neutral", "sparkles", `새로 비슷한 선배 ${res.newCount}명`) : null,
  ]);
  const children = [];
  if (res.recomputed) children.push(statusLabel("info", "info", "내 기록이 바뀌어 다시 추천할 수 있어요"));
  children.push(head);

  if (!seniors.length) {
    children.push(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 해당 활동을 경험한 선배가 없어요" }),
      el("p", { className: "sub", text: "궁금한 점은 질문함에 남기면 선배 인터뷰 때 먼저 물어볼게요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/?mode=ask" } }),
    ]));
  } else {
    children.push(el("div", { className: "senior-list" }, seniors.map((s) => seniorCard(s))));
    if (res.hasMore) {
      const more = el("button", { className: "btn btn--secondary btn--block list-more", text: "선배 더 보기", attrs: { type: "button" } });
      more.addEventListener("click", () => loadSeniors(true, more));
      children.push(more);
    } else {
      // 비활성 버튼으로 두지 않고 안내 문구(7-④)
      children.push(el("p", { className: "list-end", text: "비슷한 선배를 모두 보여드렸어요" }));
    }
  }
  listArea.setAttribute("aria-busy", "false");
  listArea.replaceChildren(...children);
  drawIcons();
}

// --- 잠김(6-6, 11/22 선배 추천 열림): 숨기지 않고 조건 문구 + 두 길 ---
function renderLocked(recommend) {
  const talk = (recommend && recommend.talk) || {};
  const need = (recommend && recommend.need) || 3;
  const progress = Number.isFinite(talk.answered) ? `들려주기 답변 ${Math.min(talk.answered, need)}/${need}` : null;
  listArea.setAttribute("aria-busy", "false");
  listArea.replaceChildren(el("div", { className: "state-box" }, [
    icon("lock"),
    el("p", { className: "state-box__title", text: "선배 추천이 아직 잠겨 있어요" }),
    el("p", { className: "btn-reason" }, [icon("lock"), el("span", { text: LOCK_TEXT })]),
    progress ? el("span", { className: "status-label status-label--neutral" }, [el("span", { text: progress })]) : null,
    el("div", { className: "detail-actions" }, [
      el("a", { className: "btn btn--primary btn--block", text: "경험 들려주기", attrs: { href: "../talk/?mode=tell" } }),
      el("a", { className: "btn btn--outline btn--block", text: "궁금한 것 정리하기", attrs: { href: "../talk/?mode=ask" } }),
    ]),
    el("button", { className: "btn btn--block", text: "쪽지 요청", attrs: { type: "button", disabled: "" } }),
  ]));
  drawIcons();
}

// 요청마다 번호를 붙인다. 불러오는 중에 다른 활동·분야 칩을 누르면 새 요청을 바로 보내고,
// 늦게 도착한 옛 응답(번호가 다르거나 고른 활동이 바뀐 것)은 그리지 않고 버린다.
let loading = false;
async function loadSeniors(more, moreBtn) {
  if (!currentNoteId) return;
  if (more && loading) return; // 「선배 더 보기」는 불러오는 중에 다시 누르지 않게
  const seq = ++loadSeq;
  const noteId = currentNoteId;
  const isStale = () => seq !== loadSeq || noteId !== currentNoteId;
  loading = true;
  if (more && moreBtn) {
    moreBtn.disabled = true;
    moreBtn.textContent = "불러오는 중…";
  } else {
    listArea.setAttribute("aria-busy", "true");
    listArea.replaceChildren(...skeletons(2));
  }
  try {
    const res = await recommendSeniors(noteId, more);
    if (isStale()) return; // 그 사이 다른 칩을 눌렀음 — 새 요청의 응답만 그린다
    if (res && res.locked) { locked = res.recommend || {}; renderLocked(locked); }
    else if (!res || res.error || !Array.isArray(res.seniors)) throw new Error((res && res.error) || "추천 없음");
    else renderList(res);
  } catch (err) {
    if (isStale()) return;
    console.error(err);
    if (more && moreBtn) {
      moreBtn.disabled = false;
      moreBtn.textContent = "선배 더 보기";
      toast("더 불러오지 못했어요. 다시 시도해 주세요", "circle-alert");
    } else {
      listArea.setAttribute("aria-busy", "false");
      listArea.replaceChildren(errorBox(() => loadSeniors(false)));
      drawIcons();
    }
  } finally {
    if (seq === loadSeq) loading = false;
  }
  if (isStale()) return;
  if (new URLSearchParams(location.search).has("senior")) route(); // 프로필 주소로 바로 들어온 경우
}

// ---------------------------------------------------------------------------
// 6. 화면 이동 — 주소로 정한다. 들어간 화면은 pushState라 브라우저 뒤로도 같이 동작
// ---------------------------------------------------------------------------

const views = {
  senior: document.getElementById("viewSenior"),
  profile: document.getElementById("viewProfile"),
};
let movedInside = false; // 이 화면 안에서 들어왔으면 ←는 브라우저 뒤로(목록 스크롤 유지)
let listScrollY = 0;

function show(name) {
  for (const [k, v] of Object.entries(views)) v.hidden = k !== name;
}

function go(query) {
  if (views.senior.hidden === false) listScrollY = window.scrollY;
  movedInside = true;
  const url = new URL(location.href);
  url.searchParams.delete("senior");
  const extra = new URLSearchParams(query);
  for (const [k, v] of extra) url.searchParams.set(k, v);
  history.pushState({ inner: true }, "", url.pathname + url.search);
  route();
}

function goBack() {
  if (movedInside) {
    movedInside = false;
    history.back();
  } else {
    const url = new URL(location.href);
    url.searchParams.delete("senior");
    history.replaceState(null, "", url.pathname + url.search);
    route();
  }
}

function findSenior(letter) {
  return ((seniorsRes && seniorsRes.seniors) || []).find((s) => letterOf(s) === letter) || null;
}

function route() {
  const p = new URLSearchParams(location.search);
  if (p.get("senior") && findSenior(p.get("senior"))) {
    show("profile");
    window.scrollTo(0, 0);
    renderProfilePage(findSenior(p.get("senior")));
  } else {
    show("senior");
    document.title = "닮은선배 · 외대人사이드";
    if (seniorsRes) renderList(seniorsRes); // 쪽지 상태가 바뀌었을 수 있으니 버튼을 다시 그림
    window.scrollTo(0, listScrollY);
  }
}

document.getElementById("profileBack").addEventListener("click", goBack);
window.addEventListener("popstate", () => {
  movedInside = false;
  route();
});

// ---------------------------------------------------------------------------
// 7. 선배 프로필(2단계, 8절) — 상세 헤더 → 중립 아바타 + 표시명 → 경험 태그 → 추천 이유 → 하단 고정 「쪽지 요청」
// ---------------------------------------------------------------------------

function renderProfilePage(s) {
  const note = notesById.get(currentNoteId);
  document.getElementById("profileTitle").textContent = s.nickname || "선배 프로필";
  document.title = `${s.nickname || "선배"} · 닮은선배`;
  document.getElementById("profileBody").replaceChildren(
    el("div", { className: "profile-head" }, [
      el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
      el("h1", { className: "senior-card__name", text: s.nickname || "선배" }),
      el("p", { className: "sub", text: "이름과 학번은 보이지 않아요. 쪽지도 이 이름으로 주고받아요." }),
    ]),
    el("section", { className: "card" }, [
      el("h2", { className: "section-title", text: "경험" }),
      experienceTags(note) || el("p", { className: "sub", text: "–" }),
    ]),
    el("section", { className: "card" }, [
      el("h2", { className: "section-title", text: "추천 이유" }),
      el("ul", { className: "profile-reasons" }, (s.reasons && s.reasons.length ? s.reasons : ["희망 프로그램을 경험했어요"]).map((r) =>
        el("li", {}, [el("span", { className: "ai-mark", attrs: { "aria-hidden": "true" } }, [icon("sparkles")]), el("span", { text: r })]))),
      el("div", { className: "tag-row" }, matchChips(s.reasons).map((c) => el("span", { className: "ai-chip", text: c }))),
    ]),
  );
  // 하단 고정 Primary 「쪽지 요청」(상태에 따라 요청 보냄·쪽지 보기·안내)
  document.getElementById("profileDock").replaceChildren(requestControl(s, { block: true }));
  drawIcons();
}

// 쪽지 검사(checkMessage)에 걸렸을 때: 주의 라벨(짧은 이유) + 그 아래 서버 문구. 전송은 하지 않는다.
// 한도 초과·네트워크 실패 같은 진짜 오류는 지금처럼 빨간 오류 문구(field__error)로 둔다.
const CHECK_LABEL = { 연락처: "연락처가 있어요", 학번: "학번이 있어요", 비방: "보낼 수 없는 표현이 있어요" };
function showCheckWarning(box, check) {
  box.replaceChildren(
    statusLabel("warning", "triangle-alert", check.label || CHECK_LABEL[check.reason] || "보낼 수 없는 내용이 있어요"),
    el("p", { className: "check-warn__text", text: check.message || "이 내용은 쪽지로 보낼 수 없어요. 고쳐서 다시 보내 주세요." }),
  );
  box.hidden = false;
  drawIcons();
}

// ---------------------------------------------------------------------------
// 8. 쪽지 요청 바텀시트(8절) — 내 익명 이름 안내(previewNickname) + 첫 쪽지 + 연락처·학번 검사(checkMessage)
//     → sendMessage. 서버가 막으면(한도·선배한도·잠김·차단) 그 message를 그대로 보여 준다.
// ---------------------------------------------------------------------------

const sheet = document.getElementById("requestSheet");
const nickBox = document.getElementById("requestNick");
const textBox = document.getElementById("requestText");
const errorLine = document.getElementById("requestError");
const submitBtn = document.getElementById("requestSubmit");
const reasonLine = document.getElementById("requestReason");
let target = null;
let targetNick = "";
let sending = false;
let lastFocus = null;

const warnLine = document.getElementById("requestWarn");

function showError(message) {
  errorLine.replaceChildren(icon("circle-alert"), el("span", { text: message }));
  errorLine.hidden = false;
  textBox.setAttribute("aria-invalid", "true");
  drawIcons();
}
function clearError() {
  errorLine.hidden = true;
  errorLine.replaceChildren();
  warnLine.hidden = true;
  warnLine.replaceChildren();
  textBox.removeAttribute("aria-invalid");
}

function updateSubmit() {
  const len = textBox.value.trim().length;
  submitBtn.disabled = sending || len < MIN_TEXT || !target || optedOut.has(target.studentId); // 추천 제외 선배는 다시 못 보냄
  // 입력칸 바로 아래 안내: 몇 자부터 보낼 수 있는지 + 지금 글자 수
  document.getElementById("requestHelp").textContent = len < MIN_TEXT
    ? `${MIN_TEXT}자 이상 적어 주세요 · 지금 ${len}자`
    : `${len}/${textBox.maxLength}자`;
  // 버튼 아래 비활성 이유(5-4)
  reasonLine.hidden = len >= MIN_TEXT;
  reasonLine.querySelector("span").textContent = len === 0 ? "보낼 내용을 적어 주세요" : `${MIN_TEXT - len}자 더 적으면 보낼 수 있어요`;
}
textBox.addEventListener("input", () => {
  clearError();
  updateSubmit();
});

async function openRequestSheet(s) {
  target = s;
  targetNick = "";
  lastFocus = document.activeElement;
  document.getElementById("requestTitle").textContent = `${s.nickname || "선배"}에게 쪽지 요청`;
  textBox.value = "";
  clearError();
  nickBox.replaceChildren(el("div", { className: "skeleton", attrs: { "aria-hidden": "true", style: "height:28px" } }));
  updateSubmit();
  sheet.hidden = false;
  document.body.classList.add("sheet-open");
  sheet.querySelector(".sheet").focus();
  drawIcons();

  // 내 익명 이름은 시트를 여는 순간 서버가 정한다(대화마다 새로, 학과 없음)
  try {
    const res = await previewNickname(s.studentId);
    if (target !== s) return;
    if (res && res.locked) {
      closeRequestSheet();
      toast(res.message || LOCK_TEXT, "lock");
      return;
    }
    if (!res || res.error || !res.myNickname) throw new Error((res && res.error) || "닉네임 없음");
    targetNick = res.myNickname;
    nickBox.replaceChildren(statusLabel("info", "info", `선배에게는 '${res.myNickname}'${josaRo(res.myNickname)} 보여요`));
  } catch (err) {
    console.error(err);
    nickBox.replaceChildren(statusLabel("info", "info", "선배에게는 익명 이름으로 보여요"));
  }
  drawIcons();
}

function closeRequestSheet() {
  if (sending) return;
  sheet.hidden = true;
  document.body.classList.remove("sheet-open");
  target = null;
  if (lastFocus && lastFocus.isConnected) lastFocus.focus();
}

submitBtn.addEventListener("click", async () => {
  if (!target || submitBtn.disabled) return;
  const text = textBox.value.trim();
  const s = target;
  sending = true;
  updateSubmit();
  submitBtn.textContent = "보내는 중…";
  try {
    // ① 연락처·학번·비방 검사(코드 정규식 — spec checkMessage). 걸리면 보내지 않고 이유를 보여 준다
    const check = await checkMessage(text);
    if (check && check.ok === false) {
      showCheckWarning(warnLine, check); // 입력칸 위 주의 라벨 + 문구(3-4·8절, 작업 28 완료 기준)
      return;
    }
    // ② 보내기 — 서버가 한도·잠김·차단을 다시 막는다
    const res = await sendMessage(s.studentId, text);
    if (res && res.reason === "추천 제외") {
      // 추천받기를 끈 선배: 오류(빨강)가 아니라 주의 라벨 + 서버 문구, 보내기 버튼은 막고 뒤 카드도 비활성으로
      optedOut.add(s.studentId);
      showCheckWarning(warnLine, { label: NO_REQUEST_TEXT, message: "다른 선배에게 보내거나, 궁금한 것을 질문함에 남겨 주세요." });
      if (seniorsRes) renderList(seniorsRes);
      if (!views.profile.hidden) renderProfilePage(s);
      return;
    }
    if (!res || res.error || res.ok === false) {
      showError((res && (res.message || res.error)) || "쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
      if (res && res.reason === "한도") waitingCount = waitingLimit;
      if (res && res.reason === "취소" && res.retryAt) {
        // 취소한 선배에게 7일 안에 다시 보냄: 카드에 다시 보낼 수 있는 날을 붙인다
        retryWith.set(s.studentId, res.retryAt);
        if (seniorsRes) renderList(seniorsRes);
        if (!views.profile.hidden) renderProfilePage(s);
      }
      return;
    }
    // 성공: 이 선배는 「요청 보냄」, 대기 수 +1
    const at = res.at || new Date().toISOString();
    // mock sendMessage는 누구에게 보내든 같은 threadId(T-0001)를 돌려준다 → 다른 선배와의 대화를 덮지 않게 이 화면에서만 따로 둔다
    const clash = threads.find((x) => x.threadId === res.threadId && x.withId !== s.studentId);
    const tid = clash ? `${res.threadId}~${letterOf(s)}` : res.threadId;
    const thread = { threadId: tid, role: "asker", withId: s.studentId, nickname: s.nickname, myNickname: res.myNickname || targetNick, status: "waiting", requestedAt: at, unread: 0, messages: [] };
    rememberRequest({ ...thread, messages: [{ from: "me", text, at }] }); // 내 보관함 · 쪽지 탭에도 바로 보이게(mock용)
    const existing = threads.find((x) => x.threadId === tid);
    if (existing) Object.assign(existing, { status: "waiting" });
    else threads.push({ ...thread, messages: [{ from: "me", text, at }] });
    threadsByWith.set(s.studentId, existing || threads[threads.length - 1]);
    waitingCount += 1;
    sending = false;
    closeRequestSheet();
    toast("쪽지 요청을 보냈어요. 선배가 수락하면 대화가 열려요");
    if (seniorsRes) renderList(seniorsRes);
    if (!views.profile.hidden) renderProfilePage(s);
  } catch (err) {
    console.error(err);
    showError("쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
  } finally {
    sending = false;
    submitBtn.textContent = "쪽지 요청";
    updateSubmit();
  }
});
document.getElementById("requestCancel").addEventListener("click", closeRequestSheet);
sheet.querySelector(".sheet-scrim").addEventListener("click", closeRequestSheet);
sheet.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeRequestSheet();
});

// ---------------------------------------------------------------------------
// 9. 시작 — getMe(프로필·열림 상태) + getInbox(관심 등록: 질문함·스크랩) + listNotes(활동 이름·분야) + getMessages(요청 상태)
// ---------------------------------------------------------------------------

async function start() {
  const p = new URLSearchParams(location.search);
  listArea.setAttribute("aria-busy", "true");
  listArea.replaceChildren(...skeletons(2));
  try {
    let inboxFailed = false;
    let notesFailed = false;
    const [meInfo, inbox, list] = await Promise.all([
      getMe(),
      getInbox().then((r) => { if (!r || r.error) throw new Error((r && r.error) || "보관함 없음"); return r; })
        .catch((err) => { console.error(err); inboxFailed = true; return null; }),
      listNotes({}).then((r) => { if (!r || r.error || !Array.isArray(r.notes)) throw new Error((r && r.error) || "노트 없음"); return r; })
        .catch((err) => { console.error(err); notesFailed = true; return { notes: [] }; }),
      loadThreads(),
    ]);
    if (!meInfo || meInfo.error) throw new Error((meInfo && meInfo.error) || "내 정보 없음");
    profile = meInfo;
    notesById = new Map(list.notes.map((n) => [n.id, n]));
    activityError = notesFailed || inboxFailed;
    activities = collectActivities(inbox, p.get("noteId"));
    // 열림 상태는 getMe.recommend가 먼저 알려 준다(서버도 recommendSeniors에서 막음)
    locked = meInfo.recommend && meInfo.recommend.ready === false ? meInfo.recommend : null;

    // 처음에는 분야·활동 모두 고르지 않은 상태. 「닮은선배 보기」(?noteId=)로 왔으면 그 활동을 골라 둔다
    const fromUrl = notesById.get(p.get("noteId"));
    currentCat = fromUrl ? CATEGORY[fromUrl.type] : null;
    currentNoteId = fromUrl ? fromUrl.id : null;
    if (!fromUrl && p.has("noteId")) setNoteInUrl(null);
    renderProfile();
    renderListArea();
  } catch (err) {
    console.error(err);
    listArea.setAttribute("aria-busy", "false");
    listArea.replaceChildren(errorBox(start));
    drawIcons();
  }
}

drawIcons();
if (me) start();
