"""
mcp_client.py — Browser MCP client using stdio_client with background thread for sync support.
"""
import asyncio
import threading
import urllib.parse
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class BrowserMCP:
    """
    Connects to the @playwright/mcp MCP server via stdio.
    Uses a persistent background event-loop thread so synchronous callers
    (e.g. LangChain @tool functions) can call connect() / search() without
    needing to manage async themselves.
    """

    _NAV_TOOL  = "browser_navigate"
    _EVAL_TOOL = "browser_evaluate"

    def __init__(self):
        self.server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
            env=None,
        )
        self.exit_stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None

        # "Loop ready" event — ensures connect() never calls
        # run_coroutine_threadsafe before run_forever() has started.
        self._loop_ready = threading.Event()
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._thread.start()
        # Block until the event loop is actually running
        self._loop_ready.wait(timeout=5)

    # ------------------------------------------------------------------
    # Background event-loop thread
    # ------------------------------------------------------------------

    def _start_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.call_soon(self._loop_ready.set)   # signal "ready" once scheduled
        self.loop.run_forever()

    def _submit(self, coro, timeout: float = 30.0):
        """Submit a coroutine to the background loop and wait for result.
        Raises concurrent.futures.TimeoutError if the operation takes longer than `timeout` seconds."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)

    # ------------------------------------------------------------------
    # Public sync API
    # ------------------------------------------------------------------

    def connect(self):
        """Spawn the MCP server process and initialize the session."""
        self._submit(self._connect())

    async def _connect(self):
        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(self.server_params)
            )
            self.stdio, self.write = stdio_transport
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.stdio, self.write)
            )
            await self.session.initialize()
        except Exception:
            await self.exit_stack.aclose()
            raise

    def disconnect(self):
        self._submit(self._disconnect())

    async def _disconnect(self):
        await self.exit_stack.aclose()

    def search(self, query: str) -> dict:
        """Navigate to DuckDuckGo and extract the results page text."""
        return self._submit(self._search(query))

    async def _search(self, query: str) -> dict:
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"

            await self.session.call_tool(self._NAV_TOOL, {"url": url})

            # Give the page time to settle
            await asyncio.sleep(2)

            # Use browser_evaluate to extract text from the page
            result = await self.session.call_tool(
                self._EVAL_TOOL, 
                {"function": "() => document.body.innerText"}
            )

            text = ""
            for item in result.content:
                text_val = getattr(item, "text", None)
                if text_val is None and isinstance(item, dict):
                    text_val = item.get("text")
                if text_val:
                    text += text_val

            if not text:
                text = str(result.content)

            # Only append truncation marker when actually truncated
            if len(text) > 2000:
                text = text[:2000] + "...(truncated)"

            return {"results": text}

        except Exception as e:
            return {"error": str(e)}


class DDGSSearchClient:
    """
    Synchronous DuckDuckGo fallback using the `duckduckgo-search` package.
    Note: the package was recently renamed to `ddgs`; import both for compat.
    """

    def __init__(self):
        from ddgs import DDGS
        self.ddgs = DDGS()


    def search(self, query: str, max_results: int = 5):
        try:
            return list(self.ddgs.text(query, max_results=max_results))
        except Exception as e:
            return {"error": str(e)}