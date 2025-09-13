importScripts("api.js");

const api = new API("http://127.0.0.1:8000");

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      let result;

      switch (message.action) {
        case "checkServerStatus":
          result = await api.checkServerStatus();
          break;
        default:
          throw new Error("Unknown action: " + message.action);
      }

      sendResponse({ success: true, data: result });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  })();

  return true;
});