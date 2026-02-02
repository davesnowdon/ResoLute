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

# Player data (will be populated from API later)
var player_data: Dictionary = {
	"name": "Brave Bard",
	"level": 1,
	"experience": 0,
	"experience_needed": 100,
	"songs_learned": 0
}

# Location data (will be populated from API later)
var location_data: Dictionary = {
	"name": "Willowdale Village",
	"description": "A peaceful village nestled in the rolling hills",
	"mentor_message": "Welcome, young bard! Your journey to master the ancient songs begins here. Seek out the villagers - they may have fragments of the lost melodies."
}

# Song fragments (will be populated from API later)
var song_fragments: Array = [
	{"name": "Verse of Courage", "pieces": 2, "total": 4},
	{"name": "Melody of Wisdom", "pieces": 0, "total": 4}
]

func _ready() -> void:
	# Connect button signals
	enter_tavern_btn.pressed.connect(_on_enter_tavern_pressed)
	travel_btn.pressed.connect(_on_travel_pressed)
	practice_btn.pressed.connect(_on_practice_pressed)
	logout_btn.pressed.connect(_on_logout_pressed)
	
	# Update UI with current data
	update_location_display()
	update_player_stats()
	update_fragment_list()

func update_location_display() -> void:
	location_name.text = "🏰 " + location_data.get("name", "Unknown Location")
	location_desc.text = location_data.get("description", "")
	mentor_message.text = location_data.get("mentor_message", "")

func update_player_stats() -> void:
	player_name_label.text = "🎭 Name: " + player_data.get("name", "Unknown")
	level_label.text = "⭐ Level: " + str(player_data.get("level", 1))
	var exp = player_data.get("experience", 0)
	var exp_needed = player_data.get("experience_needed", 100)
	experience_label.text = "✨ Experience: " + str(exp) + " / " + str(exp_needed)
	songs_learned_label.text = "🎵 Songs Learned: " + str(player_data.get("songs_learned", 0))

func update_fragment_list() -> void:
	# Clear existing fragments
	for child in fragment_list.get_children():
		child.queue_free()
	
	# Add fragment entries
	if song_fragments.is_empty():
		var empty_label = Label.new()
		empty_label.text = "(No song fragments yet)"
		empty_label.add_theme_color_override("font_color", Color(0.5, 0.5, 0.5))
		fragment_list.add_child(empty_label)
	else:
		for fragment in song_fragments:
			var label = Label.new()
			var pieces = fragment.get("pieces", 0)
			var total = fragment.get("total", 4)
			label.text = "📜 " + fragment.get("name", "Unknown") + " (" + str(pieces) + "/" + str(total) + " pieces)"
			label.add_theme_font_size_override("font_size", 13)
			fragment_list.add_child(label)

# API integration methods (to be implemented)
func load_location_data(location_id: String) -> void:
	# TODO: Fetch location data from API
	print("Loading location: ", location_id)
	update_location_display()

func load_player_data() -> void:
	# TODO: Fetch player data from API
	print("Loading player data")
	update_player_stats()
	update_fragment_list()

# Button handlers
func _on_enter_tavern_pressed() -> void:
	print("Entering tavern...")
	get_tree().change_scene_to_file("res://tavern.tscn")

func _on_travel_pressed() -> void:
	print("Opening travel map...")
	# TODO: Change to travel/map scene
	# get_tree().change_scene_to_file("res://travel.tscn")

func _on_practice_pressed() -> void:
	print("Opening practice mode...")
	# TODO: Implement practice mode

func _on_logout_pressed() -> void:
	print("Logging out...")
	get_tree().change_scene_to_file("res://landing_screen.tscn")
