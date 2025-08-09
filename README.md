# wbor-llm

SMS-based assistant for WBOR 91.1 FM. Listeners text the station's phone number to inquire about the song currently playing, and the assistant responds with the song title and artist.

Python microservice built with FastAPI, containerized using Docker. Leverages LangChain to create an intelligent agent powered by an OpenAI language model (e.g., GPT-3.5-turbo). Processes incoming SMS messages (via a webhook from a service like Twilio), determines the user's intent, and uses a custom tool to fetch the latest song information from [WBOR's API](https://api-1.wbor.org/api/spins?count=1).

Includes:

* An API endpoint (`/process-sms`) to receive SMS content.
* A tool (`GetCurrentSongTool`) to interact with the WBOR API.
* OpenAI Functions Agent to orchestrate the interaction and formulate responses.
* A health check endpoint (`/health`).
* Integration with [LangSmith](https://www.langchain.com/langsmith) for tracing/observability.

## Usage

1. **Set Environment Variables:**
    * `export OPENAI_API_KEY="your_actual_openai_api_key"`
    * If using LangSmith:
        * `export LANGSMITH_TRACING="true"`
        * `export LANGSMITH_API_KEY="your_actual_langsmith_api_key"`
        * `export LANGSMITH_PROJECT="WBOR SMS Agent"`

2. **Local Development:**
    * Create a virtual environment: `python -m venv venv && source venv/bin/activate`
    * Install dependencies: `pip install -r requirements.txt`
    * Run: `python main.py`
    * The API will be available at `http://localhost:8000`. You can test with tools like `curl` or Postman:

        ```shell
        curl -X POST "http://localhost:8000/process-sms" \
             -H "Content-Type: application/json" \
             -d '{"sms_body":"what song is playing?"}'
        ```

        ```shell
        curl http://localhost:8000/health
        ```

3. **Docker:**
    * Build the image: `docker build -t wbor-sms-agent .`
    * Run the container:

        ```shell
        docker run -d -p 8080:8000 \
               -e OPENAI_API_KEY="your_actual_openai_api_key" \
               -e LANGSMITH_TRACING="true" \
               -e LANGSMITH_API_KEY="your_actual_langsmith_api_key" \
               -e LANGSMITH_PROJECT="WBOR SMS Agent" \
               --name wbor-agent-container \
               wbor-sms-agent
        ```

        The service will be accessible at `http://localhost:8080`.

## Future Directions for Development

* Sophisticated intent recognition and handling:
  * Wider variety of ways a user might ask for the current song. LandSmith data will help with this.
  * Handle ambiguous requests. Instead of "I don't know", offer hints or ask clarifying questions.
  * Handle negative queries (e.g., "What song is NOT playing?").
* Improve `GetCurrentSongTool`
  * Make asynchronous
  * Cache song information for a short period with the option to use the proxy's SSE channel to make real-time evicts.
* Chat history
  * Each SMS is currently treated as a new interaction. Perhaps within a short time window, we can treat them as part of the same conversation so that the user can ask follow-up questions like:
    * "What's the song playing now?" (after asking "What song is playing?")
    * "What was the last song?" (after asking "What song is playing?")
    * "What album was the last song from?" (after asking "What song is playing?")
  * Simple storage mechanism to keep track of the last few songs played.
* `GetNLastSongTool`
  * Add a tool to get the last N songs played.
  * This will be useful for users who want to know what songs have been played recently as opposed to just the current song.
    * Input: Optional number of songs or time window
    * Output: List
    * Option to ask "What was two songs ago?" or "What was the last song played?" to query from the list.
* `GetSongInfoTool`
  * Add a tool to get information about a song.
  * This will be useful for users who want to know more about a specific song.
    * Input: Song name
    * Output: Information about the song (e.g., artist, album, release date)
* `MakeSongRequestTool`
  * Add a tool to submit a song request to the live DJ.
  * This will be useful for users who want to request a specific song to be played.
    * Input: Song name
    * Output: Confirmation of the request
    * Backend: Submit the request to the live DJ via a web form or API.
* `GetStationInfoTool`
  * Add a tool to get information about the radio station.
  * This will be useful for users who want to know more about the station.
    * Input: None
    * Output: Information about the station (e.g., name, frequency, website)
* Feedback Mechanism
  * Add a feedback mechanism to allow users to provide feedback on the service (e.g., "Was this helpful?").
  * Log feedback in LangSmith to evaluate and improve performance.
