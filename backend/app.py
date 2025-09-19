import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
import uvicorn
from contextlib import asynccontextmanager
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from tf_idf import load_model, predict

load_dotenv()
HOST = os.getenv("API_HOST")
PORT = int(os.getenv("API_PORT"))
MODEL = os.getenv("TRAINED_MODEL")

app = FastAPI()
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
        "message": f"WTF is running on {HOST}:{PORT}",
        "timestamp": datetime.now(timezone.utc)
        }

@app.get("/favicon.ico")
async def favicon():
    return None

model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    print("Loading model...")
    try:
        model = load_model(MODEL)
        if not model:
            print("ERROR: Failed to load model. Please ensure all.pkl exists in trained_models/")
            raise RuntimeError("Model loading failed")
    except Exception as e:
        print(f"ERROR loading model: {e}")
        raise RuntimeError(f"Failed to load model: {e}")
    
    yield
    
    print("Shutting down...")

# @app.post("/predict")
# async def predict(request):
#     if not ngram_model or not ngram_model.is_trained:
#         raise HTTPException(status_code=500, detail="Model not loaded or not trained")

#     if not user_settings["extension_enabled"]:
#         raise HTTPException(status_code=503, detail="Extension is disabled")

#     text = request.text.strip()
#     if not text:
#         raise HTTPException(status_code=400, detail="Text input cannot be empty")
    
#     tokens = text.split()
#     if len(tokens) > 50:  # Limit context length
#         return {
#             "input": text,
#             "top_k": 0,
#             "method": request.method,
#             "predictions": [],
#             "model": user_settings["active_model"],
#             "message": "Input too long for prediction"
#         }
    
#     top_k = max(1, min(request.top_k or user_settings["suggestions_count"], 50))
#     method = request.method or user_settings["prediction_method"]

#     try:
#         if method.lower() == "interpolation":
#             predictions = ngram_model.predict_with_interpolation(text, top_k)
#         else:
#             predictions = ngram_model.predict_next(text, top_k)

#         return {
#             "input": text,
#             "top_k": top_k,
#             "method": method,
#             "predictions": predictions,
#             "model": user_settings["active_model"]
#         }
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
