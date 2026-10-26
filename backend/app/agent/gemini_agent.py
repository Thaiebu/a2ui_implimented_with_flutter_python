import os
import json
import asyncio
import logging
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from dotenv import load_dotenv

from app.protocol.models import (
    A2UIMessage,
    CreateSurfacePayload,
    UpdateComponentsPayload,
    UpdateDataModelPayload,
    DeleteSurfacePayload,
    ComponentDefinition,
    ComponentChildren,
    ActionDefinition,
    PickerOption
)

from a2ui.builder.v0_9 import (
    Column as A2UIColumn,
    Card as A2UICard,
    Text as A2UIText,
    Button as A2UIButton,
    Action as A2UIAction,
    ActionEvent as A2UIActionEvent,
    ChoicePicker as A2UIChoicePicker,
    ChoicePickerOption as A2UIChoicePickerOption,
    TextField as A2UITextField,
    Divider as A2UIDivider,
    DataBinding as A2UIDataBinding,
)

from app.agent.project_store import (
    save_app_to_disk,
    load_saved_app,
    list_saved_apps,
    delete_saved_app,
    export_app_to_dart
)

logger = logging.getLogger("a2ui.agent")


class AppBuilderSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.app_id = f"app_{session_id}"
        self.app_name = "Untitled App"
        self.surface_id = f"surface_{session_id}"
        self.history: List[Dict[str, str]] = []
        self.current_components: List[Dict[str, Any]] = []
        self.current_data: Dict[str, Any] = {}
        # Intent clarification & confirmation tracking
        self.phase: str = "idle"  # "idle", "clarifying", "confirming", "building"
        self.original_prompt: str = ""
        self.clarification_answers: Dict[str, Any] = {}
        self.clarify_surface_id: str = f"clarify_{session_id}"
        self.proposed_plan: Dict[str, Any] = {}

    def reset(self):
        self.app_id = f"app_{self.session_id}"
        self.app_name = "Untitled App"
        self.history.clear()
        self.current_components.clear()
        self.current_data.clear()
        self.phase = "idle"
        self.original_prompt = ""
        self.clarification_answers.clear()
        self.proposed_plan.clear()


class A2UIAgent:
    def __init__(self):
        self.sessions: Dict[str, AppBuilderSession] = {}
        self._init_client()

    def _init_client(self):
        env_file = Path(".env")
        if not env_file.exists():
            env_file = Path(__file__).resolve().parent.parent.parent / ".env"
        
        load_dotenv(dotenv_path=env_file, override=True)
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Initialized Gemini Client with Gemini 3.8 Flash.")
            except Exception as e:
                logger.warning(f"Could not initialize Gemini Client: {e}")

    def get_or_create_session(self, session_id: Optional[str] = None) -> AppBuilderSession:
        sid = session_id or "default_session"
        if sid not in self.sessions:
            self.sessions[sid] = AppBuilderSession(sid)
        return self.sessions[sid]

    async def process_user_turn(self, user_prompt: str, session_id: Optional[str] = None) -> List[A2UIMessage]:
        """Handles multi-turn conversational app building with intent clarification."""
        if not self.client:
            self._init_client()

        session = self.get_or_create_session(session_id)
        lowered = user_prompt.lower().strip()

        # Handle explicit reset command
        if lowered in ["reset", "start over", "clear app", "new app"]:
            was_clarifying = session.phase == "clarifying"
            clarify_sid = session.clarify_surface_id
            session.reset()

            messages = []
            if was_clarifying:
                messages.append(A2UIMessage(
                    sessionId=session.session_id,
                    deleteSurface=DeleteSurfacePayload(surfaceId=clarify_sid)
                ))
            messages.append(A2UIMessage(
                sessionId=session.session_id,
                phase="idle",
                assistantMessage="Canvas reset! What kind of app would you like to build? (e.g. 'Task Manager', 'Fitness Workout Tracker', 'Expense Logger')",
                deleteSurface=DeleteSurfacePayload(surfaceId=session.surface_id)
            ))
            return messages

        # If currently in clarifying phase and user sends a text prompt (not the form),
        # treat it as additional context and proceed to explain plan
        if session.phase == "clarifying":
            session.clarification_answers["user_refinement"] = user_prompt
            session.history.append({"role": "user", "content": user_prompt})
            return await self.process_clarification_answer(
                session.clarification_answers, session.session_id
            )

        # If currently in confirming phase and user sends a text prompt
        if session.phase == "confirming":
            session.history.append({"role": "user", "content": user_prompt})
            if lowered in ["yes", "confirm", "go", "build", "looks good", "ok", "okay", "sure", "proceed", "start", "build it"]:
                return await self.process_confirmation({}, session.session_id)
            else:
                # Treat user message as adjustment to the proposed plan, then build
                return await self.process_confirmation({"adjustment": user_prompt}, session.session_id)

        # If session already has an existing app, skip clarification (this is a modification)
        has_existing_app = len(session.current_components) > 0

        if has_existing_app:
            # Existing multi-turn modification flow — no clarification needed
            if self.client:
                for attempt in range(2):
                    try:
                        return await self._call_gemini_multiturn(user_prompt, session)
                    except Exception as e:
                        logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
                        if attempt == 0:
                            await asyncio.sleep(0.5)
            return self._smart_multiturn_fallback(user_prompt, session)

        # NEW APP: Check intent clarity first
        if self.client:
            for attempt in range(2):
                try:
                    return await self._call_gemini_with_intent_check(user_prompt, session)
                except Exception as e:
                    logger.warning(f"Gemini intent check attempt {attempt + 1} failed: {e}")
                    if attempt == 0:
                        await asyncio.sleep(0.5)

        # Fallback: simple vague detection when Gemini is offline
        return self._smart_intent_fallback(user_prompt, session)

    # ──────────────────────────────────────────────────────
    # Intent Classification & Clarification (NEW)
    # ──────────────────────────────────────────────────────

    async def _call_gemini_with_intent_check(self, user_prompt: str, session: AppBuilderSession) -> List[A2UIMessage]:
        """Single LLM call that either asks clarification questions or builds the app."""

        full_prompt = f"""
You are an expert AI App Builder implementing Google's A2UI (Agent-to-User Interface) protocol (v0.9).

USER'S REQUEST:
"{user_prompt}"

STEP 1: INTENT ANALYSIS
Determine if the request is specific enough to build a complete, functional app.

The intent is CLEAR if you can identify:
- A specific type of app (e.g., workout tracker, expense logger, task manager, recipe book, tic-tac-toe game)
- At least 2-3 implied features or data fields
- A clear purpose

The intent NEEDS CLARIFICATION if:
- The request is vague (e.g., "build me an app", "make something cool", "create an application")
- You cannot determine what kind of data or features to include
- Multiple very different apps could satisfy the request

STEP 2: OUTPUT (strictly valid JSON, NO markdown code blocks)

IF INTENT IS CLEAR - Build the app directly:
{{
  "phase": "build",
  "assistant_message": "Brief explanation of what you built (1-2 sentences)",
  "components": [
    {{
      "id": "root_col",
      "component": "Column",
      "children": {{"explicitList": ["child_id_1", "child_id_2"]}}
    }}
  ],
  "data": {{}}
}}

IF INTENT NEEDS CLARIFICATION - Ask 2-4 questions:
{{
  "phase": "clarify",
  "assistant_message": "Brief message explaining you need more details",
  "questions": [
    {{
      "id": "q_type",
      "question": "What type of app would you like?",
      "type": "choice",
      "options": ["Task Manager", "Fitness Tracker", "Expense Logger", "Recipe Book"]
    }},
    {{
      "id": "q_features",
      "question": "What key features should it have?",
      "type": "text"
    }}
  ]
}}

ALLOWED COMPONENTS (only when phase is "build"):
- Layout: "Column", "Row", "Card", "Divider"
- Display: "Text" (usageHint: "h1", "h2", "body", "caption")
- Controls:
  - "Button" (text, action: {{"name": "action_id", "contextPath": "/path"}})
  - "TextField" (label, placeholder, value: {{"path": "/data/pointer"}})
  - "ChoicePicker" (label, options: [{{"label": "...", "value": "..."}}], value: {{"path": "/data/pointer"}})
  - "Slider" (label, min, max, value: {{"path": "/data/pointer"}})
- Root component MUST have id "root_col" and component "Column"

QUESTION RULES (only when phase is "clarify"):
- 2-4 questions maximum
- Each question id starts with "q_"
- "choice" type: include 3-6 specific, descriptive options
- "text" type: for open-ended answers
- Questions should be actionable and help you build the right app

Output ONLY raw valid JSON. No wrapping.
"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model='gemini-3.8-flash',
                contents=full_prompt,
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        phase = parsed.get("phase", "build")
        assistant_message = parsed.get("assistant_message", "")

        if phase == "clarify":
            questions = parsed.get("questions", [])
            session.phase = "clarifying"
            session.original_prompt = user_prompt
            session.history.append({"role": "user", "content": user_prompt})
            session.history.append({"role": "assistant", "content": assistant_message})
            return self._build_clarification_messages(session, assistant_message, questions)
        else:
            # phase == "build" — proceed with building the app
            session.history.append({"role": "user", "content": user_prompt})
            session.history.append({"role": "assistant", "content": assistant_message})
            return self._finalize_build(session, user_prompt, parsed)

    def _build_clarification_messages(
        self, session: AppBuilderSession, assistant_message: str, questions: List[Dict]
    ) -> List[A2UIMessage]:
        """Converts clarification questions into an interactive A2UI surface using a2ui.builder.v0_9."""
        clarify_surface_id = session.clarify_surface_id
        data: Dict[str, Any] = {"clarification": {}}

        children_nodes = [
            A2UIText(id="clarify_title", text="📋 Help me understand what you'd like to build", variant="h1")
        ]

        for q in questions:
            q_id = q.get("id", f"q_{len(children_nodes)}")
            q_text = q.get("question", "Please specify:")
            q_type = q.get("type", "text")

            children_nodes.append(A2UIText(id=f"{q_id}_label", text=q_text, variant="h2"))

            if q_type == "choice":
                options_raw = q.get("options", [])
                picker_options = [
                    A2UIChoicePickerOption(
                        label=str(opt),
                        value=str(opt).lower().replace(" ", "_")
                    )
                    for opt in options_raw
                ]
                children_nodes.append(A2UIChoicePicker(
                    id=q_id,
                    label="Select one",
                    options=picker_options,
                    value=A2UIDataBinding(path=f"/clarification/{q_id}")
                ))
            else:
                children_nodes.append(A2UITextField(
                    id=q_id,
                    label="Your answer",
                    value=A2UIDataBinding(path=f"/clarification/{q_id}")
                ))
            data["clarification"][q_id] = ""

        children_nodes.append(A2UIDivider(id="clarify_divider"))
        children_nodes.append(A2UIButton(
            id="submit_clarification_btn",
            child=A2UIText(text="✅ Build My App"),
            action=A2UIAction(event=A2UIActionEvent(name="submit_clarification", context={"path": "/clarification"}))
        ))

        tree = A2UIColumn(id="root", children=children_nodes)
        components = tree.flatten()

        return [
            A2UIMessage(
                sessionId=session.session_id,
                phase="clarifying",
                assistantMessage=assistant_message,
                createSurface=CreateSurfacePayload(surfaceId=clarify_surface_id)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="clarifying",
                updateComponents=UpdateComponentsPayload(
                    surfaceId=clarify_surface_id, components=components
                )
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="clarifying",
                updateDataModel=UpdateDataModelPayload(
                    surfaceId=clarify_surface_id, path="/", value=data
                )
            )
        ]

    async def process_clarification_answer(
        self, answers: Dict[str, Any], session_id: str
    ) -> List[A2UIMessage]:
        """Handles the user's answers to clarification questions and explains the plan to user."""
        session = self.get_or_create_session(session_id)
        # Unwrap nested dicts like {"clarification": {...}} or {"value": {...}}
        unwrapped: Dict[str, Any] = {}
        if isinstance(answers, dict):
            for k, v in answers.items():
                if isinstance(v, dict):
                    unwrapped.update(v)
                elif v not in (None, ""):
                    unwrapped[k] = v
        session.clarification_answers.update(unwrapped)

        # Format answers for the LLM
        answers_text = "\n".join(
            [f"- {k}: {v}" for k, v in session.clarification_answers.items() if v not in (None, "", {})]
        )

        # Explain what will be built and request user confirmation before starting build
        return await self._explain_and_propose_plan(session, answers_text)

    async def _explain_and_propose_plan(
        self, session: AppBuilderSession, answers_text: str
    ) -> List[A2UIMessage]:
        """Explains what the AI will build and presents a confirmation surface."""
        session.phase = "confirming"

        if self.client:
            for attempt in range(2):
                try:
                    return await self._call_gemini_propose_plan(session, answers_text)
                except Exception as e:
                    logger.warning(f"Gemini plan proposal attempt {attempt + 1} failed: {e}")
                    if attempt == 0:
                        await asyncio.sleep(0.5)

        return self._propose_plan_fallback(session, answers_text)

    async def _call_gemini_propose_plan(
        self, session: AppBuilderSession, answers_text: str
    ) -> List[A2UIMessage]:
        history_summary = "\n".join(
            [f"{h['role'].upper()}: {h['content']}" for h in session.history[-6:]]
        )

        full_prompt = f"""
You are an expert AI App Builder implementing Google's A2UI protocol (v0.9).

ORIGINAL USER REQUEST:
"{session.original_prompt}"

USER'S CLARIFICATION ANSWERS:
{answers_text}

CONVERSATION HISTORY:
{history_summary}

TASK:
1. Synthesize the user's intent into a clear, exciting plan for the Flutter application you will build.
2. Outline the app's title, overview explanation, and 3-4 specific key features you will build.
3. Keep the tone helpful, clear, and reassuring.

OUTPUT FORMAT (strictly valid JSON, NO markdown code blocks):
{{
  "app_name": "Concise app title (e.g. TaskFlow Master, FitTrack Pro, BudgetLens)",
  "explanation": "Friendly 2-sentence explanation of what you will build based on their answers.",
  "features": [
    "Feature 1: brief description of widget / interaction",
    "Feature 2: brief description of widget / interaction",
    "Feature 3: brief description of widget / interaction"
  ]
}}
"""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model='gemini-3.8-flash',
                contents=full_prompt,
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        return self._build_confirmation_messages(session, parsed)

    def _build_confirmation_messages(
        self, session: AppBuilderSession, plan: Dict[str, Any]
    ) -> List[A2UIMessage]:
        app_name = plan.get("app_name", "Custom App")
        explanation = plan.get("explanation", "Here is what I will build for you.")
        features = plan.get("features", ["Clean Material 3 UI", "Interactive controls", "Dynamic data model"])
        session.proposed_plan = plan
        session.app_name = app_name

        feature_bullets = "\n".join([f"• {f}" for f in features])
        assistant_msg = (
            f"Here is what I plan to build for **{app_name}**:\n\n"
            f"{explanation}\n\n"
            f"**Key features:**\n{feature_bullets}\n\n"
            "Please review the plan below and tap **Confirm & Build App** when ready!"
        )
        session.history.append({"role": "assistant", "content": assistant_msg})

        feat_texts = [
            A2UIText(id=f"feat_{i}", text=f"✨ {feat}", variant="caption")
            for i, feat in enumerate(features[:4])
        ]

        tree = A2UIColumn(
            id="root",
            children=[
                A2UIText(id="plan_title", text=f"📋 Blueprint: {app_name}", variant="h1"),
                A2UIText(id="plan_desc", text=explanation, variant="body"),
                A2UICard(
                    id="features_card",
                    child=A2UIColumn(children=feat_texts)
                ),
                A2UIDivider(id="plan_div"),
                A2UITextField(
                    id="adjustments_input",
                    label="Any quick adjustments? (optional)",
                    value=A2UIDataBinding(path="/confirmation/adjustments")
                ),
                A2UIButton(
                    id="confirm_build_btn",
                    child=A2UIText(text="🚀 Confirm & Build App"),
                    action=A2UIAction(event=A2UIActionEvent(name="confirm_build", context={"path": "/confirmation"}))
                )
            ]
        )
        components = tree.flatten()

        surface_id = session.clarify_surface_id

        return [
            A2UIMessage(
                sessionId=session.session_id,
                phase="confirming",
                assistantMessage=assistant_msg,
                createSurface=CreateSurfacePayload(surfaceId=surface_id)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="confirming",
                updateComponents=UpdateComponentsPayload(
                    surfaceId=surface_id, components=components
                )
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="confirming",
                updateDataModel=UpdateDataModelPayload(
                    surfaceId=surface_id, path="/", value={"confirmation": {"adjustments": ""}}
                )
            )
        ]

    def _propose_plan_fallback(self, session: AppBuilderSession, answers_text: str) -> List[A2UIMessage]:
        answers = session.clarification_answers
        all_answers = " ".join([str(v) for v in answers.values()]).lower()

        if "task" in all_answers or "todo" in all_answers or "to-do" in all_answers:
            app_name = "TaskFlow Manager"
            explanation = "A modern task manager with priority tagging, status tracking, and quick task creation."
            features = [
                "Task checklist with completion toggles",
                "Category and priority tagging",
                "Quick-add task form",
                "Active task counter and progress indicator"
            ]
        elif "expense" in all_answers or "budget" in all_answers or "money" in all_answers:
            app_name = "SmartBudget Tracker"
            explanation = "A personal finance tool to log expenses, track categories, and manage spending."
            features = [
                "Expense logger with amount and category fields",
                "Category spending breakdown",
                "Budget threshold slider",
                "Real-time expense summary card"
            ]
        elif "fitness" in all_answers or "workout" in all_answers or "exercise" in all_answers:
            app_name = "FitTrack Pro"
            explanation = "An interactive workout companion with exercise logging, set counters, and rest intervals."
            features = [
                "Exercise tracker with active routines",
                "Set & repetition counter buttons",
                "Rest interval duration slider",
                "Workout completion status banner"
            ]
        else:
            app_name = (session.original_prompt.title() or "Custom App")[:28]
            explanation = f"A customized interactive utility designed around: {session.original_prompt}."
            features = [
                "Responsive Material 3 layout",
                "Interactive controls and inputs",
                "Live reactive data model",
                "Instant action feedback buttons"
            ]

        plan = {
            "app_name": app_name,
            "explanation": explanation,
            "features": features
        }
        return self._build_confirmation_messages(session, plan)

    async def process_confirmation(
        self, data: Dict[str, Any], session_id: str
    ) -> List[A2UIMessage]:
        """Builds the app after the user confirms the proposed plan."""
        session = self.get_or_create_session(session_id)

        # Check for user adjustments
        if isinstance(data, dict):
            adj = data.get("adjustments") or data.get("adjustment") or data.get("value")
            if adj and isinstance(adj, str) and adj.strip():
                session.clarification_answers["user_adjustment"] = adj.strip()
                session.history.append({"role": "user", "content": f"[Adjustment: {adj.strip()}]"})

        answers_text = "\n".join(
            [f"- {k}: {v}" for k, v in session.clarification_answers.items() if v not in (None, "", {})]
        )
        if session.proposed_plan:
            plan_str = f"Confirmed Plan for '{session.proposed_plan.get('app_name')}': {session.proposed_plan.get('explanation')}"
            answers_text = f"{plan_str}\n{answers_text}"

        session.phase = "building"

        if self.client:
            for attempt in range(2):
                try:
                    return await self._call_gemini_build_from_clarification(session, answers_text)
                except Exception as e:
                    logger.warning(f"Gemini build attempt {attempt + 1} failed: {e}")
                    if attempt == 0:
                        await asyncio.sleep(0.5)

        return self._build_from_clarification_fallback(session)

    async def _call_gemini_build_from_clarification(
        self, session: AppBuilderSession, answers_text: str
    ) -> List[A2UIMessage]:
        """Builds the app using the original prompt plus clarification answers."""

        history_summary = "\n".join(
            [f"{h['role'].upper()}: {h['content']}" for h in session.history[-6:]]
        )

        full_prompt = f"""
You are an expert AI App Builder implementing Google's A2UI protocol (v0.9).

ORIGINAL USER REQUEST:
"{session.original_prompt}"

USER'S CLARIFICATION ANSWERS:
{answers_text}

CONVERSATION HISTORY:
{history_summary}

TASK:
Based on the user's original request and their clarification answers, build a complete,
functional interactive application UI. Create a rich, responsive interface with appropriate
input controls, display cards, action buttons, and sensible default data.

ALLOWED COMPONENTS:
- Layout: "Column", "Row", "Card", "Divider"
- Display: "Text" (usageHint: "h1", "h2", "body", "caption")
- Controls:
  - "Button" (text, action: {{"name": "action_id", "contextPath": "/path"}})
  - "TextField" (label, placeholder, value: {{"path": "/data/pointer"}})
  - "ChoicePicker" (label, options: [{{"label": "...", "value": "..."}}], value: {{"path": "/data/pointer"}})
  - "Slider" (label, min, max, value: {{"path": "/data/pointer"}})
- Root component MUST have id "root_col" and component "Column"

OUTPUT FORMAT (strictly valid JSON, NO markdown):
{{
  "assistant_message": "Brief explanation of the app you built",
  "components": [... component definitions ...],
  "data": {{... initial state values ...}}
}}
"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model='gemini-3.8-flash',
                contents=full_prompt,
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        assistant_message = parsed.get("assistant_message", "Here's your app!")
        combined_prompt = f"{session.original_prompt} ({answers_text})"

        session.history.append({"role": "user", "content": f"[Clarification answers: {answers_text}]"})
        session.history.append({"role": "assistant", "content": assistant_message})

        # Delete clarification surface, then build the app
        delete_msg = A2UIMessage(
            sessionId=session.session_id,
            phase="building",
            deleteSurface=DeleteSurfacePayload(surfaceId=session.clarify_surface_id)
        )

        build_messages = self._finalize_build(session, combined_prompt, parsed)
        return [delete_msg] + build_messages

    def _finalize_build(
        self, session: AppBuilderSession, user_prompt: str, parsed: Dict[str, Any]
    ) -> List[A2UIMessage]:
        """Common build finalization: parse components, update session, save to disk, return messages."""
        assistant_message = parsed.get("assistant_message", "Here is your app!")
        components_raw = parsed.get("components", [])
        data_raw = parsed.get("data", {})

        components = [ComponentDefinition(**c) for c in components_raw]

        session.phase = "building"
        session.current_components = [c.model_dump(exclude_none=True) for c in components]
        session.current_data = data_raw

        if session.app_name == "Untitled App":
            cleaned_title = (
                user_prompt
                .replace("build", "").replace("create", "").replace("make", "")
                .strip().title()
            )
            session.app_name = cleaned_title[:32] or "Custom App"
            session.app_id = session.app_name.lower().replace(" ", "_")

        try:
            save_app_to_disk(
                session.app_id, session.app_name,
                session.current_components, session.current_data, session.history
            )
            logger.info(f"Auto-saved app '{session.app_name}' ({session.app_id}) to disk.")
        except Exception as e:
            logger.warning(f"Could not auto-save app to disk: {e}")

        return [
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                assistantMessage=assistant_message,
                createSurface=CreateSurfacePayload(surfaceId=session.surface_id)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                updateComponents=UpdateComponentsPayload(
                    surfaceId=session.surface_id, components=components
                )
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                updateDataModel=UpdateDataModelPayload(
                    surfaceId=session.surface_id, path="/", value=data_raw
                )
            )
        ]

    def _smart_intent_fallback(self, user_prompt: str, session: AppBuilderSession) -> List[A2UIMessage]:
        """Fallback intent detection when Gemini is offline."""
        lowered = user_prompt.lower().strip()

        specific_keywords = [
            "tracker", "calculator", "dashboard", "game", "tic tac toe",
            "todo", "task", "expense", "budget", "workout", "fitness",
            "recipe", "weather", "timer", "counter", "quiz", "poll",
            "booking", "reservation", "calendar", "notes", "journal",
            "shopping", "inventory", "contact", "chat", "music",
            "pomodoro", "habit", "meal", "planner"
        ]

        is_specific = any(kw in lowered for kw in specific_keywords) and len(lowered.split()) >= 3

        if is_specific:
            # Clear enough intent — build directly using existing fallback
            return self._smart_multiturn_fallback(user_prompt, session)

        # Vague prompt → ask clarification questions
        session.phase = "clarifying"
        session.original_prompt = user_prompt
        session.history.append({"role": "user", "content": user_prompt})

        questions = [
            {
                "id": "q_app_type",
                "question": "What type of app would you like to build?",
                "type": "choice",
                "options": [
                    "📋 Task / Todo Manager",
                    "🏋️ Fitness / Workout Tracker",
                    "💰 Expense / Budget Tracker",
                    "🎮 Interactive Game",
                    "📊 Data Dashboard",
                    "📝 Notes / Journal"
                ]
            },
            {
                "id": "q_key_feature",
                "question": "What is the most important feature?",
                "type": "choice",
                "options": [
                    "Data Input Forms",
                    "Charts & Visualizations",
                    "Real-time Updates",
                    "Category Filters"
                ]
            },
            {
                "id": "q_extra",
                "question": "Any specific requirements or features you'd like?",
                "type": "text"
            }
        ]

        assistant_msg = (
            "I'd love to build something great for you! "
            "Let me ask a few questions to make sure I get it right."
        )
        session.history.append({"role": "assistant", "content": assistant_msg})

        return self._build_clarification_messages(session, assistant_msg, questions)

    def _build_from_clarification_fallback(self, session: AppBuilderSession) -> List[A2UIMessage]:
        """Builds a basic app from clarification answers when Gemini is offline."""
        answers = session.clarification_answers
        # Combine all answer text
        all_answers = " ".join([str(v) for v in answers.values()]).lower()
        extra = str(answers.get("q_extra", answers.get("q_specific_features", "")))

        if "fitness" in all_answers or "workout" in all_answers or "exercise" in all_answers:
            user_prompt = "workout fitness tracker"
        elif "expense" in all_answers or "budget" in all_answers or "money" in all_answers:
            user_prompt = "personal expense budget tracker"
        elif "game" in all_answers:
            user_prompt = "interactive game"
        elif "task" in all_answers or "todo" in all_answers or "to-do" in all_answers:
            user_prompt = "task todo manager"
        elif "dashboard" in all_answers or "data" in all_answers:
            user_prompt = "data dashboard"
        elif "notes" in all_answers or "journal" in all_answers:
            user_prompt = "notes journal app"
        elif "recipe" in all_answers or "meal" in all_answers:
            user_prompt = "recipe meal planner"
        elif "quiz" in all_answers or "flashcard" in all_answers:
            user_prompt = "flashcard study quiz"
        else:
            user_prompt = session.original_prompt or "custom app"

        if extra:
            user_prompt += f" with {extra}"

        # Delete the clarification surface
        delete_msg = A2UIMessage(
            sessionId=session.session_id,
            phase="building",
            deleteSurface=DeleteSurfacePayload(surfaceId=session.clarify_surface_id)
        )

        # Reset phase so fallback builder creates a new app
        session.phase = "idle"
        build_messages = self._smart_multiturn_fallback(user_prompt, session)
        session.phase = "building"

        # Stamp all build messages with the building phase
        for msg in build_messages:
            msg.phase = "building"

        return [delete_msg] + build_messages

    # ──────────────────────────────────────────────────────
    # EXISTING: Multi-turn modification flow (preserved)
    # ──────────────────────────────────────────────────────

    async def _call_gemini_multiturn(self, user_prompt: str, session: AppBuilderSession) -> List[A2UIMessage]:
        has_existing_app = len(session.current_components) > 0

        # Construct multi-turn context
        history_summary = "\n".join([f"{h['role'].upper()}: {h['content']}" for h in session.history[-6:]])

        if has_existing_app:
            context_prompt = f"""
CONVERSATION HISTORY:
{history_summary}

CURRENT ACTIVE APP BLUEPRINT (JSON):
{json.dumps(session.current_components, indent=2)}

CURRENT ACTIVE APP DATA MODEL (JSON):
{json.dumps(session.current_data, indent=2)}

USER'S NEW REQUEST:
"{user_prompt}"

TASK:
You are incrementally EVOLVING / MODIFYING the user's existing app.
1. Preserve existing components and their IDs unless the user explicitly requested to remove or replace them.
2. Add, update, or style components according to the user's request.
3. Keep the root component with id "root_col" and component "Column".
"""
        else:
            context_prompt = f"""
CONVERSATION HISTORY:
{history_summary}

USER'S INITIAL REQUEST:
"{user_prompt}"

TASK:
Build a BRAND NEW, functional interactive application UI to fulfill the user's request.
Create a rich, responsive interface with input controls, display cards, action buttons, and sensible default data.
Root component MUST have id "root_col" and component "Column".
"""

        full_prompt = f"""
You are an expert AI App Builder implementing Google's A2UI (Agent-to-User Interface) protocol (v0.9).
{context_prompt}

ALLOWED COMPONENTS:
- Layout: "Column", "Row", "Card", "Divider"
- Display: "Text" (usageHint: "h1", "h2", "body", "caption")
- Controls: 
  - "Button" (text, action: {{"name": "action_id", "contextPath": "/path"}})
  - "TextField" (label, placeholder, value: {{"path": "/data/pointer"}})
  - "ChoicePicker" (label, options: [{{"label": "...", "value": "..."}}], value: {{"path": "/data/pointer"}})
  - "Slider" (label, min, max, value: {{"path": "/data/pointer"}})

OUTPUT FORMAT:
Return a strictly valid JSON object with EXACTLY three fields:
1. "assistant_message": A concise, friendly message (1-2 sentences) explaining what you built or changed in this turn.
2. "components": Full list of component definitions.
3. "data": Dictionary of initial state values matching all JSON pointer paths.

DO NOT wrap in markdown code blocks. Output ONLY raw valid JSON.
"""

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model='gemini-3.8-flash',
                contents=full_prompt,
            )
        )

        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()

        parsed = json.loads(text)
        assistant_message = parsed.get("assistant_message", "Here is your updated app!")

        # Update history and finalize build
        session.history.append({"role": "user", "content": user_prompt})
        session.history.append({"role": "assistant", "content": assistant_message})
        return self._finalize_build(session, user_prompt, parsed)

    def _smart_multiturn_fallback(self, user_prompt: str, session: AppBuilderSession) -> List[A2UIMessage]:
        """Smart fallback that actually mutates existing components if network drops."""
        lowered = user_prompt.lower()
        has_existing = len(session.current_components) > 0

        if has_existing:
            # Incremental addition to existing app
            root = next((c for c in session.current_components if c["id"] == "root_col"), None)
            if not root:
                root = {"id": "root_col", "component": "Column", "children": {"explicitList": []}}
                session.current_components.insert(0, root)

            children_list = root["children"]["explicitList"] if isinstance(root.get("children"), dict) else root.get("children", [])

            if "slider" in lowered or "timer" in lowered or "rest" in lowered:
                slider_id = f"slider_{len(session.current_components)}"
                session.current_components.append({
                    "id": slider_id,
                    "component": "Slider",
                    "label": {"literalString": "Rest Timer (Seconds)"},
                    "min": 30.0,
                    "max": 180.0,
                    "value": {"path": "/app/restTimer"}
                })
                children_list.append(slider_id)
                session.current_data.setdefault("app", {})["restTimer"] = 60
                assistant_msg = "Added a rest timer slider (30-180 seconds) to your workout tracker!"

            elif "picker" in lowered or "choice" in lowered or "priority" in lowered or "difficulty" in lowered:
                picker_id = f"picker_{len(session.current_components)}"
                session.current_components.append({
                    "id": picker_id,
                    "component": "ChoicePicker",
                    "label": {"literalString": "Intensity Level"},
                    "options": [
                        {"label": "🟢 Easy", "value": "easy"},
                        {"label": "🟡 Moderate", "value": "moderate"},
                        {"label": "🔴 Hard", "value": "hard"}
                    ],
                    "value": {"path": "/app/intensity"}
                })
                children_list.append(picker_id)
                session.current_data.setdefault("app", {})["intensity"] = "moderate"
                assistant_msg = "Added intensity level choice chips to your app!"

            elif "button" in lowered or "action" in lowered or "log" in lowered:
                btn_id = f"btn_{len(session.current_components)}"
                session.current_components.append({
                    "id": btn_id,
                    "component": "Button",
                    "text": {"literalString": "Log Completed Set"},
                    "action": {"name": "log_set", "contextPath": "/app"}
                })
                children_list.append(btn_id)
                assistant_msg = "Added a 'Log Completed Set' action button to your app!"

            else:
                field_id = f"field_{len(session.current_components)}"
                session.current_components.append({
                    "id": field_id,
                    "component": "TextField",
                    "label": {"literalString": "Notes or Feedback"},
                    "placeholder": "Type here...",
                    "value": {"path": "/app/notes"}
                })
                children_list.append(field_id)
                session.current_data.setdefault("app", {})["notes"] = ""
                assistant_msg = f"Updated your app with a new field for '{user_prompt}'!"

            session.history.append({"role": "user", "content": user_prompt})
            session.history.append({"role": "assistant", "content": assistant_msg})

            components = [ComponentDefinition(**c) for c in session.current_components]
            return [
                A2UIMessage(
                    sessionId=session.session_id,
                    assistantMessage=assistant_msg,
                    updateComponents=UpdateComponentsPayload(surfaceId=session.surface_id, components=components)
                ),
                A2UIMessage(
                    sessionId=session.session_id,
                    updateDataModel=UpdateDataModelPayload(surfaceId=session.surface_id, path="/", value=session.current_data)
                )
            ]

        # Initial App Creation Fallback
        assistant_msg = f"Built your initial {user_prompt.title()} app! What features or controls would you like to add next?"
        session.history.append({"role": "user", "content": user_prompt})
        session.history.append({"role": "assistant", "content": assistant_msg})

        components = [
            ComponentDefinition(
                id="root_col",
                component="Column",
                children=ComponentChildren(explicitList=["card_header", "content_card", "input_field", "submit_btn"])
            ),
            ComponentDefinition(
                id="card_header",
                component="Text",
                text={"literalString": f"🏋️ {user_prompt.title()}"},
                usageHint="h1"
            ),
            ComponentDefinition(
                id="content_card",
                component="Card",
                children=ComponentChildren(explicitList=["desc_text", "status_text"])
            ),
            ComponentDefinition(
                id="desc_text",
                component="Text",
                text={"path": "/app/description"},
                usageHint="body"
            ),
            ComponentDefinition(
                id="status_text",
                component="Text",
                text={"path": "/app/status"},
                usageHint="caption"
            ),
            ComponentDefinition(
                id="input_field",
                component="TextField",
                label={"literalString": "Exercise or Task Name"},
                placeholder="e.g. Barbell Squats",
                value={"path": "/app/exercise"}
            ),
            ComponentDefinition(
                id="submit_btn",
                component="Button",
                text={"literalString": "Log Entry"},
                action=ActionDefinition(name="log_entry", contextPath="/app")
            )
        ]

        data = {
            "app": {
                "description": f"Active workout routine for: {user_prompt}",
                "status": "Session Active • 0 sets completed",
                "exercise": "Bench Press"
            }
        }
        session.current_components = [c.model_dump(exclude_none=True) for c in components]
        session.current_data = data

        if session.app_name == "Untitled App":
            cleaned_title = user_prompt.replace("build", "").replace("create", "").replace("make", "").strip().title()
            session.app_name = cleaned_title[:32] or "Custom App"
            session.app_id = session.app_name.lower().replace(" ", "_")

        try:
            save_app_to_disk(
                session.app_id,
                session.app_name,
                session.current_components,
                session.current_data,
                session.history
            )
            logger.info(f"Auto-saved app '{session.app_name}' ({session.app_id}) to disk.")
        except Exception as e:
            logger.warning(f"Could not auto-save app to disk: {e}")

        return [
            A2UIMessage(
                sessionId=session.session_id,
                assistantMessage=assistant_msg,
                createSurface=CreateSurfacePayload(surfaceId=session.surface_id)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                updateComponents=UpdateComponentsPayload(surfaceId=session.surface_id, components=components)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                updateDataModel=UpdateDataModelPayload(surfaceId=session.surface_id, path="/", value=data)
            )
        ]

    # ──────────────────────────────────────────────────────
    # EXISTING: Project loading & saving (preserved)
    # ──────────────────────────────────────────────────────

    def load_saved_app_into_session(self, session_id: str, app_id: str) -> Optional[List[A2UIMessage]]:
        """Loads a previously saved app from disk into the active session."""
        app_data = load_saved_app(app_id)
        if not app_data:
            return None

        session = self.get_or_create_session(session_id)
        session.app_id = app_data.get("id", app_id)
        session.app_name = app_data.get("name", "Untitled App")
        session.current_components = app_data.get("components", [])
        session.current_data = app_data.get("data", {})
        session.history = app_data.get("history", [])
        session.phase = "building"

        components = [ComponentDefinition(**c) for c in session.current_components]
        assistant_msg = f"📂 Successfully loaded saved app: '{session.app_name}' ({len(components)} components)."

        return [
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                assistantMessage=assistant_msg,
                createSurface=CreateSurfacePayload(surfaceId=session.surface_id)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                updateComponents=UpdateComponentsPayload(surfaceId=session.surface_id, components=components)
            ),
            A2UIMessage(
                sessionId=session.session_id,
                phase="building",
                updateDataModel=UpdateDataModelPayload(surfaceId=session.surface_id, path="/", value=session.current_data)
            )
        ]

    def save_app_with_name(self, session_id: str, app_name: str) -> Dict[str, Any]:
        """Manually saves or renames current session app."""
        session = self.get_or_create_session(session_id)
        session.app_name = app_name.strip() or session.app_name
        session.app_id = session.app_name.lower().replace(" ", "_")

        return save_app_to_disk(
            session.app_id,
            session.app_name,
            session.current_components,
            session.current_data,
            session.history
        )
