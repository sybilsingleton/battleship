import hashlib
import random
import json
import typing

from dys import _chain, SCRIPT_ADDRESS, CALLER

TEXTAREA = typing.Annotated[str, '{"format": "textarea"}']


# game states
PRECOMMIT = "precommit"
FIRE = "fire"
REVEAL = "reveal"
OVER = "over"

COORD = list[int]  # [x, y, salt]


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


def create_game(
    player_a_address: str,
    player_b_address: str,
    board_size: int = 10,
    ship_sizes: list[int] = [5, 4, 3, 3, 2],
):
    assert 2 <= board_size <= 10, "Board size must be between 5 and 20"
    if isinstance(ship_sizes, str):
        ship_sizes = json.loads(ship_sizes)
    assert (
        sum(ship_sizes) <= (board_size * board_size) // 2
    ), "Too many ships for the specified board size"
    assert max(ship_sizes) <= board_size, "A ship is too large for the board size"

    game_id = get("game_counter") or 0
    game_id += 1
    game_state = {
        "players": [player_a_address, player_b_address],
        "state": PRECOMMIT,
        "board_size": board_size,
        "ship_sizes": ship_sizes,
        # sha256 hash of ships
        "ship_precommits": [[], []],  # player 0 or 1
        # x,y positions
        "revealed_positions": [
            [],
            [],  # player 0 or 1
        ],
        "guessed_positions": [[], []],  # positions guessed by each player
        "hit_counter": [0, 0],  # player 0 or 1
    }
    _set("games/" + str(game_id), game_state)
    _set("game_counter", game_id)
    return game_id


def set_ship_commits(game_id: int, ship_commits: list[str]):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    assert game_state["state"] == PRECOMMIT, "Invalid game state"
    assert CALLER in game_state["players"], "You are not a player in this game"

    player_index = game_state["players"].index(CALLER)
    game_state["ship_precommits"][player_index] = ship_commits

    # Check if both players have committed their ships
    if all(game_state["ship_precommits"]):
        game_state["state"] = FIRE

    _set("games/" + str(game_id), game_state)


def generate_ship_commit(ship_x_y_salts: list[COORD]) -> str:
    return hashlib.sha256(json.dumps(ship_x_y_salts).encode()).hexdigest()


def fire_at_position(game_id: int, x: int, y: int):
    game_state = get("games/" + str(game_id))

    assert game_state, "Game does not exist"
    assert game_state["state"] == FIRE, "Invalid game state"
    assert CALLER in game_state["players"], "You are not a player in this game"

    player_index = game_state["players"].index(CALLER)
    game_state["guessed_positions"][player_index] = [x, y]
    print(f"{CALLER} fired at {x}, {y}")

    # Check if both players have fired
    if all(game_state["guessed_positions"]):
        game_state["state"] = REVEAL

    _set("games/" + str(game_id), game_state)


MISS = ""


def reveal_position(game_id: int, x: int, y: int, miss_or_salt: str):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    assert game_state["state"] == REVEAL, "Invalid game state"
    assert CALLER in game_state["players"], "You are not a player in this game"

    player_index = game_state["players"].index(CALLER)
    assert [x, y] == game_state["guessed_positions"][
        1 - player_index
    ], "Invalid position to reveal"

    game_state["revealed_positions"][player_index].append([x, y, miss_or_salt])

    if miss_or_salt != MISS:
        print(f"{CALLER} was HIT at {x}, {y}")
        game_state["hit_counter"][1 - player_index] += 1
    else:
        print(f"{CALLER} was MISSED at {x}, {y}")

    # Check if both players have revealed
    if len(game_state["revealed_positions"][0]) == len(
        game_state["revealed_positions"][1]
    ):
        game_state["state"] = FIRE
        game_state["guessed_positions"] = [[], []]

        # Check if the game is over and ended in a tie or single winner
        if all(
            [
                game_state["hit_counter"][player_index] == sum(game_state["ship_sizes"])
                for player_index in [0, 1]
            ]
        ):
            game_state["state"] = OVER
            game_state["winner"] = "tie"  # Indicate a tie
        elif any(
            [
                game_state["hit_counter"][player_index] == sum(game_state["ship_sizes"])
                for player_index in [0, 1]
            ]
        ):
            game_state["state"] = OVER
            game_state["winner"] = game_state["players"][
                game_state["hit_counter"].index(sum(game_state["ship_sizes"]))
            ]

    _set("games/" + str(game_id), game_state)


def reveal_ships(game_id: int, ship_positions: list[list[COORD]]):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    assert game_state["state"] == REVEAL, f"Invalid game state: {game_state['state']}"
    assert CALLER in game_state["players"], "You are not a player in this game"

    player_index = game_state["players"].index(CALLER)
    # Validate the revealed ship positions
    ship_commits, _ = validate_ship_positions(
        game_state["board_size"],
        game_state["ship_sizes"],
        game_state["ship_precommits"][player_index],
        ship_positions,
    )

    # Make sure the commits match
    assert (
        ship_commits == game_state["ship_precommits"][player_index]
    ), "Invalid ship reveal"

    game_state["revealed_positions"][player_index] = ship_positions

    # Check if the game is over
    if all(game_state["revealed_positions"]):
        check_game_over(game_id, game_state)

    _set("games/" + str(game_id), game_state)


def get_game_winner(game_id: int):
    game_state = get("games/" + str(game_id))
    assert game_state, "Game does not exist"
    assert game_state["state"] == OVER, "Game is not over"

    return game_state["winner"]


def delete_game(game_id: int):
    assert SCRIPT_ADDRESS == CALLER, "not allowed"
    return _chain(
        "dyson/sendMsgDeleteStorage",
        creator=SCRIPT_ADDRESS,
        index=SCRIPT_ADDRESS + "/" + "games/" + str(game_id),
    )


def validate_ship_positions(
    board_size: int,
    ship_sizes: list[int],
    ship_commits: list[str],
    ship_positions: list[list[COORD]],
):
    """
    Validate the ship positions for a given boardsize and return
    the precommit hashes for the positions and ships.
    """

    position_commits = {}

    ship_size_counter = []

    for ship in ship_positions:
        if generate_ship_commit(ship) not in ship_commits:
            raise Exception("Ship was not in ship_commits: {ship}")

        ship_size_counter.append(len(ship))
        x_first, y_first, _ = ship[0]
        horizontal = True
        vertical = True
        contiguous_x = True
        contiguous_y = True
        for i, (x, y, _) in enumerate(ship):
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
            if x < 0 or x >= board_size or y < 0 or y >= board_size:
                raise ValueError(f"Ship {ship} out of bounds")
            # Check for overlaps

            # Mark cell as occupied
            positions_key = f"{x},{y}"
            if positions_key in position_commits:
                raise ValueError(f"Overlapping ship at coordinates ({positions_key})")

            position_commits[positions_key] = 1

        if not (horizontal and contiguous_y) and not (vertical and contiguous_x):
            raise ValueError(f"Invalid orientation or non-contiguous ship {ship}")

    # Validate the correct number of ships of each size
    if json.dumps(ship_sizes) != json.dumps(ship_size_counter):
        raise ValueError(f"Incorrect number of ships")

    return ship_commits, position_commits

