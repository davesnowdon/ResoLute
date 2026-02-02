extends Control

@onready var username_field: LineEdit = $CenterContainer/VBoxContainer/FormContainer/UsernameField
@onready var password_field: LineEdit = $CenterContainer/VBoxContainer/FormContainer/PasswordField
@onready var error_label: Label = $CenterContainer/VBoxContainer/FormContainer/ErrorLabel
@onready var start_quest_button: Button = $CenterContainer/VBoxContainer/StartQuestButton
@onready var back_button: Button = $CenterContainer/VBoxContainer/BackButton

func _ready() -> void:
	# Connect button signals
	start_quest_button.pressed.connect(_on_start_quest_pressed)
	back_button.pressed.connect(_on_back_pressed)
	
	# Allow Enter key to submit from password field
	password_field.text_submitted.connect(_on_password_submitted)
	
	# Clear errors when user starts typing
	username_field.text_changed.connect(_on_input_changed)
	password_field.text_changed.connect(_on_input_changed)
	
	# Ensure error label is empty on start
	clear_error()

func show_error(message: String) -> void:
	error_label.text = message

func clear_error() -> void:
	error_label.text = ""

func _on_input_changed(_new_text: String) -> void:
	# Clear error when user modifies input
	clear_error()

func _on_start_quest_pressed() -> void:
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
	
	# TODO: Implement actual authentication
	print("Login attempt - Username: ", username)
	
	# For now, transition to the opening screen / main game
	get_tree().change_scene_to_file("res://location_screen.tscn")

func _on_back_pressed() -> void:
	# Return to landing screen
	get_tree().change_scene_to_file("res://landing_screen.tscn")

func _on_password_submitted(_text: String) -> void:
	# Trigger login when Enter is pressed in password field
	_on_start_quest_pressed()
