// 헤더 종의 새 소식 점 + 쪽지 읽음 기억 (11/24, 내 보관함 · 쪽지 탭으로 옮기며 만듦)
// 인터BOO·해봤노트·닮은선배·내 보관함 네 화면이 같이 쓴다: <script type="module" src="../questions/bell.js">
//   종(#bellBtn) 안의 점(#bellDot)을 켠다 — 안 읽은 알림(getInbox.alerts) 또는 안 읽은 쪽지(getMessages.threads[].unread)
//   서버는 대화 중 새 쪽지에 알림을 만들지 않으므로(spec getMessages [11/23 읽음]) 쪽지는 unread로 따로 본다.
//   POLL_MS마다, 그리고 탭으로 돌아올 때 다시 확인한다(실시간 연결은 하지 않음 — 작업 28 비고).
// 규칙: 데이터는 common/data.js 함수로만. 읽음 기억은 sessionStorage(탭마다 따로 — 두 창 시연).
// common/에 둘 만한 코드지만 common은 미리 담당이라, 알림 목록이 있는 내 보관함 폴더에 둔다.

import { currentUser, getInbox, getMessages } from "../../common/data.js";

const POLL_MS = 15000;

// --- 알림: 이 탭에서 알림 목록을 마지막으로 연 시각보다 늦은 알림이 안 읽은 것(getInbox에 읽음 표시가 없음) ---
const SEEN_KEY = "vccAlertsSeenAt";
export function seenAt() {
  try { return sessionStorage.getItem(SEEN_KEY) || ""; } catch { return ""; }
}
export function markSeen() {
  try { sessionStorage.setItem(SEEN_KEY, new Date().toISOString()); } catch { /* 저장 못 해도 화면은 그대로 */ }
}
export const isUnread = (a) => !seenAt() || new Date(a.at) > new Date(seenAt());

// --- 쪽지: 대화창을 연 때의 마지막 쪽지 시각을 기억한다 ---
// 서버는 getMessages(threadId)로 읽음 처리하지만 mock은 기억하지 않아서, 연 대화의 unread가 계속 남는다 → 화면에서 한 번 더 거른다
const READ_KEY = "vccThreadReadAt";
function readMap() {
  try { return JSON.parse(sessionStorage.getItem(READ_KEY)) || {}; } catch { return {}; }
}
const lastAt = (t) => String(((t.messages || [])[(t.messages || []).length - 1] || {}).at || "");
export function markThreadRead(t) {
  const map = readMap();
  map[t.threadId] = lastAt(t) || new Date().toISOString();
  try { sessionStorage.setItem(READ_KEY, JSON.stringify(map)); } catch { /* 그대로 */ }
}
// 안 읽은 쪽지 수(상대가 보낸 것). 연 뒤로 새 쪽지가 없으면 0
export function unreadOf(t) {
  const n = Number.isFinite(t.unread) ? t.unread : 0;
  if (!n) return 0;
  const read = readMap()[t.threadId];
  return read && lastAt(t) && lastAt(t) <= read ? 0 : n;
}
// 쪽지 탭에 새 소식이 있나: 안 읽은 쪽지 또는 받은 수락 대기 요청
export const threadHasNews = (t) => unreadOf(t) > 0 || (t.role === "senior" && t.status === "waiting");

// --- 이 탭에서 보낸 쪽지 요청(서버 목록에 아직 없을 때 잠깐 붙여 둔다 — mock은 기억하지 않아서 필요) ---
// 닮은선배에서 보내고 내 보관함 · 쪽지 탭으로 넘어가도 보이게 sessionStorage에 둔다. 서버 목록에 보이면 버린다.
const SENT_KEY = "vccSentRequests";
export function localRequests() {
  try { return JSON.parse(sessionStorage.getItem(SENT_KEY)) || []; } catch { return []; }
}
export function rememberRequest(thread) {
  const list = localRequests().filter((t) => t.threadId !== thread.threadId);
  list.push(thread);
  try { sessionStorage.setItem(SENT_KEY, JSON.stringify(list)); } catch { /* 그대로 */ }
}
export function forgetRequests(threadIds) {
  if (!threadIds.length) return;
  const list = localRequests().filter((t) => !threadIds.includes(t.threadId));
  try { sessionStorage.setItem(SENT_KEY, JSON.stringify(list)); } catch { /* 그대로 */ }
}

// --- 종 점 ---
let last = { alerts: [], threads: [] };
export const latest = () => last;

function paint() {
  const dot = document.getElementById("bellDot");
  const btn = document.getElementById("bellBtn");
  if (!dot || !btn) return;
  const fresh = last.alerts.filter(isUnread);
  const alerted = new Set(fresh.map((a) => a.threadId).filter(Boolean)); // 같은 대화를 알림·쪽지로 두 번 세지 않게
  const alerts = fresh.length;
  const notes = last.threads.reduce((sum, t) => sum + (alerted.has(t.threadId) ? 0 : unreadOf(t)), 0);
  const n = alerts + notes;
  dot.hidden = n === 0;
  btn.setAttribute("aria-label", n ? `알림, 새 소식 ${n}개` : "알림");
}

// 서버에 다시 물어 점을 그린다. 화면이 이미 받은 값이 있으면 넘겨서 다시 부르지 않게 한다
export async function refreshBell(given) {
  if (given) {
    if (given.alerts) last = { ...last, alerts: given.alerts };
    if (given.threads) last = { ...last, threads: given.threads };
    paint();
    return;
  }
  const [box, msgs] = await Promise.all([getInbox().catch(() => null), getMessages().catch(() => null)]);
  if (box && !box.error) last = { ...last, alerts: box.alerts || [] };
  if (msgs && !msgs.error) last = { ...last, threads: Array.isArray(msgs.threads) ? msgs.threads : [] };
  paint();
  for (const fn of listeners) fn(last);
}
// 내 보관함이 탭 점을 같이 바꾸려고 듣는다
const listeners = new Set();
export const onBell = (fn) => listeners.add(fn);
export const repaintBell = paint;

let timer = null;
function startPolling() {
  clearInterval(timer);
  timer = setInterval(() => { if (!document.hidden) refreshBell(); }, POLL_MS);
}
if (currentUser() && document.getElementById("bellBtn")) {
  refreshBell();
  startPolling();
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshBell(); });
}
