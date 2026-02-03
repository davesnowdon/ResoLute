extends Control

func _ready() -> void:
	# Connect the Enter button signal
	$CenterContainer/VBoxContainer/EnterButton.pressed.connect(_on_enter_pressed)

func _on_enter_pressed() -> void:
	# Transition to login screen
	get_tree().change_scene_to_file("res://login_screen.tscn")
