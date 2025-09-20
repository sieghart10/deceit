importScripts("api.js");

const api = new API("http://127.0.0.1:8000");

// download image and convert to base64
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

// get page title from tab
async function getPageTitle(tabId) {
  return new Promise((resolve) => {
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      function: () => document.title
    }, (results) => {
      if (chrome.runtime.lastError || !results || !results[0]) {
        resolve("Unknown Title");
      } else {
        resolve(results[0].result);
      }
    });
  });
}

// check if content script is available
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

// inject content script if needed
async function ensureContentScript(tabId) {
  try {
    const isAvailable = await isContentScriptAvailable(tabId);
    if (!isAvailable) {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['extension/scripts/content.js']
      });
      // wait for the script to initialize
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
          
          // get source URL and page title from the tab
          let sourceUrl = null;
          let pageTitle = null;
          
          if (sender.tab) {
            sourceUrl = sender.tab.url;
            pageTitle = sender.tab.title || await getPageTitle(sender.tab.id);
          }
          
          // create request with source information
          const textRequest = {
            text: request.text,
            type: 'text',
            source_url: sourceUrl,
            page_title: pageTitle
          };
          
          result = await api.predict(textRequest);
          break;

        case "verifyImage":
          console.log("Verifying image:", request.imageUrl || "Base64 data");
          if (!request.imageUrl && !request.imageData) {
            throw new Error("No image provided for verification");
          }
          
          // get source URL and page title
          let imageSourceUrl = null;
          let imagePageTitle = null;
          
          if (sender.tab) {
            imageSourceUrl = sender.tab.url;
            imagePageTitle = sender.tab.title || await getPageTitle(sender.tab.id);
          }
          
          // if URL but no base64 data, try to download and convert it
          if (request.imageUrl && !request.imageData) {
            try {
              const base64Data = await downloadImageAsBase64(request.imageUrl);
              
              // Create enhanced request with source information
              const imageRequest = {
                type: 'image',
                imageData: base64Data,
                source_url: imageSourceUrl,
                page_title: imagePageTitle
              };
              
              result = await api.predict(imageRequest);
              
            } catch (downloadError) {
              console.error('Failed to download image for verification:', downloadError);
              
              // just the URL
              const fallbackRequest = {
                type: 'image',
                imageUrl: request.imageUrl,
                source_url: imageSourceUrl,
                page_title: imagePageTitle
              };
              
              result = await api.predict(fallbackRequest);
            }
          } else {
            // create request with source information
            const imageRequest = {
              type: 'image',
              imageUrl: request.imageUrl,
              imageData: request.imageData,
              source_url: imageSourceUrl,
              page_title: imagePageTitle
            };
            
            result = await api.predict(imageRequest);
          }
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
          
          // add source URL for Facebook posts
          let facebookSourceUrl = null;
          if (sender.tab && sender.tab.url) {
            facebookSourceUrl = sender.tab.url;
          }
          
          const apiResult = await api.verifyFacebookPost(request.text, request.imageUrl, facebookSourceUrl);
          
          // console.log("=== FACEBOOK API RESULT ===");
          // console.log(JSON.stringify(apiResult, null, 2));
          
          if (apiResult.success && apiResult.data) {
            result = apiResult.data;
          } else {
            result = apiResult;
          }
          break;

        case "predict":
          console.log("Making prediction with data:", request.data);
          if (!request.data) {
            throw new Error("No data provided for prediction");
          }
          
          // add source information if not present
          if (sender.tab && !request.data.source_url) {
            request.data.source_url = sender.tab.url;
            request.data.page_title = sender.tab.title || await getPageTitle(sender.tab.id);
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

// create context menu
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

// handle context menu clicks
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    if (info.menuItemId === "textMenu" && info.selectionText) {
      console.log("Selected text to verify:", info.selectionText);
      
      // create request with source information
      const textRequest = {
        text: info.selectionText,
        type: 'text',
        source_url: tab ? tab.url : null,
        page_title: tab ? tab.title : null
      };
      
      const result = await api.predict(textRequest);
      
      // send message to content script, don't fail if not available
      if (tab && tab.id) {
        const contentScriptAvailable = await ensureContentScript(tab.id);
        if (contentScriptAvailable) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'textVerificationResult',
            text: info.selectionText,
            result: result
          }, (response) => {
            if (chrome.runtime.lastError) {
              console.log(`response: ${response.status}`)
              console.log('Could not send message to content script:', chrome.runtime.lastError.message);
            }
          });
        }
      }
      
      // always show notification
      if (result.success && result.data) {
        const data = result.data;
        const isFake = data.prediction === 'fake';
        const confidence = (data.confidence * 100).toFixed(1);
        
        let notificationMessage = `${data.message}`;
        
        // add source information to notification if available
        if (data.source_info && data.confidence_explanation) {
          const sourceInfo = data.source_info;
          notificationMessage += `\nSource: ${sourceInfo.domain} (${sourceInfo.confidence_level} reliability)`;
          
          if (data.original_confidence && Math.abs(data.confidence - data.original_confidence) > 0.05) {
            const change = data.confidence > data.original_confidence ? "boosted" : "reduced";
            notificationMessage += `\nConfidence ${change} based on source reliability`;
          }
        }

        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: isFake ? 'Warning: Fake News Detected' : 'Verified: Real News',
          message: notificationMessage
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
        // download image and convert to base64
        const base64Data = await downloadImageAsBase64(info.srcUrl);
        
        // create request with source information
        const imageRequest = {
          type: 'image',
          imageData: base64Data,
          source_url: tab ? tab.url : null,
          page_title: tab ? tab.title : null
        };
        
        const result = await api.predict(imageRequest);
        
        if (tab && tab.id) {
          const contentScriptAvailable = await ensureContentScript(tab.id);
          if (contentScriptAvailable) {
            chrome.tabs.sendMessage(tab.id, {
              action: 'imageVerificationResult',
              imageUrl: info.srcUrl,
              result: result
            }, (response) => {
              if (chrome.runtime.lastError) {
                console.log(`response: ${response.status}`)
                console.log('Could not send message to content script:', chrome.runtime.lastError.message);
              }
            });
          }
        }
        
        if (result.success && result.data) {
          const data = result.data;
          const isFake = data.prediction === 'fake';
          const confidence = (data.confidence * 100).toFixed(1);
          
          let notificationMessage = `${data.message}`;
          let message = data.message;
          
          if (data.confidence_explanation && data.original_confidence && 
              Math.abs(data.confidence - data.original_confidence) > 0.05 &&
              !message.includes('boosted') && !message.includes('reduced')) {
              const change = data.confidence > data.original_confidence ? "boosted" : "reduced";
              message += `\nConfidence ${change} based on source reliability`;
          }
          
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon48.png',
            title: isFake ? 'Warning: Fake News in Image' : 'Verified: Real News in Image',
            message: message
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
      
      if (tab && tab.id) {
        const contentScriptAvailable = await ensureContentScript(tab.id);
        if (contentScriptAvailable) {
          chrome.tabs.sendMessage(tab.id, {
            action: 'linkVerificationResult',
            url: info.linkUrl,
            result: result
          }, (response) => {
            if (chrome.runtime.lastError) {
              console.log(`response: ${response.status}`)
              console.log('Could not send message to content script:', chrome.runtime.lastError.message);
            }
          });
        }
      }
      
      if (result.success && result.data) {
        const data = result.data;
        const isFake = data.prediction === 'fake';
        const confidence = (data.confidence * 100).toFixed(1);
        
        let notificationMessage = `${data.title ? data.title.substring(0, 50) + '...' : 'Article'} - ${confidence}% confidence`;
        
        if (data.source_info && data.confidence_explanation) {
          const sourceInfo = data.source_info;
          notificationMessage += `\nSource: ${sourceInfo.domain} (${sourceInfo.confidence_level} reliability)`;
        }
        
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icons/icon48.png',
          title: isFake ? 'Warning: Fake News Article' : 'Verified: Real News Article',
          message: notificationMessage
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

chrome.runtime.onStartup.addListener(() => {
  console.log("Extension starting up...");
  api.checkServerStatus().then(status => {
    console.log("Startup server status:", status);
    chrome.storage.local.set({ serverStatus: status });
  });
});

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

console.log("Background script loaded successfully");