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
import json
from bs4 import BeautifulSoup
import random

# from tf_idf import load_model, predict as tfidf_predict
from bag_of_words import load_model, predict as bow_predict
from utils.tesseract import image_to_text
from utils.source_scorer import SourceScorer

load_dotenv()
HOST = os.getenv("API_HOST")
PORT = int(os.getenv("API_PORT"))
MODEL = os.getenv("TRAINED_MODEL")
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone17,1; CPU iPhone OS 18_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:15.0) Gecko/20100101 Firefox/15.0.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

model = None
source_scorer = SourceScorer()
user_settings = {
    "extension_enabled": True
}

# Request/Response Models
class TextPredictRequest(BaseModel):
    text: str
    type: Optional[str] = "text"
    source_url: Optional[str] = None 
    page_title: Optional[str] = None

class ImagePredictRequest(BaseModel):
    imageUrl: Optional[str] = None
    imageData: Optional[str] = None  # Base64 encoded image
    type: Optional[str] = "image"
    source_url: Optional[str] = None
    page_title: Optional[str] = None 

class LinkCheckRequest(BaseModel):
    url: str

class SettingsUpdateRequest(BaseModel):
    extension_enabled: Optional[bool] = None

class PredictionResponse(BaseModel):
    input: str
    prediction: str
    confidence: float
    original_confidence: float
    probabilities: dict
    score_difference: float
    message: str
    source_info: Optional[dict] = None
    confidence_explanation: Optional[str] = None

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
        print(f"✅ Model loaded successfully")
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

def apply_source_scoring(prediction_result, source_url = None, page_title: str = "", content_preview: str = ""):
    if not source_url:
        return prediction_result
    
    try:
        source_info = source_scorer.calculate_source_confidence(
            source_url, page_title, content_preview
        )
        
        original_confidence = prediction_result['confidence']
        boosted_confidence, explanation = source_scorer.boost_prediction_confidence(
            original_confidence, 
            source_info['overall_score'], 
            prediction_result['prediction']
        )
        
        prediction_result['original_confidence'] = original_confidence
        prediction_result['confidence'] = boosted_confidence
        prediction_result['source_info'] = source_info
        prediction_result['confidence_explanation'] = explanation
        
        print(f"Source scoring applied:")
        print(f"  Source: {source_info['domain']} (score: {source_info['overall_score']})")
        print(f"  Original confidence: {original_confidence:.3f}")
        print(f"  Boosted confidence: {boosted_confidence:.3f}")
        print(f"  Explanation: {explanation}")
        
    except Exception as e:
        print(f"Error applying source scoring: {e}")
        prediction_result['source_info'] = {"error": str(e)}
    
    return prediction_result

@app.get("/")
async def root():
    return {
        "message": f"Fake News Detector API running on {HOST}:{PORT}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "online",
        "model_loaded": model is not None,
        "source_scoring_enabled": True
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
        class_counts, class_word_counts, vocab_size = model

        prediction_result = bow_predict(
            text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
            is_log=False
        )
        
        if request.source_url:
            prediction_result = apply_source_scoring(
                prediction_result, 
                request.source_url, 
                request.page_title or "",
                text[:200]
            )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            confidence_level = "high"
            message = f"{'⚠️ Likely fake news' if is_fake else '✅ Likely real news'} (High confidence: {confidence:.1%})"
        elif confidence > 0.6:
            confidence_level = "medium"
            message = f"{'Possibly fake news' if is_fake else 'Possibly real news'} (Medium confidence: {confidence:.1%})"
        else:
            confidence_level = "low"
            message = f"Uncertain - manual review recommended (Low confidence: {confidence:.1%})"
        
        if prediction_result.get('source_info') and prediction_result.get('confidence_explanation'):
            source_info = prediction_result['source_info']
            message += f" | Source: {source_info['domain']} ({source_info['confidence_level']} reliability)"
        
        response_data = {
            "input": text[:200] + "..." if len(text) > 200 else text,
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message
        }
        
        if 'original_confidence' in prediction_result:
            response_data["original_confidence"] = prediction_result['original_confidence']
        if 'source_info' in prediction_result:
            response_data["source_info"] = prediction_result['source_info']
        if 'confidence_explanation' in prediction_result:
            response_data["confidence_explanation"] = prediction_result['confidence_explanation']
        
        return PredictionResponse(**response_data)
        
    except Exception as e:
        print(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

@app.post("/predict/image")
async def predict_image(request: Request):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    try:
        raw_body = await request.body()
        json_data = json.loads(raw_body)
        parsed_request = ImagePredictRequest(**json_data)
        
        print(f"Processing image request - URL: {bool(parsed_request.imageUrl)}, Data: {bool(parsed_request.imageData)}")
        
        if not parsed_request.imageUrl and not parsed_request.imageData:
            raise HTTPException(status_code=400, detail="No image provided for verification")
        
        extracted_text = ""
        
        if parsed_request.imageData:
            try:
                # remove data URL prefix
                if parsed_request.imageData.startswith('data:image'):
                    base64_data = parsed_request.imageData.split(',')[1]
                else:
                    base64_data = parsed_request.imageData
                
                image_bytes = base64.b64decode(base64_data)
                image_data = Image.open(io.BytesIO(image_bytes))
                extracted_text = image_to_text(image_data)
                print(f"Extracted text from base64 image: {extracted_text[:100]}...")
                
            except Exception as e:
                print(f"Failed to process base64 image: {e}")
                raise HTTPException(status_code=422, detail=f"Failed to process image data: {str(e)}")
                
        elif parsed_request.imageUrl:
            try:
                headers = {'User-Agent': random.choice(USER_AGENTS)}
                response = requests.get(parsed_request.imageUrl, headers=headers, timeout=10)
                response.raise_for_status()
                image_data = Image.open(io.BytesIO(response.content))
                extracted_text = image_to_text(image_data)
                print(f"Extracted text from image URL: {extracted_text[:100]}...")
                
            except Exception as e:
                print(f"Failed to download/process image from URL: {e}")
                raise HTTPException(status_code=422, detail=f"Failed to download image: {str(e)}")
        
        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="No text found in image")
        
        class_counts, class_word_counts, vocab_size = model
        prediction_result = bow_predict(
            extracted_text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
            is_log=False
        )
        
        if parsed_request.source_url:
            prediction_result = apply_source_scoring(
                prediction_result, 
                parsed_request.source_url, 
                parsed_request.page_title or "",
                extracted_text[:200]
            )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ Image text likely contains fake news' if is_fake else '✅ Image text likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"Image text possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about image text - manual review recommended ({confidence:.1%} confidence)"
        
        if prediction_result.get('source_info') and prediction_result.get('confidence_explanation'):
            source_info = prediction_result['source_info']
            message += f" | Source: {source_info['domain']} ({source_info['confidence_level']} reliability)"
        
        response_data = {
            "input": extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text,
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message,
            "extracted_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
        }
        
        if 'original_confidence' in prediction_result:
            response_data["original_confidence"] = prediction_result['original_confidence']
        if 'source_info' in prediction_result:
            response_data["source_info"] = prediction_result['source_info']
        if 'confidence_explanation' in prediction_result:
            response_data["confidence_explanation"] = prediction_result['confidence_explanation']
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Image prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/predict/image/upload")
async def predict_image_upload(file: UploadFile = File(...)):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    try:
        contents = await file.read()
        image_data = Image.open(io.BytesIO(contents))
        
        extracted_text = image_to_text(image_data)
        
        if not extracted_text.strip():
            raise HTTPException(status_code=422, detail="No text found in image")
        
        class_counts, class_word_counts, vocab_size = model

        prediction_result = bow_predict(
            extracted_text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
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
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    url = request.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    try:
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        article_text = ""
        
        # common article containers
        article_containers = soup.find_all(['article', 'main', 'div'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['content', 'article', 'post', 'entry', 'story']
        ))
        
        if article_containers:
            for container in article_containers[:3]:
                text = container.get_text(separator=' ', strip=True)
                if len(text) > len(article_text):
                    article_text = text
        
        if not article_text:
            paragraphs = soup.find_all('p')
            article_text = ' '.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50])
        
        if not article_text:
            article_text = soup.get_text(separator=' ', strip=True)
        
        article_text = ' '.join(article_text.split())  # Remove extra whitespace
        
        if len(article_text) < 100:
            raise HTTPException(status_code=422, detail="Insufficient content found on the page")
        
        title = soup.find('title').text if soup.find('title') else "Unknown Title"
        
        class_counts, class_word_counts, vocab_size = model
        prediction_result = bow_predict(
            article_text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
            is_log=False
        )
        
        prediction_result = apply_source_scoring(
            prediction_result, 
            url, 
            title,
            article_text[:500]
        )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ This article likely contains fake news' if is_fake else '✅ This article likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"This article possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about this article - manual review recommended ({confidence:.1%} confidence)"
        
        if prediction_result.get('source_info'):
            source_info = prediction_result['source_info']
            message += f" | Source: {source_info['domain']} ({source_info['confidence_level']} reliability)"
        
        response_data = {
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
        
        if 'original_confidence' in prediction_result:
            response_data["original_confidence"] = prediction_result['original_confidence']
        if 'source_info' in prediction_result:
            response_data["source_info"] = prediction_result['source_info']
        if 'confidence_explanation' in prediction_result:
            response_data["confidence_explanation"] = prediction_result['confidence_explanation']
        
        return response_data
        
    except requests.RequestException as e:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Link check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Link analysis failed: {str(e)}")

@app.post("/check/facebook")
async def check_facebook_post(request: dict):
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded")
    
    if not user_settings["extension_enabled"]:
        raise HTTPException(status_code=503, detail="Extension is disabled")
    
    try:
        post_text = request.get("text", "").strip()
        image_url = request.get("imageUrl", "").strip()
        source_url = request.get("source_url", "").strip()
        
        if not post_text and not image_url:
            raise HTTPException(status_code=400, detail="No content provided to check")
        
        combined_text = post_text
        
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
        
        if not combined_text:
            raise HTTPException(status_code=422, detail="No text content found to analyze")
        
        class_counts, class_word_counts, vocab_size = model
        prediction_result = bow_predict(
            combined_text, 
            class_counts, 
            class_word_counts, 
            vocab_size, 
            is_log=False
        )
        
        if source_url or image_url:
            actual_source = source_url if source_url else "https://facebook.com"
            prediction_result = apply_source_scoring(
                prediction_result, 
                actual_source, 
                "Facebook Post",
                combined_text[:200]
            )
        
        is_fake = prediction_result['prediction'] == 'fake'
        confidence = prediction_result['confidence']
        
        if confidence > 0.8:
            message = f"{'⚠️ This post likely contains fake news' if is_fake else '✅ This post likely contains real news'} ({confidence:.1%} confidence)"
        elif confidence > 0.6:
            message = f"This post possibly contains {'fake' if is_fake else 'real'} news ({confidence:.1%} confidence)"
        else:
            message = f"Uncertain about this post - manual review recommended ({confidence:.1%} confidence)"
        
        # if prediction_result.get('source_info'):
        #     source_info = prediction_result['source_info']
        #     message += f" | Source: {source_info['domain']} ({source_info['confidence_level']} reliability)"
        
        response_data = {
            "analyzed_text": combined_text[:500] + "..." if len(combined_text) > 500 else combined_text,
            "has_image": bool(image_url),
            "prediction": prediction_result['prediction'],
            "confidence": confidence,
            "probabilities": prediction_result['probabilities'],
            "score_difference": prediction_result['score_difference'],
            "message": message
        }
        
        if 'original_confidence' in prediction_result:
            response_data["original_confidence"] = prediction_result['original_confidence']
        if 'source_info' in prediction_result:
            response_data["source_info"] = prediction_result['source_info']
        if 'confidence_explanation' in prediction_result:
            response_data["confidence_explanation"] = prediction_result['confidence_explanation']
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Facebook post check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Facebook post analysis failed: {str(e)}")

@app.get("/settings")
async def get_settings():
    return {
        "extension_enabled": user_settings["extension_enabled"],
        "model_loaded": model is not None,
        "source_scoring_enabled": True
    }

@app.put("/settings")
async def update_settings(request: SettingsUpdateRequest):
    global user_settings
    
    if request.extension_enabled is not None:
        user_settings["extension_enabled"] = request.extension_enabled
    
    return {
        "message": "Settings updated successfully",
        "settings": user_settings
    }

@app.get("/stats")
async def get_stats():
    if not model:
        return {
            "model_loaded": False,
            "message": "Model not loaded"
        }
    
    class_counts, class_word_counts, vocab_size = model
    
    source_stats = {
        "total_domains": len(source_scorer.domain_scores),
        "domain_patterns": len(source_scorer.domain_patterns),
        "reliability_categories": {
            "highly_reliable": len([d for d, s in source_scorer.domain_scores.items() if s >= 0.8]),
            "reliable": len([d for d, s in source_scorer.domain_scores.items() if 0.6 <= s < 0.8]),
            "moderate": len([d for d, s in source_scorer.domain_scores.items() if 0.4 <= s < 0.6]),
            "questionable": len([d for d, s in source_scorer.domain_scores.items() if 0.2 <= s < 0.4]),
            "unreliable": len([d for d, s in source_scorer.domain_scores.items() if s < 0.2])
        }
    }
    
    return {
        "model_loaded": True,
        "model_info": {
            "vocab_size": vocab_size,
            "classes": list(class_counts.keys()),
            "class_distribution": class_counts,
            "total_features": vocab_size,
            "class_word_counts": class_word_counts
        },
        "source_scoring": source_stats,
        "api_status": "online",
        "extension_enabled": user_settings["extension_enabled"]
    }

@app.get("/sources")
async def get_source_info():
    return {
        "domain_scores": dict(list(source_scorer.domain_scores.items())[:20]),  # First 20
        "total_domains": len(source_scorer.domain_scores),
        "domain_patterns": source_scorer.domain_patterns,
        "reliability_levels": {
            "very_high": "0.8 - 1.0",
            "high": "0.6 - 0.8", 
            "medium": "0.4 - 0.6",
            "low": "0.2 - 0.4",
            "very_low": "0.0 - 0.2"
        }
    }

@app.post("/sources/score")
async def score_source(request: dict):
    url = request.get("url", "").strip()
    title = request.get("title", "")
    content = request.get("content", "")
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        result = source_scorer.calculate_source_confidence(url, title, content)
        return {
            "success": True,
            "url": url,
            "source_analysis": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Source scoring failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)