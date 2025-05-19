# wbor-llm

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

        ```bash
        curl -X POST "http://localhost:8000/process-sms" \
             -H "Content-Type: application/json" \
             -d '{"sms_body":"what song is playing?"}'
        ```

        ```bash
        curl http://localhost:8000/health
        ```

3. **Docker:**
    * Build the image: `docker build -t wbor-sms-agent .`
    * Run the container:

        ```bash
        docker run -d -p 8080:8000 \
               -e OPENAI_API_KEY="your_actual_openai_api_key" \
               -e LANGSMITH_TRACING="true" \
               -e LANGSMITH_API_KEY="your_actual_langsmith_api_key" \
               -e LANGSMITH_PROJECT="WBOR SMS Agent" \
               --name wbor-agent-container \
               wbor-sms-agent
        ```

        Now the service will be accessible at `http://localhost:8080`.

## Future Directions

* Sophisticated intent recognition and handling:
  * Wider variety of ways a user might ask for the current song. LandSmith data will help with this.
  * Handle ambiguous requests. Instead of "I don't know", offer hints or ask clarifying questions.
  * Handle negative queries (e.g., "What song is NOT playing?").
* Improve GetCurrentSongTool
  * Make asynchronous
  * Cache song information for a short period with the option to use the proxy's SSE channel to make real-time evicts.
* Chat history
  * Each SMS is currently treated as a new interaction. Perhaps within a short time window, we can treat them as part of the same conversation so that the user can ask follow-up questions like:
    * "What's the song playing now?" (after asking "What song is playing?")
    * "What was the last song?" (after asking "What song is playing?")
    * "What album was the last song from?" (after asking "What song is playing?")
  * Simple storage mechanism to keep track of the last few songs played.
