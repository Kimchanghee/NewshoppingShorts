const BRIDGE_BASE = "http://127.0.0.1:38471";
const PLATFORM_SITES = {
  douyin: "douyin.com/video",
  kuaishou: "kuaishou.com/short-video",
  xiaohongshu: "xiaohongshu.com/explore",
};
const PLATFORM_PATTERNS = {
  douyin: "^https://www\\.douyin\\.com/video/\\d{10,25}(?:[/?#].*)?$",
  kuaishou:
    "^https://www\\.kuaishou\\.com/short-video/[0-9A-Za-z_-]{8,}(?:[/?#].*)?$",
  xiaohongshu:
    "^https://www\\.xiaohongshu\\.com/explore/[0-9a-f]{20,}(?:[/?#].*)?$",
};

let pollActive = false;

async function storedToken() {
  const state = await chrome.storage.local.get(["bridgeToken"]);
  return String(state.bridgeToken || "");
}

async function bridgeFetch(path, options = {}) {
  const token = await storedToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body) headers.set("Content-Type", "application/json");
  return fetch(`${BRIDGE_BASE}${path}`, { ...options, headers, cache: "no-store" });
}

async function pairWithCode(code) {
  const response = await fetch(`${BRIDGE_BASE}/v1/pair`, {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code: String(code || "").trim() }),
  });
  if (!response.ok) throw new Error("연결 코드를 확인해 주세요.");
  const payload = await response.json();
  if (!payload.ok || !payload.token) throw new Error("연결에 실패했습니다.");
  await chrome.storage.local.set({ bridgeToken: payload.token });
  runPollLoop();
  return { ok: true };
}

async function readBridgeStatus() {
  try {
    const response = await fetch(`${BRIDGE_BASE}/v1/status`, { cache: "no-store" });
    if (!response.ok) return { ok: false, connected: false };
    return await response.json();
  } catch (_error) {
    return { ok: false, connected: false };
  }
}

async function waitForTabComplete(tabId, timeoutMs = 15000) {
  const current = await chrome.tabs.get(tabId);
  if (current.status === "complete") return;
  return new Promise((resolve, reject) => {
    let finished = false;
    const cleanup = () => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      clearTimeout(timer);
    };
    const done = (callback) => {
      if (finished) return;
      finished = true;
      cleanup();
      callback();
    };
    const onUpdated = (updatedTabId, changeInfo) => {
      if (updatedTabId === tabId && changeInfo.status === "complete") {
        done(resolve);
      }
    };
    const timer = setTimeout(
      () => done(() => reject(new Error("검색 페이지 응답 시간이 초과되었습니다."))),
      timeoutMs,
    );
    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

async function collectIndexedLinks(tabId, patternSource) {
  const execution = await chrome.scripting.executeScript({
    target: { tabId },
    args: [patternSource],
    func: (source) => {
      const pattern = new RegExp(source);
      const output = [];
      const seen = new Set();
      const add = (raw) => {
        let value = String(raw || "").trim();
        if (!value) return;
        try {
          const parsed = new URL(value, location.href);
          if (parsed.hostname.endsWith("google.com") && parsed.pathname === "/url") {
            value = parsed.searchParams.get("q") || parsed.searchParams.get("url") || value;
          } else {
            value = parsed.href;
          }
        } catch (_error) {
          return;
        }
        if (!pattern.test(value)) return;
        const canonical = value.split("?", 1)[0].split("#", 1)[0].replace(/\/$/, "");
        if (!seen.has(canonical)) {
          seen.add(canonical);
          output.push(canonical);
        }
      };
      document.querySelectorAll("a[href]").forEach((anchor) => {
        add(anchor.href);
        add(anchor.getAttribute("href"));
      });
      return output.slice(0, 30);
    },
  });
  return Array.isArray(execution?.[0]?.result) ? execution[0].result : [];
}

async function executeSearchTask(task) {
  const platform = String(task.platform || "");
  const query = String(task.query || "").trim().slice(0, 180);
  const site = PLATFORM_SITES[platform];
  const pattern = PLATFORM_PATTERNS[platform];
  if (task.action !== "google_index_search" || !site || !pattern || !query) {
    throw new Error("지원하지 않는 검색 요청입니다.");
  }

  const searchUrl = new URL("https://www.google.com/search");
  searchUrl.searchParams.set("q", `${query} site:${site}`);
  searchUrl.searchParams.set("hl", "zh-CN");

  const tab = await chrome.tabs.create({ active: false, url: searchUrl.href });
  try {
    await waitForTabComplete(tab.id);
    return await collectIndexedLinks(tab.id, pattern);
  } finally {
    if (tab?.id != null) {
      try {
        await chrome.tabs.remove(tab.id);
      } catch (_error) {
        // The user may already have closed the temporary search tab.
      }
    }
  }
}

async function postTaskResult(task, links, error = "") {
  await bridgeFetch("/v1/results", {
    method: "POST",
    body: JSON.stringify({
      task_id: String(task.task_id || ""),
      links: Array.isArray(links) ? links : [],
      error: String(error || "").slice(0, 240),
    }),
  });
}

async function pollOnce() {
  if (!(await storedToken())) return false;
  const response = await bridgeFetch("/v1/tasks?wait=20");
  if (response.status === 204) return true;
  if (response.status === 401) {
    await chrome.storage.local.remove(["bridgeToken"]);
    return false;
  }
  if (!response.ok) return false;
  const task = await response.json();
  try {
    const links = await executeSearchTask(task);
    await postTaskResult(task, links);
  } catch (error) {
    await postTaskResult(task, [], error instanceof Error ? error.message : String(error));
  }
  return true;
}

async function runPollLoop() {
  if (pollActive) return;
  pollActive = true;
  try {
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const keepGoing = await pollOnce().catch(() => false);
      if (!keepGoing) break;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  } finally {
    pollActive = false;
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("ssmaker-poll", { periodInMinutes: 0.5 });
  runPollLoop();
});
chrome.runtime.onStartup.addListener(() => {
  chrome.alarms.create("ssmaker-poll", { periodInMinutes: 0.5 });
  runPollLoop();
});
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "ssmaker-poll") runPollLoop();
});
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "pair") {
    pairWithCode(message.code).then(sendResponse).catch((error) => {
      sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
    });
    return true;
  }
  if (message?.type === "status") {
    readBridgeStatus().then(sendResponse);
    return true;
  }
  if (message?.type === "poll") {
    runPollLoop().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});

chrome.alarms.create("ssmaker-poll", { periodInMinutes: 0.5 });
runPollLoop();
