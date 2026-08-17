const statusElement = document.getElementById("status");
const codeElement = document.getElementById("code");
const pairButton = document.getElementById("pair");

function showStatus(message, connected = false) {
  statusElement.textContent = message;
  statusElement.classList.toggle("connected", connected);
}

async function refreshStatus() {
  const status = await chrome.runtime.sendMessage({ type: "status" });
  if (status?.connected) {
    showStatus("Chrome이 SSMaker와 연결되었습니다.", true);
    pairButton.textContent = "다시 확인";
    return;
  }
  if (status?.paired) {
    showStatus("연결을 다시 시도하고 있어요. SSMaker가 실행 중인지 확인해 주세요.");
    await chrome.runtime.sendMessage({ type: "poll" });
    return;
  }
  showStatus("SSMaker에서 연결 코드를 확인해 입력해 주세요.");
}

pairButton.addEventListener("click", async () => {
  const code = codeElement.value.replace(/\D/g, "");
  if (code.length !== 6) {
    showStatus("6자리 연결 코드를 입력해 주세요.");
    return;
  }
  pairButton.disabled = true;
  showStatus("연결하고 있어요.");
  try {
    const result = await chrome.runtime.sendMessage({ type: "pair", code });
    if (!result?.ok) throw new Error(result?.error || "연결에 실패했습니다.");
    showStatus("Chrome이 SSMaker와 연결되었습니다.", true);
    codeElement.value = "";
  } catch (error) {
    showStatus(error instanceof Error ? error.message : "연결에 실패했습니다.");
  } finally {
    pairButton.disabled = false;
  }
});

refreshStatus();
