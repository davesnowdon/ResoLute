extends CharacterBody2D

@export var move_speed: float = 100
@export var starting_direction: Vector2 = Vector2(0, 0.5)

# parameters/idle/blend_position
# parameters/walk/blend_position

@onready var animation_tree = $AnimationTree

func _ready() -> void:
	animation_tree.set("parameters/idle/blend_position", starting_direction)

func _physics_process(_delta: float) -> void:
	var input_direction = Vector2(
		Input.get_action_strength("right") - Input.get_action_strength("left"),
		Input.get_action_strength("down") - Input.get_action_strength("up")
	)

	velocity = input_direction * move_speed

	move_and_slide()
