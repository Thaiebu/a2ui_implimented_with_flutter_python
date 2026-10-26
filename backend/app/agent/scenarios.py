from typing import List, Dict, Any
from app.protocol.models import (
    A2UIMessage,
    CreateSurfacePayload,
    UpdateComponentsPayload,
    UpdateDataModelPayload,
    ComponentDefinition,
    ComponentChildren,
    ActionDefinition,
    PickerOption
)

def get_agent_introduction_messages() -> List[A2UIMessage]:
    surface_id = "intro_surface"
    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=[
                    ComponentDefinition(
                        id="root_col",
                        component="Column",
                        children=ComponentChildren(
                            explicitList=[
                                "intro_title",
                                "profile_card",
                                "capabilities_card",
                                "action_label",
                                "prompt_shortcut"
                            ]
                        )
                    ),
                    ComponentDefinition(
                        id="intro_title",
                        component="Text",
                        text={"literalString": "🤖 Agent-to-UI (A2UI) Assistant"},
                        usageHint="h1"
                    ),
                    ComponentDefinition(
                        id="profile_card",
                        component="Card",
                        children=ComponentChildren(
                            explicitList=["profile_heading", "profile_desc"]
                        )
                    ),
                    ComponentDefinition(
                        id="profile_heading",
                        component="Text",
                        text={"path": "/agent/title"},
                        usageHint="h2"
                    ),
                    ComponentDefinition(
                        id="profile_desc",
                        component="Text",
                        text={"path": "/agent/bio"},
                        usageHint="body"
                    ),
                    ComponentDefinition(
                        id="capabilities_card",
                        component="Card",
                        children=ComponentChildren(
                            explicitList=["cap_title", "cap_points"]
                        )
                    ),
                    ComponentDefinition(
                        id="cap_title",
                        component="Text",
                        text={"literalString": "💡 What Makes A2UI Different?"},
                        usageHint="h2"
                    ),
                    ComponentDefinition(
                        id="cap_points",
                        component="Text",
                        text={"path": "/agent/features"},
                        usageHint="body"
                    ),
                    ComponentDefinition(
                        id="action_label",
                        component="Text",
                        text={"literalString": "Try an interactive workflow below:"},
                        usageHint="caption"
                    ),
                    ComponentDefinition(
                        id="prompt_shortcut",
                        component="Button",
                        text={"literalString": "✈️ Launch Flight Reservation"},
                        action=ActionDefinition(
                            name="quick_launch_flight",
                            contextPath="/agent"
                        )
                    )
                ]
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "agent": {
                        "title": "Generative UI Agent powered by Gemini",
                        "bio": "I am an A2UI intelligent agent. Rather than replying with only markdown or plain text, I dynamically construct native Flutter interactive UI surfaces (cards, sliders, forms, pickers) and react to your taps in real-time.",
                        "features": "• Native Flutter Material 3 widgets\n• Declarative JSON schema (No unsafe JS/HTML)\n• Reactive RFC 6901 JSON pointer state bindings\n• Bi-directional real-time WebSocket communication"
                    }
                }
            )
        )
    ]

def get_flight_booking_messages() -> List[A2UIMessage]:
    surface_id = "flight_surface"
    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=[
                    ComponentDefinition(
                        id="root_col",
                        component="Column",
                        children=ComponentChildren(
                            explicitList=[
                                "title_header",
                                "flight_card",
                                "class_picker",
                                "passenger_count",
                                "confirm_btn"
                            ]
                        )
                    ),
                    ComponentDefinition(
                        id="title_header",
                        component="Text",
                        text={"literalString": "✈️ Flight Reservation"},
                        usageHint="h1"
                    ),
                    ComponentDefinition(
                        id="flight_card",
                        component="Card",
                        children=ComponentChildren(
                            explicitList=["flight_route", "flight_timing", "flight_price"]
                        )
                    ),
                    ComponentDefinition(
                        id="flight_route",
                        component="Text",
                        text={"path": "/flight/route"},
                        usageHint="h2"
                    ),
                    ComponentDefinition(
                        id="flight_timing",
                        component="Text",
                        text={"path": "/flight/departureTime"},
                        usageHint="body"
                    ),
                    ComponentDefinition(
                        id="flight_price",
                        component="Text",
                        text={"path": "/flight/priceFormatted"},
                        usageHint="caption"
                    ),
                    ComponentDefinition(
                        id="class_picker",
                        component="ChoicePicker",
                        label={"literalString": "Cabin Class"},
                        options=[
                            PickerOption(label="Economy ($280)", value="economy"),
                            PickerOption(label="Premium ($450)", value="premium"),
                            PickerOption(label="Business ($920)", value="business"),
                        ],
                        value={"path": "/booking/cabinClass"}
                    ),
                    ComponentDefinition(
                        id="passenger_count",
                        component="Slider",
                        label={"literalString": "Number of Passengers"},
                        min=1,
                        max=6,
                        value={"path": "/booking/passengers"}
                    ),
                    ComponentDefinition(
                        id="confirm_btn",
                        component="Button",
                        text={"path": "/booking/buttonLabel"},
                        action=ActionDefinition(
                            name="confirm_flight_booking",
                            contextPath="/booking"
                        )
                    )
                ]
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "flight": {
                        "airline": "Skyline Airways",
                        "route": "San Francisco (SFO) ➔ Tokyo (HND)",
                        "departureTime": "Departure: Nov 12 • 10:45 AM • Flight SK-808",
                        "priceFormatted": "Starting at $280 • Non-stop • 11h 20m"
                    },
                    "booking": {
                        "cabinClass": "economy",
                        "passengers": 1,
                        "buttonLabel": "Confirm Booking for $280"
                    }
                }
            )
        )
    ]

def get_smart_home_messages() -> List[A2UIMessage]:
    surface_id = "smarthome_surface"
    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=[
                    ComponentDefinition(
                        id="root_col",
                        component="Column",
                        children=ComponentChildren(
                            explicitList=[
                                "home_header",
                                "temp_card",
                                "mode_picker",
                                "temp_slider",
                                "toggle_btn"
                            ]
                        )
                    ),
                    ComponentDefinition(
                        id="home_header",
                        component="Text",
                        text={"literalString": "🏡 Living Room Climate Control"},
                        usageHint="h1"
                    ),
                    ComponentDefinition(
                        id="temp_card",
                        component="Card",
                        children=ComponentChildren(
                            explicitList=["current_temp", "humidity_info"]
                        )
                    ),
                    ComponentDefinition(
                        id="current_temp",
                        component="Text",
                        text={"path": "/climate/displayTemp"},
                        usageHint="h2"
                    ),
                    ComponentDefinition(
                        id="humidity_info",
                        component="Text",
                        text={"path": "/climate/humidity"},
                        usageHint="body"
                    ),
                    ComponentDefinition(
                        id="mode_picker",
                        component="ChoicePicker",
                        label={"literalString": "System Mode"},
                        options=[
                            PickerOption(label="❄️ Cooling", value="cool"),
                            PickerOption(label="🔥 Heating", value="heat"),
                            PickerOption(label="🍃 Eco", value="eco"),
                        ],
                        value={"path": "/climate/mode"}
                    ),
                    ComponentDefinition(
                        id="temp_slider",
                        component="Slider",
                        label={"literalString": "Target Temperature (°F)"},
                        min=60,
                        max=85,
                        value={"path": "/climate/targetTemp"}
                    ),
                    ComponentDefinition(
                        id="toggle_btn",
                        component="Button",
                        text={"path": "/climate/powerStatusLabel"},
                        action=ActionDefinition(
                            name="toggle_climate_power",
                            contextPath="/climate"
                        )
                    )
                ]
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "climate": {
                        "displayTemp": "Current: 72°F • Target: 68°F",
                        "humidity": "Indoor Humidity: 42% • Air Quality: Excellent",
                        "mode": "cool",
                        "targetTemp": 68,
                        "poweredOn": True,
                        "powerStatusLabel": "Power: ON (Tap to turn OFF)"
                    }
                }
            )
        )
    ]

def get_food_delivery_messages() -> List[A2UIMessage]:
    surface_id = "food_surface"
    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=[
                    ComponentDefinition(
                        id="root_col",
                        component="Column",
                        children=ComponentChildren(
                            explicitList=[
                                "food_header",
                                "restaurant_card",
                                "meal_picker",
                                "notes_input",
                                "order_button"
                            ]
                        )
                    ),
                    ComponentDefinition(
                        id="food_header",
                        component="Text",
                        text={"literalString": "🍱 Artisan Ramen House"},
                        usageHint="h1"
                    ),
                    ComponentDefinition(
                        id="restaurant_card",
                        component="Card",
                        children=ComponentChildren(
                            explicitList=["rating_text", "delivery_time"]
                        )
                    ),
                    ComponentDefinition(
                        id="rating_text",
                        component="Text",
                        text={"path": "/restaurant/rating"},
                        usageHint="h2"
                    ),
                    ComponentDefinition(
                        id="delivery_time",
                        component="Text",
                        text={"path": "/restaurant/eta"},
                        usageHint="caption"
                    ),
                    ComponentDefinition(
                        id="meal_picker",
                        component="ChoicePicker",
                        label={"literalString": "Select Bowl"},
                        options=[
                            PickerOption(label="Tonkotsu Deluxe ($16.50)", value="tonkotsu"),
                            PickerOption(label="Spicy Miso ($15.50)", value="spicy_miso"),
                            PickerOption(label="Truffle Shoyu ($18.00)", value="truffle_shoyu"),
                        ],
                        value={"path": "/order/item"}
                    ),
                    ComponentDefinition(
                        id="notes_input",
                        component="TextField",
                        label={"literalString": "Special Requests (Optional)"},
                        placeholder="e.g. Extra scallions, less salt",
                        value={"path": "/order/notes"}
                    ),
                    ComponentDefinition(
                        id="order_button",
                        component="Button",
                        text={"path": "/order/orderButtonText"},
                        action=ActionDefinition(
                            name="place_food_order",
                            contextPath="/order"
                        )
                    )
                ]
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "restaurant": {
                        "name": "Artisan Ramen House",
                        "rating": "⭐ 4.9 (420+ reviews) • Michelin Recommended",
                        "eta": "Estimated delivery: 25 - 35 mins"
                    },
                    "order": {
                        "item": "tonkotsu",
                        "notes": "Extra chashu slice please",
                        "orderButtonText": "Place Order ($16.50)"
                    }
                }
            )
        )
    ]
