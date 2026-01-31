extends CharacterBody2D

@export var move_speed: float = 100
@export var starting_direction: Vector2 = Vector2(0, 0.5)

@onready var sprite: Sprite2D = $Sprite2D
@onready var animation_tree: AnimationTree = $AnimationTree
@onready var state_machine: AnimationNodeStateMachinePlayback = animation_tree.get("parameters/playback")

var current_state: StringName = &"idle"

func _ready() -> void:
	update_animation_parameters(starting_direction)

func _physics_process(_delta: float) -> void:
	var input_direction = Vector2(
		Input.get_action_strength("right") - Input.get_action_strength("left"),
		Input.get_action_strength("down") - Input.get_action_strength("up")
	)
	
	# Flip sprite for left movement (sheet only has right-facing)
	if input_direction.x != 0:
		sprite.flip_h = input_direction.x < 0
	
	update_animation_parameters(input_direction)
	velocity = input_direction.normalized() * move_speed
	pick_new_state()
	move_and_slide()

func update_animation_parameters(move_input : Vector2) -> void:
	if (move_input != Vector2.ZERO):
		animation_tree.set("parameters/idle/blend_position", move_input)
		animation_tree.set("parameters/walk/blend_position", move_input)

func pick_new_state() -> void:
	var new_state: StringName = &"walk" if velocity != Vector2.ZERO else &"idle"
	if new_state != current_state:
		current_state = new_state
		state_machine.travel(current_state)
