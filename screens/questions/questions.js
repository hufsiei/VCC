// 내 보관함 화면 (작업 23) — 내 경험노트 / 질문함 / 스크랩 탭(1단계) + 알림 목록(2단계, #alerts)
// 기준: docs/design-rules.md 7-⑥·5-2·6-3~6-5·8절(알림 목록), docs/spec-v1.md 4장 getInbox·listNotes·scrapNote
// 규칙: 데이터는 common/data.js 함수로만, 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만.

import { currentUser, getInbox, listNotes, scrapNote } from "../../common/data.js";

// ---------------------------------------------------------------------------
// 0. 로그인 확인
// ---------------------------------------------------------------------------

const me = currentUser();
if (!me) location.replace("../login/");
if (me && me.status === "직원") document.getElementById("consoleBtn").hidden = false;

const CATEGORY = { 교환: "global", 파견: "global", 인턴: "practice", 비교과: "extra" };
const CATEGORY_NAME = { global: "국제교류", practice: "현장실습", extra: "비교과" };
const KIND_NAME = { 교환: "교환학생", 파견: "파견", 인턴: "인턴", 비교과: "" };
const DASH = "–";
const TABS = ["notes", "questions", "scraps"];

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
const orDash = (v) => (v === null || v === undefined || String(v).trim() === "" ? DASH : String(v));

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

function emptyBox(title, desc, button) {
  return el("div", { className: "state-box" }, [
    el("img", { className: "boo-illust", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }),
    el("p", { className: "state-box__title", text: title }),
    el("p", { className: "sub", text: desc }),
    button,
  ]);
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
// 2. 데이터 — getInbox + listNotes(스크랩·경험노트 카드의 분야·커버 정보)
// ---------------------------------------------------------------------------

let inbox = null;
let notesById = new Map();
let notesByProgram = new Map();
let currentTab = "notes";

async function load() {
  const panel = document.getElementById("tabPanel");
  panel.setAttribute("aria-busy", "true");
  panel.replaceChildren(...[0, 1].map(() => el("div", { className: "skeleton inbox-skeleton", attrs: { "aria-hidden": "true" } })));
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
    const notes = (list && list.notes) || [];
    notesById = new Map(notes.map((n) => [n.id, n]));
    notesByProgram = new Map(notes.map((n) => [n.program, n]));
    renderTabsMeta();
    renderPanel();
  } catch (err) {
    console.error(err);
    panel.setAttribute("aria-busy", "false");
    panel.replaceChildren(errorBox(load));
    drawIcons();
  }
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
  const bell = document.getElementById("bellBtn");
  document.getElementById("bellDot").hidden = unread.length === 0;
  bell.setAttribute("aria-label", unread.length ? `알림, 새 알림 ${unread.length}개` : "알림");
}

// ---------------------------------------------------------------------------
// 3. 탭 내용
// ---------------------------------------------------------------------------

// --- 내 경험노트 탭 ---
// 공유 상태 라벨(7-⑥): 나만 보기=중립, 반영 중=중립, N문장 공유=중립, 해봤노트 공유됨=긍정
// [임시 — 미리님 확인 전] spec·mock의 myNotes에는 share가 없어 없으면 「나만 보기」로 둔다(서버 기본값 private).
// 채운 칸 수·공유 문장 수·「반영 중」 값이 spec에 들어오면 여기만 바꾼다.
function shareLabel(note) {
  if (note.share === "shared") return statusLabel("success", "check", "해봤노트 공유됨");
  if (note.share === "partial") {
    return statusLabel("neutral", "share-2", Number.isFinite(note.sharedCount) ? `${note.sharedCount}문장 공유` : "일부 공유");
  }
  if (note.share === "pending") return statusLabel("neutral", "clock", "반영 중");
  return statusLabel("neutral", "lock", "나만 보기");
}

function myNoteCard(note) {
  const pub = notesByProgram.get(note.program); // 같은 프로그램의 해봤노트 → 분야
  const cat = pub ? CATEGORY[pub.type] : null;
  const frame = Number.isFinite(note.filled) && Number.isFinite(note.total) ? `노트 틀 ${note.filled}/${note.total}` : `노트 틀 ${DASH}`;

  // 「자소서용 요약 보기」 — v4.3: 비활성 + 「운영 연계 시 열려요」(6-6)
  const resume = el("button", { className: "btn btn--secondary btn--block", text: "자소서용 요약 보기", attrs: { type: "button", disabled: "" } });

  return el("article", { className: `note-card${cat ? ` cat-${cat}` : ""}` }, [
    el("div", { className: "note-card__band" }, [
      el("span", { className: "category-tag", text: cat ? CATEGORY_NAME[cat] : "경험" }),
      el("span", { className: "note-card__kind", text: orDash(note.program) }),
    ]),
    el("div", { className: "mynote__body" }, [
      el("h3", { className: "note-card__title", text: `${orDash(note.program)} 경험노트` }),
      el("div", { className: "mynote__meta" }, [el("span", { text: frame }), shareLabel(note)]),
      resume,
      el("p", { className: "btn-reason" }, [icon("lock"), el("span", { text: "운영 연계 시 열려요" })]),
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
function questionCard(q) {
  const children = [];
  if (q.status === "answered") {
    children.push(
      statusLabel("success", "check", "선배가 답했어요"),
      el("p", { className: "question__text", text: orDash(q.text) }),
      el("span", { className: "question__date", text: `${dateText(q.askedAt)} 남김 · ${dateText(q.answeredAt)} 답변` }),
    );
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
      statusLabel("info", "info", "공식 안내"),
      el("p", { className: "question__text", text: orDash(q.text) }),
      el("span", { className: "question__date", text: `${dateText(q.askedAt)} 남김` }),
      el("p", { className: "question__info", text: "학교 규정·절차 질문이라 공식 안내에서 확인해 주세요." }),
    );
  } else {
    children.push(
      statusLabel("neutral", "clock", "답을 기다려요"),
      el("p", { className: "question__text", text: orDash(q.text) }),
      el("span", { className: "question__date", text: `${dateText(q.askedAt)} 남김` }),
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
function selectTab(tab) {
  currentTab = TABS.includes(tab) ? tab : "notes";
  for (const t of TABS) document.getElementById(`tab-${t}`).setAttribute("aria-selected", String(t === currentTab));
  const url = new URL(location.href);
  url.searchParams.set("tab", currentTab);
  url.searchParams.delete("from");
  history.replaceState(history.state, "", url.pathname + url.search + url.hash);
  if (inbox) renderPanel();
}
document.querySelector(".top-tabs").addEventListener("click", (e) => {
  const tab = e.target.closest(".top-tab");
  if (tab) selectTab(tab.dataset.tab);
});

// ---------------------------------------------------------------------------
// 4. 알림 목록(2단계, #alerts) — 상세 헤더 + 하단 탭 숨김
// ---------------------------------------------------------------------------

const viewInbox = document.getElementById("viewInbox");
const viewAlerts = document.getElementById("viewAlerts");
let openedAlertsFromInbox = false;

function renderAlerts() {
  const body = document.getElementById("alertsBody");
  if (!inbox) {
    body.replaceChildren(...[0, 1].map(() => el("div", { className: "skeleton inbox-skeleton", attrs: { "aria-hidden": "true" } })));
    return;
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
        icon(a.noteId ? "message-circle" : "bell"),
        el("div", { className: "alert-row__body" }, [
          el("p", { text: orDash(a.text) }),
          el("span", { className: "alert-row__time", text: unread ? `${timeText(a.at)} · 안 읽음` : timeText(a.at) }),
        ]),
      ];
      const cls = `alert-row${unread ? " alert-row--unread" : ""}`;
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

function route() {
  if (location.hash === "#alerts") {
    viewInbox.hidden = true;
    viewAlerts.hidden = false;
    window.scrollTo(0, 0);
    renderAlerts();
  } else {
    viewAlerts.hidden = true;
    viewInbox.hidden = false;
  }
}

document.getElementById("bellBtn").addEventListener("click", () => { openedAlertsFromInbox = true; });
document.getElementById("alertsBack").addEventListener("click", () => {
  if (openedAlertsFromInbox) {
    openedAlertsFromInbox = false;
    history.back();
  } else {
    history.replaceState(null, "", location.pathname + location.search);
    route();
  }
});
window.addEventListener("hashchange", route);

// ---------------------------------------------------------------------------
// 5. 시작 — ?tab=notes|questions|scraps, 인터BOO 「나중에 할게요」는 ?from=later
// ---------------------------------------------------------------------------

const params = new URLSearchParams(location.search);
const fromLater = params.get("from") === "later";
selectTab(params.get("tab") || "notes");
drawIcons();
route();
if (me) {
  load().then(() => {
    if (location.hash === "#alerts") renderAlerts();
    if (fromLater) toast("내 경험노트에 저장해 두었어요. 언제든 해봤노트에 공유할 수 있어요");
  });
}
