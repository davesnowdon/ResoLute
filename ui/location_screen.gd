extends Control

# UI References
@onready var location_name: Label = $MainContainer/LeftPanel/LocationHeader/HeaderContent/LocationName
@onready var location_desc: Label = $MainContainer/LeftPanel/LocationHeader/HeaderContent/LocationDesc
@onready var mentor_message: Label = $MainContainer/LeftPanel/MentorPanel/MentorContent/MentorMessage
@onready var player_name_label: Label = $MainContainer/RightPanel/StatsPanel/StatsContent/PlayerName
@onready var level_label: Label = $MainContainer/RightPanel/StatsPanel/StatsContent/Level
@onready var experience_label: Label = $MainContainer/RightPanel/StatsPanel/StatsContent/Experience
@onready var songs_learned_label: Label = $MainContainer/RightPanel/StatsPanel/StatsContent/SongsLearned
@onready var fragment_list: VBoxContainer = $MainContainer/RightPanel/InventoryPanel/InventoryContent/FragmentList

# Action Buttons
@onready var enter_tavern_btn: Button = $MainContainer/RightPanel/ActionsPanel/ActionsContent/ButtonContainer/EnterTavernButton
@onready var travel_btn: Button = $MainContainer/RightPanel/ActionsPanel/ActionsContent/ButtonContainer/TravelButton
@onready var practice_btn: Button = $MainContainer/RightPanel/ActionsPanel/ActionsContent/ButtonContainer/PracticeButton
@onready var logout_btn: Button = $MainContainer/RightPanel/ActionsPanel/ActionsContent/ButtonContainer/LogoutButton

# Player data
var player_data: Dictionary = {}

# Location data
var location_data: Dictionary = {}

# Song fragments / inventory
var collected_segments: Array = []
var total_segments: int = 4

# Available destinations for travel
var available_destinations: Array = []

var origin_name: String = ""
var travelling_to: String = ""

func _ready() -> void:
	# Connect button signals
	enter_tavern_btn.pressed.connect(_on_enter_tavern_pressed)
	travel_btn.pressed.connect(_on_travel_pressed)
	practice_btn.pressed.connect(_on_practice_pressed)
	logout_btn.pressed.connect(_on_logout_pressed)
	
	# Connect WebSocket signals
	WebSocket.message_received.connect(_on_message_received)
	WebSocket.error.connect(_on_websocket_error)
	WebSocket.disconnected.connect(_on_websocket_disconnected)
	
	# Check if we're authenticated
	if not WebSocket.is_authenticated():
		print("[Location] Not authenticated, returning to login")
		get_tree().change_scene_to_file("res://login_screen.tscn")
		return
	
	# Use player data from WebSocket if available
	if not WebSocket.player_data.is_empty():
		player_data = WebSocket.player_data.duplicate()
		update_player_stats()
	
	# Request fresh data from server
	_request_game_data()


func _exit_tree() -> void:
	# Disconnect signals when leaving scene
	if WebSocket.message_received.is_connected(_on_message_received):
		WebSocket.message_received.disconnect(_on_message_received)
	if WebSocket.error.is_connected(_on_websocket_error):
		WebSocket.error.disconnect(_on_websocket_error)
	if WebSocket.disconnected.is_connected(_on_websocket_disconnected):
		WebSocket.disconnected.disconnect(_on_websocket_disconnected)


func _request_game_data() -> void:
	# Request location state (includes inventory)
	print("[Location] Requesting location data...")
	WebSocket.request_location()
	
	# Request player stats
	print("[Location] Requesting player data...")
	WebSocket.request_player()


func update_location_display() -> void:
	var loc = location_data.get("location", {})
	location_name.text = "🏰 " + loc.get("name", "Unknown Location")
	location_desc.text = loc.get("description", "A mysterious place...")
	
	# Mentor message - could come from location or be generated
	var mentor_text = loc.get("mentor_message", "")
	if mentor_text.is_empty():
		mentor_text = "Welcome, brave bard! Explore this location and seek out song fragments."
	mentor_message.text = mentor_text


func update_player_stats() -> void:
	var name = player_data.get("name", WebSocket.player_id)
	var level = player_data.get("level", 1)
	var xp = player_data.get("xp", 0)
	var xp_needed = player_data.get("xp_to_next_level", 100)
	var gold = player_data.get("gold", 0)
	var reputation = player_data.get("reputation", 0)
	
	player_name_label.text = "🎭 Name: " + str(name)
	level_label.text = "⭐ Level: " + str(level)
	experience_label.text = "✨ XP: " + str(xp) + " / " + str(xp_needed)
	
	# Show collected segments count
	var segments_count = len(collected_segments)
	songs_learned_label.text = "🎵 Fragments: " + str(segments_count) + " / " + str(total_segments)


func update_fragment_list() -> void:
	# Clear existing fragments
	for child in fragment_list.get_children():
		child.queue_free()
	
	# Add fragment entries
	if collected_segments.is_empty():
		var empty_label = Label.new()
		empty_label.text = "(No song fragments yet)"
		empty_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
		fragment_list.add_child(empty_label)
	else:
		for segment in collected_segments:
			var label = Label.new()
			var seg_name = segment.get("name", "Unknown Fragment")
			var seg_desc = segment.get("description", "")
			label.text = "📜 " + seg_name
			if not seg_desc.is_empty():
				label.tooltip_text = seg_desc
			label.add_theme_font_size_override("font_size", 13)
			fragment_list.add_child(label)


# WebSocket message handler
func _on_message_received(msg_type: String, content: String, data: Dictionary) -> void:
	print("[Location] Received message: ", msg_type)
	
	match msg_type:
		"location_state":
			# Full location data including inventory
			location_data = data
			collected_segments = data.get("collected_segments", [])
			total_segments = data.get("total_segments", 4)
			available_destinations = data.get("available_destinations", [])
			print("[Location] Location data received: ", data.get("location", {}).get("name", "unknown"))
			update_location_display()
			update_fragment_list()
			update_player_stats()  # Update fragment count
		
		"player_state":
			# Player stats
			player_data = data
			print("[Location] Player data received: ", data.get("name", "unknown"))
			update_player_stats()
		
		"world_state":
			# World was generated/loaded
			print("[Location] World state received")
			# Request location after world is ready
			WebSocket.request_location()
		
		"world_generating":
			# World is being generated
			print("[Location] World is being generated...")
			mentor_message.text = "A new realm is being woven just for you... Please wait."
		
		"inventory_update":
			# Inventory updated
			collected_segments = data.get("collected_segments", [])
			total_segments = data.get("total_segments", 4)
			update_fragment_list()
			update_player_stats()
		
		"exercise_state":
			# Travel initiated, switch to travel screen
			print("[Location] Travel started, switching to travel screen")
			# Store travel data for the travel screen
			var travel_scene = load("res://travel.tscn").instantiate()
			travel_scene.set_origin(location_data.get("location", {}).get("name", "Unknown"))
			travel_scene.set_destination(travelling_to)
			get_tree().root.add_child(travel_scene)
			travel_scene.start_travel(data)
			queue_free()  # Remove this screen
		
		"error":
			print("[Location] Error: ", content)
			mentor_message.text = "⚠️ " + content


func _on_websocket_error(message: String) -> void:
	print("[Location] WebSocket error: ", message)
	mentor_message.text = "⚠️ Connection error: " + message


func _on_websocket_disconnected() -> void:
	print("[Location] WebSocket disconnected")
	# Return to login screen
	get_tree().change_scene_to_file("res://login_screen.tscn")


# Button handlers
func _on_enter_tavern_pressed() -> void:
	print("Entering tavern...")
	get_tree().change_scene_to_file("res://tavern.tscn")


func _on_travel_pressed() -> void:
	print("Opening travel map...")
	# For now, show available destinations in mentor message
	if available_destinations.is_empty():
		mentor_message.text = "There are no destinations available from here."
	else:
		# If only one destination, travel directly
		if available_destinations.size() == 1:
			var dest = available_destinations[0]
			_start_travel_to(dest)
		else:
			# Show destination selection (for now, just travel to first)
			var dest_names = []
			for dest in available_destinations:
				dest_names.append(dest.get("name", "Unknown"))
			mentor_message.text = "Available destinations: " + ", ".join(dest_names) + "\nTraveling to first destination..."
			_start_travel_to(available_destinations[0])


func _start_travel_to(destination: Dictionary) -> void:
	"""Start travel to a destination."""
	var dest_id = destination.get("id", 0)
	var dest_name = destination.get("name", "Unknown")
	print("[Location] Starting travel to: ", dest_name, " (id: ", dest_id, ")")
	
	# Store current location as origin for travel screen
	origin_name = location_data.get("location", {}).get("name", "Unknown")
	travelling_to = dest_name
	
	# Store travel info in a global or pass via scene change
	# For now, we'll request travel and handle the response
	WebSocket.travel_to(dest_name)
	# The exercise_state response will trigger scene change

func _on_practice_pressed() -> void:
	print("Opening practice mode...")
	mentor_message.text = "Practice mode coming soon! Keep collecting song fragments."
	# TODO: Implement practice mode


func _on_logout_pressed() -> void:
	print("Logging out...")
	# Disconnect WebSocket
	WebSocket.disconnect_from_server()
	# Return to landing screen
	get_tree().change_scene_to_file("res://landing_screen.tscn")
