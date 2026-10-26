# A2UI Multi-Turn App Studio (Flutter + Python + Gemini)

A working implementation of **[A2UI (Agent-to-User Interface)](https://a2ui.org/)** transformed into an **Interactive Multi-Turn AI App Studio** featuring **In-Chat Intent Clarification**, **Plan Confirmation**, **Disk Persistence**, and **Flutter Code Export**.

---

## 🏗️ Studio Architecture & 3-Phase Workflow

Rather than prematurely generating an app from a vague prompt, the studio operates in 3 distinct, interactive phases:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              A2UI STUDIO WORKFLOW                           │
├────────────────────────────────┬────────────────────────────────────────────┤
│ 1. Clarification Phase         │ 💬 Copilot renders an interactive A2UI     │
│    (if prompt is ambiguous)    │    form inside the chat (Chips, Inputs).   │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 2. Plan Confirmation Phase     │ 📋 Copilot presents a proposed UI blueprint│
│    (review before build)       │    card with a [ 🚀 Confirm & Build ] btn. │
├────────────────────────────────┼────────────────────────────────────────────┤
│ 3. Build & Live Canvas Phase   │ 📱 Flutter dynamically renders native M3   │
│    (instant 60 FPS streaming)  │    widgets on the Live Canvas.             │
└────────────────────────────────┴────────────────────────────────────────────┘
```

### Visual Studio Layout:

```
┌─────────────────────────────────┬───────────────────────────────────────────┐
│        💬 AI Chat Copilot       │            📱 Live App Canvas             │
├─────────────────────────────────┼───────────────────────────────────────────┤
│ User: "Build a workout app"     │  🏋️ Pro Workout Routine                   │
│                                 │  ┌─────────────────────────────────────┐  │
│ AI: "What kind of workout?"     │  │ Barbell Bench Press                 │  │
│ [Strength] [Cardio] [HIIT]      │  │ Target: 4 Sets x 8-10 Reps          │  │
│ [ Submit Preferences ]          │  └─────────────────────────────────────┘  │
│                                 │  Rest Timer (Seconds): [ 90 ────────── ]  │
│ AI: "Proposed Plan: 4 widgets"  │  Intensity: ( ) Warmup (*) Med ( ) Max    │
│ [ 🚀 Confirm & Build App ]      │  [ Log Completed Set ]                    │
│                                 │  🟢 Auto-Saved to backend/saved_apps/     │
├─────────────────────────────────┴───────────────────────────────────────────┤
│ [ Ask AI to add features, controls, or change layout...                ] ⬆  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Tech Stack & Project Breakdown

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | Python 3.12 (FastAPI, Uvicorn, google-genai) | Orchestrates the Gemini LLM agent, manages sessions, validates A2UI schemas, and serves WebSockets. |
| **A2UI Schemas** | Declarative JSON (`backend/saved_apps/*.json`) | Intermediate Representation (IR) defining UI component trees, RFC 6901 reactive state paths, and event actions. |
| **Frontend** | Dart & Flutter (Material 3) | Studio UI and dynamic runtime renderer mapping A2UI JSON components to native Flutter widgets in real time. |
| **Code Exporter** | Python Code Generator (`/api/apps/{id}/export`) | Compiles declarative A2UI JSON trees into standalone Flutter Dart source code. |

---

## 💾 App Persistence & Export

1. **Auto-Saved to Disk**:
   - Every app you build or modify is automatically saved as a JSON blueprint under:
     `backend/saved_apps/<app_name>.json`
   - Contains the full component tree, RFC 6901 reactive data model, and chat history.
2. **"Saved Apps" Project Library**:
   - Tap **"Saved Apps"** in the top AppBar to browse all saved projects on disk.
   - Click **Open** to immediately load any previous project onto the canvas.
3. **Standalone Flutter Dart Export**:
   - Tap the `< >` (code) icon on any saved app in the library to view and copy clean, standalone Flutter Dart code ready to paste into any new Flutter project!
4. **Save As / Rename**:
   - Click the Save icon in the AppBar to rename or explicitly persist your project.

---

## 🚀 How Multi-Turn App Building Works

1. **Turn 1 (Prompt & Clarification)**:
   - User types: *"Build an expense tracker"*
   - AI determines missing context and renders an interactive **Clarification Form** with category tags in the chat.
2. **Turn 2 (Plan Confirmation)**:
   - User submits selections; AI returns a **Blueprint Card** summarizing the planned layout.
   - User clicks **"🚀 Confirm & Build App"**.
3. **Turn 3 (Incremental Modification)**:
   - User types: *"Add a budget limit slider from $100 to $2000"*
   - The backend passes the **existing UI blueprint** to Gemini.
   - AI modifies and extends the tree in place without wiping previous user progress.
4. **Turn 4 (Interactive Testing)**:
   - User adjusts sliders or types input on the live Canvas.
   - Dynamic user changes are automatically synchronized and persisted.
5. **New Project**:
   - Tap **"New App"** in the top AppBar to start a new app from scratch.

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.10+
- Flutter 3.22+
- Gemini API Key (from [Google AI Studio](https://aistudio.google.com/app/apikey))

### 1. Configure Backend Environment
```bash
cd backend
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY
```

### 2. Start the Backend Server
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Start the Flutter Studio
```bash
cd frontend
flutter pub get

# Run on macOS desktop (fastest, no web CDN dependencies):
flutter run -d macos

# OR run in Chrome:
flutter run -d chrome
```

---

## 📚 Documentation
- [A2UI_DEEP_DIVE_EXPLAINED.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/A2UI_DEEP_DIVE_EXPLAINED.md) — **Deep Dive**: How A2UI works, JSON state tracking vs. custom Dart code, and why it exists.
- [A2UI_FLUTTER_IMPLEMENTATION_PLAN.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/A2UI_FLUTTER_IMPLEMENTATION_PLAN.md) — Master multi-turn architecture specification.
- [docs/flutter_guide.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/docs/flutter_guide.md) — Flutter widget catalog & JSON Pointer binding.
- [docs/backend_guide.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/docs/backend_guide.md) — Python backend & Gemini agent guide.
