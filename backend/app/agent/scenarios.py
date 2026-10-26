from typing import List, Dict, Any
from a2ui.builder.v0_9 import (
    Column,
    Card,
    Text,
    Button,
    Action,
    ActionEvent,
    ChoicePicker,
    ChoicePickerOption,
    Slider,
    TextField,
    DataBinding
)
from app.protocol.models import (
    A2UIMessage,
    CreateSurfacePayload,
    UpdateComponentsPayload,
    UpdateDataModelPayload,
)

def get_agent_introduction_messages() -> List[A2UIMessage]:
    surface_id = "intro_surface"
    tree = Column(
        id="root",
        children=[
            Text(id="intro_title", text="🤖 Agent-to-UI (A2UI) Assistant", variant="h1"),
            Card(
                id="profile_card",
                child=Column(
                    children=[
                        Text(id="profile_heading", text=DataBinding(path="/agent/title"), variant="h2"),
                        Text(id="profile_desc", text=DataBinding(path="/agent/bio"), variant="body"),
                    ]
                )
            ),
            Card(
                id="capabilities_card",
                child=Column(
                    children=[
                        Text(id="cap_title", text="💡 What Makes A2UI Different?", variant="h2"),
                        Text(id="cap_points", text=DataBinding(path="/agent/features"), variant="body"),
                    ]
                )
            ),
            Text(id="action_label", text="Try an interactive workflow below:", variant="caption"),
            Button(
                id="prompt_shortcut",
                child=Text(text="✈️ Launch Flight Reservation"),
                action=Action(event=ActionEvent(name="quick_launch_flight", context={"path": "/agent"}))
            )
        ]
    )

    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=tree.flatten()
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "agent": {
                        "name": "Gemini 3.8 Flash A2UI Agent",
                        "title": "Generative Interactive UI Protocol (A2UI)",
                        "bio": "Instead of raw chat text or static mockups, this assistant generates real, interactive, native Material 3 user interfaces directly streamed from the AI backend.",
                        "features": "• Native Flutter rendering with Google GenUI & A2UI Core\n• Live reactive two-way data bindings\n• Multi-turn intent clarification & app refinement\n• Pure declarative A2UI JSON wire protocol"
                    }
                }
            )
        )
    ]

def get_flight_booking_messages() -> List[A2UIMessage]:
    surface_id = "flight_surface"
    tree = Column(
        id="root",
        children=[
            Text(id="title_header", text="✈️ Flight Reservation", variant="h1"),
            Card(
                id="flight_card",
                child=Column(
                    children=[
                        Text(id="flight_route", text=DataBinding(path="/flight/route"), variant="h2"),
                        Text(id="flight_timing", text=DataBinding(path="/flight/departureTime"), variant="body"),
                        Text(id="flight_price", text=DataBinding(path="/flight/price"), variant="h2"),
                    ]
                )
            ),
            ChoicePicker(
                id="class_picker",
                label="Select Cabin Class",
                options=[
                    ChoicePickerOption(label="Economy ($350)", value="economy"),
                    ChoicePickerOption(label="Premium Economy ($580)", value="premium"),
                    ChoicePickerOption(label="Business First ($1,250)", value="business"),
                ],
                value=DataBinding(path="/flight/selectedClass"),
            ),
            Slider(
                id="passenger_count",
                label="Passenger Seats",
                min=1.0,
                max=6.0,
                value=DataBinding(path="/flight/passengers"),
            ),
            Button(
                id="confirm_btn",
                child=Text(text="Confirm Reservation"),
                action=Action(event=ActionEvent(name="confirm_flight_booking", context={"path": "/flight"}))
            )
        ]
    )

    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=tree.flatten()
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "flight": {
                        "route": "San Francisco (SFO) ➔ Tokyo Haneda (HND)",
                        "departureTime": "Flight GA-804 • Departs Tomorrow at 10:45 AM (Non-stop)",
                        "price": "Total: $350.00 USD",
                        "selectedClass": "economy",
                        "passengers": 1.0,
                        "status": "Ready for confirmation"
                    }
                }
            )
        )
    ]

def get_smart_home_messages() -> List[A2UIMessage]:
    surface_id = "smarthome_surface"
    tree = Column(
        id="root",
        children=[
            Text(id="home_header", text="🏡 Living Room Climate Control", variant="h1"),
            Card(
                id="temp_card",
                child=Column(
                    children=[
                        Text(id="current_temp", text=DataBinding(path="/climate/displayTemp"), variant="h2"),
                        Text(id="humidity_info", text=DataBinding(path="/climate/humidity"), variant="body"),
                    ]
                )
            ),
            ChoicePicker(
                id="mode_picker",
                label="System Mode",
                options=[
                    ChoicePickerOption(label="❄️ Cooling", value="cool"),
                    ChoicePickerOption(label="🔥 Heating", value="heat"),
                    ChoicePickerOption(label="🍃 Eco", value="eco"),
                ],
                value=DataBinding(path="/climate/mode")
            ),
            Slider(
                id="temp_slider",
                label="Target Temperature (°F)",
                min=60.0,
                max=85.0,
                value=DataBinding(path="/climate/targetTemp")
            ),
            Button(
                id="toggle_btn",
                child=Text(text="Turn Climate Off"),
                action=Action(event=ActionEvent(name="toggle_climate", context={"path": "/climate"}))
            )
        ]
    )

    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=tree.flatten()
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "climate": {
                        "displayTemp": "Currently 72°F (Comfortable)",
                        "humidity": "Indoor Humidity: 45% • Air Filter: Good",
                        "mode": "cool",
                        "targetTemp": 70.0,
                        "power": "on"
                    }
                }
            )
        )
    ]

def get_food_delivery_messages() -> List[A2UIMessage]:
    surface_id = "food_surface"
    tree = Column(
        id="root",
        children=[
            Text(id="food_header", text="🍱 Artisan Ramen House", variant="h1"),
            Card(
                id="restaurant_card",
                child=Column(
                    children=[
                        Text(id="rating_text", text=DataBinding(path="/restaurant/rating"), variant="h2"),
                        Text(id="delivery_time", text=DataBinding(path="/restaurant/eta"), variant="caption"),
                    ]
                )
            ),
            ChoicePicker(
                id="meal_picker",
                label="Select Bowl",
                options=[
                    ChoicePickerOption(label="Tonkotsu Deluxe ($16.50)", value="tonkotsu"),
                    ChoicePickerOption(label="Spicy Miso ($15.50)", value="spicy_miso"),
                    ChoicePickerOption(label="Shoyu Truffle ($18.00)", value="shoyu"),
                    ChoicePickerOption(label="Vegan Mushroom Ramen ($14.00)", value="vegan"),
                ],
                value=DataBinding(path="/order/selectedMeal")
            ),
            TextField(
                id="notes_input",
                label="Special Requests / Allergies",
                value=DataBinding(path="/order/notes")
            ),
            Button(
                id="order_button",
                child=Text(text="Place Order ($16.50)"),
                action=Action(event=ActionEvent(name="place_food_order", context={"path": "/order"}))
            )
        ]
    )

    return [
        A2UIMessage(
            createSurface=CreateSurfacePayload(surfaceId=surface_id)
        ),
        A2UIMessage(
            updateComponents=UpdateComponentsPayload(
                surfaceId=surface_id,
                components=tree.flatten()
            )
        ),
        A2UIMessage(
            updateDataModel=UpdateDataModelPayload(
                surfaceId=surface_id,
                path="/",
                value={
                    "restaurant": {
                        "rating": "⭐ 4.9 • Authentic Handmade Noodles",
                        "eta": "Estimated Delivery: 25-35 mins (0.8 miles away)"
                    },
                    "order": {
                        "selectedMeal": "tonkotsu",
                        "notes": "Extra scallions please",
                        "total": "$16.50"
                    }
                }
            )
        )
    ]
