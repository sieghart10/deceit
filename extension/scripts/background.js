// Import API script
importScripts("api.js");

const api = new API("http://127.0.0.1:8000");

// On extension install
chrome.runtime.onInstalled.addListener(() => {
  console.log("hello");
});

// Receiving a message
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log(sender.tab ? "from a content script:" + sender.tab.url : "from the extension");

  // Wrap in async to allow await calls
  (async () => {
    try {
      let result;

      switch (request.action) {
        case "checkServerStatus":
          result = await api.checkServerStatus();
          break;

        case "hello":
          if (request.greeting === "hello") {
            result = { farewell: "goodbye" };
          }
          break;

        default:
          throw new Error("Unknown action: " + request.action);
      }

      sendResponse({ success: true, data: result });
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  })();

  return true; // keeps message channel open for async
});

// Create context menu
chrome.contextMenus.create({
  id: "1",
  // title: "You selected '%s'",
  title: "Verify",
  contexts: ["selection"],
});

chrome.contextMenus.create({
  id: "imageMenu",
  title: "Verify this image",
  contexts: ["image"],
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "textMenu" && info.selectionText) {
    console.log("Selected text to verify:", info.selectionText);
    // TODO: send to API for verification
  }

  if (info.menuItemId === "imageMenu" && info.srcUrl) {
    console.log("Image URL to verify:", info.srcUrl);
    // TODO: send to API for verification
  }
});


// importScripts("api.js");

// const api = new API("http://127.0.0.1:8000");

// chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
//   (async () => {
//     try {
//       let result;

//       switch (message.action) {
//         case "checkServerStatus":
//           result = await api.checkServerStatus();
//           break;
//         default:
//           throw new Error("Unknown action: " + message.action);
//       }

//       sendResponse({ success: true, data: result });
//     } catch (err) {
//       sendResponse({ success: false, error: err.message });
//     }
//   })();

//   return true;
// });