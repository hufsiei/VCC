// 닮은선배 화면 (작업 28) — 1단계: 추천 목록 + 잠김 / 2단계: 선배 프로필 + 쪽지 요청 시트
//   3단계: 내 쪽지 목록(받은 요청·대화·보낸 요청) + 대화창(5초 폴링) + 요청 취소·수락·거절
// 기준: docs/design-rules.md 7-④·6-6·5-5·5-8·5-9·5-10·8절(선배 프로필·익명 쪽지 요청·기다리는 요청·받은 쪽지 요청·익명 쪽지 대화),
//       docs/spec-v1.md 4장 recommendSeniors·getMe(recommend)·getInbox·listNotes·getMessages·previewNickname·checkMessage·
//       sendMessage·respondRequest·cancelRequest, PRD 4장 닮은선배 행·2-2(쿨다운·횟수 제한 UI 없음, 이름·학번 표시 없음)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
// 학번(studentId·withId)은 화면과 주소에 쓰지 않는다 — 주소의 선배는 표시명 글자(A, B…), 대화는 threadId.
// 주소: ?senior=B(프로필) · ?view=messages(내 쪽지) · ?thread=T-0001(대화)
// 다음 단계: 4단계 신고·차단(reportThread, 대화 ⋮ 메뉴).

import {
  currentUser, getMe, getInbox, listNotes, recommendSeniors,
  getMessages, previewNickname, checkMessage, sendMessage, respondRequest, cancelRequest,
} from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const LOCK_TEXT = "경험을 들려주거나 궁금한 것을 정리하면 선배 추천이 열려요";
const MAX_BASE = 4;   // 기준 노트 칩은 최대 4개
const MIN_TEXT = 5;   // 쪽지 첫 문장 최소 글자 수(빈 인사만 보내지 않게)
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

const noteLabel = (note) => {
  const kind = KIND_NAME[note.type] ?? "";
  return note.country ? [kind, note.country].filter(Boolean).join("·") : (kind || CATEGORY_NAME[CATEGORY[note.type]] || "");
};
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
let baseIds = [];
let currentNoteId = null;
let profile = null;
let seniorsRes = null;          // 마지막 recommendSeniors 응답
let threads = [];               // getMessages.threads(내가 보낸 것·받은 것 모두)
let threadsByWith = new Map();  // 선배(studentId) → 내가 보낸(asker) 대화 — 버튼 상태용
let waitingCount = 0;
let waitingLimit = 3;
let threadsLoaded = false;
// 이 화면에서 보낸 쪽지(서버 목록에 아직 안 보이면 잠깐 붙여 둔다 — mock은 기억하지 않아서 필요)
const localSent = new Map();    // threadId → [{from:"me", text, at}]

// ---------------------------------------------------------------------------
// 3. 기준 노트 정하기 (11/23 미리님 결정)
//    주소 ?noteId= → 없으면 getInbox: ① 질문함 최근 질문의 noteId(궁금한 것 정리하기로 전한 질문도 포함) → ② 최근 스크랩
//    → ③ 둘 다 없으면 「관심 경험을 골라 주세요」 + 「해봤노트 둘러보기」. 후보가 여럿이면 위에 프로그램 칩.
// ---------------------------------------------------------------------------

const timeOf = (q) => String(q.answeredAt || q.askedAt || "");

function pickBaseNotes(inbox, fromUrl) {
  const ids = [];
  const add = (id) => { if (id && !ids.includes(id)) ids.push(id); };
  add(fromUrl);
  const questions = ((inbox && inbox.questions) || []).filter((q) => q.noteId).slice()
    .sort((a, b) => timeOf(b).localeCompare(timeOf(a)));
  for (const q of questions) add(q.noteId);
  for (const s of (inbox && inbox.scraps) || []) add(s.noteId); // 스크랩은 최근이 위(spec)
  return ids.slice(0, MAX_BASE);
}

// --- 「나의 프로필 요약」(SOFT BLUE): 학과·학년·관심 경험(분야 태그). 이름·학번은 쓰지 않는다 ---
function renderProfile() {
  const box = document.getElementById("profileBox");
  if (!profile) { box.replaceChildren(); return; }
  const note = notesById.get(currentNoteId);
  const cat = note ? CATEGORY[note.type] : null;
  const interest = note
    ? [el("span", { className: `category-tag cat-${cat}`, text: CATEGORY_NAME[cat] }), el("span", { text: `${noteLabel(note)} · ${note.program}` })]
    : [el("span", { className: "sub", text: "아직 정하지 않았어요" })];
  box.replaceChildren(el("div", { className: "profile-card" }, [
    el("span", { className: "profile-card__title", text: "나의 프로필 요약" }),
    el("div", { className: "profile-card__line" }, [
      el("span", { className: "profile-card__dept", text: profile.crs_nm || "학과 –" }),
      el("span", { text: Number.isFinite(profile.regst_grad) ? `${profile.regst_grad}학년` : "" }),
      profile.dbl_mjr_nm ? el("span", { className: "sub", text: `이중전공 ${profile.dbl_mjr_nm}` }) : null,
    ]),
    el("div", { className: "profile-card__line" }, [el("span", { className: "sub", text: "관심 경험" }), ...interest]),
  ]));
}

function renderBaseChips() {
  const box = document.getElementById("baseChips");
  box.hidden = baseIds.length < 2;
  box.replaceChildren(...baseIds.map((id) => {
    const note = notesById.get(id);
    const chip = el("button", {
      className: "choice-chip",
      text: note ? note.program : id,
      attrs: { type: "button", "aria-pressed": String(id === currentNoteId) },
    });
    chip.addEventListener("click", () => {
      if (id === currentNoteId) return;
      selectNote(id);
    });
    return chip;
  }));
}

function selectNote(id) {
  currentNoteId = id;
  // 주소에도 남겨 새로고침·뒤로가기에서 같은 노트(해봤노트의 「닮은선배 보기」와 같은 모양)
  const url = new URL(location.href);
  url.searchParams.set("noteId", id);
  for (const k of ["senior", "view", "thread"]) url.searchParams.delete(k);
  history.replaceState(null, "", url.pathname + url.search);
  renderBaseChips();
  renderProfile();
  loadSeniors(false);
}

// ---------------------------------------------------------------------------
// 4. 쪽지 상태 (getMessages) — 버튼 상태·내 쪽지 목록·대화창이 같이 쓴다
// ---------------------------------------------------------------------------

// 이 화면에서 바꾼 대화 상태(요청 취소·수락·거절). 서버가 아직 「수락 대기」로 주면 이 값을 쓴다
// (진짜 서버는 바뀐 상태를 바로 돌려주지만 mock은 기억하지 않아서 필요)
const localStatus = new Map(); // threadId → status

// 서버 목록에 이 화면에서 보낸 쪽지·바꾼 상태를 합친다(서버에 이미 보이면 지역 사본은 버린다)
function mergeLocal(t) {
  const changed = localStatus.get(t.threadId);
  if (changed && t.status === "waiting") t = { ...t, status: changed };
  else if (changed) localStatus.delete(t.threadId);
  const extra = localSent.get(t.threadId);
  if (!extra || !extra.length) return t;
  const seen = new Set((t.messages || []).filter((m) => m.from === "me").map((m) => m.text));
  const left = extra.filter((m) => !seen.has(m.text));
  localSent.set(t.threadId, left);
  return left.length ? { ...t, messages: [...(t.messages || []), ...left] } : t;
}

async function loadThreads() {
  try {
    const res = await getMessages();
    if (!res || res.error) throw new Error((res && res.error) || "쪽지 없음");
    threads = (Array.isArray(res.threads) ? res.threads : []).map(mergeLocal);
    // 이 화면에서 새로 만든 대화(서버 목록에 아직 없음)도 남겨 둔다
    for (const [tid, msgs] of localSent) {
      if (!threads.some((t) => t.threadId === tid) && localThreads.has(tid)) {
        threads.push(mergeLocal({ ...localThreads.get(tid), messages: [] , status: localThreads.get(tid).status }));
        threads[threads.length - 1].messages = msgs;
      }
    }
    threadsByWith = new Map(threads.filter((t) => t.role === "asker").map((t) => [t.withId, t]));
    const localWaiting = threads.filter((t) => t.role === "asker" && t.status === "waiting").length;
    waitingCount = Math.max(Number.isFinite(res.waitingCount) ? res.waitingCount : 0, localWaiting);
    if (Number.isFinite(res.waitingLimit)) waitingLimit = res.waitingLimit;
    threadsLoaded = true;
    renderMessagesBadge();
    return true;
  } catch (err) {
    console.error(err); // 쪽지 상태를 못 받아도 목록은 보여 준다(보낼 때 서버가 한도를 다시 막는다)
    return false;
  }
}
const localThreads = new Map(); // threadId → 이 화면에서 처음 보낸 요청(서버 목록에 아직 없을 때만 씀)

// 「내 쪽지」 버튼 옆 숫자: 받은 수락 대기 요청 + 안 읽은 쪽지
function renderMessagesBadge() {
  const btn = document.getElementById("myMessagesBtn");
  btn.querySelector(".count-badge")?.remove();
  const n = threads.filter((t) => t.role === "senior" && t.status === "waiting").length
    + threads.reduce((sum, t) => sum + (Number.isFinite(t.unread) ? t.unread : 0), 0);
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
    const b = el("button", { className: `${cls} btn--primary`, text: "쪽지 보기", attrs: { type: "button" } });
    b.addEventListener("click", () => go(`thread=${encodeURIComponent(thread.threadId)}`));
    return b;
  }
  if (status === "declined") {
    // 선배가 요청을 받지 않음: 다시 누를 수 없게 비활성 + 이유(5-4). 다시 요청할 수 있는 날(retryAt)은 서버 값이 정해지면 붙인다
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
  if (s.requestsFull) {
    // 받는 한도(선배 대기 5건): 쪽지 대신 질문함으로(7-④, spec recommendSeniors requestsFull)
    return el("div", { className: "request-note" }, [
      statusLabel("neutral", "clock", "지금은 요청이 많아요"),
      el("a", { className: `${cls} btn--secondary`, text: "질문함으로 묻기", attrs: { href: "../talk/?mode=ask" } }),
    ]);
  }
  if (waitingCount >= waitingLimit) {
    // 보내는 한도(대기 3건): 시트를 열지 않고 안내 + 내 쪽지로(8절)
    const link = el("button", { className: "btn btn--text", text: "기다리는 요청 보기", attrs: { type: "button" } });
    link.addEventListener("click", () => go("view=messages"));
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

function seniorCard(s, note) {
  const profileBtn = el("button", { className: "btn btn--outline", text: "프로필 보기", attrs: { type: "button" } });
  profileBtn.addEventListener("click", () => go(`senior=${encodeURIComponent(letterOf(s))}`));

  return el("article", { className: "card senior-card" }, [
    el("div", { className: "senior-card__top" }, [
      el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
      el("h3", { className: "senior-card__name", text: s.nickname || "선배" }),
    ]),
    experienceTags(note),
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
  const note = notesById.get(currentNoteId);
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
      el("p", { className: "state-box__title", text: "아직 이 경험을 한 선배가 없어요" }),
      el("p", { className: "sub", text: "궁금한 점은 질문함에 남기면 선배 인터뷰 때 먼저 물어볼게요." }),
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/?mode=ask" } }),
    ]));
  } else {
    children.push(el("div", { className: "senior-list" }, seniors.map((s) => seniorCard(s, note))));
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
  document.getElementById("baseChips").hidden = true;
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

// --- 기준 노트가 없을 때(③) ---
function renderNoBase() {
  listArea.setAttribute("aria-busy", "false");
  listArea.replaceChildren(el("div", { className: "state-box" }, [
    el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
    el("p", { className: "state-box__title", text: "관심 경험을 골라 주세요" }),
    el("p", { className: "sub", text: "해봤노트에서 궁금한 경험을 고르면 그 경험을 해본 선배를 추천해요." }),
    el("a", { className: "btn btn--secondary", text: "해봤노트 둘러보기", attrs: { href: "../note/" } }),
  ]));
  drawIcons();
}

// 요청마다 번호를 붙인다. 불러오는 중에 다른 프로그램 칩을 누르면 새 요청을 바로 보내고,
// 늦게 도착한 옛 응답(번호가 다르거나 기준 노트가 바뀐 것)은 그리지 않고 버린다.
let loading = false;
let loadSeq = 0;
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
    if (res && res.locked) renderLocked(res.recommend);
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
  messages: document.getElementById("viewMessages"),
  thread: document.getElementById("viewThread"),
};
let movedInside = false; // 이 화면 안에서 들어왔으면 ←는 브라우저 뒤로(목록 스크롤 유지)
let listScrollY = 0;

function show(name) {
  for (const [k, v] of Object.entries(views)) v.hidden = k !== name;
  if (name !== "thread") stopPolling();
}

function go(query) {
  if (views.senior.hidden === false) listScrollY = window.scrollY;
  movedInside = true;
  const url = new URL(location.href);
  for (const k of ["senior", "view", "thread"]) url.searchParams.delete(k);
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
    const fromThread = url.searchParams.has("thread");
    for (const k of ["senior", "view", "thread"]) url.searchParams.delete(k);
    if (fromThread) url.searchParams.set("view", "messages"); // 알림에서 바로 들어온 대화 → 내 쪽지
    history.replaceState(null, "", url.pathname + url.search);
    route();
  }
}

function findSenior(letter) {
  return ((seniorsRes && seniorsRes.seniors) || []).find((s) => letterOf(s) === letter) || null;
}

function route() {
  const p = new URLSearchParams(location.search);
  if (p.get("thread")) {
    show("thread");
    window.scrollTo(0, 0);
    openThread(p.get("thread"));
  } else if (p.get("view") === "messages") {
    show("messages");
    window.scrollTo(0, 0);
    document.title = "내 쪽지 · 닮은선배";
    renderMessages();
  } else if (p.get("senior") && findSenior(p.get("senior"))) {
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

for (const btn of document.querySelectorAll("[data-back], #profileBack")) btn.addEventListener("click", goBack);
window.addEventListener("popstate", () => {
  movedInside = false;
  route();
});
document.getElementById("myMessagesBtn").addEventListener("click", () => go("view=messages"));

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

// ---------------------------------------------------------------------------
// 8. 내 쪽지 목록(2단계) — 받은 요청(수락·거절) → 대화 → 보낸 요청(수락 대기·요청 취소, 취소함·응답 없음은 맨 아래)
//    8절: 받은 요청 카드에 학과는 보이지 않는다(학과 + 학년이면 특정하기 쉬움)
// ---------------------------------------------------------------------------

const messagesBody = document.getElementById("messagesBody");

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

function threadRow(t, { muted = false } = {}) {
  const last = lastMessage(t);
  const row = el("a", { className: `card thread-row${muted ? " thread-row--muted" : ""}`, attrs: { href: `?thread=${encodeURIComponent(t.threadId)}` } }, [
    el("span", { className: "avatar", attrs: { "aria-hidden": "true" } }, [icon("user")]),
    el("div", { className: "thread-row__body" }, [
      el("div", { className: "thread-row__name" }, [
        el("span", { text: t.nickname || "상대" }),
        t.unread > 0 ? el("span", { className: "count-badge", text: t.unread, attrs: { "aria-label": `안 읽은 쪽지 ${t.unread}개` } }) : null,
        STATUS_LABEL[t.status] && t.status !== "accepted" ? STATUS_LABEL[t.status]() : null,
      ]),
      last ? el("p", { className: "thread-row__last", text: `${last.from === "me" ? "나: " : ""}${last.text}` }) : null,
      el("span", { className: "thread-row__time", text: shortTime((last && last.at) || t.requestedAt) }),
    ]),
  ]);
  row.addEventListener("click", (e) => {
    e.preventDefault();
    go(`thread=${encodeURIComponent(t.threadId)}`);
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
  cancel.addEventListener("click", () => confirmCancel(t, cancel));
  return el("div", { className: "msg-group" }, [row, cancel]);
}

async function renderMessages() {
  messagesBody.setAttribute("aria-busy", "true");
  if (!threadsLoaded) messagesBody.replaceChildren(...skeletons(2, "detail-skeleton"));
  const ok = await loadThreads();
  if (!ok && !threadsLoaded) {
    messagesBody.setAttribute("aria-busy", "false");
    messagesBody.replaceChildren(errorBox(renderMessages));
    drawIcons();
    return;
  }
  const received = threads.filter((t) => t.role === "senior" && t.status === "waiting");
  const talking = threads.filter((t) => t.status === "accepted" || (t.status === "blocked"))
    .sort((a, b) => String((lastMessage(b) || {}).at || "").localeCompare(String((lastMessage(a) || {}).at || "")));
  const sentWaiting = threads.filter((t) => t.role === "asker" && t.status === "waiting");
  const sentDone = threads.filter((t) => t.role === "asker" && ["cancelled", "expired", "declined"].includes(t.status)); // 맨 아래

  const children = [];
  if (!threads.length) {
    children.push(el("div", { className: "state-box" }, [
      el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
      el("p", { className: "state-box__title", text: "아직 주고받은 쪽지가 없어요" }),
      el("p", { className: "sub", text: "닮은선배에게 쪽지를 요청해 보세요." }),
      el("button", { className: "btn btn--secondary", text: "닮은선배 보기", attrs: { type: "button", "data-go": "senior" } }),
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
  messagesBody.setAttribute("aria-busy", "false");
  messagesBody.replaceChildren(...children);
  for (const b of messagesBody.querySelectorAll("[data-go='senior']")) b.addEventListener("click", goBack);
  drawIcons();
}

async function respond(t, accept, buttons) {
  for (const b of buttons) b.disabled = true;
  try {
    const res = await respondRequest(t.threadId, accept);
    if (!res || res.error || res.ok === false) throw new Error((res && (res.message || res.error)) || "응답 실패");
    t.status = res.status || (accept ? "accepted" : "declined");
    localStatus.set(t.threadId, t.status);
    toast(accept ? "요청을 수락했어요. 대화가 열렸어요" : "요청을 거절했어요");
    if (accept) go(`thread=${encodeURIComponent(t.threadId)}`);
    else renderMessages();
  } catch (err) {
    console.error(err);
    for (const b of buttons) b.disabled = false;
    toast("처리하지 못했어요. 다시 시도해 주세요", "circle-alert");
  }
}

// ---------------------------------------------------------------------------
// 9. 확인 시트(5-10) — 요청 취소
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
        waitingCount = Math.max(0, waitingCount - 1);
        toast("요청을 취소했어요");
        if (!views.thread.hidden) openThread(t.threadId, { reuse: true });
        else renderMessages();
      } catch (err) {
        console.error(err);
        toast("취소하지 못했어요. 다시 시도해 주세요", "circle-alert");
      }
    },
  });
}

// ---------------------------------------------------------------------------
// 10. 익명 쪽지 대화(3단계, 8절) — 상대 이름은 보는 사람에 따라 다르다(후배 화면 「독일어과 선배 A」, 선배 화면 「용감한 수달」)
//     5초마다 새 쪽지 확인(getMessages), 보내기 전 연락처·학번 검사(checkMessage)
// ---------------------------------------------------------------------------

const threadChat = document.getElementById("threadChat");
const threadTop = document.getElementById("threadTop");
const threadDock = document.getElementById("threadDock");
let currentThreadId = null;
let pollTimer = null;
let lastRenderedKey = "";

function stopPolling() {
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
    const form = el("form", { className: "composer" }, [input, send]);
    input.addEventListener("input", () => {
      send.disabled = input.value.trim() === "";
      err.hidden = true;
      input.removeAttribute("aria-invalid");
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      sendInThread(t, input, send, err);
    });
    threadDock.replaceChildren(err, form);
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
    const text = { cancelled: "취소한 요청이에요", expired: "선배가 아직 못 봤어요. 다른 선배에게 보내 볼까요?", declined: "선배가 이번에는 대화를 열지 않았어요" }[t.status] || "더 이어 갈 수 없는 대화예요";
    const back = el("button", { className: "btn btn--outline btn--block", text: "닮은선배 보기", attrs: { type: "button" } });
    back.addEventListener("click", () => {
      const url = new URL(location.href);
      for (const k of ["senior", "view", "thread"]) url.searchParams.delete(k);
      history.replaceState(null, "", url.pathname + url.search);
      movedInside = false;
      route();
    });
    threadDock.replaceChildren(el("div", { className: "dock-note" }, [el("p", { className: "btn-reason" }, [icon("info"), el("span", { text })]), back]));
  }
  drawIcons();
}

function renderThread(t, { keepDock = false } = {}) {
  document.getElementById("threadTitle").textContent = t.nickname || "쪽지";
  document.title = `${t.nickname || "쪽지"} · 내 쪽지`;
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

async function openThread(threadId, { reuse = false } = {}) {
  const firstOpen = currentThreadId !== threadId || !reuse;
  currentThreadId = threadId;
  if (firstOpen) {
    lastRenderedKey = "";
    threadTop.replaceChildren();
    threadDock.replaceChildren();
    threadChat.replaceChildren(...skeletons(2, "detail-skeleton"));
  }
  const local = threads.find((x) => x.threadId === threadId);
  if (local && reuse) renderThread(local);
  const ok = await loadThreads();
  if (currentThreadId !== threadId) return; // 그 사이 다른 화면으로 감
  const t = threads.find((x) => x.threadId === threadId);
  if (!t) {
    threadChat.replaceChildren(ok ? el("div", { className: "state-box" }, [
      el("p", { className: "state-box__title", text: "대화를 찾지 못했어요" }),
      el("p", { className: "sub", text: "내 쪽지에서 다시 골라 주세요." }),
    ]) : errorBox(() => openThread(threadId)));
    threadDock.replaceChildren();
    drawIcons();
    return;
  }
  renderThread(t);
  // 5초마다 새 쪽지 확인 — 이 화면을 떠나면 멈춘다
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (document.hidden || currentThreadId !== threadId) return;
    if (await loadThreads()) {
      const fresh = threads.find((x) => x.threadId === threadId);
      if (fresh && currentThreadId === threadId) renderThread(fresh, { keepDock: fresh.status === "accepted" });
    }
  }, POLL_MS);
}

async function sendInThread(t, input, send, err) {
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
      fail(check.message || "보낼 수 없는 내용이 있어요.");
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
  } catch (e) {
    console.error(e);
    fail("쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
  } finally {
    input.disabled = false;
    send.disabled = input.value.trim() === "";
    input.focus();
  }
}

// ---------------------------------------------------------------------------
// 11. 쪽지 요청 바텀시트(8절) — 내 익명 이름 안내(previewNickname) + 첫 쪽지 + 연락처·학번 검사(checkMessage)
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

function showError(message) {
  errorLine.replaceChildren(icon("circle-alert"), el("span", { text: message }));
  errorLine.hidden = false;
  textBox.setAttribute("aria-invalid", "true");
  drawIcons();
}
function clearError() {
  errorLine.hidden = true;
  errorLine.replaceChildren();
  textBox.removeAttribute("aria-invalid");
}

function updateSubmit() {
  const len = textBox.value.trim().length;
  submitBtn.disabled = sending || len < MIN_TEXT || !target;
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
      showError(check.message || "보낼 수 없는 내용이 있어요.");
      return;
    }
    // ② 보내기 — 서버가 한도·잠김·차단을 다시 막는다
    const res = await sendMessage(s.studentId, text);
    if (!res || res.error || res.ok === false) {
      showError((res && (res.message || res.error)) || "쪽지를 보내지 못했어요. 잠시 뒤 다시 시도해 주세요.");
      if (res && res.reason === "한도") waitingCount = waitingLimit;
      return;
    }
    // 성공: 이 선배는 「요청 보냄」, 대기 수 +1, 내 쪽지에도 바로 보이게
    const at = res.at || new Date().toISOString();
    // mock sendMessage는 누구에게 보내든 같은 threadId(T-0001)를 돌려준다 → 다른 선배와의 대화를 덮지 않게 이 화면에서만 따로 둔다
    const clash = threads.find((x) => x.threadId === res.threadId && x.withId !== s.studentId);
    const tid = clash ? `${res.threadId}~${letterOf(s)}` : res.threadId;
    const thread = { threadId: tid, role: "asker", withId: s.studentId, nickname: s.nickname, myNickname: res.myNickname || targetNick, status: "waiting", requestedAt: at, unread: 0, messages: [] };
    localThreads.set(tid, thread);
    localSent.set(tid, [{ from: "me", text, at }]);
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
// 12. 시작 — getMe(프로필·열림 상태) + getInbox(기준 노트) + listNotes(프로그램 이름·분야) + getMessages(요청 상태)
// ---------------------------------------------------------------------------

async function start() {
  listArea.replaceChildren(...skeletons(2));
  // 내 쪽지·대화 주소로 바로 들어왔으면(알림 「쪽지 요청이 왔어요」 등) 그 화면부터
  const p = new URLSearchParams(location.search);
  if (p.has("thread") || p.get("view") === "messages") route();
  try {
    const [meInfo, inbox, list] = await Promise.all([
      getMe(),
      getInbox().catch(() => null),
      listNotes({}).catch(() => ({ notes: [] })),
      loadThreads(),
    ]);
    if (!meInfo || meInfo.error) throw new Error((meInfo && meInfo.error) || "내 정보 없음");
    profile = meInfo;
    notesById = new Map(((list && list.notes) || []).map((n) => [n.id, n]));
    baseIds = pickBaseNotes(inbox, p.get("noteId"));
    currentNoteId = baseIds[0] || null;
    renderProfile();

    // 열림 상태는 getMe.recommend가 먼저 알려 준다(서버도 recommendSeniors에서 막음)
    if (meInfo.recommend && meInfo.recommend.ready === false) {
      renderLocked(meInfo.recommend);
      return;
    }
    if (!currentNoteId) {
      renderNoBase();
      return;
    }
    renderBaseChips();
    loadSeniors(false);
  } catch (err) {
    console.error(err);
    listArea.setAttribute("aria-busy", "false");
    listArea.replaceChildren(errorBox(start));
    drawIcons();
  }
}

drawIcons();
if (me) start();
