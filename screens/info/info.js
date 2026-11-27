// 후속 개발 및 확장방안 안내(11/27, 민지) — 학생 화면 네 곳 메인 헤더의 ⓘ 버튼(#infoBtn)
//   누르면 바텀시트(5-10)로 screens/info/roadmap.md 내용을 보여 준다. 글은 팀원이 그 파일만 고친다(화면 코드에 문구를 두지 않음).
//   데이터는 common/data.js getRoadmap()으로만 받는다(fetch 직접 금지).
//   Markdown은 아래 작은 변환기로 그린다 — 모든 글은 textContent, innerHTML 0건. 파일 안의 HTML·스크립트는 글자로만 보인다.
//   지원: # ## ### 제목 · 문단(줄바꿈 유지) · - * + 글머리(들여쓰기 한 단계) · 1. 번호 · > 인용 · --- 구분선 ·
//         **굵게** · *기울임* · `코드` · [글](https://…) 링크(http·https만) · <!-- 주석 -->(화면에 안 보임)
// 쓰는 법: index.html 헤더에 #infoBtn을 두고 <script type="module" src="../info/info.js"></script>

import { getRoadmap } from "../../common/data.js";

const TITLE = "후속 개발 및 확장방안";

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

// ---------------------------------------------------------------------------
// 1. Markdown → 요소 (안전: 노드를 직접 만들고 글은 textContent로만)
// ---------------------------------------------------------------------------

// 한 줄 안의 강조: **굵게** · __굵게__ · *기울임* · _기울임_ · `코드` · [글](주소)
const INLINE = /(\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\[([^\]]+)\]\(([^)\s]+)\)|\*([^*\s][^*]*)\*|(?<![\w가-힣])_([^_\s][^_]*)_(?![\w가-힣]))/g;
function inline(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index > last) out.push(document.createTextNode(text.slice(last, m.index)));
    if (m[2] || m[3]) out.push(el("strong", { text: m[2] || m[3] }));
    else if (m[4]) out.push(el("code", { text: m[4] }));
    else if (m[5]) {
      // 링크는 http·https만 연다(javascript: 등은 글자로만)
      const safe = /^https?:\/\//i.test(m[6]);
      out.push(safe ? el("a", { text: m[5], attrs: { href: m[6], target: "_blank", rel: "noopener noreferrer" } }) : document.createTextNode(m[5]));
    } else out.push(el("em", { text: m[7] || m[8] }));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(document.createTextNode(text.slice(last)));
  return out;
}

// 여러 줄 → 한 덩어리 안에서 줄바꿈 유지
function withBreaks(lines) {
  const out = [];
  lines.forEach((line, i) => {
    if (i) out.push(el("br"));
    out.push(...inline(line));
  });
  return out;
}

const LIST = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;

export function renderMarkdown(source) {
  const text = String(source || "").replace(/\r\n?/g, "\n").replace(/<!--[\s\S]*?(-->|$)/g, "");
  const lines = text.split("\n");
  const blocks = [];
  let para = [];
  let quote = [];
  let list = null; // { node, ordered, sub: { node, ordered } | null, lastItem }

  const flushPara = () => { if (para.length) blocks.push(el("p", {}, withBreaks(para))); para = []; };
  const flushQuote = () => { if (quote.length) blocks.push(el("blockquote", {}, withBreaks(quote))); quote = []; };
  const flushList = () => { if (list) blocks.push(list.node); list = null; };
  const flushAll = () => { flushPara(); flushQuote(); flushList(); };

  for (const raw of lines) {
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { flushAll(); continue; }

    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) {
      flushAll();
      const level = Math.min(h[1].length, 3); // 시트 제목(h2) 아래: # → h3, ## → h4, ### 이하 → h5
      blocks.push(el(`h${level + 2}`, { className: `md-h${level}` }, inline(h[2].replace(/\s+#+$/, ""))));
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flushAll(); blocks.push(el("hr")); continue; }

    const q = line.match(/^\s*>\s?(.*)$/);
    if (q) { flushPara(); flushList(); quote.push(q[1]); continue; }

    const li = line.match(LIST);
    if (li) {
      flushPara(); flushQuote();
      const ordered = /\d/.test(li[2]);
      const nested = li[1].replace(/\t/g, "  ").length >= 2 && list && list.lastItem;
      const item = el("li", {}, inline(li[3]));
      if (nested) {
        if (!list.sub || list.sub.ordered !== ordered) {
          list.sub = { node: el(ordered ? "ol" : "ul"), ordered };
          list.lastItem.append(list.sub.node);
        }
        list.sub.node.append(item);
      } else {
        if (!list || list.ordered !== ordered) { flushList(); list = { node: el(ordered ? "ol" : "ul"), ordered, sub: null, lastItem: null }; }
        list.node.append(item);
        list.lastItem = item;
        list.sub = null;
      }
      continue;
    }

    // 글머리 바로 아래 들여 쓴 줄은 그 항목에 이어 붙인다
    if (list && list.lastItem && /^\s{2,}/.test(raw)) {
      const target = list.sub ? list.sub.node.lastElementChild : list.lastItem;
      target.append(el("br"), ...inline(line.trim()));
      continue;
    }
    flushQuote(); flushList();
    para.push(line.trim());
  }
  flushAll();
  return blocks;
}

// ---------------------------------------------------------------------------
// 2. 바텀시트 — 다른 화면 위에 덮일 뿐이라 하단 탭·보던 화면·선택 상태는 그대로(5-2)
// ---------------------------------------------------------------------------

const btn = document.getElementById("infoBtn");
let layer = null;
let body = null;
let lastFocus = null;
let loadSeq = 0;

function build() {
  body = el("div", { className: "sheet__body roadmap", attrs: { id: "roadmapBody", "aria-live": "polite" } });
  const close = el("button", { className: "btn btn--secondary btn--block", text: "닫기", attrs: { type: "button" } });
  close.addEventListener("click", closeSheet);
  const sheet = el("div", { className: "sheet", attrs: { role: "dialog", "aria-modal": "true", "aria-labelledby": "roadmapTitle", tabindex: "-1" } }, [
    el("div", { className: "sheet__handle", attrs: { "aria-hidden": "true" } }),
    el("h2", { className: "sheet__title", text: TITLE, attrs: { id: "roadmapTitle" } }),
    body,
    el("div", { className: "sheet__footer" }, [close]),
  ]);
  const scrim = el("div", { className: "sheet-scrim" });
  scrim.addEventListener("click", closeSheet);
  layer = el("div", { className: "sheet-layer", attrs: { id: "roadmapSheet", hidden: "" } }, [scrim, sheet]);
  layer.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeSheet();
    if (e.key === "Tab") { // 시트 안에서만 포커스가 돈다
      const items = [...sheet.querySelectorAll("a[href], button:not([disabled])")];
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === sheet)) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });
  (document.querySelector(".app") || document.body).append(layer);
}

function stateBox(children) {
  return el("div", { className: "roadmap-state" }, children);
}

async function load() {
  const seq = ++loadSeq;
  body.setAttribute("aria-busy", "true");
  body.replaceChildren(...[0, 1, 2].map(() => el("div", { className: "skeleton roadmap-skeleton", attrs: { "aria-hidden": "true" } })));
  const res = await getRoadmap();
  if (seq !== loadSeq) return;
  body.setAttribute("aria-busy", "false");
  if (!res || res.error || typeof res.text !== "string") {
    // 불러오기 실패(6-5): 오류 라벨 + 문구 + 다시 시도
    if (res && res.error) console.error(res.error);
    const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
    retry.addEventListener("click", load);
    body.replaceChildren(stateBox([
      el("span", { className: "status-label status-label--error" }, [icon("circle-alert"), el("span", { text: "불러오지 못했어요" })]),
      el("p", { className: "sub", text: "잠시 뒤 다시 시도해 주세요." }),
      retry,
    ]));
  } else {
    const blocks = renderMarkdown(res.text);
    // 비어 있음(6-4): 주석만 있거나 빈 파일
    body.replaceChildren(...(blocks.length ? [el("div", { className: "md-body" }, blocks)] : [stateBox([
      icon("file-text"),
      el("p", { className: "roadmap-state__title", text: "아직 올라온 내용이 없어요" }),
      el("p", { className: "sub", text: "정리되는 대로 이곳에 올릴게요." }),
    ])]));
  }
  drawIcons();
}

function openSheet() {
  if (!layer) build();
  lastFocus = document.activeElement;
  layer.hidden = false;
  document.body.classList.add("sheet-open");
  body.scrollTop = 0;
  layer.querySelector(".sheet").focus();
  load(); // 열 때마다 새로 읽는다 — 파일을 고친 뒤 시트만 다시 열어도 보이게
}

function closeSheet() {
  if (!layer || layer.hidden) return;
  layer.hidden = true;
  // 다른 시트가 열려 있지 않을 때만 뒤 화면 스크롤을 풀어 준다
  if (![...document.querySelectorAll(".sheet-layer")].some((x) => x !== layer && !x.hidden)) document.body.classList.remove("sheet-open");
  if (lastFocus && lastFocus.isConnected) lastFocus.focus();
}

if (btn) btn.addEventListener("click", openSheet);
