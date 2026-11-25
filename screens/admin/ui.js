// 관리자 콘솔 공통 도우미 — 요소 만들기(글은 textContent로만, innerHTML 금지), 아이콘, 상태 라벨, 토스트.

export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  const { className, text, attrs } = props;
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, String(v));
  for (const child of [].concat(children)) if (child !== null && child !== undefined && child !== false) node.append(child);
  return node;
}

export const icon = (name) => el("i", { className: "icon", attrs: { "data-lucide": name } });
export const drawIcons = () => window.lucide && window.lucide.createIcons({ attrs: { "stroke-width": 1.75 } });

// 상태 라벨(3-4): 색 + 아이콘 + 문구
export const statusLabel = (kind, iconName, text) =>
  el("span", { className: `status-label status-label--${kind}` }, [iconName ? icon(iconName) : null, el("span", { text })]);

export const fmt = (n) => (typeof n === "number" && Number.isFinite(n) ? n.toLocaleString("ko-KR") : "–");

export function toast(text, iconName = "check") {
  const host = document.getElementById("toastHost");
  host.replaceChildren(el("span", { className: "toast" }, [icon(iconName), el("span", { text })]));
  drawIcons();
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => host.replaceChildren(), 3000);
}

// 오류(6-5): 오류 라벨 + 문구 + 「다시 시도」(외곽선)
export function errorBox(message, onRetry) {
  const retry = el("button", { className: "btn btn--outline", text: "다시 시도", attrs: { type: "button" } });
  retry.addEventListener("click", onRetry);
  return el("div", { className: "card state-box" }, [
    statusLabel("error", "circle-alert", "불러오지 못했어요"),
    el("p", { text: message || "잠시 뒤 다시 시도해 주세요." }),
    retry,
  ]);
}
