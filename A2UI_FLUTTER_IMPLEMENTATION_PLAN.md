# A2UI (Agent-to-User Interface) with Flutter & Python Backend
## Comprehensive Implementation Plan & Architecture Specification

> **Reference Standard**: [A2UI Protocol Specification (a2ui.org)](https://a2ui.org/)  
> **Target Client**: Flutter (Cross-platform: iOS, Android, Web, Desktop)  
> **Target Backend**: Python (FastAPI, WebSockets/SSE, Google Gemini / LLM Agent)

---

## 1. Executive Summary & Protocol Overview

### What is A2UI?
**A2UI (Agent-to-User Interface)** is an open standard streaming protocol developed by Google and community partners. It solves the fundamental challenges of **Generative UI** in AI applications:

| Challenge in Traditional GenUI | How A2UI Solves It |
|---|---|
| **Security Risks**: LLMs generating executable HTML/JS/React directly leads to XSS and arbitrary code execution vulnerabilities. | **Declarative & Safe**: LLMs output declarative JSON specifications referencing pre-vetted catalog components. No arbitrary client-side code execution. |
| **Deep Tree Hallucinations**: LLMs struggle with deeply nested JSON trees, often breaking bracket closing or hierarchy. | **Flat Adjacency Lists**: Components are streamed as a flat list where components reference child IDs (`explicitList: ["child_1", "child_2"]`). |
| **Monolithic Rendering & Redundancy**: Re-rendering an entire screen whenever a single value updates is slow and jittery. | **Decoupled Data Binding**: Layout (`updateComponents`) is strictly separated from dynamic state (`updateDataModel`), bound via **JSON Pointer (RFC 6901)** paths (e.g. `/cart/total`). |
| **Platform Lock-in**: Code generated for Web (React) does not run natively on mobile or desktop without heavy webviews. | **Framework Agnostic**: The same JSON payload renders natively in Flutter, SwiftUI, Jetpack Compose, or Lit/React using the platform's native design system. |

---

## 2. End-to-End System Architecture: Multi-Turn App Builder

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Flutter as Flutter Studio (Chat + Canvas)
    participant Session as Python Session Store
    participant Agent as Gemini 3.8 Flash Agent

    Note over User,Flutter: Turn 1: Build Initial App
    User->>Flutter: "Build a workout tracker with sets counter"
    Flutter->>Session: WebSocket { type: "prompt", prompt: "Build a workout...", sessionId: "..." }
    Session->>Agent: Prompt: [Empty Tree] + User Request
    Agent-->>Session: { assistant_message: "Created workout tracker V1!", components: [...], data: {...} }
    Session->>Session: Store active V1 components & data
    Session->>Flutter: Stream assistantMessage + createSurface + updateComponents + updateDataModel
    Flutter->>Flutter: Chat renders AI response; Live Canvas renders Workout Tracker V1

    Note over User,Flutter: Turn 2: Incremental Modification
    User->>Flutter: "Add a rest timer slider (30-180s) and difficulty picker"
    Flutter->>Session: WebSocket { type: "prompt", prompt: "Add rest timer...", sessionId: "..." }
    Session->>Agent: Prompt: [Existing V1 Tree + Data] + User Modification Request
    Agent-->>Session: { assistant_message: "Added a rest timer slider and difficulty choice chips!", components: [V2], data: {V2} }
    Session->>Session: Update active V2 components & data
    Session->>Flutter: Stream assistantMessage + updateComponents (V2) + updateDataModel (V2)
    Flutter->>Flutter: Live Canvas hot-updates in place without full page reloads!

    Note over User,Flutter: Turn 3: User Interaction with App
    User->>Flutter: Interacts on Canvas (Adjusts slider to 90s, taps "Log Set")
    Flutter->>Session: userAction { surfaceId: "app_surface", action: "log_set", data: {...} }
    Session->>Flutter: updateDataModel { path: "/workout/status", value: "Logged set! Rest timer started." }
    Flutter->>User: App Canvas reacts in real-time!
```

---

## 3. Protocol Message Structure (v0.9 / v1.0 Spec)

All streaming messages follow the A2UI JSON Lines (`.jsonl`) structure:

### 1. `createSurface`
Initializes a new UI surface slot and links it to an allowed component catalog.
```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "hotel_booking_surface",
    "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
  }
}
```

### 2. `updateComponents`
Defines the component hierarchy using a flat list of component definitions.
```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "hotel_booking_surface",
    "components": [
      {
        "id": "root_column",
        "component": "Column",
        "children": {
          "explicitList": ["hotel_title", "price_badge", "guest_picker", "book_btn"]
        }
      },
      {
        "id": "hotel_title",
        "component": "Text",
        "text": {
          "path": "/hotel/name"
        },
        "usageHint": "h1"
      },
      {
        "id": "price_badge",
        "component": "Text",
        "text": {
          "path": "/hotel/formattedPrice"
        },
        "usageHint": "caption"
      },
      {
        "id": "guest_picker",
        "component": "ChoicePicker",
        "label": { "literalString": "Number of Guests" },
        "options": [
          { "label": "1 Guest", "value": 1 },
          { "label": "2 Guests", "value": 2 },
          { "label": "4+ Guests", "value": 4 }
        ],
        "value": { "path": "/booking/guests" }
      },
      {
        "id": "book_btn",
        "component": "Button",
        "text": { "literalString": "Reserve Now" },
        "action": {
          "name": "submit_reservation",
          "contextPath": "/booking"
        }
      }
    ]
  }
}
```

### 3. `updateDataModel`
Pushes data into the surface's reactive state store using RFC 6901 JSON Pointers.
```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "hotel_booking_surface",
    "path": "/",
    "value": {
      "hotel": {
        "name": "Grand Palace Hotel",
        "formattedPrice": "$180 / night"
      },
      "booking": {
        "guests": 2
      }
    }
  }
}
```

### 4. Client-to-Agent `userAction`
Sent when a user interacts with an input or button.
```json
{
  "version": "v0.9",
  "userAction": {
    "surfaceId": "hotel_booking_surface",
    "action": "submit_reservation",
    "timestamp": 1729321200000,
    "data": {
      "guests": 2
    }
  }
}
```

---

## 4. Flutter Client Architecture

Flutter has two integration paths:
1. **Google's Official `genui` SDK**: Packages `genui`, `genui_catalog`, and `genui_a2a` on pub.dev.
2. **Custom / Native Flutter A2UI Renderer**: Provides full architectural control, custom animations, custom branding, offline testing, and independence from alpha package changes.

### Recommended Approach: Hybrid Architecture
Build a **clean, modular A2UI interpreter package** in Flutter that can consume standard A2UI JSON streams, while providing the option to drop in `genui` plugins.

### Client Core Modules

```
flutter_a2ui/
├── lib/
│   ├── a2ui.dart                     # Main entrypoint
│   ├── protocol/                     # Protocol definitions & models
│   │   ├── surface_message.dart      # createSurface, updateComponents, updateDataModel
│   │   ├── component_node.dart       # Component schema (id, type, props, children)
│   │   └── user_action.dart          # Action payload model
│   ├── state/
│   │   ├── surface_controller.dart   # Manages surfaces & lifecycle
│   │   ├── data_model_store.dart     # RFC 6901 JSON Pointer evaluator & reactive store
│   │   └── dynamic_value.dart        # Resolves literalString vs. path binding
│   ├── catalog/                      # Component Registry & Catalog
│   │   ├── component_catalog.dart    # Abstract catalog interface
│   │   ├── basic_catalog.dart        # Standard Material 3 implementation
│   │   └── widget_builder.dart       # Factory interface for individual components
│   ├── widgets/                      # Native Flutter widget renderers
│   │   ├── a2ui_surface.dart         # Container for a specific surfaceId
│   │   ├── layout/                   # Column, Row, Card, List, Tabs
│   │   ├── display/                  # Text, Heading, Image, Icon, Divider
│   │   └── inputs/                   # Button, TextField, ChoicePicker, Slider
│   └── transport/
│       ├── a2ui_client.dart          # Base transport client
│       ├── websocket_client.dart     # WebSocket streaming
│       └── sse_client.dart           # Server-Sent Events streaming
```

### Key Flutter Implementation Details

#### 1. JSON Pointer (RFC 6901) Data Binding
```dart
class DataModelStore extends ChangeNotifier {
  final Map<String, dynamic> _data = {};

  dynamic getByPointer(String pointer) {
    if (pointer.isEmpty || pointer == '/') return _data;
    final tokens = pointer.split('/').skip(1).map((t) => t.replaceAll('~1', '/').replaceAll('~0', '~'));
    dynamic current = _data;
    for (final token in tokens) {
      if (current is Map) {
        current = current[token];
      } else if (current is List) {
        final index = int.tryParse(token);
        current = (index != null && index >= 0 && index < current.length) ? current[index] : null;
      } else {
        return null;
      }
    }
    return current;
  }

  void updatePointer(String pointer, dynamic value) {
    // updates nested dictionary and calls notifyListeners()
    // ...
    notifyListeners();
  }
}
```

#### 2. Flat List / Adjacency List Tree Assembly
```dart
Widget buildComponent(String componentId, BuildContext context) {
  final node = surfaceController.getComponent(componentId);
  if (node == null) return const SizedBox.shrink();

  final builder = catalog.resolve(node.component);
  return builder.build(
    context: context,
    node: node,
    surfaceController: surfaceController,
    buildChild: (childId) => buildComponent(childId, context),
  );
}
```

---

## 5. Python Backend Architecture

The backend serves as the **AI Agent Host and A2UI Streamer**.

### Backend Directory Structure
```
backend/
├── app/
│   ├── main.py                       # FastAPI entrypoint (WebSocket + HTTP)
│   ├── config.py                     # App settings & Gemini API keys
│   ├── agent/
│   │   ├── a2ui_agent.py             # Agent runtime (Google GenAI / Gemini 2.0 / 1.5)
│   │   ├── prompts.py                # System instructions & catalog schemas
│   │   └── tools.py                  # Backend tools (e.g. database, APIs)
│   ├── protocol/
│   │   ├── models.py                 # Pydantic models for A2UI messages
│   │   └── serializer.py             # JSONL stream formatter
│   └── sessions/
│       ├── session_manager.py        # Active WebSocket sessions & surfaces
│       └── surface_state.py          # Server-side mirror of component tree & data model
├── catalogs/
│   └── basic_catalog.json            # Official A2UI Basic Catalog schema
└── requirements.txt
```

### Agent Orchestration Flow (FastAPI + Google Gemini)
1. **Catalog Injection**: The system instruction embeds the JSON schema of `basic_catalog.json` and instructs the model to return A2UI JSON operations.
2. **Tool Execution**: When the user provides input or actions, the agent uses function calling to query backend services.
3. **Structured Streaming**: The agent formats output as atomic operations:
   - `createSurface`
   - `updateComponents`
   - `updateDataModel`
4. **Handling `userAction`**: When the user presses a button, the backend receives the event with the surface's current form values, triggers the next agent cycle, and streams delta updates to the UI.

---

## 6. Implementation Roadmap

### Phase 1: Environment & Protocol Specifications
- [ ] Initialize Python backend (`fastapi`, `uvicorn`, `google-genai`, `pydantic`).
- [ ] Initialize Flutter workspace with `flutter create`.
- [ ] Download & validate official `a2ui` catalog schemas (v0.9/v1.0).
- [ ] Define shared protocol schemas (JSON contracts for messages and actions).

### Phase 2: Python Backend Agent & Streaming Service
- [ ] Create FastAPI WebSocket endpoint `/ws/a2ui`.
- [ ] Implement Gemini AI Agent with structured JSON output configured for A2UI messages.
- [ ] Build mock generator mode (for rapid client-side Flutter testing without LLM costs).
- [ ] Implement interactive tool execution and data model delta emission.

### Phase 3: Flutter A2UI Renderer Engine
- [ ] Build `DataModelStore` with RFC 6901 pointer resolution and Flutter `ChangeNotifier`/`InheritedNotifier`.
- [ ] Implement `A2UISurface` widget and surface state manager.
- [ ] Implement core Component Catalog:
  - Layout: `Column`, `Row`, `Card`, `Divider`
  - Display: `Text` (with typography variants `h1`, `h2`, `body`, `caption`), `Image`, `Icon`
  - Input: `Button`, `TextField`, `ChoicePicker`, `Slider`
- [ ] Implement WebSocket transport client with automatic reconnection and streaming parser.

### Phase 4: Bi-directional Action Loop & Client Functions
- [ ] Wire user actions (`onPressed`, `onChanged`, `onSubmit`) to emit `userAction` events.
- [ ] Implement client-side functions (e.g., local currency formatting, input validation) without roundtrips.
- [ ] Handle dynamic updates: update only modified sub-trees without flickering or full rebuilds.

### Phase 5: Production Readiness & Advanced Capabilities
- [ ] Dynamic styling & theme tokens (Material 3 Dark/Light mode synchronization).
- [ ] Error boundary handling (fallback widgets for unsupported components or schema mismatches).
- [ ] Offline caching and surface rehydration.
- [ ] Multi-surface support (e.g., chat thread containing multiple independent interactive surfaces).

---

## 7. Concrete Code Blueprints

Detailed code templates and starter blueprints are provided in the companion files:
- [backend_guide.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/docs/backend_guide.md)
- [flutter_guide.md](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/docs/flutter_guide.md)
- [catalog_example.json](file:///Users/mohamedthaiebu/Documents/stride_explore/a2ui/docs/catalog_example.json)
