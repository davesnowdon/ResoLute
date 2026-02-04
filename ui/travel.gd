extends Node2D

## Travel screen - shows player walking between locations during exercise
## Player position is controlled by exercise progress (0-100%)

# Signals
signal exercise_completed
signal travel_cancelled

# Node references
@onready var player: CharacterBody2D = $Player

# UI references - using unique names set in scene
@onready var origin_label: Label = %OriginLabel
@onready var destination_label: Label = %DestinationLabel
@onready var exercise_name_label: Label = %ExerciseNameLabel
@onready var time_label: Label = %TimeLabel
@onready var progress_bar: ProgressBar = %ProgressBar
@onready var instruction_label: Label = %InstructionLabel

# Travel path configuration
var start_position: Vector2 = Vector2(12, 90)  # Left side of screen
var end_position: Vector2 = Vector2(280, 90)   # Right side of screen

# Exercise data
var origin_name: String = "Unknown"
var destination_name: String = "Unknown"
var exercise_name: String = "Practice"
var duration_seconds: float = 60.0
var elapsed_seconds: float = 0.0
var progress_percent: float = 0.0
var is_complete: bool = false

# State
var is_traveling: bool = false
var poll_timer: float = 0.0
const POLL_INTERVAL: float = 1.0  # Poll server every second


func _ready() -> void:
	# Connect to WebSocket signals
	WebSocket.message_received.connect(_on_message_received)
	
	# Set initial player position
	player.position = start_position
	
	# Update player animation to face right (walking direction)
	_set_player_walking(false)


func _exit_tree() -> void:
	# Disconnect signals when leaving scene
	if WebSocket.message_received.is_connected(_on_message_received):
		WebSocket.message_received.disconnect(_on_message_received)


func _process(delta: float) -> void:
	if not is_traveling:
		return
	
	# Poll server for exercise status
	poll_timer += delta
	if poll_timer >= POLL_INTERVAL:
		poll_timer = 0.0
		WebSocket.check_exercise()
	
	# Update player position based on progress
	_update_player_position()
	
	# Update time display locally (for smoother countdown)
	elapsed_seconds += delta
	var remaining = max(0, duration_seconds - elapsed_seconds)
	_update_time_display(remaining)


func start_travel(data: Dictionary) -> void:
	"""Start the travel sequence with exercise data from server."""
	print("[Travel] Starting travel with data: ", data)
	
	# Extract exercise session data
	var session = data.get("session", data)  # Handle both formats
	exercise_name = session.get("exercise_name", "Practice")
	duration_seconds = session.get("duration_seconds", 60.0)
	elapsed_seconds = session.get("elapsed_seconds", 0.0)
	progress_percent = session.get("progress_percent", 0.0)
	is_complete = session.get("is_complete", false)
	
	# Extract destination data if available
	#var dest = data.get("destination", {})
	#destination_name = dest.get("name", "Unknown Destination")
	
	# Update UI
	_update_ui()
	
	# Start traveling
	is_traveling = true
	poll_timer = 0.0
	
	# Set player to walking animation
	_set_player_walking(true)


func _update_player_position() -> void:
	"""Update player position based on progress percentage."""
	var t = progress_percent / 100.0
	player.position = start_position.lerp(end_position, t)
	

func _update_ui() -> void:
	"""Update all UI elements."""
	if origin_label:
		origin_label.text = origin_name
	if destination_label:
		destination_label.text = destination_name
	if exercise_name_label:
		exercise_name_label.text = exercise_name
	if progress_bar:
		progress_bar.value = progress_percent
	if instruction_label:
		instruction_label.text = "Complete the exercise to continue your journey!"
	
	var remaining = max(0, duration_seconds - elapsed_seconds)
	_update_time_display(remaining)


func _update_time_display(remaining_seconds: float) -> void:
	"""Update the time remaining display."""
	if time_label:
		var minutes = int(remaining_seconds) / 60
		var seconds = int(remaining_seconds) % 60
		time_label.text = "%d:%02d" % [minutes, seconds]


func _set_player_walking(walking: bool) -> void:
	"""Set player animation state."""
	if player and player.has_node("AnimationTree"):
		var anim_tree = player.get_node("AnimationTree")
		var state_machine = anim_tree.get("parameters/playback")
		
		# Set blend position to face right
		anim_tree.set("parameters/idle/blend_position", Vector2(1, 0))
		anim_tree.set("parameters/walk/blend_position", Vector2(1, 0))
		
		# Set state
		if walking:
			state_machine.travel("walk")
		else:
			state_machine.travel("idle")


func _on_message_received(msg_type: String, content: String, data: Dictionary) -> void:
	"""Handle messages from server."""
	if not is_traveling:
		return
	
	match msg_type:
		"exercise_state":
			# Update exercise progress
			progress_percent = data.get("progress_percent", progress_percent)
			elapsed_seconds = data.get("elapsed_seconds", elapsed_seconds)
			is_complete = data.get("is_complete", false)
			
			_update_ui()
			_update_player_position()
			
			# Check if exercise is complete
			if is_complete:
				_on_exercise_complete()
		
		"exercise_complete":
			# Exercise completed and rewards received
			is_traveling = false
			_set_player_walking(false)
			exercise_completed.emit()
			# Return to location screen
			_return_to_location()
		
		"error":
			print("[Travel] Error: ", content)


func _on_exercise_complete() -> void:
	"""Called when exercise timer completes."""
	print("[Travel] Exercise complete! Requesting completion...")
	
	# Update UI to show completion
	if instruction_label:
		instruction_label.text = "Exercise complete! Arriving at destination..."
	
	# Move player to end position
	progress_percent = 100.0
	_update_player_position()
	
	# Stop walking animation
	_set_player_walking(false)
	
	# Request completion from server
	WebSocket.complete_exercise()


func _return_to_location() -> void:
	"""Return to the location screen after travel completes."""
	print("[Travel] Returning to location screen")
	# Small delay to show completion message
	await get_tree().create_timer(1.5).timeout
	#get_tree().change_scene_to_file("res://location_screen.tscn")
	var location_scene = load("res://location_screen.tscn").instantiate()
	get_tree().root.add_child(location_scene)
	queue_free()  # Remove this screen

func set_origin(name: String) -> void:
	"""Set the origin location name."""
	print("[Travel] set origin: ", name)
	origin_name = name
	if origin_label:
		origin_label.text = origin_name


func set_destination(name: String) -> void:
	"""Set the destination location name."""
	print("[Travel] set destination: ", name)
	destination_name = name
	if destination_label:
		destination_label.text = destination_name


func cancel_travel() -> void:
	"""Cancel the current travel."""
	is_traveling = false
	_set_player_walking(false)
	travel_cancelled.emit()
