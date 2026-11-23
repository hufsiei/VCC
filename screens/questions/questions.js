// 내 보관함 화면 (작업 23) — 1단계: 내 경험노트 / 질문함 / 스크랩 탭
//   2단계: 알림 목록(#alerts) · 내 경험노트 상세(?mynote=M-…) · 질문 상세(?question=Q-…)
// 기준: docs/design-rules.md 7-⑥·5-2·6-1~6-5·8절(내 경험노트 상세·질문 상세·알림 목록),
//       docs/spec-v1.md 4장 getInbox·getMyNote·getNote·listNotes·scrapNote·saveConsent
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.
// 공개 동의 시트는 common/consent.js(작업 70, 11/22 common으로 옮김)를 쓴다: "open-consent"로 열고 "consent-saved"로 끝을 받는다.

import { currentUser, getInbox, getMyNote, getNote, listNotes, scrapNote } from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const DOC_LABEL = { 귀국보고서: "결과보고서", 현장실습후기: "현장실습후기", 인터뷰: "선배 인터뷰" };
const QUESTION_SECTION = "후배 질문";
const DASH = "–";
const TABS = ["notes", "questions", "scraps"];

// ---------------------------------------------------------------------------
// 1. 작은 도우미 — 요소 만들기(글은 textContent로만), 아이콘, 토스트, 날짜·학기
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
const orDash = (v) => (v === null || v === undefined || String(v).trim() === "" ? DASH : String(v));
const skeletons = (n, cls) => Array.from({ length: n }, () => el("div", { className: `skeleton ${cls}`, attrs: { "aria-hidden": "true" } }));

function toast(text, iconName = "check") {
  const host = document.getElementById("toastHost");
  host.replaceChildren(el("span", { className: "toast" }, [icon(iconName), el("span", { text })]));
  drawIcons();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.replaceChildren(), 3000);
}

// "2026-11-19T15:00:00+09:00" → "11월 19일"
function dateText(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return DASH;
  return `${d.getMonth() + 1}월 ${d.getDate()}일`;
}
// 질문 날짜 줄: 「11월 18일 남김 · 11월 19일 답변」 — 없는 값은 빼고 보여 준다
function questionDates(q) {
  const parts = [];
  if (q.askedAt) parts.push(`${dateText(q.askedAt)} 남김`);
  if (q.answeredAt) parts.push(`${dateText(q.answeredAt)} 답변`);
  return parts.length ? parts.join(" · ") : DASH;
}
function timeText(iso) {
  const d = new Date(iso);
  if (!iso || Number.isNaN(d.getTime())) return DASH;
  return `${dateText(iso)} ${d.toLocaleTimeString("ko-KR", { hour: "numeric", minute: "2-digit" })}`;
}
function semesterText(s) {
  if (!s) return DASH;
  const [year, term] = String(s).split("-");
  if (term === "1" || term === "2") return `${year}-${term}학기`;
  if (term === "여름") return `${year} 하계방학`;
  if (term === "겨울") return `${year} 동계방학`;
  return String(s);
}
const SEM_ORDER = { 1: 1, 여름: 2, 2: 3, 겨울: 4 };
const semesterKey = (sem) => {
  const [year, part] = String(sem || "").split("-");
  return Number(year || 0) * 10 + (SEM_ORDER[part] || 0);
};
const yearOf = (sem) => String(sem || DASH).split("-")[0]; // 출처 칩은 연도만(v4.3)

function emptyBox(title, desc, button) {
  return el("div", { className: "state-box" }, [
    el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
    el("p", { className: "state-box__title", text: title }),
    el("p", { className: "sub", text: desc }),
    button,
  ]);
}

function errorBox(onRetry, message = "불러오지 못했어요") {
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", onRetry);
  return el("div", { className: "state-box" }, [
    statusLabel("error", "circle-alert", message),
    el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]);
}

// 안 읽은 알림: 이 탭에서 알림 목록을 마지막으로 연 시각보다 늦은 알림(getInbox에 읽음 표시가 없어서 탭마다 기억)
const SEEN_KEY = "vccAlertsSeenAt";
function seenAt() {
  try { return sessionStorage.getItem(SEEN_KEY) || ""; } catch { return ""; }
}
function markSeen() {
  try { sessionStorage.setItem(SEEN_KEY, new Date().toISOString()); } catch { /* 저장 못 해도 화면은 그대로 */ }
}
const isUnread = (a) => !seenAt() || new Date(a.at) > new Date(seenAt());

// ---------------------------------------------------------------------------
// 2. 화면 이동 — 주소로 정한다. 들어간 화면은 pushState라 브라우저 뒤로도 같이 동작
// ---------------------------------------------------------------------------

let currentTab = "notes";
let movedInside = false; // 이 화면 안에서 들어왔으면 ←는 브라우저 뒤로(탭·스크롤 유지)
let inboxScrollY = 0;

function inboxUrl() {
  return `${location.pathname}?tab=${currentTab}`;
}

function go(query) {
  inboxScrollY = window.scrollY;
  movedInside = true;
  history.pushState({ inner: true }, "", `${location.pathname}?tab=${currentTab}&${query}`);
  route();
}

function goBack() {
  if (movedInside) {
    movedInside = false;
    history.back();
  } else {
    history.replaceState(null, "", inboxUrl());
    route();
  }
}

const views = {
  inbox: document.getElementById("viewInbox"),
  alerts: document.getElementById("viewAlerts"),
  myNote: document.getElementById("viewMyNote"),
  question: document.getElementById("viewQuestion"),
};
function show(name) {
  for (const [k, v] of Object.entries(views)) v.hidden = k !== name;
}

function route() {
  const params = new URLSearchParams(location.search);
  if (location.hash === "#alerts") {
    show("alerts");
    window.scrollTo(0, 0);
    renderAlerts();
  } else if (params.get("mynote")) {
    show("myNote");
    window.scrollTo(0, 0);
    loadMyNote(params.get("mynote"));
  } else if (params.get("question")) {
    show("question");
    window.scrollTo(0, 0);
    renderQuestion(params.get("question"));
  } else {
    show("inbox");
    document.title = "내 보관함 · 외대人사이드";
    window.scrollTo(0, inboxScrollY);
  }
}

for (const btn of document.querySelectorAll("[data-back]")) btn.addEventListener("click", goBack);
document.getElementById("bellBtn").addEventListener("click", () => {
  inboxScrollY = window.scrollY;
  movedInside = true;
});
window.addEventListener("popstate", () => {
  movedInside = false;
  route();
});
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------------------
// 3. 데이터 — getInbox + listNotes(스크랩 커버·질문의 노트 이름)
// ---------------------------------------------------------------------------

let inbox = null;
let notesById = new Map();
let inboxReady = null; // 상세 화면이 보관함 데이터를 기다릴 때 쓰는 약속

function loadInbox() {
  const panel = document.getElementById("tabPanel");
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(...skeletons(2, "inbox-skeleton"));
  inboxReady = (async () => {
    try {
      const [box, list] = await Promise.all([getInbox(), listNotes({}).catch(() => ({ notes: [] }))]);
      if (!box || box.error) throw new Error((box && box.error) || "보관함 없음");
      inbox = {
        myNotes: box.myNotes || [],
        // 답변 도착이 맨 위(7-⑥), 그다음 최근 순
        questions: (box.questions || []).slice().sort((a, b) =>
          (a.status !== "answered") - (b.status !== "answered") || String(b.answeredAt || b.askedAt).localeCompare(String(a.answeredAt || a.askedAt))),
        scraps: box.scraps || [],
        alerts: box.alerts || [],
      };
      notesById = new Map(((list && list.notes) || []).map((n) => [n.id, n]));
      renderTabsMeta();
      renderPanel();
      return true;
    } catch (err) {
      console.error(err);
      panel.setAttribute("aria-busy", "false");
      panel.replaceChildren(errorBox(loadInbox));
      drawIcons();
      return false;
    }
  })();
  return inboxReady;
}

// 탭 이름 옆 개수 + 새 소식 점, 헤더 종의 점
function renderTabsMeta() {
  const counts = { notes: inbox.myNotes.length, questions: inbox.questions.length, scraps: inbox.scraps.length };
  const unread = inbox.alerts.filter(isUnread);
  const news = { notes: false, questions: unread.some((a) => a.questionId), scraps: false };
  for (const t of TABS) {
    const btn = document.getElementById(`tab-${t}`);
    btn.querySelector(".top-tab__count").textContent = String(counts[t]);
    btn.querySelector(".top-tab__dot").hidden = !news[t];
  }
  document.getElementById("bellDot").hidden = unread.length === 0;
  document.getElementById("bellBtn").setAttribute("aria-label", unread.length ? `알림, 새 알림 ${unread.length}개` : "알림");
}

// ---------------------------------------------------------------------------
// 4. 1단계 탭 내용
// ---------------------------------------------------------------------------

// --- 공유 상태 라벨(7-⑥, 11/22): 나만 보기=중립 / N문장 공유=중립 / 해봤노트 공유됨=긍정. 「반영 중」은 없다 ---
function shareLabel(note) {
  if (note.share === "shared") return statusLabel("success", "check", "해봤노트 공유됨");
  if (note.share === "partial") return statusLabel("neutral", "share-2", Number.isFinite(note.sharedLines) ? `${note.sharedLines}문장 공유` : "일부 공유");
  return statusLabel("neutral", "lock", "나만 보기");
}
const frameText = (note) =>
  Number.isFinite(note.filled) && Number.isFinite(note.total) ? `노트 틀 ${note.filled}/${note.total}` : `노트 틀 ${DASH}`;

// 「자소서용 요약 보기」 — v4.3: 비활성 + 「운영 연계 시 열려요」(6-6)
function resumeButton() {
  return [
    el("button", { className: "btn btn--secondary btn--block", text: "자소서용 요약 보기", attrs: { type: "button", disabled: "" } }),
    el("p", { className: "btn-reason" }, [icon("lock"), el("span", { text: "운영 연계 시 열려요" })]),
  ];
}

function myNoteCard(note) {
  // 분야 띠는 카드의 type으로, 없을 때만 같은 프로그램의 해봤노트로 찾는다(#104 미리님 수정과 같음)
  const pub = [...notesById.values()].find((n) => n.program === note.program);
  const cat = CATEGORY[note.type] || (pub ? CATEGORY[pub.type] : null);
  const title = el("a", { className: "link-plain", text: `${orDash(note.program)} 경험노트`, attrs: { href: `?tab=notes&mynote=${encodeURIComponent(note.id)}` } });
  title.addEventListener("click", (e) => {
    e.preventDefault();
    go(`mynote=${encodeURIComponent(note.id)}`);
  });
  return el("article", { className: `note-card${cat ? ` cat-${cat}` : ""}` }, [
    el("div", { className: "note-card__band" }, [
      el("span", { className: "category-tag", text: cat ? CATEGORY_NAME[cat] : "경험" }),
      el("span", { className: "note-card__kind", text: orDash(note.program) }),
    ]),
    el("div", { className: "mynote__body" }, [
      el("h3", { className: "note-card__title" }, [title]),
      el("div", { className: "mynote__meta" }, [el("span", { text: frameText(note) }), shareLabel(note)]),
      ...resumeButton(),
    ]),
  ]);
}

function renderNotesTab(panel) {
  if (!inbox.myNotes.length) {
    panel.replaceChildren(emptyBox(
      "아직 내 경험노트가 없어요",
      "인터BOO에서 경험을 들려주면 여기에 저장돼요.",
      el("a", { className: "btn btn--secondary", text: "경험 들려주기", attrs: { href: "../talk/" } }),
    ));
    return;
  }
  panel.replaceChildren(...inbox.myNotes.map(myNoteCard));
}

// --- 질문함 탭 ---
function questionLink(q, className) {
  const a = el("a", { className: `link-plain ${className}`, text: orDash(q.text), attrs: { href: `?tab=questions&question=${encodeURIComponent(q.questionId)}` } });
  a.addEventListener("click", (e) => {
    e.preventDefault();
    go(`question=${encodeURIComponent(q.questionId)}`);
  });
  return a;
}

function questionStatusLabel(q) {
  if (q.status === "answered") return statusLabel("success", "check", "선배가 답했어요");
  if (q.status === "official") return statusLabel("info", "info", "공식 안내");
  return statusLabel("neutral", "clock", "답을 기다려요");
}

function questionCard(q) {
  const children = [questionStatusLabel(q), questionLink(q, "question__text")];
  if (q.status === "answered") {
    children.push(el("span", { className: "question__date", text: questionDates(q) }));
    const pub = notesById.get(q.noteId);
    children.push(el("p", { className: "question__info", text: pub ? `${pub.program} 해봤노트 「후배 질문」 칸에 답이 실렸어요` : "해봤노트 「후배 질문」 칸에 답이 실렸어요" }));
    if (q.noteId) {
      const id = encodeURIComponent(q.noteId);
      children.push(el("div", { className: "btn-row" }, [
        el("a", { className: "btn btn--primary", text: "해봤노트 보기", attrs: { href: `../note/?id=${id}` } }),
        el("a", { className: "btn btn--outline", text: "닮은선배 보기", attrs: { href: `../senior/?noteId=${id}` } }),
      ]));
    }
  } else if (q.status === "official") {
    children.push(
      el("span", { className: "question__date", text: questionDates(q) }),
      el("p", { className: "question__info", text: "학교 규정·절차 질문이라 공식 안내에서 확인해 주세요." }),
    );
  } else {
    children.push(
      el("span", { className: "question__date", text: questionDates(q) }),
      el("p", { className: "question__info", text: "근거 0건 · 선배 인터뷰 질문으로 전달됐어요" }),
    );
  }
  return el("article", { className: "card question" }, children);
}

function renderQuestionsTab(panel) {
  if (!inbox.questions.length) {
    panel.replaceChildren(emptyBox(
      "아직 남긴 질문이 없어요",
      "BOO에게 물어보고 답이 없으면 여기에 담겨요.",
      el("a", { className: "btn btn--secondary", text: "BOO에게 물어보기", attrs: { href: "../talk/" } }),
    ));
    return;
  }
  panel.replaceChildren(...inbox.questions.map(questionCard));
}

// --- 스크랩 탭: 해봤노트와 같은 노트 커버(7-③), 스크랩 아이콘은 채운 상태 ---
function kindText(note) {
  const kind = KIND_NAME[note.type] ?? "";
  return note.country ? [kind, note.country].filter(Boolean).join(" · ") : kind;
}

function scrapButton(noteId, initial) {
  const btn = el("button", { className: "icon-btn", attrs: { type: "button" } }, [icon("bookmark")]);
  const set = (on) => {
    btn.setAttribute("aria-pressed", String(on));
    btn.setAttribute("aria-label", on ? "스크랩 취소" : "스크랩");
  };
  set(initial);
  btn.addEventListener("click", async () => {
    const want = btn.getAttribute("aria-pressed") !== "true";
    btn.disabled = true;
    try {
      const res = await scrapNote(noteId, want);
      if (!res || !res.ok) throw new Error((res && res.error) || "스크랩 실패");
      set(res.scrapped === true);
      // 해제해도 카드는 바로 없애지 않는다(잘못 눌렀을 때 다시 켤 수 있게). 다음에 들어오면 목록에서 빠진다.
      toast(res.scrapped ? "내 보관함 스크랩에 담았어요" : "스크랩을 해제했어요");
    } catch (err) {
      console.error(err);
      toast("스크랩하지 못했어요. 다시 시도해 주세요", "circle-alert");
    } finally {
      btn.disabled = false;
    }
  });
  return btn;
}

function scrapCard(scrap) {
  const note = notesById.get(scrap.noteId) || { id: scrap.noteId, program: scrap.program };
  const cat = CATEGORY[note.type] || null;
  const count = Number.isFinite(note.evidenceCount) ? `${note.evidenceCount}건` : DASH;
  const dot = () => el("span", { text: "·", attrs: { "aria-hidden": "true" } });
  const meta = el("p", { className: "note-card__meta" }, [
    el("span", { text: `근거 ${count}` }), dot(),
    el("span", { text: `최근 ${semesterText(note.lastSemester)}` }), dot(),
    el("span", { className: "note-card__star", attrs: { "aria-label": `만족도 ${orDash(note.satisfaction)}` } },
      [icon("star"), el("span", { text: orDash(note.satisfaction) })]),
  ]);
  if (note.type === "비교과") {
    const done = note.completedCount === null || note.completedCount === undefined ? DASH : `${note.completedCount}명`;
    meta.append(dot(), el("span", { text: `이수 ${done}` }));
  }
  return el("article", { className: `note-card${cat ? ` cat-${cat}` : ""}` }, [
    el("div", { className: "note-card__band" }, [
      el("span", { className: "category-tag", text: cat ? CATEGORY_NAME[cat] : "해봤노트" }),
      el("span", { className: "note-card__kind", text: kindText(note) }),
      scrapButton(note.id, true),
    ]),
    el("a", { className: "note-card__body", attrs: { href: `../note/?id=${encodeURIComponent(note.id)}` } }, [
      el("h3", { className: "note-card__title", text: orDash(note.program) }),
      el("p", { className: "note-card__summary", text: orDash(note.oneLine) }),
      el("p", { className: "note-card__target", text: orDash(note.forWhom) }),
      meta,
    ]),
  ]);
}

function renderScrapsTab(panel) {
  if (!inbox.scraps.length) {
    panel.replaceChildren(emptyBox(
      "아직 담아둔 해봤노트가 없어요",
      "해봤노트에서 책갈피를 누르면 여기에 모여요.",
      el("a", { className: "btn btn--secondary", text: "해봤노트 둘러보기", attrs: { href: "../note/" } }),
    ));
    return;
  }
  panel.replaceChildren(...inbox.scraps.map(scrapCard));
}

function renderPanel() {
  const panel = document.getElementById("tabPanel");
  panel.setAttribute("aria-busy", "false");
  panel.setAttribute("aria-labelledby", `tab-${currentTab}`);
  if (currentTab === "questions") renderQuestionsTab(panel);
  else if (currentTab === "scraps") renderScrapsTab(panel);
  else renderNotesTab(panel);
  drawIcons();
}

// 상단 탭 전환 — 같은 화면 안이라 하단 탭은 그대로(5-2). 주소의 ?tab=도 바꿔 새로고침해도 같은 탭
function selectTab(tab, { updateUrl = true } = {}) {
  currentTab = TABS.includes(tab) ? tab : "notes";
  for (const t of TABS) document.getElementById(`tab-${t}`).setAttribute("aria-selected", String(t === currentTab));
  if (updateUrl) history.replaceState(history.state, "", inboxUrl());
  if (inbox) renderPanel();
}
document.querySelector(".top-tabs").addEventListener("click", (e) => {
  const tab = e.target.closest(".top-tab");
  if (tab) selectTab(tab.dataset.tab);
});

// ---------------------------------------------------------------------------
// 5. 알림 목록(2단계, #alerts) — 행 = 아이콘 + 문장 + 시간, 안 읽은 알림은 SOFT BLUE
// ---------------------------------------------------------------------------

async function renderAlerts() {
  const body = document.getElementById("alertsBody");
  document.title = "알림 · 내 보관함";
  if (!inbox) {
    body.replaceChildren(...skeletons(2, "inbox-skeleton"));
    if (!(await inboxReady)) {
      body.replaceChildren(errorBox(() => loadInbox().then(renderAlerts)));
      drawIcons();
      return;
    }
  }
  if (!inbox.alerts.length) {
    body.replaceChildren(emptyBox("아직 알림이 없어요", "선배가 내 질문에 답하면 여기에 알려 드려요.", null));
    drawIcons();
    return;
  }
  const rows = inbox.alerts
    .slice()
    .sort((a, b) => String(b.at).localeCompare(String(a.at)))
    .map((a) => {
      const unread = isUnread(a);
      const inner = [
        icon(a.threadId ? "mail" : a.questionId ? "message-circle" : "notebook-text"),
        el("div", { className: "alert-row__body" }, [
          el("p", { text: orDash(a.text) }),
          el("span", { className: "alert-row__time", text: unread ? `${timeText(a.at)} · 안 읽음` : timeText(a.at) }),
        ]),
      ];
      const cls = `alert-row${unread ? " alert-row--unread" : ""}`;
      // 내 질문에 답이 왔으면 질문 상세로, 내 이야기가 반영됐으면(11/22) 해봤노트 상세로
      if (a.questionId) {
        const row = el("a", { className: cls, attrs: { href: `?tab=questions&question=${encodeURIComponent(a.questionId)}` } }, inner);
        row.addEventListener("click", (e) => {
          e.preventDefault();
          currentTab = "questions";
          history.replaceState(null, "", inboxUrl()); // ← 하면 알림이 아니라 질문함으로
          movedInside = false;
          go(`question=${encodeURIComponent(a.questionId)}`);
        });
        return row;
      }
      // 쪽지 알림(「쪽지 요청이 왔어요」·「선배가 아직 못 봤어요…」)은 그 대화로 바로(11/23 미리님 결정, 작업 28)
      if (a.threadId) {
        return el("a", { className: cls, attrs: { href: `../senior/?thread=${encodeURIComponent(a.threadId)}` } }, inner);
      }
      return a.noteId
        ? el("a", { className: cls, attrs: { href: `../note/?id=${encodeURIComponent(a.noteId)}` } }, inner)
        : el("div", { className: cls }, inner);
    });
  body.replaceChildren(el("div", { className: "alert-list" }, rows));
  drawIcons();
  // 연 순간 읽은 것으로(다음에 들어오면 흰 배경, 종·질문함 점도 꺼짐)
  markSeen();
  renderTabsMeta();
}

// ---------------------------------------------------------------------------
// 6. 내 경험노트 상세(2단계, 8절) — 본인만 열람 표시, 칸별 내 문장(공유한 문장에 「공유됨」),
//    「자소서용 요약 보기」 비활성, 「해봤노트에 공유」 / 「공유 범위 바꾸기」 → 공개 동의 시트
// ---------------------------------------------------------------------------

const myNoteBody = document.getElementById("myNoteBody");
let myNote = null;

async function loadMyNote(id) {
  myNote = null;
  document.getElementById("myNoteTitle").textContent = "내 경험노트";
  myNoteBody.setAttribute("aria-busy", "true");
  myNoteBody.replaceChildren(...skeletons(3, "detail-skeleton"));
  try {
    const res = await getMyNote(id);
    if (!res || res.error || !Array.isArray(res.sections)) throw new Error((res && res.error) || "경험노트 없음");
    myNote = res;
    renderMyNote();
  } catch (err) {
    console.error(err);
    myNoteBody.setAttribute("aria-busy", "false");
    // 남의 기록·없는 기록이면 서버 문구(「볼 수 없는 기록이에요」)를 그대로
    myNoteBody.replaceChildren(errorBox(() => loadMyNote(id), err.message && err.message !== "경험노트 없음" ? err.message : "불러오지 못했어요"));
    drawIcons();
  }
}

function myNoteRow(section) {
  const row = el("div", { className: "summary-row" }, [el("span", { className: "summary-row__name", text: section.name })]);
  const lines = section.lines || [];
  if (!lines.length) row.append(el("p", { className: "summary-row__empty", text: DASH }));
  for (const line of lines) {
    // 후배 질문 칸: Q(후배 질문 원문, 인용) + A(내 답)
    if (section.name === QUESTION_SECTION && line.asked) row.append(el("span", { className: "msg__quote", text: `Q. ${line.asked}` }));
    row.append(el("p", { text: section.name === QUESTION_SECTION ? `A. ${line.text}` : line.text }));
    // 공유한 문장에는 작은 긍정 라벨 「공유됨」(8절)
    if (line.shared) {
      const mark = statusLabel("success", "check", "공유됨");
      mark.classList.add("shared-mark");
      row.append(mark);
    }
  }
  return row;
}

function renderMyNote() {
  const n = myNote;
  const title = `${orDash(n.program)} 경험노트`;
  document.getElementById("myNoteTitle").textContent = title;
  document.title = `${title} · 내 보관함`;

  const card = el("article", { className: "summary-card" }, [
    el("div", { className: "summary-card__head" }, [icon("sparkles"), el("span", { text: title })]),
    ...n.sections.map(myNoteRow),
  ]);

  const shareBtn = el("button", {
    className: "btn btn--primary btn--block",
    text: n.share === "private" ? "해봤노트에 공유" : "공유 범위 바꾸기",
    attrs: { type: "button" },
  });
  shareBtn.disabled = !n.draftId || !n.publicDraft;
  shareBtn.addEventListener("click", openConsent);

  const actions = [shareBtn];
  if (shareBtn.disabled) actions.push(el("p", { className: "btn-reason" }, [icon("info"), el("span", { text: "공유할 요약 초안이 없어요" })]));
  if (n.noteId && n.share !== "private") {
    actions.push(el("a", { className: "link-more", text: `${orDash(n.program)} 해봤노트에서 보기 ›`, attrs: { href: `../note/?id=${encodeURIComponent(n.noteId)}` } }));
  }
  actions.push(...resumeButton());

  myNoteBody.setAttribute("aria-busy", "false");
  myNoteBody.replaceChildren(
    el("div", { className: "label-row" }, [
      statusLabel("info", "lock", "나만 보기"),
      shareLabel(n),
      el("span", { className: "question__date", text: frameText(n) }),
    ]),
    card,
    el("div", { className: "detail-actions" }, actions),
  );
  drawIcons();
}

// 공개 동의 시트(common/consent.js) 열기 — getMyNote 응답을 그대로 넘긴다(spec 4장 getMyNote).
// 「공유 범위 바꾸기」로 열면 시트가 lines[].shared를 보고 지금 공유된 문장만 켠 채로 시작한다.
function openConsent() {
  if (!myNote || !myNote.publicDraft) return;
  document.dispatchEvent(new CustomEvent("open-consent", { detail: myNote }));
}

// 공유가 끝나면: 토스트(11/22 — 「반영 중」 없음, 인터BOO와 같은 문구) + getMyNote를 다시 불러 「공유됨」 라벨을 새로 그림 + 카드 값도
document.addEventListener("consent-saved", (event) => {
  if (!myNote || event.detail.draftId !== myNote.draftId) return;
  if (event.detail.shared > 0) toast("해봤노트에 반영됐어요");
  loadMyNote(myNote.id);
  loadInbox();
});

// ---------------------------------------------------------------------------
// 7. 질문 상세(2단계, 8절) — 질문 문장 + 상태 라벨 + 관련 해봤노트 근거 블록(6-1/6-2)
//    + 답했으면 「후배 질문」 칸의 A 문장과 「해봤노트에서 보기」 + 닮은선배
// ---------------------------------------------------------------------------

const questionBody = document.getElementById("questionBody");

function emptyEvidence(message) {
  return el("div", { className: "evidence evidence--empty" }, [
    el("div", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", el("span", { className: "evidence__num", text: "0" }), "건 · 결과보고서 – · 선배 인터뷰 – · 최근 –"]),
      ]),
    ]),
    el("div", { className: "evidence__empty-body" }, [el("p", { text: message })]),
  ]);
}

// 근거 블록(6-1) — 해봤노트 상세와 같은 모양. 출처는 연도만, 1~2건이면 「선배 N명의 경험이에요」
function evidenceBlock(lines, sources) {
  const items = lines.map((l) => sources[l.sourceId] || {});
  const reports = items.filter((s) => s.docType && s.docType !== "인터뷰").length;
  const interviews = items.filter((s) => s.docType === "인터뷰").length;
  const latest = items.map((s) => s.semester).filter(Boolean).sort((a, b) => semesterKey(b) - semesterKey(a))[0];
  const num = (n) => (n > 0 ? el("span", { className: "evidence__num", text: n }) : DASH);
  const few = lines.length <= 2 ? statusLabel("neutral", "user", `선배 ${lines.length}명의 경험이에요`) : null;
  return el("details", { className: "evidence" }, [
    el("summary", { className: "evidence__head" }, [
      el("span", { className: "evidence__summary" }, [
        icon("sparkles"),
        el("span", {}, ["근거 ", num(lines.length), "건 · 결과보고서 ", num(reports), " · 선배 인터뷰 ", num(interviews), ` · 최근 ${semesterText(latest)}`]),
      ]),
      el("span", { className: "evidence__side" }, [
        few,
        el("span", { className: "evidence__toggle" }, [
          el("span", { className: "evidence__toggle-closed", text: "펼치기" }),
          el("span", { className: "evidence__toggle-open", text: "접기" }),
          icon("chevron-down"),
        ]),
      ]),
    ]),
    el("ul", { className: "evidence__list" }, items
      .slice()
      .sort((a, b) => semesterKey(b.semester) - semesterKey(a.semester))
      .map((s) => el("li", { className: "evidence__item" }, [
        DOC_LABEL[s.docType] || orDash(s.docType), " ", el("span", { className: "evidence__sep", text: "|" }), " ", yearOf(s.semester),
      ]))),
  ]);
}

async function renderQuestion(questionId) {
  document.title = "질문 · 내 보관함";
  questionBody.setAttribute("aria-busy", "true");
  questionBody.replaceChildren(...skeletons(2, "detail-skeleton"));
  if (!inbox && !(await inboxReady)) {
    questionBody.replaceChildren(errorBox(() => loadInbox().then(() => renderQuestion(questionId))));
    drawIcons();
    return;
  }
  const q = inbox.questions.find((x) => x.questionId === questionId);
  if (!q) {
    questionBody.setAttribute("aria-busy", "false");
    questionBody.replaceChildren(emptyBox("질문을 찾지 못했어요", "질문함에서 다시 골라 주세요.", null));
    drawIcons();
    return;
  }

  const head = el("div", { className: "question-head" }, [
    questionStatusLabel(q),
    el("p", { className: "question-head__text", text: orDash(q.text) }),
    el("span", { className: "question__date", text: questionDates(q) }),
  ]);
  const children = [head];

  if (q.status === "answered" && q.noteId) {
    const id = encodeURIComponent(q.noteId);
    // 해봤노트 「후배 질문」 칸에서 이 질문(answersQuestionId)에 대한 선배 답만 찾는다
    let note = null;
    try {
      note = await getNote(q.noteId);
      if (note && note.error) note = null;
    } catch (err) {
      console.error(err);
    }
    const section = note && (note.sections || []).find((s) => s.name === QUESTION_SECTION);
    const answers = section ? (section.lines || []).filter((l) => l.answersQuestionId === q.questionId) : [];
    const sources = (note && note.sources) || {};

    children.push(el("h3", { className: "section-title", text: "선배의 답" }));
    if (answers.length) {
      children.push(...answers.map((a) => {
        const src = sources[a.sourceId] || {};
        return el("div", { className: "line" }, [
          el("div", { className: "qa__a" }, [
            el("span", { className: "qa__mark", text: "A", attrs: { "aria-label": "선배 답" } }),
            el("div", { className: "qa__a-body" }, [
              el("p", { text: a.text }),
              el("div", { className: "line__meta" }, [el("span", { text: `${DOC_LABEL[src.docType] || orDash(src.docType)} · ${yearOf(src.semester)}` })]),
            ]),
          ]),
        ]);
      }));
      children.push(evidenceBlock(answers, sources));
    } else {
      // 답 문장을 못 찾았어도(신고로 숨김 등) 틀은 유지하고 지어내지 않는다(6-2)
      children.push(emptyEvidence(note ? "이 질문에 실린 답이 지금은 보이지 않아요." : "해봤노트를 불러오지 못했어요."));
    }
    children.push(el("div", { className: "btn-row" }, [
      el("a", { className: "btn btn--primary", text: "해봤노트에서 보기", attrs: { href: `../note/?id=${id}` } }),
      el("a", { className: "btn btn--outline", text: "닮은선배 보기", attrs: { href: `../senior/?noteId=${id}` } }),
    ]));
  } else if (q.status === "official") {
    children.push(
      el("div", { className: "evidence-after" }, [statusLabel("info", "info", "공식 안내")]),
      el("p", { className: "sub", text: "학교 규정·절차에 관한 질문이라 선배 경험 대신 공식 안내에서 확인해 주세요." }),
    );
  } else {
    // 답을 기다리는 질문: 근거 0건 틀 + 닮은선배 보기(6-2와 같은 처리)
    children.push(
      emptyEvidence("아직 이 질문에 답한 선배가 없어요. 다음 선배 인터뷰 때 먼저 물어볼게요."),
      el("a", { className: "btn btn--secondary btn--block", text: "닮은선배 보기", attrs: { href: "../senior/" } }),
    );
  }

  questionBody.setAttribute("aria-busy", "false");
  questionBody.replaceChildren(...children);
  drawIcons();
}

// ---------------------------------------------------------------------------
// 8. 시작 — ?tab=notes|questions|scraps, 인터BOO 「나중에 할게요」는 ?from=later
// ---------------------------------------------------------------------------

const params = new URLSearchParams(location.search);
const fromLater = params.get("from") === "later";
// 상세 주소(?mynote=·?question=)로 바로 들어왔으면 주소는 그대로 두고 탭만 맞춘다
const deepLink = params.has("mynote") || params.has("question");
selectTab(params.get("tab") || (params.has("question") ? "questions" : "notes"), { updateUrl: !deepLink });
drawIcons();
if (me) {
  loadInbox().then(() => {
    if (fromLater) toast("내 경험노트에 저장해 두었어요. 언제든 해봤노트에 공유할 수 있어요");
  });
  route();
}
