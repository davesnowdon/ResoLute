extends Node

## WebSocket client singleton for communicating with the ResoLute backend.
## Handles connection, authentication, and message routing.

# Signals
signal connected
signal disconnected
signal authenticated(success: bool, player_data: Dictionary)
signal message_received(msg_type: String, content: String, data: Dictionary)
signal error(message: String)

# Connection state
enum State { DISCONNECTED, CONNECTING, CONNECTED, AUTHENTICATING, AUTHENTICATED }
var state: State = State.DISCONNECTED

# WebSocket
var _socket: WebSocketPeer = WebSocketPeer.new()
var _server_url: String = ""

# Player data (populated after authentication)
var player_id: String = ""
var player_data: Dictionary = {}

# Configuration
const DEFAULT_SERVER_URL = "ws://localhost:8000/ws"
const RECONNECT_DELAY = 3.0

func _ready() -> void:
	# Process WebSocket in _process
	set_process(true)

func _process(_delta: float) -> void:
	if state == State.DISCONNECTED:
		return

	_socket.poll()

	var socket_state = _socket.get_ready_state()

	match socket_state:
		WebSocketPeer.STATE_OPEN:
			# Read all available messages
			while _socket.get_available_packet_count() > 0:
				var packet = _socket.get_packet()
				var text = packet.get_string_from_utf8()
				_handle_message(text)

		WebSocketPeer.STATE_CLOSING:
			pass  # Wait for close

		WebSocketPeer.STATE_CLOSED:
			var code = _socket.get_close_code()
			var reason = _socket.get_close_reason()
			print("[WebSocket] Connection closed: ", code, " - ", reason)
			_on_disconnected()

## Connect to the WebSocket server
func connect_to_server(url: String = DEFAULT_SERVER_URL) -> Error:
	if state != State.DISCONNECTED:
		push_warning("Already connected or connecting")
		return ERR_ALREADY_IN_USE

	_server_url = url
	state = State.CONNECTING

	print("[WebSocket] Connecting to: ", url)
	var err = _socket.connect_to_url(url)
	if err != OK:
		print("[WebSocket] Connection failed: ", err)
		state = State.DISCONNECTED
		error.emit("Failed to connect to server")
		return err

	return OK

## Authenticate with username and password
func authenticate(username: String, password: String) -> void:
	if state != State.CONNECTED:
		push_warning("Cannot authenticate: not connected")
		error.emit("Not connected to server")
		return

	state = State.AUTHENTICATING

	var msg = {
		"type": "authenticate",
		"content": "",
		"data": {
			"username": username,
			"password": password
		}
	}

	_send_json(msg)

## Send a message to the server (must be authenticated)
func send_message(msg_type: String, content: String = "", data: Dictionary = {}) -> void:
	if state != State.AUTHENTICATED:
		push_warning("Cannot send message: not authenticated")
		error.emit("Not authenticated")
		return

	var msg = {
		"type": msg_type,
		"content": content,
		"data": data
	}

	_send_json(msg)

## Request location state
func request_location() -> void:
	send_message("location")

## Request player stats
func request_player() -> void:
	send_message("player")

## Request world state
func request_world() -> void:
	send_message("world")

## Request inventory
func request_inventory() -> void:
	send_message("inventory")

## Start travel to a destination
func travel_to(destination: String) -> void:
	send_message("travel", destination)

## Check exercise status
func check_exercise() -> void:
	send_message("exercise", "check")

## Complete current exercise
func complete_exercise() -> void:
	send_message("exercise", "complete")

## Collect a song segment
func collect_segment(segment_id: int) -> void:
	send_message("collect", "", {"segment_id": segment_id})

## Perform at tavern
func perform() -> void:
	send_message("perform")

## Chat with mentor
func chat(message: String) -> void:
	send_message("chat", message)

## Disconnect from server
func disconnect_from_server() -> void:
	if state == State.DISCONNECTED:
		return

	_socket.close(1000, "Client disconnect")
	_on_disconnected()

## Check if connected and authenticated
func is_authenticated() -> bool:
	return state == State.AUTHENTICATED

## Check if connected (may not be authenticated yet)
func is_socket_connected() -> bool:
	return state in [State.CONNECTED, State.AUTHENTICATING, State.AUTHENTICATED]

# Internal: Send JSON message
func _send_json(data: Dictionary) -> void:
	var json_str = JSON.stringify(data)
	print("[WebSocket] Sending: ", json_str.substr(0, 100))
	_socket.send_text(json_str)

# Internal: Handle incoming message
func _handle_message(text: String) -> void:
	print("[WebSocket] Received: ", text.substr(0, 200))

	var json = JSON.new()
	var parse_result = json.parse(text)
	if parse_result != OK:
		push_error("Failed to parse server message: ", json.get_error_message())
		return

	var data = json.get_data()
	if not data is Dictionary:
		push_error("Server message is not a dictionary")
		return

	var msg_type = data.get("type", "")
	var content = data.get("content", data.get("message", ""))
	var msg_data = data.get("data", {})

	# Handle special message types
	match msg_type:
		"connected":
			# Initial connection confirmed, ready for auth
			print("[WebSocket] Connected to server")
			state = State.CONNECTED
			connected.emit()

		"auth_success":
			# Authentication successful
			player_id = msg_data.get("player_id", "")
			player_data = msg_data.get("player", {})
			state = State.AUTHENTICATED
			print("[WebSocket] Authenticated as: ", player_id)
			authenticated.emit(true, player_data)

		"auth_failed":
			# Authentication failed
			state = State.CONNECTED  # Back to connected, can retry
			print("[WebSocket] Authentication failed: ", content)
			authenticated.emit(false, {"error": content})

		"error":
			# Error message
			print("[WebSocket] Error: ", content)
			error.emit(content)
			message_received.emit(msg_type, content, msg_data)

		_:
			# All other messages
			message_received.emit(msg_type, content, msg_data)

# Internal: Handle disconnection
func _on_disconnected() -> void:
	var was_authenticated = state == State.AUTHENTICATED
	state = State.DISCONNECTED
	player_id = ""
	player_data = {}

	# Create a fresh socket for potential reconnection
	_socket = WebSocketPeer.new()

	disconnected.emit()
