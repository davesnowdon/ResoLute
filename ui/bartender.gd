extends CharacterBody2D

enum CHARACTER_STATE {IDLE, WALK}

@export var move_speed: float = 30
@export var idle_time: float = 5
@export var walk_time: float = 2

@onready var sprite: Sprite2D = $Sprite2D
@onready var animation_tree: AnimationTree = $AnimationTree
@onready var state_machine: AnimationNodeStateMachinePlayback = animation_tree.get("parameters/playback")
@onready var timer: Timer = $Timer

var move_direction: Vector2 = Vector2.ZERO
var current_state: CHARACTER_STATE = CHARACTER_STATE.IDLE

func _ready() -> void:
	pick_new_state()

func _physics_process(delta: float) -> void:
	#print("Processing: ", name) 
	velocity = move_direction.normalized() * move_speed
	move_and_slide()

func select_new_direction() -> void:
	move_direction = Vector2(
		randi_range(-1,1),
		randi_range(-1, 1)
	)
	
	# Flip sprite for left movement (sheet only has right-facing)
	if move_direction.x != 0:
		sprite.flip_h = move_direction.x < 0
	
func pick_new_state() -> void:
	if (current_state == CHARACTER_STATE.IDLE):
		state_machine.travel("walk")
		current_state = CHARACTER_STATE.WALK
		select_new_direction()
		timer.start(walk_time)
	else:
		state_machine.travel("idle")
		current_state = CHARACTER_STATE.IDLE
		move_direction = Vector2.ZERO
		timer.start(idle_time)

func _on_timer_timeout() -> void:
	pick_new_state()
