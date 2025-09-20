import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, File, UploadFile, Request
import uvicorn
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from typing import Optional
import base64
from PIL import Image
import io
import requests
from bs4 import BeautifulSoup
import random

from tf_idf import load_model, predict as tfidf_predict
from bag_of_words import load_model, predict as bow_predict
from utils.tesseract import image_to_text

load_dotenv()
HOST = os.getenv("API_HOST")
PORT = int(os.getenv("API_PORT"))
MODEL = os.getenv("TRAINED_MODEL", "tf_idf_naive_bayes_model_v1.pkl")
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

model = None
user_settings = {
    "extension_enabled": True
}

# Request/Response Models
class TextPredictRequest(BaseModel):
    text: str
    type: Optional[str] = "text"

class ImagePredictRequest(BaseModel):
    imageUrl: Optional[str] = None
    imageData: Optional[str] = None  # Base64 encoded image
    type: Optional[str] = "image"

class LinkCheckRequest(BaseModel):
    url: str

class SettingsUpdateRequest(BaseModel):
    extension_enabled: Optional[bool] = None

class PredictionResponse(BaseModel):
    input: str
    prediction: str
    confidence: float
    probabilities: dict
    score_difference: float
    message: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print("Loading model...")
    try:
        model_data = load_model(MODEL)
        if not model_data:
            print("ERROR: Failed to load model. Please ensure model exists in trained_models/")
            raise RuntimeError("Model loading failed")
        model = model_data
        print(f"✓ Model loaded successfully")
    except Exception as e:
        print(f"ERROR loading model: {e}")
        raise RuntimeError(f"Failed to load model: {e}")
    
    yield
    
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": f"Fake News Detector API running on {HOST}:{PORT}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "online",
        "model_loaded": model is not None
    }

@app.get("/favicon.ico")
async def favicon():
    return None

@app.post("/predict")
async def predict_text(request: TextPredictRequest):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text input cannot be empty")
    
    try:
        class_counts, class_word_counts, vocab_size, idf_values = model
        
        # Make prediction
        prediction_result = tfidf_predict(
            text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
            idf_values,
            is_log=False
        )
        
        # Format response
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        # Create confidence message
        if confidence > 0.8:
            confidence_level = "high"
            message = f"{'⚠️ Likely fake news' if is_fake else '✓ Likely real news'} (High confidence: {confidence:.1%})"
        elif confidence > 0.6:
            confidence_level = "medium"
            message = f"{'Possibly fake news' if is_fake else 'Possibly real news'} (Medium confidence: {confidence:.1%})"
        else:
            confidence_level = "low"
            message = f"Uncertain - manual review recommended (Low confidence: {confidence:.1%})"
        
        return PredictionResponse(
            input=text[:200] + "..." if len(text) > 200 else text,
            prediction=prediction_result['prediction'],
            confidence=confidence,
            probabilities=prediction_result['probabilities'],
            score_difference=prediction_result['score_difference'],
            message=message
        )
        
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/predict/image")
async def predict_image(request: Request):
    """DEBUG VERSION - Extract text from image and predict if it's fake or real news"""
    
    # Get raw request body for debugging
    raw_body = await request.body()
    print(f"DEBUG: Raw request body length: {len(raw_body)}")
    print(f"DEBUG: Raw request body (first 200 chars): {raw_body[:200]}")
    
    try:
        # Try to parse as JSON
        import json
        json_data = json.loads(raw_body)
        print(f"DEBUG: Parsed JSON keys: {list(json_data.keys())}")
        
        for key, value in json_data.items():
            if key == 'imageData' and value:
                print(f"DEBUG: imageData length: {len(value)}")
                print(f"DEBUG: imageData starts with: {value[:50]}...")
            else:
                print(f"DEBUG: {key}: {value}")
                
    except Exception as e:
        print(f"DEBUG: Failed to parse JSON: {e}")
        return {"error": "Failed to parse request body", "raw_body_preview": raw_body[:100].decode('utf-8', errors='ignore')}
    
    # Now try the normal Pydantic parsing
    try:
        parsed_request = ImagePredictRequest(**json_data)
        print(f"DEBUG: Pydantic parsing successful")
        print(f"DEBUG: parsed_request.imageUrl: {parsed_request.imageUrl}")
        print(f"DEBUG: parsed_request.imageData exists: {bool(parsed_request.imageData)}")
        
        if not parsed_request.imageUrl and not parsed_request.imageData:
            return {"error": "No image provided after Pydantic parsing", "debug_info": json_data}
        
        return {"success": "Request parsed successfully", "has_imageData": bool(parsed_request.imageData), "has_imageUrl": bool(parsed_request.imageUrl)}
        
    except Exception as e:
        print(f"DEBUG: Pydantic parsing failed: {e}")
        return {"error": f"Pydantic parsing failed: {e}", "debug_info": json_data}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Unexpected error in image prediction: {str(e)}")
        print(f"DEBUG: Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/predict/image/upload")
async def predict_image_upload(file: UploadFile = File(...)):
    """Handle image file uploads directly"""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    try:
        # Read file contents
        contents = await file.read()
        image_data = Image.open(io.BytesIO(contents))
        
        # Extract text from image using Tesseract
        extracted_text = image_to_text(image_data)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="No text found in image")
        
        # Make prediction on extracted text
        class_counts, class_word_counts, vocab_size, idf_values = model
        prediction_result = tfidf_predict(
            extracted_text,
            class_counts,
            class_word_counts,
            vocab_size,
            idf_values,
            is_log=False
        )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ Image text likely contains fake news' if is_fake else '✅ Image text likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"Image text possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about image text - manual review recommended ({confidence:.1%} confidence)"
        
        return {
            "filename": file.filename,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Image upload prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/check/link")
async def check_link(request: LinkCheckRequest):
    """Scrape content from a URL and check if it's fake news"""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    # Validate URL format
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        # Scrape the content from the URL
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract text content (you can improve this based on specific sites)
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Try to find article content
        article_text = ""
        
        # Look for common article containers
        article_containers = soup.find_all(['article', 'main', 'div'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['content', 'article', 'post', 'entry', 'story']
        ))
        
        if article_containers:
            for container in article_containers[:3]:  # Check first 3 matching containers
                text = container.get_text(separator=' ', strip=True)
                if len(text) > len(article_text):
                    article_text = text
        
        # Fallback to paragraphs if no article container found
        if not article_text:
            paragraphs = soup.find_all('p')
            article_text = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
        
        # If still no content, use all text
        if not article_text:
            article_text = soup.get_text(separator=' ', strip=True)
        
        # Clean up text
        article_text = ' '.join(article_text.split())  # Remove extra whitespace
        
        if len(article_text) < 100:
            raise HTTPException(status_code=422, detail="Insufficient content found on the page")
        
        # Make prediction
        class_counts, class_word_counts, vocab_size, idf_values = model
        prediction_result = tfidf_predict(
            article_text,
            class_counts,
            class_word_counts,
            vocab_size,
            idf_values,
            is_log=False
        )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ This article likely contains fake news' if is_fake else '✓ This article likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"This article possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about this article - manual review recommended ({confidence:.1%} confidence)"
        
        # Get page title
        title = soup.find('title').text if soup.find('title') else "Unknown Title"
        
        return {
            "url": url,
            "title": title,
            "content_preview": article_text[:500] + "..." if len(article_text) > 500 else article_text,
            "content_length": len(article_text),
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message
        }
        
    except requests.RequestException as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Link check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Link analysis failed: {str(e)}")

@app.post("/check/facebook")
async def check_facebook_post(request: dict):
    """Check Facebook post content (text and/or image)"""
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    try:
        post_text = request.get("text", "").strip()
        image_url = request.get("imageUrl", "").strip()
        
        if not post_text and not image_url:
            raise HTTPException(status_code=400, detail="No content provided to check")
        
        combined_text = post_text
        
        # If there's an image, extract text from it
        if image_url:
            try:
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                response = requests.get(image_url, headers=headers, timeout=10)
                response.raise_for_status()
                image_data = Image.open(io.BytesIO(response.content))
                image_text = image_to_text(image_data)
                if image_text.strip():
                    combined_text = f"{post_text} {image_text}".strip()
            except Exception as e:
                print(f"Failed to extract text from image: {e}")
                # Continue with just the post text
        
        if not combined_text:
            raise HTTPException(status_code=422, detail="No text content found to analyze")
        
        # Make prediction
        class_counts, class_word_counts, vocab_size, idf_values = model
        prediction_result = tfidf_predict(
            combined_text,
            class_counts,
            class_word_counts,
            vocab_size,
            idf_values,
            is_log=False
        )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ This post likely contains fake news' if is_fake else '✓ This post likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"This post possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about this post - manual review recommended ({confidence:.1%} confidence)"
        
        return {
            "analyzed_text": combined_text[:500] + "..." if len(combined_text) > 500 else combined_text,
            "has_image": bool(image_url),
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Facebook post check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Facebook post analysis failed: {str(e)}")

@app.get("/settings")
async def get_settings():
    """Get current extension settings"""
    return {
        "extension_enabled": user_settings["extension_enabled"],
        "model_loaded": model is not None
    }

@app.put("/settings")
async def update_settings(request: SettingsUpdateRequest):
    """Update extension settings"""
    global user_settings
    
    if request.extension_enabled is not None:
        user_settings["extension_enabled"] = request.extension_enabled
    
    return {
        "message": "Settings updated successfully",
        "settings": user_settings
    }

@app.get("/stats")
async def get_stats():
    """Get API statistics and model information"""
    if not model:
        return {
            "model_loaded": False,
            "message": "Model not loaded"
        }
    
    class_counts, class_word_counts, vocab_size, idf_values = model
    
    return {
        "model_loaded": True,
        "model_info": {
            "vocab_size": vocab_size,
            "classes": list(class_counts.keys()),
            "class_distribution": class_counts,
            "total_features": len(idf_values) if idf_values else 0
        },
        "api_status": "online",
        "extension_enabled": user_settings["extension_enabled"]
    }

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)