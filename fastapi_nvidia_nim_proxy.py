
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import asyncio
import json
import os
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="NVIDIA NIM OpenAI Proxy", version="1.0.0")

# Configuration
NVIDIA_NIM_BASE_URL = os.getenv("NVIDIA_NIM_BASE_URL", "http://localhost:8000")
NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")
PROXY_API_KEY = os.getenv("PROXY_API_KEY", "your-proxy-api-key")

class OpenAIToNIMTranslator:
    @staticmethod
    def translate_request(openai_request: Dict[str, Any]) -> Dict[str, Any]:
        """Translate OpenAI request format to NVIDIA NIM format"""
        nim_request = openai_request.copy()

        # Handle model mapping (if needed)
        if "model" in nim_request:
            # You can add model name mapping here if needed
            pass

        # Handle any parameter differences
        # NVIDIA NIM is generally OpenAI compatible, but you can add transformations here

        return nim_request

    @staticmethod
    def translate_response(nim_response: Dict[str, Any]) -> Dict[str, Any]:
        """Translate NVIDIA NIM response format to OpenAI format"""
        openai_response = nim_response.copy()

        # Handle any response format differences
        # NVIDIA NIM responses are generally OpenAI compatible

        return openai_response

async def authenticate_request(request: Request) -> bool:
    """Validate the incoming request authentication"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False

    token = auth_header.split("Bearer ")[1]
    return token == PROXY_API_KEY

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Authentication middleware"""
    if request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    if not await authenticate_request(request):
        return JSONResponse(
            status_code=401,
            content={"error": {"message": "Invalid API key", "type": "invalid_request_error"}}
        )

    return await call_next(request)

@app.get("/")
async def root():
    return {"message": "NVIDIA NIM OpenAI Proxy Server", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/v1/models")
async def list_models():
    """List available models"""
    try:
        async with httpx.AsyncClient() as client:
            headers = {}
            if NVIDIA_NIM_API_KEY:
                headers["Authorization"] = f"Bearer {NVIDIA_NIM_API_KEY}"

            response = await client.get(
                f"{NVIDIA_NIM_BASE_URL}/v1/models",
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(status_code=response.status_code, detail=response.text)

    except Exception as e:
        logger.error(f"Error fetching models: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch models")

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    try:
        # Parse request body
        request_data = await request.json()

        # Translate OpenAI request to NIM format
        nim_request = OpenAIToNIMTranslator.translate_request(request_data)

        # Prepare headers for NVIDIA NIM
        headers = {
            "Content-Type": "application/json"
        }
        if NVIDIA_NIM_API_KEY:
            headers["Authorization"] = f"Bearer {NVIDIA_NIM_API_KEY}"

        # Check if streaming is requested
        is_stream = request_data.get("stream", False)

        async with httpx.AsyncClient() as client:
            if is_stream:
                # Handle streaming response
                async def generate_stream():
                    async with client.stream(
                        "POST",
                        f"{NVIDIA_NIM_BASE_URL}/v1/chat/completions",
                        json=nim_request,
                        headers=headers,
                        timeout=60.0
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            yield f"data: {json.dumps({'error': {'message': error_text.decode(), 'type': 'api_error'}})}

"
                            return

                        async for chunk in response.aiter_lines():
                            if chunk:
                                yield f"{chunk}
"

                return StreamingResponse(
                    generate_stream(),
                    media_type="text/plain",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
                )
            else:
                # Handle non-streaming response
                response = await client.post(
                    f"{NVIDIA_NIM_BASE_URL}/v1/chat/completions",
                    json=nim_request,
                    headers=headers,
                    timeout=60.0
                )

                if response.status_code == 200:
                    nim_response = response.json()
                    openai_response = OpenAIToNIMTranslator.translate_response(nim_response)
                    return openai_response
                else:
                    error_data = response.text
                    raise HTTPException(status_code=response.status_code, detail=error_data)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in chat completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/completions")
async def completions(request: Request):
    """OpenAI-compatible completions endpoint"""
    try:
        # Parse request body
        request_data = await request.json()

        # Translate OpenAI request to NIM format
        nim_request = OpenAIToNIMTranslator.translate_request(request_data)

        # Prepare headers for NVIDIA NIM
        headers = {
            "Content-Type": "application/json"
        }
        if NVIDIA_NIM_API_KEY:
            headers["Authorization"] = f"Bearer {NVIDIA_NIM_API_KEY}"

        # Check if streaming is requested
        is_stream = request_data.get("stream", False)

        async with httpx.AsyncClient() as client:
            if is_stream:
                # Handle streaming response
                async def generate_stream():
                    async with client.stream(
                        "POST",
                        f"{NVIDIA_NIM_BASE_URL}/v1/completions",
                        json=nim_request,
                        headers=headers,
                        timeout=60.0
                    ) as response:
                        if response.status_code != 200:
                            error_text = await response.aread()
                            yield f"data: {json.dumps({'error': {'message': error_text.decode(), 'type': 'api_error'}})}

"
                            return

                        async for chunk in response.aiter_lines():
                            if chunk:
                                yield f"{chunk}
"

                return StreamingResponse(
                    generate_stream(),
                    media_type="text/plain",
                    headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
                )
            else:
                # Handle non-streaming response
                response = await client.post(
                    f"{NVIDIA_NIM_BASE_URL}/v1/completions",
                    json=nim_request,
                    headers=headers,
                    timeout=60.0
                )

                if response.status_code == 200:
                    nim_response = response.json()
                    openai_response = OpenAIToNIMTranslator.translate_response(nim_response)
                    return openai_response
                else:
                    error_data = response.text
                    raise HTTPException(status_code=response.status_code, detail=error_data)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        logger.error(f"Error in completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8080,
        log_level="info"
    )
