extends Control

@onready var username_field: LineEdit = $CenterContainer/VBoxContainer/FormContainer/UsernameField
@onready var password_field: LineEdit = $CenterContainer/VBoxContainer/FormContainer/PasswordField
@onready var error_label: Label = $CenterContainer/VBoxContainer/FormContainer/ErrorLabel
@onready var start_quest_button: Button = $CenterContainer/VBoxContainer/StartQuestButton
@onready var back_button: Button = $CenterContainer/VBoxContainer/BackButton

# Server configuration
const SERVER_URL = "ws://localhost:8000/ws"

# State
var _connecting: bool = false

func _ready() -> void:
	# Connect button signals
	start_quest_button.pressed.connect(_on_start_quest_pressed)
	back_button.pressed.connect(_on_back_pressed)

	# Allow Enter key to submit from password field
	password_field.text_submitted.connect(_on_password_submitted)

	# Clear errors when user starts typing
	username_field.text_changed.connect(_on_input_changed)
	password_field.text_changed.connect(_on_input_changed)

	# Connect WebSocket signals
	WebSocket.connected.connect(_on_websocket_connected)
	WebSocket.authenticated.connect(_on_websocket_authenticated)
	WebSocket.error.connect(_on_websocket_error)
	WebSocket.disconnected.connect(_on_websocket_disconnected)

	# Ensure error label is empty on start
	clear_error()

func _exit_tree() -> void:
	# Disconnect signals when leaving scene
	if WebSocket.connected.is_connected(_on_websocket_connected):
		WebSocket.connected.disconnect(_on_websocket_connected)
	if WebSocket.authenticated.is_connected(_on_websocket_authenticated):
		WebSocket.authenticated.disconnect(_on_websocket_authenticated)
	if WebSocket.error.is_connected(_on_websocket_error):
		WebSocket.error.disconnect(_on_websocket_error)
	if WebSocket.disconnected.is_connected(_on_websocket_disconnected):
		WebSocket.disconnected.disconnect(_on_websocket_disconnected)

func show_error(message: String) -> void:
	error_label.text = message
	_set_ui_enabled(true)

func clear_error() -> void:
	error_label.text = ""

func _set_ui_enabled(enabled: bool) -> void:
	start_quest_button.disabled = not enabled
	username_field.editable = enabled
	password_field.editable = enabled
	_connecting = not enabled

	if enabled:
		start_quest_button.text = "Start Quest"
	else:
		start_quest_button.text = "Connecting..."

func _on_input_changed(_new_text: String) -> void:
	# Clear error when user modifies input
	clear_error()

func _on_start_quest_pressed() -> void:
	if _connecting:
		return

	var username = username_field.text.strip_edges()
	var password = password_field.text

	if username.is_empty():
		show_error("⚠ Username is required")
		username_field.grab_focus()
		return

	if password.is_empty():
		show_error("⚠ Password is required")
		password_field.grab_focus()
		return

	clear_error()
	_set_ui_enabled(false)

	# Check if already connected
	if WebSocket.is_connected():
		# Already connected, just authenticate
		print("[Login] Already connected, authenticating...")
		WebSocket.authenticate(username, password)
	else:
		# Need to connect first
		print("[Login] Connecting to server: ", SERVER_URL)
		var err = WebSocket.connect_to_server(SERVER_URL)
		if err != OK:
			show_error("⚠ Failed to connect to server")
			return
		# Authentication will happen in _on_websocket_connected

func _on_back_pressed() -> void:
	# Disconnect if connected
	if WebSocket.is_connected():
		WebSocket.disconnect_from_server()

	# Return to landing screen
	get_tree().change_scene_to_file("res://landing_screen.tscn")

func _on_password_submitted(_text: String) -> void:
	# Trigger login when Enter is pressed in password field
	_on_start_quest_pressed()

# WebSocket signal handlers
func _on_websocket_connected() -> void:
	print("[Login] WebSocket connected, sending credentials...")
	var username = username_field.text.strip_edges()
	var password = password_field.text
	WebSocket.authenticate(username, password)

func _on_websocket_authenticated(success: bool, player_data: Dictionary) -> void:
	if success:
		print("[Login] Authentication successful!")
		print("[Login] Player data: ", player_data)
		# Transition to location screen
		get_tree().change_scene_to_file("res://location_screen.tscn")
	else:
		var error_msg = player_data.get("error", "Authentication failed")
		print("[Login] Authentication failed: ", error_msg)
		show_error("⚠ " + error_msg)

func _on_websocket_error(message: String) -> void:
	print("[Login] WebSocket error: ", message)
	show_error("⚠ " + message)

func _on_websocket_disconnected() -> void:
	print("[Login] WebSocket disconnected")
	if _connecting:
		show_error("⚠ Connection lost")
