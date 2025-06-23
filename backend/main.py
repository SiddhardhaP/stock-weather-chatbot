from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import logging
import os
import sys
from pathlib import Path
import re  # For optional cleanup

# --- Add this block to help with relative imports ---
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))
# ----------------------------------------------------

# --- Load environment variables explicitly from backend/.env ---
from dotenv import load_dotenv
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)
# ---------------------------------------------------------------

# Import the global agent instance from langgraph_core.py
from .langgraph_core import agent_instance, WeatherStockAgent

app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

agent: WeatherStockAgent = agent_instance

# Configure CORS
ALLOWED_ORIGINS_CSV = os.getenv(
    "ALLOWED_ORIGINS_CSV",
    "http://localhost:5173,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in ALLOWED_ORIGINS_CSV.split(',')]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Request model
class AskRequest(BaseModel):
    question: str

# Streaming response with filtered output
async def generate_response_stream(user_question: str):
    """
    Async generator to stream cleaned responses from the LangGraph agent.
    Filters out internal logs like START, MEMORY_INFO, and PROCESSING.
    """
    try:
        # agent.run_with_streaming is now an async generator
        async for text_chunk in agent.run_with_streaming(user_question):
            # If the chunk is a log message (starts with [...]), it will be filtered out.
            # If it's part of the actual content (e.g., a word, a space, a newline),
            # it won't start with '[' (after stripping whitespace) and will be yielded.
            # The agent's run_with_streaming now yields content chunks directly.
            if not text_chunk.strip().startswith("["):
                yield text_chunk  # Yield the chunk as is (agent handles spaces/newlines for content)
            # else:
                # Optionally, you could log the filtered out chunks here if needed for debugging
                # logger.debug(f"Filtered out log chunk: {text_chunk.strip()}")
    except Exception as e:
        logger.error(f"Error during agent streaming: {e}", exc_info=True)
        yield f"STREAM_ERROR: An error occurred: {str(e)}\n"

# Endpoint for asking the agent
@app.post("/ask")
async def ask_agent_streaming(req: AskRequest):
    user_question = req.question
    logger.info(f"Received question: {user_question}")
    return StreamingResponse(generate_response_stream(user_question), media_type="text/plain")

# Root check
@app.get("/")
async def read_root():
    return {"message": "FastAPI backend is running"}
