// Import API script
importScripts("api.js");

const api = new API("http://127.0.0.1:8000");

// Helper function to download image and convert to base64
async function downloadImageAsBase64(imageUrl) {
  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('Failed to download image:', error);
    throw error;
  }
}

// Helper function to check if content script is available
async function isContentScriptAvailable(tabId) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, { action: 'ping' }, (response) => {
      if (chrome.runtime.lastError) {
        resolve(false);
      } else {
        resolve(true);
      }
    });
  });
}

// Helper function to inject content script if needed
async function ensureContentScript(tabId) {
  try {
    const isAvailable = await isContentScriptAvailable(tabId);
    if (!isAvailable) {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['extension/scripts/content.js']
      });
      // Wait a bit for the script to initialize
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return true;
  } catch (error) {
    console.log('Could not inject content script:', error.message);
    return false;
  }
}

// On extension install
chrome.runtime.onInstalled.addListener(() => {
  console.log("Fake News Detector Extension running in background.");
});

// Receiving a message
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log(sender.tab ? "from a content script:" + sender.tab.url : "from the extension");

  (async () => {
    try {
      let result;

      switch (request.action) {
        case "ping":
          // Simple ping response for content script availability check
          result = { status: "pong" };
          break;

        case "checkServerStatus":
          result = await api.checkServerStatus();
          break;

        case "verifyText":
          console.log("Verifying text:", request.text);
          if (!request.text) {
            throw new Error("No text provided for verification");
          }
          result = await api.verifyText(request.text);
          break;

        case "verifyImage":
          console.log("Verifying image:", request.imageUrl || "Base64 data");
          if (!request.imageUrl && !request.imageData) {
            throw new Error("No image provided for verification");
          }
          // If we have a URL but no base64 data, try to download and convert it
          if (request.imageUrl && !request.imageData) {
            try {
              const base64Data = await downloadImageAsBase64(request.imageUrl);
              // Send the base64 data to the API instead of URL
              result = await api.verifyImage(null, base64Data);
              
            } catch (downloadError) {
              console.error('Failed to download image for verification:', downloadError);
              // Fallback to trying with just the URL
              result = await api.verifyImage(request.imageUrl, null);
              
            }
          } else {
            result = await api.verifyImage(request.imageUrl, request.imageData);
          }
          console.log("Request data structure:", JSON.stringify({
              imageUrl: request.imageUrl,
              hasImageData: !!request.imageData,
              imageDataLength: request.imageData ? request.imageData.length : 0
          }));
          break;

        case "verifyLink":
          console.log("Verifying link:", request.url);
          if (!request.url) {
            throw new Error("No URL provided for verification");
          }
          result = await api.verifyLink(request.url);
          break;

        case "verifyFacebookPost":
          console.log("Verifying Facebook post");
          if (!request.text && !request.imageUrl) {
            throw new Error("No content provided for Facebook post verification");
          }
          result = await api.verifyFacebookPost(request.text, request.imageUrl);
          break;

        case "predict":
          console.log("Making prediction with data:", request.data);
          if (!request.data) {
            throw new Error("No data provided for prediction");
          }
          result = await api.predict(request.data);
          break;

        case "getSettings":
          result = await api.getSettings();
          break;

        case "updateSettings":
          if (!request.settings) {
            throw new Error("No settings provided");
          }
          result = await api.updateSettings(request.settings);
          break;

        case "getStats":
          result = await api.getStats();
          break;

        default:
          throw new Error("Unknown action: " + request.action);
      }

      sendResponse({ success: true, data: result });
    } catch (err) {
      console.error("Background script error:", err);
      sendResponse({ success: false, error: err.message });
    }
  })();

  return true; // keeps message channel open for async
});

// Create context menu
chrome.contextMenus.create({
  id: "textMenu",
  title: "Verify selected text: '%s'",
  contexts: ["selection"],
});

chrome.contextMenus.create({
  id: "imageMenu",
  title: "Verify this image",
  contexts: ["image"],
});

chrome.contextMenus.create({
  id: "linkMenu",
  title: "Verify this link",
  contexts: ["link"],
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    if (info.menuItemId === "textMenu" && info.selectionText) {
      console.log("Selected text to verify:", info.selectionText);
      
      const result = await api.verifyText(info.selectionText);
      
      // Try to send message to content script, but don't fail if it's not available
      if (tab && tab.id) {
        const contentScriptAvailable = await ensureContentScript(tab.id);
        if (contentScriptAvailable) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'textVerificationResult',
            text: info.selectionText,
            result: result
          }, (response) => {
            if (chrome.runtime.lastError) {
              console.log('Could not send message to content script:', chrome.runtime.lastError.message);
            }
          });
        }
      }
      
      // Always show notification regardless of content script
      if (result.success && result.data) {
        const data = result.data;
        const isFake = data.prediction === 'fake';
        const confidence = (data.confidence * 100).toFixed(1);
        
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: isFake ? 'Warning: Fake News Detected' : 'Verified: Real News',
          message: `${data.message} (${confidence}% confidence)`
        });
      } else {
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Verification Error',
          message: result.error || 'Failed to verify text'
        });
      }
    }

    if (info.menuItemId === "imageMenu" && info.srcUrl) {
      console.log("Image URL to verify:", info.srcUrl);
      
      try {
        // Download image and convert to base64
        const base64Data = await downloadImageAsBase64(info.srcUrl);
        
        // Verify the image using base64 data instead of URL
        const result = await api.verifyImage(null, base64Data);
        
        // Try to send message to content script, but don't fail if it's not available
        if (tab && tab.id) {
          const contentScriptAvailable = await ensureContentScript(tab.id);
          if (contentScriptAvailable) {
            chrome.tabs.sendMessage(tab.id, {
              action: 'imageVerificationResult',
              imageUrl: info.srcUrl,
              result: result
            }, (response) => {
              if (chrome.runtime.lastError) {
                console.log('Could not send message to content script:', chrome.runtime.lastError.message);
              }
            });
          }
        }
        
        // Always show notification regardless of content script
        if (result.success && result.data) {
          const data = result.data;
          const isFake = data.prediction === 'fake';
          const confidence = (data.confidence * 100).toFixed(1);
          
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: isFake ? 'Warning: Fake News in Image' : 'Verified: Real News in Image',
            message: `${data.message} (${confidence}% confidence)`
          });
        } else {
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: 'Image Verification Error',
            message: result.error || 'Failed to verify image'
          });
        }
      } catch (downloadError) {
        console.error('Failed to download image:', downloadError);
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Image Download Error',
          message: 'Could not download image for verification'
        });
      }
    }

    if (info.menuItemId === "linkMenu" && info.linkUrl) {
      console.log("Link to verify:", info.linkUrl);
      
      const result = await api.verifyLink(info.linkUrl);
      
      // Try to send message to content script, but don't fail if it's not available
      if (tab && tab.id) {
        const contentScriptAvailable = await ensureContentScript(tab.id);
        if (contentScriptAvailable) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'linkVerificationResult',
            url: info.linkUrl,
            result: result
          }, (response) => {
            if (chrome.runtime.lastError) {
              console.log('Could not send message to content script:', chrome.runtime.lastError.message);
            }
          });
        }
      }
      
      // Always show notification regardless of content script
      if (result.success && result.data) {
        const data = result.data;
        const isFake = data.prediction === 'fake';
        const confidence = (data.confidence * 100).toFixed(1);
        
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: isFake ? 'Warning: Fake News Article' : 'Verified: Real News Article',
          message: `${data.title ? data.title.substring(0, 50) + '...' : 'Article'} - ${confidence}% confidence`
        });
      } else {
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: 'Link Verification Error',
          message: result.error || 'Failed to verify link'
        });
      }
    }
  } catch (error) {
    console.error('Context menu action error:', error);
    
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icons/icon48.png',
      title: 'Verification Error',
      message: `Error: ${error.message}`
    });
  }
});

// Handle extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log("Extension starting up...");
  api.checkServerStatus().then(status => {
    console.log("Startup server status:", status);
    chrome.storage.local.set({ serverStatus: status });
  });
});

// Handle tab updates to inject content script if needed
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url) {
    if (tab.url.includes('facebook.com')) {
      chrome.storage.sync.get(['extensionEnabled', 'facebookEnabled'], (result) => {
        const extensionEnabled = result.extensionEnabled !== false;
        const facebookEnabled = result.facebookEnabled !== false;
        
        if (extensionEnabled && facebookEnabled) {
          chrome.scripting.executeScript({
            target: { tabId: tabId },
            files: ['content.js']
          }).catch(err => {
            console.log('Content script injection skipped:', err.message);
          });
        }
      });
    }
  }
});

// Periodic server health check
// setInterval(async () => {
//   try {
//     const status = await api.checkServerStatus();
//     chrome.storage.local.set({ serverStatus: status });
//     console.log("Periodic health check:", status.online ? "Server online" : "Server offline");
//   } catch (error) {
//     console.error("Health check failed:", error);
//     chrome.storage.local.set({ 
//       serverStatus: { 
//         online: false, 
//         error: error.message 
//       } 
//     });
//   }
// }, 60000);

console.log("Background script loaded successfully");