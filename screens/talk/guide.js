// 인터BOO 첫 안내(가이드 화면, 11/27 민지) — 로그인 뒤 처음 들어온 인터BOO 위에 어두운 막을 덮고
// 버튼 하나씩 밝게 비추며 설명 카드를 보여 준다. 기준: docs/design-rules.md 5-12 · 8절 「첫 진입」.
// 규칙: 화면 글은 textContent로만(innerHTML 금지), 색은 style.css 변수만, 서버·AI 호출 없음(고정 문구).
//
// 언제 보이나
//   - 이 탭에서 이 사람이 아직 안 봤을 때(sessionStorage — 로그인이 탭마다 따로라 「다음 로그인」 = 새 탭).
//   - 단, 「다시 보지 않기」(이 브라우저에서 계속) · 「오늘 그만 보기」(오늘 날짜까지)를 눌렀으면 안 보인다(localStorage, 학번별).
//   - 주소에 ?intro=1 이 있으면 위 기억과 상관없이 다시 보인다(시연·리허설용). 보인 뒤 주소에서 지운다.
// 버튼
//   - 「닫기」·Esc·마지막 단계 칩 = 지금만 닫기(다음 로그인 때 다시).
//   - 마지막 단계 칩: 궁금한 게 있어요 → 물어보기 입력창 / 제 경험을 들려줄래요 → 들려주기 탭 / 둘러볼게요 → 닫기.
//     칩은 talk.js 안을 건드리지 않고 화면에 있는 탭 버튼을 대신 누른다.

import { currentUser } from "../../common/data.js";

const me = currentUser();
const ID = me ? me.colreg_no : "";
const SEEN_KEY = `booGuideSeen:${ID}`; // sessionStorage: 이 탭에서 이미 보임
const SKIP_KEY = `booGuideSkip:${ID}`; // localStorage: "never" 또는 "today:YYYY-MM-DD"

// ---------------------------------------------------------------------------
// 1. 단계 — target이 없으면 가운데 카드(막 전체), 있으면 그 요소만 밝게
// ---------------------------------------------------------------------------

const STEPS = [
  {
    boo: true,
    title: "안녕하세요, 저는 BOO예요",
    body: [
      "교환학생, 해외 인턴, 비교과 프로그램처럼 먼저 「해봤던」 선배들의 경험을 모아서 전해 드리고 있어요.",
      "아래의 해봤노트에 선배들의 경험을 카드로 모아 뒀어요.",
    ],
  },
  {
    target: "#tabAsk",
    shape: "pill",
    title: "물어보기",
    body: ["궁금한 걸 물어보면 선배들의 보고서와 인터뷰에서 찾아 알려 드려요. 이렇게 물어봐도 돼요."],
    list: [
      "마르부르크 생활비는 한 달에 얼마나 들어요?",
      "독일 기숙사는 언제 신청해요?",
      "영어를 잘 못해도 지원할 수 있을까요?",
    ],
    after: "아직 정한 곳이 없다면 「어디부터 알아봐야 할지 모르겠어요」라고 하셔도 괜찮아요.",
  },
  {
    target: "#tabTell",
    shape: "pill",
    title: "들려주기",
    body: ["다녀온 경험이 있다면 제가 질문을 드릴게요. 편하게 답해 주시면 노트로 정리해 드려요."],
    list: [
      "정답은 없어요. 기억나는 만큼만 편하게 말해 주세요.",
      "잘 모르겠으면 「모르겠어요」, 그만하고 싶으면 「그만」이라고 하시면 돼요.",
      "후배들이 궁금해한 질문이 있으면 그것부터 여쭤볼게요.",
      "다 끝나면 노트로 정리해서 보여 드려요. 공개할지는 확인하신 뒤에 정하시면 돼요.",
    ],
  },
  {
    target: "#composer",
    title: "어디서 나온 내용인지 함께 적어요",
    body: [
      "제 답에는 늘 어디서 나온 내용인지 함께 적어 드려요.",
      "선배들이 남긴 기록에 없는 내용은 지어내지 않고 「모른다」고 말씀드리고 질문함에 남겨 드릴게요.",
    ],
  },
  {
    target: ".tabbar",
    title: "천천히 둘러보세요",
    list: [
      "해봤노트: 선배들 경험을 프로그램별로 정리해 둔 곳이에요.",
      "닮은선배: 나와 비슷한 선배를 찾아볼 수 있어요.",
      "내 보관함: 내가 한 질문과 남긴 노트, 받은 쪽지, 스크랩이 모여 있어요.",
    ],
    after: "궁금한 게 생기면 언제든 인터BOO로 돌아와 물어보세요.",
  },
  {
    boo: true,
    title: "무엇부터 해 볼까요?",
    choices: [
      { label: "궁금한 게 있어요", run: goAsk },
      { label: "제 경험을 들려줄래요", run: goTell },
      { label: "둘러볼게요", run: () => {} },
    ],
  },
];

// ---------------------------------------------------------------------------
// 2. 보일지 정하기
// ---------------------------------------------------------------------------

const todayText = () => new Date().toLocaleDateString("sv-SE"); // 이 PC 시간대의 YYYY-MM-DD

function skipped() {
  try {
    const v = localStorage.getItem(SKIP_KEY);
    return v === "never" || v === `today:${todayText()}`;
  } catch { return false; }
}
function remember(value) {
  try { localStorage.setItem(SKIP_KEY, value); } catch { /* 저장이 막힌 브라우저면 다음에 다시 보인다 */ }
}
function seenHere() {
  try { return sessionStorage.getItem(SEEN_KEY) === "1"; } catch { return false; }
}
function markSeen() {
  try { sessionStorage.setItem(SEEN_KEY, "1"); } catch { /* 위와 같음 */ }
}

function shouldShow() {
  if (!me) return false;
  const url = new URL(location.href);
  if (url.searchParams.get("intro") === "1") {
    url.searchParams.delete("intro"); // 새로고침해도 다시 강제로 뜨지 않게
    history.replaceState(history.state, "", url);
    return true;
  }
  return !seenHere() && !skipped();
}

// ---------------------------------------------------------------------------
// 3. 그리기
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
const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });

let index = 0;
let layer, spot, card, controls, lastFocus;

function build() {
  spot = el("div", { className: "guide-spot", attrs: { "aria-hidden": "true" } });
  card = el("div", { className: "guide-card" });
  controls = el("div", { className: "guide-controls" }, [
    el("button", { className: "btn btn--text", text: "오늘 그만 보기", attrs: { type: "button" }, on: { click: () => { remember(`today:${todayText()}`); close(); } } }),
    el("button", { className: "btn btn--text", text: "다시 보지 않기", attrs: { type: "button" }, on: { click: () => { remember("never"); close(); } } }),
    el("button", { className: "btn btn--text", text: "닫기", attrs: { type: "button" }, on: { click: () => close() } }),
  ]);
  layer = el("div", {
    className: "guide-layer",
    attrs: { role: "dialog", "aria-modal": "true", "aria-labelledby": "guideTitle" },
  }, [spot, card, controls]);
  // 막·카드 빈 곳을 누르면 다음 단계(버튼을 누른 것은 제외). 마지막 단계는 칩이나 닫기로만 끝난다
  layer.addEventListener("click", (e) => {
    if (e.target.closest("button")) return;
    if (index < STEPS.length - 1) go(index + 1);
  });
  layer.addEventListener("keydown", onKey);
  (document.querySelector(".app") || document.body).append(layer);
}

function stepCard(step) {
  const n = STEPS.indexOf(step);
  const last = n === STEPS.length - 1;
  const parts = [];
  if (step.boo) parts.push(el("img", { className: "boo-illust boo-illust--sm guide-card__boo", attrs: { src: "../../assets/boo-portrait.png", alt: "BOO" } }));
  parts.push(el("h2", { className: "guide-card__title", text: step.title, attrs: { id: "guideTitle", tabindex: "-1" } }));
  for (const p of step.body || []) parts.push(el("p", { className: "guide-card__text", text: p }));
  if (step.list) parts.push(el("ul", { className: "guide-card__list" }, step.list.map((t) => el("li", { text: t }))));
  if (step.after) parts.push(el("p", { className: "guide-card__text", text: step.after }));
  if (step.choices) {
    parts.push(el("div", { className: "guide-card__choices" }, step.choices.map((c) => el("button", {
      className: "btn btn--secondary btn--block",
      text: c.label,
      attrs: { type: "button" },
      on: { click: () => { close(); c.run(); } },
    }))));
  }
  const nav = el("div", { className: "guide-card__nav" }, [
    el("span", { className: "guide-card__count num", text: `${n + 1} / ${STEPS.length}` }),
    n > 0 ? el("button", { className: "btn btn--text", text: "이전", attrs: { type: "button" }, on: { click: () => go(n - 1) } }) : null,
    last ? null : el("button", { className: "btn btn--primary", attrs: { type: "button" }, on: { click: () => go(n + 1) } }, [
      document.createTextNode("다음"), el("i", { className: "icon", attrs: { "data-lucide": "chevron-right" } }),
    ]),
  ]);
  parts.push(nav);
  return parts;
}

// 비출 요소가 화면에 보이면 그 사각형, 아니면(숨김·키보드로 탭이 가려짐 등) null → 가운데 카드
function targetRect(step) {
  if (!step.target) return null;
  const node = document.querySelector(step.target);
  if (!node) return null;
  const r = node.getBoundingClientRect();
  if (r.width === 0 || r.height === 0) return null;
  return r;
}

const PAD = 4; // 밝은 구멍을 요소보다 조금 크게
const GAP = 12; // 구멍과 카드 사이

function place() {
  const step = STEPS[index];
  const r = targetRect(step);
  const vh = window.innerHeight;
  layer.classList.toggle("guide-layer--dim", !r);
  spot.hidden = !r;
  card.classList.toggle("guide-card--center", !r);
  card.style.top = card.style.bottom = "";
  let low = false;
  if (r) {
    spot.className = `guide-spot${step.shape === "pill" ? " guide-spot--pill" : ""}`;
    Object.assign(spot.style, {
      top: `${r.top - PAD}px`, left: `${r.left - PAD}px`,
      width: `${r.width + PAD * 2}px`, height: `${r.height + PAD * 2}px`,
    });
    low = r.top + r.height / 2 > vh / 2; // 아래쪽 요소면 카드는 그 위에
    if (low) card.style.bottom = `${vh - r.top + PAD + GAP}px`;
    else card.style.top = `${r.bottom + PAD + GAP}px`;
  }
  // 아래쪽(입력줄·하단 탭)을 비출 때는 오른쪽 아래 버튼이 가리지 않게 위로 비킨다
  controls.classList.toggle("guide-controls--top", low);
}

function go(next) {
  index = Math.max(0, Math.min(STEPS.length - 1, next));
  const step = STEPS[index];
  const node = step.target && document.querySelector(step.target);
  // 문서 안의 요소(세그먼트 탭)는 화면 안으로 먼저 데려온다. 고정된 입력줄·하단 탭은 그대로
  if (node && getComputedStyle(node).position !== "fixed" && !node.closest(".dock, .tabbar")) {
    const r = node.getBoundingClientRect();
    if (r.top < 64 || r.bottom > window.innerHeight * 0.45) window.scrollBy({ top: r.top - 80, behavior: "instant" });
  }
  card.replaceChildren(...stepCard(step));
  drawIcons();
  place();
  card.querySelector("#guideTitle").focus({ preventScroll: true });
}

function focusables() {
  return [...layer.querySelectorAll("button, [tabindex='-1']")].filter((n) => !n.disabled && n.offsetParent !== null);
}

function onKey(e) {
  if (e.key === "Escape") { e.preventDefault(); close(); return; }
  if (e.key === "ArrowRight" && index < STEPS.length - 1) { e.preventDefault(); go(index + 1); return; }
  if (e.key === "ArrowLeft" && index > 0) { e.preventDefault(); go(index - 1); return; }
  if (e.key === "Tab") { // 안내가 열린 동안 Tab은 안내 안에서만 돈다
    const list = focusables();
    if (!list.length) return;
    const first = list[0];
    const lastNode = list[list.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); lastNode.focus(); }
    else if (!e.shiftKey && document.activeElement === lastNode) { e.preventDefault(); first.focus(); }
  }
}

function open() {
  markSeen();
  lastFocus = document.activeElement;
  build();
  document.body.classList.add("guide-open");
  window.addEventListener("resize", place);
  window.addEventListener("scroll", place, { passive: true });
  if (window.visualViewport) window.visualViewport.addEventListener("resize", place);
  go(0);
}

function close() {
  if (!layer) return;
  window.removeEventListener("resize", place);
  window.removeEventListener("scroll", place);
  if (window.visualViewport) window.visualViewport.removeEventListener("resize", place);
  layer.remove();
  layer = null;
  document.body.classList.remove("guide-open");
  if (lastFocus && lastFocus.isConnected && lastFocus !== document.body) lastFocus.focus({ preventScroll: true });
}

// ---------------------------------------------------------------------------
// 4. 마지막 단계 칩 — 화면에 있는 버튼을 대신 누른다(talk.js 내부를 바꾸지 않음)
// ---------------------------------------------------------------------------

function goAsk() {
  const tab = document.getElementById("tabAsk");
  if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
  const input = document.getElementById("composerInput");
  if (input) input.focus();
}

function goTell() {
  const tab = document.getElementById("tabTell");
  if (tab && tab.getAttribute("aria-selected") !== "true") tab.click();
}

if (shouldShow()) open();
