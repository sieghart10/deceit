class API {
    constructor(baseUrl = 'http://127.0.0.1:8000') {
        this.baseUrl = baseUrl;
        this.initialized = false;
        this.initialize();
    }

    initialize() {
        if (this.initialized) return;
        
        this.initialized = true;
        console.log('API initialized successfully');
    }
        
    async call(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        
        const config = {
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        console.log(`Making ${config.method || 'GET'} request to ${url}`);
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), config.timeout);

            const response = await fetch(url, {
                ...config,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.text().catch(() => null);
                let errorMessage;
                let parsedError;
                
                try {
                    parsedError = JSON.parse(errorData);
                    errorMessage = parsedError.detail || parsedError.message || errorData;
                } catch {
                    errorMessage = errorData;
                }

                if (response.status === 404) {
                    errorMessage = `Resource not found: ${errorMessage || 'Unknown error'}`;
                } else if (response.status === 500) {
                    errorMessage = `Server error: ${errorMessage || 'Internal server error'}`;
                } else if (response.status === 503) {
                    errorMessage = `Service unavailable: ${errorMessage || 'Extension disabled'}`;
                } else if (response.status === 422) {
                    errorMessage = `Processing error: ${errorMessage || 'Unable to process content'}`;
                } else {
                    errorMessage = errorMessage || `HTTP ${response.status}: ${response.statusText}`;
                }

                throw new Error(errorMessage);
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error.message);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout - server may be slow');
            } else if (error instanceof TypeError && error.message.includes('fetch')) {
                throw new Error('Network error - check if server is running');
            }
            throw error;
        }
    }

    async checkServerStatus() {
        try {
            console.log('Checking server status...');
            const data = await this.call('/');
            console.log('Server status response:', data);
            return { 
                online: data.status === 'online', 
                data,
                modelLoaded: data.model_loaded 
            };
        } catch (error) {
            console.error('Server status check failed:', error.message);
            return { 
                online: false, 
                error: error.message,
                modelLoaded: false 
            };
        }
    }

    async predict(data) {
        try {
            console.log('Making prediction with data:', data);
            
            if (!data) {
                throw new Error('No data provided for prediction');
            }
            
            // Determine which endpoint to use based on data type
            let endpoint = '/predict';
            let requestBody = data;
            
            if (data.type === 'image') {
                endpoint = '/predict/image';
                // FIX: Make sure the structure matches ImagePredictRequest exactly
                requestBody = {};
                if (data.imageUrl) {
                    requestBody.imageUrl = data.imageUrl;
                }
                if (data.imageData) {
                    requestBody.imageData = data.imageData;
                }
                requestBody.type = 'image';
                
                console.log('Image request body structure:', {
                    hasImageUrl: !!requestBody.imageUrl,
                    hasImageData: !!requestBody.imageData,
                    imageDataLength: requestBody.imageData ? requestBody.imageData.length : 0,
                    type: requestBody.type
                });
                
            } else if (data.type === 'link') {
                endpoint = '/check/link';
                requestBody = { url: data.url };
            } else if (data.type === 'facebook') {
                endpoint = '/check/facebook';
                requestBody = {
                    text: data.text,
                    imageUrl: data.imageUrl
                };
            } else {
                // Default text prediction
                requestBody = {
                    text: data.text || data,
                    type: 'text'
                };
            }
            
            console.log(`Sending ${requestBody.type || 'text'} request to ${endpoint}:`, Object.keys(requestBody));
            
            const result = await this.call(endpoint, {
                method: 'POST',
                body: JSON.stringify(requestBody)
            });
            
            console.log('Prediction result:', result);
            return { success: true, data: result };
            
        } catch (error) {
            console.error('Prediction error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async verifyText(text) {
        try {
            console.log('Verifying text:', text.substring(0, 100) + '...');
            
            if (!text || typeof text !== 'string') {
                throw new Error('Invalid text provided for verification');
            }
            
            const result = await this.predict({ 
                text: text.trim(),
                type: 'text'
            });
            
            return result;
            
        } catch (error) {
            console.error('Text verification error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async verifyImage(imageUrl, imageData = null) {
        try {
            console.log('Verifying image:', imageUrl ? imageUrl.substring(0, 50) + '...' : 'Base64 data provided');
            
            if (!imageUrl && !imageData) {
                throw new Error('No image provided for verification');
            }
            
            // Create the request body
            const requestBody = {
                type: 'image'
            };
            
            // Add image data or URL
            if (imageData) {
                requestBody.imageData = imageData;
                console.log('Sending base64 image data to API');
            } else if (imageUrl) {
                requestBody.imageUrl = imageUrl.trim();
                console.log('Sending image URL to API');
            }
            
            const result = await this.call('/predict/image', {
                method: 'POST',
                body: JSON.stringify(requestBody)
            });
            
            console.log('Image verification result:', result);
            return { success: true, data: result };
            
        } catch (error) {
            console.error('Image verification error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async verifyLink(url) {
        try {
            console.log('Verifying link:', url);
            
            if (!url || typeof url !== 'string') {
                throw new Error('Invalid URL provided for verification');
            }
            
            const result = await this.predict({ 
                url: url.trim(),
                type: 'link'
            });
            
            return result;
            
        } catch (error) {
            console.error('Link verification error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async verifyFacebookPost(postText, imageUrl = null) {
        try {
            console.log('Verifying Facebook post');
            
            if (!postText && !imageUrl) {
                throw new Error('No content provided for verification');
            }
            
            const result = await this.predict({ 
                text: postText ? postText.trim() : '',
                imageUrl: imageUrl ? imageUrl.trim() : null,
                type: 'facebook'
            });
            
            return result;
            
        } catch (error) {
            console.error('Facebook post verification error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async getSettings() {
        try {
            console.log('Fetching settings...');
            const data = await this.call('/settings');
            return { success: true, data };
        } catch (error) {
            console.error('Failed to fetch settings:', error.message);
            return { success: false, error: error.message };
        }
    }

    async updateSettings(settings) {
        try {
            console.log('Updating settings:', settings);
            const data = await this.call('/settings', {
                method: 'PUT',
                body: JSON.stringify(settings)
            });
            return { success: true, data };
        } catch (error) {
            console.error('Failed to update settings:', error.message);
            return { success: false, error: error.message };
        }
    }

    async getStats() {
        try {
            console.log('Fetching API stats...');
            const data = await this.call('/stats');
            return { success: true, data };
        } catch (error) {
            console.error('Failed to fetch stats:', error.message);
            return { success: false, error: error.message };
        }
    }

    // Helper function to convert image file to base64
    async fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    }

    // Helper function to verify an image file
    async verifyImageFile(file) {
        try {
            const base64Data = await this.fileToBase64(file);
            return await this.verifyImage(null, base64Data);
        } catch (error) {
            console.error('Image file verification error:', error.message);
            return { success: false, error: error.message };
        }
    }
}

// Export for use in other scripts if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}