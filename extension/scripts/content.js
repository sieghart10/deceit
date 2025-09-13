// content.js - Fake News Detector Extension
class FakeNewsDetector {
    constructor() {
        this.isExtensionEnabled = true;
        this.isFacebookEnabled = true;
        this.isFacebook = window.location.hostname.includes("facebook.com");
        this.observer = null;

        this.initialize();
    }

    async initialize() {
        console.log("Content script loaded: Fake News Detector");

        await this.loadSettings();

        // Initialize API connection (via background)
        try {
            const status = await this.sendApiMessage("checkServerStatus");
            console.log("API server status:", status);
        } catch (err) {
            console.error("API not reachable:", err.message);
        }

        if (this.isExtensionEnabled && this.isFacebookEnabled && this.isFacebook) {
            this.initializeDetector();
        }

        // Watch for settings changes
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
        const ellipsisMenus = document.querySelectorAll(
            'div[aria-label="Actions for this post"]'
        );

        ellipsisMenus.forEach((menu) => {
            const parent = menu.parentElement;

            if (parent && !parent.querySelector(".fake-news-verify-btn")) {
                parent.style.display = "flex";
                parent.style.flexDirection = "column";
                parent.style.alignItems = "flex-start";
                parent.style.gap = "10px";

                const button = this.createVerifyButton(parent);
                parent.appendChild(button);

                const target = document.querySelector(
                    '[role="article"] div[dir="auto"]'
                );
                if (target) target.style.width = "300px";
            }
        });
    }

    createVerifyButton(container) {
        const button = document.createElement("button");
        button.className = "fake-news-verify-btn";
        button.innerHTML = `<span class="verify-icon">Verify</span>`;

        Object.assign(button.style, {
            background: "linear-gradient(135deg, #A1DD70, #A23131)",
            color: "white",
            border: "none",
            borderRadius: "6px",
            padding: "4px 10px",
            fontSize: "12px",
            fontWeight: "600",
            cursor: "pointer",
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "left",
            gap: "4px",
            height: "28px",
            width: "50px",
        });

        button.addEventListener("click", (e) => {
            e.stopPropagation();
            e.preventDefault();
            this.verifyContent(button, container);
        });

        return button;
    }

    verifyContent(button, container) {
        button.disabled = true;
        button.style.opacity = "0.7";
        button.textContent = "...";

        const text = container.innerText || "";

        

        setTimeout(() => {
            const fake = this.detectFakeNews(text);
            this.showResult(button, fake);
        }, 2000);
    }

    detectFakeNews(text) {
        const fakeKeywords = ["breaking", "shocking", "miracle cure", "secret"];
        return fakeKeywords.some((word) =>
            text.toLowerCase().includes(word)
        );
    }

    showResult(button, isFake) {
        button.disabled = false;
        button.style.opacity = "1";

        if (isFake) {
            button.textContent = "Fake";
            button.style.background = "#A23131";
        } else {
            button.textContent = "Real";
            button.style.background = "#A1DD70";
        }

        setTimeout(() => {
            button.innerHTML = `<span class="verify-icon"></span><span class="verify-text">Verify</span>`;
            button.style.background =
                "linear-gradient(135deg, #A1DD70, #A23131)";
        }, 4000);
    }

    setupObserver() {
        if (this.observer) this.observer.disconnect();

        this.observer = new MutationObserver(() => {
            if (this.isExtensionEnabled && this.isFacebookEnabled) {
                this.addVerifyButtons();
            }
        });

        this.observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    }

    // ✅ API call method is now inside the class
    sendApiMessage(action, payload = {}) {
        return new Promise((resolve, reject) => {
            chrome.runtime.sendMessage({ action, payload }, (response) => {
                if (chrome.runtime.lastError) {
                    return reject(
                        new Error(chrome.runtime.lastError.message)
                    );
                }
                if (!response) {
                    return reject(new Error("No response from background"));
                }
                if (response.success) {
                    resolve(response.data);
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
