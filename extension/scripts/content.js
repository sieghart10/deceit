// content.js - Fake News Detector Extension
class FakeNewsDetector {
    constructor() {
        this.isExtensionEnabled = true;
        this.isFacebookEnabled = true;
        this.isFacebook = window.location.hostname.includes("facebook.com");
        this.observer = null;
        this.currentUrl = window.location.href;
        this.pageTitle = document.title;

        this.initialize();
    }

    async initialize() {
        console.log("Content script loaded: Fake News Detector");
        console.log(`Current URL: ${this.currentUrl}`);
        console.log(`Page Title: ${this.pageTitle}`);

        await this.loadSettings();

        try {
            const status = await this.sendApiMessage("checkServerStatus");
            console.log("API server status:", status);
        } catch (err) {
            console.error("API not reachable:", err.message);
        }

        if (this.isExtensionEnabled && this.isFacebookEnabled && this.isFacebook) {
            this.initializeDetector();
        }

        // watch for settings changes
        chrome.storage.onChanged.addListener((changes, namespace) => {
            if (namespace === "sync") {
                if (changes.extensionEnabled) {
                    this.isExtensionEnabled = changes.extensionEnabled.newValue;
                }
                if (changes.facebookEnabled) {
                    this.isFacebookEnabled = changes.facebookEnabled.newValue;
                }

                if (this.isExtensionEnabled && this.isFacebookEnabled && this.isFacebook) {
                    this.initializeDetector();
                } else {
                    this.removeExistingButtons();
                }
            }
        });

        // listen for messages from background script
        chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
            this.handleMessage(message, sender, sendResponse);
            return true; // keep message channel open for async responses
        });

        // watch for URL changes
        this.watchUrlChanges();
    }

    watchUrlChanges() {
        let currentUrl = window.location.href;
        
        const observer = new MutationObserver(() => {
            if (window.location.href !== currentUrl) {
                currentUrl = window.location.href;
                this.currentUrl = currentUrl;
                this.pageTitle = document.title;
                console.log(`URL changed to: ${this.currentUrl}`);
                
                // if still on Facebook
                if (this.isFacebook && this.isExtensionEnabled && this.isFacebookEnabled) {
                    setTimeout(() => this.addVerifyButtons(), 1000);
                }
            }
        });
        
        observer.observe(document, { subtree: true, childList: true });
    }

    handleMessage(message, sender, sendResponse) {
        try {
            switch (message.action) {
                case 'ping':
                    sendResponse({ status: 'pong' });
                    break;
                    
                case 'textVerificationResult':
                    this.handleVerificationResult('text', message.result, message.text);
                    sendResponse({ success: true });
                    break;
                    
                case 'imageVerificationResult':
                    this.handleVerificationResult('image', message.result, message.imageUrl);
                    sendResponse({ success: true });
                    break;
                    
                case 'linkVerificationResult':
                    this.handleVerificationResult('link', message.result, message.url);
                    sendResponse({ success: true });
                    break;
                    
                default:
                    sendResponse({ success: false, error: 'Unknown action' });
            }
        } catch (error) {
            console.error('Error handling message:', error);
            sendResponse({ success: false, error: error.message });
        }
    }

    handleVerificationResult(type, result, content) {
        if (result.success && result.data) {
            const data = result.data;
            const isFake = data.prediction === 'fake';
            const confidence = (data.confidence * 100).toFixed(1);
            
            let message;
            switch (type) {
                case 'text':
                    message = isFake ? "⚠️ Selected text may be fake news" : "✅ Selected text appears to be real news";
                    break;
                case 'image':
                    message = isFake ? "⚠️ Image text may be fake news" : "✅ Image text appears to be real news";
                    break;
                case 'link':
                    message = isFake ? "⚠️ Linked article may be fake news" : "✅ Linked article appears to be real news";
                    break;
            }
            
            message += ` (${confidence}% confidence)`;
            
            // add source information if available
            if (data.source_info) {
                const sourceInfo = data.source_info;
                message += `\nSource: ${sourceInfo.domain} (${sourceInfo.confidence_level} reliability)`;
                
                // show confidence explanation
                if (data.confidence_explanation && data.original_confidence && 
                    Math.abs(data.confidence - data.original_confidence) > 0.05) {
                    message += `\n${data.confidence_explanation}`;
                }
            }
            
            this.showToast(message, isFake ? "#A23131" : "#4CAF50");
        } else {
            this.showToast(`Verification failed: ${result.error || 'Unknown error'}`, "#ff9800");
        }
    }

    async loadSettings() {
        return new Promise((resolve) => {
            chrome.storage.sync.get(
                ["extensionEnabled", "facebookEnabled"],
                (result) => {
                    this.isExtensionEnabled = result.extensionEnabled !== false;
                    this.isFacebookEnabled = result.facebookEnabled !== false;
                    resolve();
                }
            );
        });
    }

    initializeDetector() {
        console.log("Initializing Fake News Detector on Facebook...");

        this.removeExistingButtons();
        setTimeout(() => this.addVerifyButtons(), 1000);

        this.setupObserver();

        setInterval(() => {
            if (this.isExtensionEnabled && this.isFacebookEnabled) {
                this.addVerifyButtons();
            }
        }, 5000);
    }

    removeExistingButtons() {
        document
            .querySelectorAll(".fake-news-verify-btn")
            .forEach((btn) => btn.remove());
    }

    addVerifyButtons() {
        // main post containers with class `x1lliihq`
        const postContainers = document.querySelectorAll('.x1lliihq');

        postContainers.forEach((container) => {
            // check if this container have content
            const hasPostContent = container.querySelector('[data-ad-rendering-role="story_message"], [role="article"]');
            
            if (hasPostContent && !container.querySelector(".fake-news-verify-btn")) {
                const computedStyle = window.getComputedStyle(container);
                if (computedStyle.position === 'static') {
                    container.style.position = 'relative';
                }

                const button = this.createVerifyButton(container);
                container.appendChild(button);
            }
        });
    }

    createVerifyButton(container) {
        const button = document.createElement("button");
        button.className = "fake-news-verify-btn";
        button.innerHTML = `<span class="verify-icon">Verify</span>`;

        Object.assign(button.style, {
            position: "absolute",
            top: "15px",
            right: "90px",
            background: "#e5e5e5ff",
            color: "black",
            border: "2px solid #5d5d5dff",
            borderRadius: "8px",
            padding: "5px 10px",
            fontSize: "12px",
            fontWeight: "600",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "4px",
            height: "32px",
            minWidth: "60px",
            zIndex: "1000",
            transition: "all 0.2s ease",
        });

        // Hover effects
        button.addEventListener("mouseenter", () => {
            button.style.transform = "scale(1.05)";
            button.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";
        });

        button.addEventListener("mouseleave", () => {
            button.style.transform = "scale(1)";
            button.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)";
        });

        button.addEventListener("click", (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.verifyContent(button, container);
        });

        return button;
    }

    async verifyContent(button, container) {
        button.disabled = true;
        button.style.opacity = "1";
        button.textContent = "Analyzing...";

        try {
            const text = this.getPostText(container);
            
            // extract any images from the post
            const images = container.querySelectorAll('img');
            let imageUrl = null;
            
            // find image (not profile pics, icons, etc.)
            for (const img of images) {
                if (img.src && !img.src.includes('profile') && !img.src.includes('emoji') && 
                    img.width > 100 && img.height > 100) {
                    imageUrl = img.src;
                    break;
                }
            }
            
            const status = await this.sendApiMessage("checkServerStatus");
            console.log("API server responded:", status);

            try {
                let result;
                
                if (imageUrl && text) {
                    // if have both text and image
                    result = await this.sendApiMessage("verifyFacebookPost", { 
                        text: text,
                        imageUrl: imageUrl,
                        source_url: this.currentUrl,
                        page_title: this.pageTitle
                    });
                } else if (text) {
                    // text only
                    result = await this.sendApiMessage("verifyText", { 
                        text: text,
                        source_url: this.currentUrl,
                        page_title: this.pageTitle
                    });
                } else {
                    throw new Error("No content found to verify");
                }
                
                if (result.success && result.data) {
                    const data = result.data;
                    const isFake = data.prediction === 'fake';
                    const confidence = (data.confidence * 100).toFixed(1);
                    
                    let message = `${data.message}`;
                    
                    // add source information if available
                    if (data.source_info) {
                        const sourceInfo = data.source_info;
                        message += `\nSource: ${sourceInfo.domain} (${sourceInfo.confidence_level} reliability)`;
                        
                        // show confidence change
                        if (data.original_confidence && Math.abs(data.confidence - data.original_confidence) > 0.05) {
                            const change = data.confidence > data.original_confidence ? "boosted" : "reduced";
                            message += `\nConfidence ${change} based on source reliability`;
                        }
                    }
                    
                    this.showResult(button, isFake, message);
                } else {
                    throw new Error(result.error || "API verification failed");
                }
            } catch (apiError) {
                console.log("API verification failed, using fallback:", apiError.message);
                // local detection
                const fake = this.detectFakeNews(text);
                this.showResult(button, fake, "Local detection (API unavailable)");
            }
            
        } catch (error) {
            console.error("Verification error:", error);
            this.showResult(button, false, "Verification failed: " + error.message);
        } finally {
            button.disabled = false;
            button.style.opacity = "1";
            button.textContent = "Verify";
        }
    }

    // helper: get main post text
    getPostText(container) {
        const messageNode = container.querySelector('[data-ad-rendering-role="story_message"]') 
                        || container.querySelector('div[role="article"]');
        
        if (!messageNode) return "";

        let text = "";
        const spans = messageNode.querySelectorAll("span[dir='auto']");
        for (let span of spans) {
            if (span.innerText && span.innerText.trim().length > 20) { 
                text += span.innerText.trim() + " ";
            }
        }
        return text.trim();
    }

    detectFakeNews(text) {
        const fakeKeywords = ["breaking", "shocking", "miracle cure", "secret"];
        return fakeKeywords.some((word) =>
            text.toLowerCase().includes(word)
        );
    }

    showResult(button, isFake, message) {
        const bgColor = isFake ? "#f44336" : "#4CAF50";

        this.showToast(message, bgColor);
        
        const originalBg = button.style.background;
        button.style.background = bgColor;
        button.textContent = isFake ? "Fake" : "Real";
        
        setTimeout(() => {
            button.style.background = originalBg;
            button.textContent = "Verify";
        }, 3000);
    }

    showToast(message, bgColor = "#333") {
        let toast = document.createElement("div");
        toast.innerHTML = message.replace(/\n/g, '<br>'); // line breaks
        Object.assign(toast.style, {
            position: "fixed",
            bottom: "20px",
            left: "20px",
            border: "2px solid #5d5d5dff",
            background: bgColor,
            color: "white",
            padding: "10px 16px",
            borderRadius: "8px",
            fontSize: "15px",
            fontWeight: "500",
            lineHeight: "1.4",
            zIndex: "9999",
            opacity: "0",
            transition: "opacity 0.6s ease, transform 0.6s ease",
            transform: "translateY(20px)",
            // boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
        });

        document.body.appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = "1";
            toast.style.transform = "translateY(0)";
        });

        // remove after 5s
        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(20px)";
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    setupObserver() {
        if (this.observer) this.observer.disconnect();

        this.observer = new MutationObserver(() => {
            if (this.isExtensionEnabled && this.isFacebookEnabled) {
                // debouncer
                clearTimeout(this.observerTimeout);
                this.observerTimeout = setTimeout(() => {
                    this.addVerifyButtons();
                }, 500);
            }
        });

        this.observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    sendApiMessage(action, data = {}) {
        return new Promise((resolve, reject) => {
            // include current page information
            const message = { 
                action, 
                ...data,
                // ensure source information is passed along
                current_url: this.currentUrl,
                page_title: this.pageTitle
            };
            
            chrome.runtime.sendMessage(message, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(new Error(chrome.runtime.lastError.message));
                }
                if (!response) {
                    return reject(new Error("No response from background"));
                }
                if (response.success) {
                    resolve(response);
                } else {
                    reject(new Error(response.error || "Unknown error"));
                }
            });
        });
    }
}

// --- Bootstrap ---
let detector = null;

function initializeDetector() {
    if (!detector) {
        detector = new FakeNewsDetector();
        window.fakeNewsDetector = detector; // expose for debugging
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeDetector);
} else {
    initializeDetector();
}

window.addEventListener("load", () => {
    setTimeout(() => {
        if (detector) {
            detector.addVerifyButtons();
        }
    }, 2000);
});