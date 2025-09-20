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
            
            // determine which endpoint to use based on data type
            let endpoint = '/predict';
            let requestBody = data;
            
            if (data.type === 'image') {
                endpoint = '/predict/image';
                // ensure the structure matches ImagePredictRequest exactly
                requestBody = {
                    type: 'image'
                };
                
                if (data.imageUrl) {
                    requestBody.imageUrl = data.imageUrl;
                }
                if (data.imageData) {
                    requestBody.imageData = data.imageData;
                }
                // add source information for images
                if (data.source_url) {
                    requestBody.source_url = data.source_url;
                }
                if (data.page_title) {
                    requestBody.page_title = data.page_title;
                }
                
                console.log('Image request body structure:', {
                    hasImageUrl: !!requestBody.imageUrl,
                    hasImageData: !!requestBody.imageData,
                    imageDataLength: requestBody.imageData ? requestBody.imageData.length : 0,
                    hasSourceUrl: !!requestBody.source_url,
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
                // add source URL for Facebook posts
                if (data.source_url) {
                    requestBody.source_url = data.source_url;
                }
            } else {
                // default text prediction - include source information
                requestBody = {
                    text: data.text || data,
                    type: 'text'
                };
                
                // add source information if available
                if (data.source_url) {
                    requestBody.source_url = data.source_url;
                }
                if (data.page_title) {
                    requestBody.page_title = data.page_title;
                }
            }
            
            console.log(`Sending ${requestBody.type || 'text'} request to ${endpoint}:`, {
                ...Object.keys(requestBody).reduce((acc, key) => {
                    if (key === 'imageData') {
                        acc[key] = requestBody[key] ? `[Base64 data: ${requestBody[key].length} chars]` : null;
                    } else {
                        acc[key] = requestBody[key];
                    }
                    return acc;
                }, {})
            });
            
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

    async verifyText(text, sourceUrl = null, pageTitle = null) {
        try {
            console.log('Verifying text:', text.substring(0, 100) + '...');
            
            if (!text || typeof text !== 'string') {
                throw new Error('Invalid text provided for verification');
            }
            
            const requestData = { 
                text: text.trim(),
                type: 'text'
            };
            
            // add source information if provided
            if (sourceUrl) {
                requestData.source_url = sourceUrl;
            }
            if (pageTitle) {
                requestData.page_title = pageTitle;
            }
            
            const result = await this.predict(requestData);
            return result;
            
        } catch (error) {
            console.error('Text verification error:', error.message);
            return { success: false, error: error.message };
        }
    }

    async verifyImage(imageUrl, imageData = null, sourceUrl = null, pageTitle = null) {
        try {
            console.log('Verifying image:', imageUrl ? imageUrl.substring(0, 50) + '...' : 'Base64 data provided');
            
            if (!imageUrl && !imageData) {
                throw new Error('No image provided for verification');
            }
            
            const requestBody = {
                type: 'image'
            };
            
            // add image data or URL
            if (imageData) {
                requestBody.imageData = imageData;
                console.log('Sending base64 image data to API');
            } else if (imageUrl) {
                requestBody.imageUrl = imageUrl.trim();
                console.log('Sending image URL to API');
            }
            
            // add source information if provided
            if (sourceUrl) {
                requestBody.source_url = sourceUrl;
            }
            if (pageTitle) {
                requestBody.page_title = pageTitle;
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

    async verifyFacebookPost(postText, imageUrl = null, sourceUrl = null) {
        try {
            console.log('Verifying Facebook post');
            
            if (!postText && !imageUrl) {
                throw new Error('No content provided for verification');
            }
            
            const requestData = { 
                text: postText ? postText.trim() : '',
                imageUrl: imageUrl ? imageUrl.trim() : null,
                type: 'facebook'
            };
            
            // add source URL for Facebook posts
            if (sourceUrl) {
                requestData.source_url = sourceUrl;
            }
            
            const result = await this.predict(requestData);
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

    async getSourceInfo() {
        try {
            console.log('Fetching source information...');
            const data = await this.call('/sources');
            return { success: true, data };
        } catch (error) {
            console.error('Failed to fetch source info:', error.message);
            return { success: false, error: error.message };
        }
    }

    async scoreSource(url, title = '', content = '') {
        try {
            console.log('Scoring source:', url);
            const data = await this.call('/sources/score', {
                method: 'POST',
                body: JSON.stringify({
                    url: url,
                    title: title,
                    content: content
                })
            });
            return { success: true, data };
        } catch (error) {
            console.error('Failed to score source:', error.message);
            return { success: false, error: error.message };
        }
    }

    // convert image file to base64
    async fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result);
            reader.onerror = error => reject(error);
        });
    }

    // verify an image file
    async verifyImageFile(file, sourceUrl = null, pageTitle = null) {
        try {
            const base64Data = await this.fileToBase64(file);
            return await this.verifyImage(null, base64Data, sourceUrl, pageTitle);
        } catch (error) {
            console.error('Image file verification error:', error.message);
            return { success: false, error: error.message };
        }
    }
}

// export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}