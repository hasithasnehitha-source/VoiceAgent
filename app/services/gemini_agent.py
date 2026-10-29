import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from app.core.config import settings
from app.db.session import async_session_factory
from app.db import repository
from app.services.agent_tools import (
    GEMINI_FUNCTION_DECLARATIONS,
    AVAILABLE_TOOLS,
    execute_tool
)

logger = logging.getLogger("voice_agent.gemini")

EXECUTIVE_SYSTEM_INSTRUCTION = """
You are 'Aria', an elite, highly intelligent Executive Personal AI Voice Assistant.
Your responses are spoken aloud to the executive through speech synthesis.

Guidelines for voice interaction:
1. Speak in a confident, polished, warm, and professional executive tone.
2. Keep responses brief, conversational, and direct (1 to 3 sentences max).
3. Do NOT use markdown formatting (never use asterisks, bullet points, numbered lists, hashtags, or raw links).
4. Proactively call your tools to schedule meetings, manage action items, or store and recall preferences.
5. If an action is taken (e.g. task created or meeting scheduled), confirm clearly with the exact details.
"""


def build_gemini_tools() -> List[types.Tool]:
    """Convert declarative schemas into Google GenAI Tool structures."""
    function_declarations = []
    for decl in GEMINI_FUNCTION_DECLARATIONS:
        props = {}
        for prop_name, prop_spec in decl["parameters"]["properties"].items():
            props[prop_name] = types.Schema(
                type=prop_spec["type"],
                description=prop_spec.get("description")
            )

        function_declarations.append(
            types.FunctionDeclaration(
                name=decl["name"],
                description=decl["description"],
                parameters=types.Schema(
                    type=decl["parameters"]["type"],
                    properties=props,
                    required=decl["parameters"].get("required", [])
                )
            )
        )
    return [types.Tool(function_declarations=function_declarations)]


class ExecutiveVoiceAgent:
    """Orchestrates multi-turn conversation and tool calling via Google Gemini."""

    def __init__(self, model_name: str = "gemini-2.5-flash"):
        self.model_name = model_name
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
        self.sessions: Dict[str, List[types.Content]] = {}
        self.tools = build_gemini_tools()
        self._init_client()

    def _init_client(self):
        """Initialize Google GenAI client if API key is present."""
        if self.api_key and self.api_key.strip():
            try:
                self.client = genai.Client(api_key=self.api_key.strip())
                self.is_live = True
                logger.info(f"Gemini Voice Agent initialized in LIVE mode with model '{self.model_name}'.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}. Falling back to simulation mode.")
                self.client = None
                self.is_live = False
        else:
            self.client = None
            self.is_live = False
            logger.info("No GEMINI_API_KEY provided. Agent running in Simulation / Mock mode.")

    async def process_user_message(
        self,
        user_message: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process incoming user message through multi-turn tool calling pipeline."""
        start_time = time.time()
        sid = session_id or str(uuid.uuid4())
        clean_text = user_message.strip()

        if not clean_text:
            return {
                "session_id": sid,
                "reply": "I'm listening, sir. How may I assist you?",
                "tools_executed": [],
                "latency_ms": 0.0,
                "mode": "live" if self.is_live else "simulation"
            }

        # Check if live Gemini API is configured
        if self.is_live and self.client:
            return await self._process_with_gemini(clean_text, sid, start_time)
        else:
            return await self._process_with_simulation(clean_text, sid, start_time)

    async def _process_with_gemini(
        self,
        text: str,
        sid: str,
        start_time: float
    ) -> Dict[str, Any]:
        """Execute real Gemini API call with native function calling loop."""
        tools_executed = []
        history = self.sessions.setdefault(sid, [])

        # Append user message to session history
        history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=text)]
        ))

        try:
            config = types.GenerateContentConfig(
                system_instruction=EXECUTIVE_SYSTEM_INSTRUCTION,
                tools=self.tools,
                temperature=0.7,
                max_output_tokens=300
            )

            # First turn: Gemini decides whether to speak or call a tool
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=history,
                config=config
            )

            # Check if Gemini requested function calls
            function_calls = []
            if response.candidates and response.candidates[0].content:
                parts = response.candidates[0].content.parts or []
                for p in parts:
                    if p.function_call:
                        function_calls.append(p.function_call)

            # If Gemini called tools, execute them and feed back to model
            if function_calls:
                # Add model's tool call turn to history
                history.append(response.candidates[0].content)

                tool_response_parts = []
                for fc in function_calls:
                    fn_name = fc.name
                    fn_args = dict(fc.args) if fc.args else {}
                    logger.info(f"Gemini invoked tool '{fn_name}' with args: {fn_args}")

                    tool_result = await execute_tool(fn_name, fn_args)
                    tools_executed.append({
                        "tool": fn_name,
                        "args": fn_args,
                        "result": tool_result
                    })

                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response=tool_result
                        )
                    )

                # Send tool response back to Gemini
                history.append(types.Content(
                    role="user",
                    parts=tool_response_parts
                ))

                # Final response from model synthesizing the tool outcome
                second_response = await self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=history,
                    config=config
                )
                final_text = second_response.text or "I have processed your request."
                history.append(second_response.candidates[0].content)
            else:
                final_text = response.text or "Understood, sir."
                if response.candidates and response.candidates[0].content:
                    history.append(response.candidates[0].content)

            # Prune history to keep last 12 contents
            if len(history) > 12:
                self.sessions[sid] = history[-12:]

            latency_ms = round((time.time() - start_time) * 1000, 2)

            # Log to DB
            async with async_session_factory() as db:
                await repository.log_conversation(
                    db,
                    session_id=sid,
                    role="assistant",
                    content=final_text,
                    latency_ms=latency_ms
                )

            return {
                "session_id": sid,
                "reply": final_text.strip(),
                "tools_executed": tools_executed,
                "latency_ms": latency_ms,
                "mode": "live"
            }

        except Exception as exc:
            logger.error(f"Error during Gemini processing: {exc}", exc_info=True)
            # Fall back gracefully to simulation
            return await self._process_with_simulation(text, sid, start_time, error_note=str(exc))

    async def _process_with_simulation(
        self,
        text: str,
        sid: str,
        start_time: float,
        error_note: Optional[str] = None
    ) -> Dict[str, Any]:
        """Intelligent fallback/simulation parser for offline testing or without API key."""
        lower = text.lower()
        tools_executed = []
        reply = ""

        if "schedule" in lower or "meeting" in lower or "calendar" in lower or "appointment" in lower:
            # Extract meeting title
            title = text.replace("schedule", "").replace("a meeting", "").replace("with", "").strip() or "Executive Sync"
            tool_res = await execute_tool("schedule_calendar_event", {
                "title": f"Meeting: {title[:40]}",
                "start_time": "Tomorrow at 10:00 AM",
                "location": "Boardroom / Online"
            })
            tools_executed.append({"tool": "schedule_calendar_event", "result": tool_res})
            reply = f"I have scheduled your meeting regarding {title[:30]} for tomorrow at 10:00 AM."

        elif "task" in lower or "to-do" in lower or "remind" in lower or "add" in lower:
            task_title = text.replace("add a task to", "").replace("add task", "").replace("remind me to", "").strip() or "Executive Priority"
            tool_res = await execute_tool("create_task", {
                "title": task_title.capitalize(),
                "priority": "high" if "urgent" in lower or "high" in lower else "medium",
                "due_date": "End of Day"
            })
            tools_executed.append({"tool": "create_task", "result": tool_res})
            reply = f"I have added the task to your action items: {task_title.capitalize()}."

        elif "remember" in lower or "preference" in lower or "note" in lower:
            content = text.replace("remember that", "").replace("remember", "").strip()
            tool_res = await execute_tool("save_smart_memory", {
                "key": "user_preference",
                "content": content,
                "category": "preference"
            })
            tools_executed.append({"tool": "save_smart_memory", "result": tool_res})
            reply = "I've committed that to memory for you, sir."

        elif "what" in lower or "list" in lower or "events" in lower or "tasks" in lower:
            tasks_res = await execute_tool("list_tasks", {"limit": 3})
            tools_executed.append({"tool": "list_tasks", "result": tasks_res})
            count = tasks_res.get("count", 0)
            reply = f"You currently have {count} active tasks on your agenda."

        else:
            reply = f"Understood, sir. I am monitoring your executive agenda and ready for your next request."

        latency_ms = round((time.time() - start_time) * 1000, 2)

        # Log to DB
        async with async_session_factory() as db:
            await repository.log_conversation(
                db,
                session_id=sid,
                role="assistant",
                content=reply,
                latency_ms=latency_ms
            )

        return {
            "session_id": sid,
            "reply": reply,
            "tools_executed": tools_executed,
            "latency_ms": latency_ms,
            "mode": "simulation",
            "note": "Running in offline fallback mode. Add GEMINI_API_KEY in .env to activate live Google Gemini models." if not error_note else f"API note: {error_note}"
        }


agent = ExecutiveVoiceAgent()
