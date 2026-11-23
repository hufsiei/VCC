// 닮은선배 화면 (작업 28) — 1단계: 추천 목록 + 잠김 / 2단계: 선배 프로필 + 쪽지 요청 시트
// 기준: docs/design-rules.md 7-④·6-6·5-5·5-9·5-10·8절(선배 프로필·익명 쪽지 요청), docs/spec-v1.md 4장
//       recommendSeniors·getMe(recommend)·getInbox·listNotes·getMessages·previewNickname·checkMessage·sendMessage,
//       PRD 4장 닮은선배 행·2-2(쿨다운·횟수 제한 UI 없음, 이름·학번 표시 없음)
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
// 학번(studentId)은 화면과 주소에 쓰지 않는다 — 주소의 선배는 표시명 글자(A, B…)로만 가리킨다.
// 다음 단계: 3단계 내 쪽지(목록·대화·요청 취소·받은 요청), 4단계 신고·차단(reportThread).

import {
  currentUser, getMe, getInbox, listNotes, recommendSeniors,
  getMessages, previewNickname, checkMessage, sendMessage,
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
const MAX_BASE = 4; // 기준 노트 칩은 최대 4개
const MIN_TEXT = 5; // 쪽지 첫 문장 최소 글자 수(빈 인사만 보내지 않게)

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트
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
const skeletons = (n) => Array.from({ length: n }, () => el("div", { className: "skeleton senior-skeleton", attrs: { "aria-hidden": "true" } }));

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
let threadsByWith = new Map();  // 선배(studentId) → 내가 보낸(asker) 대화 — 버튼 상태용
let waitingCount = 0;
let waitingLimit = 3;

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
  url.searchParams.delete("senior");
  history.replaceState(null, "", url.pathname + url.search);
  renderBaseChips();
  renderProfile();
  loadSeniors(false);
}

// ---------------------------------------------------------------------------
// 4. 쪽지 요청 버튼 상태 (getMessages) — 8절 「익명 쪽지 요청 (보내는 쪽)」
//    이미 보낸 요청 → 「요청 보냄」(비활성) / 대화 중 → 「쪽지 보기」 / 대기 3건 → 시트를 열지 않고 안내
// ---------------------------------------------------------------------------

async function loadThreads() {
  try {
    const res = await getMessages();
    const threads = (res && Array.isArray(res.threads)) ? res.threads : [];
    threadsByWith = new Map(threads.filter((t) => t.role === "asker").map((t) => [t.withId, t]));
    waitingCount = Number.isFinite(res && res.waitingCount) ? res.waitingCount : threads.filter((t) => t.role === "asker" && t.status === "waiting").length;
    if (Number.isFinite(res && res.waitingLimit)) waitingLimit = res.waitingLimit;
  } catch (err) {
    console.error(err); // 쪽지 상태를 못 받아도 목록은 보여 준다(보낼 때 서버가 한도를 다시 막는다)
  }
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
    b.addEventListener("click", () => toast("내 쪽지는 다음 단계에서 열려요", "info")); // 3단계에서 대화창으로
    return b;
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
    // 보내는 한도(대기 3건): 시트를 열지 않고 안내(8절)
    const link = el("button", { className: "btn btn--text", text: "기다리는 요청 보기", attrs: { type: "button" } });
    link.addEventListener("click", () => toast("내 쪽지는 다음 단계에서 열려요", "info")); // 3단계에서 내 쪽지로
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
    else if (r.includes("이중전공")) chips.push("이중전공");
    else if (/과$|학부$|전공$/.test(r.replace(/^같은\s*/, ""))) chips.push("전공");
    else if (r.includes("대학")) chips.push("단과대");
    else if (r.includes("이수")) chips.push("비교과");
  }
  // 순서는 디자인 규칙 7-④대로(관심 경험 · 전공 · 이중전공 · 단과대 · 비교과)
  const ORDER = ["관심 경험", "전공", "이중전공", "단과대", "비교과"];
  return ORDER.filter((c) => chips.includes(c));
}

const reasonText = (s) => ((s.reasons || []).length ? s.reasons.join(" · ") : "희망 프로그램을 경험했어요");

function experienceTags(note) {
  if (!note) return null;
  const cat = CATEGORY[note.type];
  return el("div", { className: "tag-row" }, [el("span", { className: `category-tag cat-${cat}`, text: CATEGORY_NAME[cat] }), el("span", { className: "sub", text: note.program })]);
}

function seniorCard(s, note) {
  const profileBtn = el("button", { className: "btn btn--outline", text: "프로필 보기", attrs: { type: "button" } });
  profileBtn.addEventListener("click", () => openProfile(s));

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

let loading = false;
async function loadSeniors(more, moreBtn) {
  if (loading || !currentNoteId) return;
  loading = true;
  if (more && moreBtn) {
    moreBtn.disabled = true;
    moreBtn.textContent = "불러오는 중…";
  } else {
    listArea.setAttribute("aria-busy", "true");
    listArea.replaceChildren(...skeletons(2));
  }
  try {
    const res = await recommendSeniors(currentNoteId, more);
    if (res && res.locked) renderLocked(res.recommend);
    else if (!res || res.error || !Array.isArray(res.seniors)) throw new Error((res && res.error) || "추천 없음");
    else renderList(res);
  } catch (err) {
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
    loading = false;
  }
  if (location.search.includes("senior=")) route(); // 프로필 주소로 바로 들어온 경우
}

// ---------------------------------------------------------------------------
// 6. 선배 프로필(2단계, 8절) — 상세 헤더 → 중립 아바타 + 표시명 → 경험 태그 → 추천 이유 → 하단 고정 「쪽지 요청」
//    주소: ?noteId=…&senior=A (학번 대신 표시명 글자). 같은 사람은 카드·프로필·쪽지창에서 같은 이름(spec).
// ---------------------------------------------------------------------------

const viewSenior = document.getElementById("viewSenior");
const viewProfile = document.getElementById("viewProfile");
let movedInside = false;
let listScrollY = 0;

function findSenior(letter) {
  return ((seniorsRes && seniorsRes.seniors) || []).find((s) => letterOf(s) === letter) || null;
}

function openProfile(s) {
  listScrollY = window.scrollY;
  movedInside = true;
  const url = new URL(location.href);
  url.searchParams.set("senior", letterOf(s));
  history.pushState({ inner: true }, "", url.pathname + url.search);
  route();
}

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

function route() {
  const letter = new URLSearchParams(location.search).get("senior");
  const s = letter ? findSenior(letter) : null;
  if (s) {
    viewSenior.hidden = true;
    viewProfile.hidden = false;
    window.scrollTo(0, 0);
    renderProfilePage(s);
  } else {
    viewProfile.hidden = true;
    viewSenior.hidden = false;
    document.title = "닮은선배 · 외대人사이드";
    window.scrollTo(0, listScrollY);
  }
}

document.getElementById("profileBack").addEventListener("click", () => {
  if (movedInside) {
    movedInside = false;
    history.back();
  } else {
    const url = new URL(location.href);
    url.searchParams.delete("senior");
    history.replaceState(null, "", url.pathname + url.search);
    route();
  }
});
window.addEventListener("popstate", () => {
  movedInside = false;
  route();
});

// ---------------------------------------------------------------------------
// 7. 쪽지 요청 바텀시트(8절) — 내 익명 이름 안내(previewNickname) + 첫 쪽지 + 연락처·학번 검사(checkMessage)
//    → sendMessage. 서버가 막으면(한도·선배한도·잠김·차단) 그 message를 그대로 보여 준다.
// ---------------------------------------------------------------------------

const sheet = document.getElementById("requestSheet");
const nickBox = document.getElementById("requestNick");
const textBox = document.getElementById("requestText");
const errorLine = document.getElementById("requestError");
const submitBtn = document.getElementById("requestSubmit");
const reasonLine = document.getElementById("requestReason");
let target = null;
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
    // 성공: 이 선배는 「요청 보냄」, 대기 수 +1
    threadsByWith.set(s.studentId, { withId: s.studentId, role: "asker", status: "waiting", threadId: res.threadId });
    waitingCount += 1;
    sending = false;
    closeRequestSheet();
    toast("쪽지 요청을 보냈어요. 선배가 수락하면 대화가 열려요");
    if (seniorsRes) renderList(seniorsRes);
    if (!viewProfile.hidden) renderProfilePage(s);
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
// 8. 시작 — getMe(프로필·열림 상태) + getInbox(기준 노트) + listNotes(프로그램 이름·분야) + getMessages(요청 상태)
// ---------------------------------------------------------------------------

async function start() {
  listArea.replaceChildren(...skeletons(2));
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
    baseIds = pickBaseNotes(inbox, new URLSearchParams(location.search).get("noteId"));
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

// 「내 쪽지」 — 3단계(쪽지 목록·대화)에서 연결
document.getElementById("myMessagesBtn").addEventListener("click", () => toast("내 쪽지는 다음 단계에서 열려요", "info"));

drawIcons();
if (me) start();
