import hashlib
import random
import json
import typing

from dys import _chain, SCRIPT_ADDRESS, CALLER, BLOCK_INFO


BLOCK_HEIGHT = BLOCK_INFO.height

TEXTAREA = typing.Annotated[str, '{"format": "textarea"}']


# game states
PRECOMMIT = "precommit"
FIRE = "fire"
REVEAL_POSITION = "reveal_position"
REVEAL_SHIPS = "reveal_ships"
OVER = "over"

COORD = list[int]  # [x, y, salt] salt is a random number


def get(index: str):
    result = _chain("dyson/QueryStorage", index=SCRIPT_ADDRESS + "/" + index)["result"]
    if not result:
        return None
    return json.loads(result.get("storage", {}).get("data"))


def _set(index: str, data):
    return _chain(
        "dyson/sendMsgUpdateStorage",
        creator=SCRIPT_ADDRESS,
        index=SCRIPT_ADDRESS + "/" + index,
        data=json.dumps(data),
        force=True,
    )


def _transition_state(game_state, player_index, current_state, new_state):

    assert (
        game_state["state"] == current_state
    ), f"Invalid move: { game_state['state'] } != {current_state}"

    assert (
        game_state["round_start_timer"][player_index] is not None
    ), f"You have already done this action: {current_state}"

    delta = BLOCK_HEIGHT - game_state["round_start_timer"][player_index]
    game_state["game_time"][player_index] += delta

    game_state["round_start_timer"][player_index] = None

    if not any(game_state["round_start_timer"]):
        game_state["round_start_timer"] = [BLOCK_HEIGHT, BLOCK_HEIGHT]
        game_state["state"] = new_state


def create_game(
    player_a_address: str,
    player_b_address: str,
    board_size: int = 10,
    ship_sizes: list[int] = [5, 4, 3, 3, 2],
    max_block_time: int = 100,
):
    assert 2 <= board_size <= 10, "Board size must be between 2 and 10"
    if isinstance(ship_sizes, str):
        ship_sizes = json.loads(ship_sizes)
    assert (
        sum(ship_sizes) <= (board_size * board_size) // 2
    ), "Too many ships for the specified board size"
    assert max(ship_sizes) <= board_size, "A ship is too large for the board size"

    game_id = get("game_counter") or 0
    game_id += 1
    game_state = {
        "game_id": game_id,
        "players": [player_a_address, player_b_address],
        "state": PRECOMMIT,
        "max_block_time": max_block_time,
        "board_size": board_size,
        "ship_sizes": ship_sizes,
        # sha256 hash of ships
        "ship_precommits": [[], []],  # player 0 or 1
        # x,y positions
        "revealed_positions": [
            {},
            {},  # player 0 or 1
        ],
        "guessed_positions": [[], []],  # positions guessed by each player
        "hit_counter": [0, 0],  # player 0 or 1
        "forfeited_players": [],  # player indices who forfeited
        "round_start_timer": [
            BLOCK_HEIGHT,
            BLOCK_HEIGHT,
        ],  # Track if a player has taken an action this round
        "game_time": [max_block_time, max_block_time],
    }
    _set("games/" + str(game_id), game_state)
    _set("game_counter", game_id)
    return game_id


def set_ship_commits(game_id: int, ship_commits: list[str]):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    player_index = game_state["players"].index(CALLER)
    _transition_state(game_state, player_index, PRECOMMIT, FIRE)
    game_state["ship_precommits"][player_index] = ship_commits
    _set("games/" + str(game_id), game_state)


def generate_ship_commit(ship_x_y_salts: list[COORD]) -> str:
    return hashlib.sha256(json.dumps(ship_x_y_salts).encode()).hexdigest()


def fire_at_position(game_id: int, x: int, y: int):
    game_state = get("games/" + str(game_id))

    assert game_state, "Game does not exist"
    player_index = game_state["players"].index(CALLER)

    _transition_state(game_state, player_index, FIRE, REVEAL_POSITION)

    key = f"{x},{y}"
    if key in game_state["revealed_positions"][1 - player_index]:
        raise Exception(f"Already fired at: {key}")

    game_state["guessed_positions"][player_index] = [x, y]
    print(f"{CALLER} fired at {x}, {y}")

    # Check if the game is over and ended in a tie or single winner
    if any(
        [
            game_state["hit_counter"][player_index] == sum(game_state["ship_sizes"])
            for player_index in [0, 1]
        ]
    ):
        game_state["state"] = REVEAL_SHIPS  # reveal ship to validate them

    _set("games/" + str(game_id), game_state)


MISS = ""


def reveal_position(game_id: int, x: int, y: int, miss_or_salt: str):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    assert game_state["state"] == REVEAL_POSITION, "Invalid game state"

    player_index = game_state["players"].index(CALLER)
    _transition_state(game_state, player_index, REVEAL_POSITION, FIRE)

    assert [x, y] == game_state["guessed_positions"][
        1 - player_index
    ], f"Invalid position to reveal: {x}, {y} != {game_state['guessed_positions'][1 - player_index]}"

    key = f"{x},{y}"
    if key in game_state["revealed_positions"][player_index]:
        print("already revealed")
    elif miss_or_salt != MISS:
        print(f"{CALLER} was HIT at {x}, {y}")
        game_state["hit_counter"][1 - player_index] += 1
    else:
        print(f"{CALLER} was MISSED at {x}, {y}")
    game_state["revealed_positions"][player_index][key] = miss_or_salt

    # Check if both players have revealed
    if game_state["state"] == FIRE:
        game_state["guessed_positions"] = [[], []]

        # Check if the game is over and ended in a tie or single winner
        if any(
            [
                game_state["hit_counter"][player_index] == sum(game_state["ship_sizes"])
                for player_index in [0, 1]
            ]
        ):
            game_state["state"] = REVEAL_SHIPS

    _set("games/" + str(game_id), game_state)


def reveal_ships(game_id: int, ship_positions: list[list[COORD]]):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    player_index = game_state["players"].index(CALLER)
    _transition_state(game_state, player_index, REVEAL_SHIPS, OVER)

    position_commits = set()
    seen_ship_commits = set()

    ship_size_counter = []
    for ship in ship_positions:
        commit = generate_ship_commit(ship)
        if commit not in game_state["ship_precommits"][player_index]:
            raise Exception("Ship was not in ship_commits: {ship}")
        seen_ship_commits |= {commit}
        ship_size_counter.append(len(ship))
        x_first, y_first, _ = ship[0]
        horizontal = True
        vertical = True
        contiguous_x = True
        contiguous_y = True
        for i, (x, y, salt) in enumerate(ship):
            key = f"{x},{y}"
            if key in game_state["revealed_positions"][player_index]:
                assert (
                    salt == game_state["revealed_positions"][player_index][key]
                ), f"Invalid salt at {x}, {y}: {salt} != {game_state['revealed_positions'][player_index][key]}"
            # Check orientation
            if x != x_first:
                horizontal = False
            if y != y_first:
                vertical = False
            # Check contiguity
            if horizontal and y != y_first + i:
                contiguous_y = False
            if vertical and x != x_first + i:
                contiguous_x = False
            # Check within bounds
            if (
                x < 0
                or x >= game_state["board_size"]
                or y < 0
                or y >= game_state["board_size"]
            ):
                raise ValueError(f"Ship {ship} out of bounds")
            # Check for overlaps

            # Mark cell as occupied
            positions_key = f"{x},{y}"
            if positions_key in position_commits:
                raise ValueError(f"Overlapping ship at coordinates ({positions_key})")

            position_commits |= {positions_key}

        if not (horizontal and contiguous_y) and not (vertical and contiguous_x):
            raise ValueError(f"Invalid orientation or non-contiguous ship {ship}")

    # Validate the correct number of ships of each size
    if json.dumps(game_state["ship_sizes"]) != json.dumps(ship_size_counter):
        raise ValueError(f"Incorrect number or order of ships")

    commit_diff = seen_ship_commits ^ set(game_state["ship_precommits"][player_index])
    if commit_diff:
        raise ValueError(f"Incorrect commits: {commit_diff}")

    _set("games/" + str(game_id), game_state)


def game_over(game_id):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"

    # if either player is out of time, set game state state to OVER
    forfeit = []
    for player_index in [0, 1]:
        delta = game_state["round_start_timer"][player_index] - BLOCK_HEIGHT
        game_state["game_time"][player_index] += delta
        game_state["round_start_timer"][player_index] = None
        if game_state["game_time"][player_index] <= 0:
            game_state["state"] = OVER
            forfeit.append(player_index)

    assert game_state["state"] == OVER, "Game is not over"

    if len(forfeit) == 2:
        game_state["winner"] = "tie"
    elif len(forfeit) == 1:
        game_state["winner"] = game_state["players"][1 - forfeit[0]]
    elif game_state["hit_counter"][0] == game_state["hit_counter"][1]:
        game_state["winner"] = "tie"  # Indicate a tie
    else:
        winner_index = game_state["hit_counter"].index(max(game_state["hit_counter"]))
        game_state["winner"] = game_state["players"][winner_index]

    _set("games/" + str(game_id), game_state)

