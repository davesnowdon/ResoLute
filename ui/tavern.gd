extends Node2D

# UI References (will be created in scene)
@onready var ui_layer: CanvasLayer = $UILayer
@onready var perform_button: Button = $UILayer/PerformPanel/PerformButton
@onready var leave_button: Button = $UILayer/PerformPanel/LeaveButton
@onready var stop_button: Button = $UILayer/PerformPanel/StopButton
@onready var timer_label: Label = $UILayer/PerformPanel/TimerLabel
@onready var status_label: Label = $UILayer/PerformPanel/StatusLabel
@onready var rewards_panel: Panel = $UILayer/RewardsPanel
@onready var rewards_label: Label = $UILayer/RewardsPanel/RewardsLabel
@onready var rewards_close_button: Button = $UILayer/RewardsPanel/CloseButton

# Performance state
var is_performing: bool = false
var performance_time: float = 0.0

func _ready() -> void:
	# Connect button signals
	perform_button.pressed.connect(_on_perform_pressed)
	leave_button.pressed.connect(_on_leave_pressed)
	stop_button.pressed.connect(_on_stop_pressed)
	rewards_close_button.pressed.connect(_on_rewards_close_pressed)
	
	# Connect WebSocket signals
	WebSocket.message_received.connect(_on_message_received)
	WebSocket.error.connect(_on_websocket_error)
	
	# Initial UI state
	_set_idle_state()
	rewards_panel.visible = false

func _exit_tree() -> void:
	# Disconnect signals when leaving scene
	if WebSocket.message_received.is_connected(_on_message_received):
		WebSocket.message_received.disconnect(_on_message_received)
	if WebSocket.error.is_connected(_on_websocket_error):
		WebSocket.error.disconnect(_on_websocket_error)

func _process(delta: float) -> void:
	if is_performing:
		performance_time += delta
		_update_timer_display()

func _update_timer_display() -> void:
	var minutes = int(performance_time) / 60
	var seconds = int(performance_time) % 60
	timer_label.text = "%02d:%02d" % [minutes, seconds]

func _set_idle_state() -> void:
	is_performing = false
	performance_time = 0.0
	perform_button.visible = true
	leave_button.visible = true
	stop_button.visible = false
	timer_label.text = "00:00"
	status_label.text = "Ready to perform"

func _set_performing_state() -> void:
	is_performing = true
	performance_time = 0.0
	perform_button.visible = false
	leave_button.visible = false
	stop_button.visible = true
	status_label.text = "Performing..."

func _on_perform_pressed() -> void:
	print("[Tavern] Starting performance...")
	_set_performing_state()

func _on_stop_pressed() -> void:
	print("[Tavern] Stopping performance after ", performance_time, " seconds")
	is_performing = false
	status_label.text = "Finishing performance..."
	stop_button.disabled = true
	
	# Calculate performance score based on time (longer = better, up to a point)
	# Min 5 seconds for any reward, optimal around 30 seconds
	var score = clamp(performance_time / 30.0, 0.1, 1.5)
	
	# Call backend to record performance
	WebSocket.perform(score)

func _on_leave_pressed() -> void:
	print("[Tavern] Leaving tavern...")
	get_tree().change_scene_to_file("res://location_screen.tscn")

func _on_rewards_close_pressed() -> void:
	rewards_panel.visible = false
	_set_idle_state()

func _on_message_received(msg_type: String, content: String, data: Dictionary) -> void:
	print("[Tavern] Received message: ", msg_type)
	
	match msg_type:
		"performance_result":
			_show_rewards(data)
		"error":
			print("[Tavern] Error: ", content)
			status_label.text = "Error: " + content
			_set_idle_state()

func _show_rewards(data: Dictionary) -> void:
	var rewards = data.get("rewards", {})
	var gold = rewards.get("gold_gained", 0)
	var reputation = rewards.get("reputation_gained", 0)
	
	rewards_label.text = "Performance Complete!\n\n"
	rewards_label.text += "Gold: +" + str(gold) + "\n"
	rewards_label.text += "Reputation: +" + str(reputation)
	
	rewards_panel.visible = true
	stop_button.disabled = false
	stop_button.visible = false

func _on_websocket_error(message: String) -> void:
	print("[Tavern] WebSocket error: ", message)
	status_label.text = "Connection error"
	_set_idle_state()
