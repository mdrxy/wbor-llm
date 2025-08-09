import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Type

import requests
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not os.getenv("OPENAI_API_KEY"):
    logger.warning(
        "OPENAI_API_KEY environment variable not set. The agent will not function."
    )
if os.getenv("LANGSMITH_TRACING") == "true" and not os.getenv("LANGSMITH_API_KEY"):
    logger.warning(
        "LANGSMITH_TRACING is true, but LANGSMITH_API_KEY is not set. Tracing will likely fail."
    )
elif not os.getenv("LANGSMITH_TRACING") == "true" and os.getenv("LANGSMITH_API_KEY"):
    logger.info(
        "LANGSMITH_API_KEY is set, but LANGSMITH_TRACING is not 'true'. LangSmith tracing may not "
        "be active as expected."
    )
elif not os.getenv(
    "LANGSMITH_API_KEY"
):  # General warning if key is missing but tracing not explicitly enabled/disabled
    logger.warning(
        "LANGSMITH_API_KEY environment variable not set. LangSmith tracing will not be available "
        "if enabled."
    )


class GetCurrentSongInput(BaseModel):
    """
    Input for GetCurrentSongTool.
    This tool requires no specific input arguments from the LLM when
    called.
    """


class GetCurrentSongTool(BaseTool):
    """
    Fetch the currently playing song from WBOR 91.1 FM's public API.
    """

    name: str = "get_current_song"
    description: str = (
        "Fetches the currently playing song from WBOR 91.1 FM's public API. "
        "Use this tool when a user asks what song is currently playing."
    )
    args_schema: Type[GetCurrentSongInput] = GetCurrentSongInput

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """
        Fetch current song information from API.
        """
        api_url = "https://api-1.wbor.org/api/spins?count=1"
        try:
            response = requests.get(api_url, timeout=3)
            response.raise_for_status()

            data = response.json()

            if data and "items" in data and len(data["items"]) > 0:
                latest_spin = data["items"][0]
                artist = latest_spin.get("artist")
                song_title = latest_spin.get("song")

                if artist and song_title:
                    # Formatted string for the LLM to use directly
                    formatted_output = (
                        f"The current song is '{song_title}' by {artist}."
                    )
                    logger.info(
                        "Successfully fetched song. Formatted output: `%s`",
                        formatted_output,
                    )
                    return formatted_output
                logger.warning(
                    "API response missing artist or song title in the latest spin."
                )
                return "I found some song information, but it seems to be incomplete."

            logger.warning(
                "No items found in API response or response format unexpected."
            )
            return (
                "I couldn't find any information about the current song from the API."
            )

        except requests.exceptions.RequestException as e:
            logger.error("API request failed: %s", e)
            return (
                "There was an error trying to fetch current song information from the station's "
                "API."
            )
        except (
            KeyError,
            IndexError,
            TypeError,
        ) as e:
            logger.error("Error parsing API response: %s", e)
            return "There was an error processing the song information from the station's API."

    async def _arun(self, *args: Any, **kwargs: Any) -> str:
        # For simplicity, using the synchronous run method.
        # TODO; true async HTTP requests using httpx.
        return self._run(*args, **kwargs)


# --- Agent Initialization (will be done in lifespan) ---
# These will be initialized in the lifespan manager
LLM_INSTANCE = None
AGENT_EXECUTOR = None


# --- FastAPI Lifespan Management for Startup/Shutdown ---
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Manages application startup and shutdown events.
    Initializes the LangChain agent on startup.
    """
    global LLM_INSTANCE, AGENT_EXECUTOR
    logger.info("Application startup: Initializing LangChain agent...")

    if not os.getenv("OPENAI_API_KEY"):
        logger.error(
            "CRITICAL: OPENAI_API_KEY is not set. Agent cannot be initialized."
        )
        # Application will start, but /process-sms will fail.
        # (Health check will reflect this.)
        LLM_INSTANCE = None
        AGENT_EXECUTOR = None
    else:
        try:
            LLM_INSTANCE = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
            tools = [GetCurrentSongTool()]

            system_prompt = (
                "You are a helpful assistant for WBOR 91.1 FM at Bowdoin College in "
                "Brunswick, Maine. Your primary function is to tell users what song is "
                "currently playing if they ask. Use the 'get_current_song' tool to "
                "find this information. If the user asks about something other than "
                "the current song, politely inform them you can only provide "
                "information about the currently playing song. If they don't ask a "
                "question, tell them thanks for listening and that they can ask. If "
                "you don't understand them, let them know. If the 'get_current_song' "
                "tool encounters an error or returns no specific song information, "
                "inform the user that you couldn't fetch the song details at this "
                "moment and suggest they could try again later. Limit excess prose, be "
                "direct."
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    MessagesPlaceholder(variable_name="chat_history", optional=True),
                    ("human", "{sms_body}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )
            agent = create_openai_functions_agent(LLM_INSTANCE, tools, prompt)
            AGENT_EXECUTOR = AgentExecutor(
                agent=agent, tools=tools, verbose=True
            )  # (Set verbose to False in production)
            logger.info("LangChain OpenAI Functions Agent initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize LangChain agent: %s", e, exc_info=True)
            LLM_INSTANCE = None
            AGENT_EXECUTOR = None

    yield  # Run app

    logger.info("Application shutdown: Cleaning up resources (if any)...")
    # Add any cleanup code here if needed


# --- FastAPI Application Setup ---
app = FastAPI(
    title="WBOR LangChain SMS Agent",
    description="Processes SMS messages to answer questions about the currently playing song.",
    version="0.1.0",
    lifespan=lifespan,
)


# --- API Endpoints ---
class SMSRequest(BaseModel):
    """
    Request body for processing SMS. This is the expected format for
    incoming SMS messages.
    """

    sms_body: str


class AgentResponse(BaseModel):
    """
    Basic response model for the agent's output. This is the format
    returned to the client after processing the SMS and generating a
    response from the agent.
    """

    response_text: str


@app.post("/process-sms", response_model=AgentResponse)
async def process_sms_endpoint(request_body: SMSRequest, _request: Request):
    """
    Process incoming SMS messages using LangChain.
    """
    if not AGENT_EXECUTOR:
        logger.error("Agent not initialized. Cannot process request.")
        raise HTTPException(
            status_code=503,
            detail="Agent service is not available. Please check server logs.",
        )

    sms_text = request_body.sms_body
    logger.info("Received SMS for processing: `%s`", sms_text)

    # LangSmith tracing context
    config = {}
    if os.getenv("LANGSMITH_TRACING") == "true" and os.getenv("LANGSMITH_API_KEY"):
        # project_name can also be set via LANGSMITH_PROJECT env var
        config = {
            "configurable": {
                "project_name": os.getenv("LANGSMITH_PROJECT", "WBOR SMS Agent Default")
            }
        }
        # Example of how to pass a run_id if provided upstream
        # langsmith_run_id = request.headers.get("x-langsmith-run-id")
        # if langsmith_run_id:
        #     config["configurable"]["run_id"] = langsmith_run_id

    try:
        agent_input = {
            "sms_body": sms_text,
            "chat_history": [],  # Assuming no chat history for simple SMS
        }
        response = await AGENT_EXECUTOR.ainvoke(agent_input, config=config)
        agent_reply = response.get(
            "output",
            "I'm sorry, I encountered an issue and couldn't process your request.",
        )
        logger.info("Agent generated reply: `%s`", agent_reply)
        return AgentResponse(response_text=agent_reply)

    except Exception as e:
        logger.error("Error during agent invocation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,  # Internal Server Error
            detail="Internal server error while processing your request.",
        ) from e


@app.get("/health", status_code=200)
async def health_check():
    """
    Health check endpoint to verify the service is running.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "status": "degraded",
            "detail": "OPENAI_API_KEY not set. Agent functionality is disabled.",
            "agent_initialized": AGENT_EXECUTOR is not None,  # Will be False
        }
    if AGENT_EXECUTOR is None:
        return {
            "status": "unhealthy",
            "detail": "Agent not initialized despite OPENAI_API_KEY being set. Check server logs "
            "for errors during startup.",
            "agent_initialized": False,
        }
    return {
        "status": "ok",
        "detail": "Agent initialized and service is running.",
        "agent_initialized": True,
    }


# --- For running directly with uvicorn (development) ---
if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: The OPENAI_API_KEY environment variable is not set.")
        print("Please set it before running the application.")
        print("Example: export OPENAI_API_KEY='your_key_here'")
        print("Application will start but agent will not function.")

    # LangSmith environment variables (reminders)
    if os.getenv("LANGSMITH_TRACING") == "true" and not os.getenv("LANGSMITH_API_KEY"):
        print(
            "WARNING: LANGSMITH_TRACING is true, but LANGSMITH_API_KEY is not set. Tracing will "
            "likely fail."
        )
    if not os.getenv("LANGSMITH_PROJECT") and os.getenv("LANGSMITH_TRACING") == "true":
        print(
            "INFO: For LangSmith, consider setting LANGSMITH_PROJECT environment variable for "
            "better organization."
        )

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
