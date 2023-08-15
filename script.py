import hashlib
import json
import typing

from dys import _chain, SCRIPT_ADDRESS, CALLER

TEXTAREA = typing.Annotated[str, '{"format": "textarea"}']


def get(index: str):
    result = _chain("dyson/QueryStorage", index=SCRIPT_ADDRESS + index)["result"]
    return json.loads(result["storage"]["data"])


def _set(index: str, data):
    return _chain(
        "dyson/sendMsgUpdateStorage",
        creator=SCRIPT_ADDRESS,
        index=SCRIPT_ADDRESS + index,
        data=json.dumps(data),
        force=True,
    )


def create_game(
    player_a_address: str,
    player_b_address: str,
    board_size: int = 10,
    ships: TEXTAREA = [5, 4, 3, 2],
):
    assert 5 <= board_size <= 20, "Board size must be between 5 and 20"
    assert (
        sum(ships) <= (board_size * board_size) // 2
    ), "Too many ships for the specified board size"
    if isinstance(ships, str):
        ships = json.loads(ships)

    game_id = get("/game_counter") or 0
    game_id += 1
    game_state = {
        "players": [player_a_address, player_b_address],
        "current_player": player_a_address,
        "status": "commit",
        "boards": [None, None],
        "ships": [None, None],  # Initialize ships with None
        "board_size": board_size,
        "ship_lengths": ships,
    }
    _set("/games/" + str(game_id), game_state)
    _set("/game_counter", game_id)
    return game_id


def commit_ships(game_id: int, board_commits: TEXTAREA, ship_commits: TEXTAREA):
    board_commits = board_commits.split()
    ship_commits = ship_commits.split()
    game_state = get("/games/" + str(game_id))
    assert game_state["status"] == "commit", "Game is not in commit phase"
    assert CALLER in game_state["players"], "not allowed"
    player_index = game_state["players"].index(CALLER)
    assert (
        len(board_commits) == game_state["board_size"] ** 2
    ), "Invalid number of board commits"
    assert len(ship_commits) == len(
        game_state["ship_lengths"]
    ), "Invalid number of ship commits"
    # Populate the board with the commit hashes
    for i in range(game_state["board_size"]):
        for j in range(game_state["board_size"]):
            game_state["boards"][player_index][i][j] = board_commits[
                i * game_state["board_size"] + j
            ]
    game_state["ships"][player_index] = ship_commits
    _set("/games/" + str(game_id), game_state)


def guess(game_id: int, x: int, y: int):
    game_state = get("/games/" + str(game_id))
    assert game_state["status"] == "play", "Game is not in play phase"
    assert CALLER == game_state["current_player"], "not allowed"
    player_index = game_state["players"].index(CALLER)
    game_state["boards"][player_index][x][y] = 1  # Marking the guess
    _set("/games/" + str(game_id), game_state)


def reveal(game_id: int, x: int, y: int, hit_or_not: int, salt: str):
    game_state = get("/games/" + str(game_id))
    assert game_state["status"] == "play", "Game is not in play phase"
    other_player_index = 1 - game_state["players"].index(game_state["current_player"])
    assert CALLER == game_state["players"][other_player_index], "not allowed"
    commit = game_state["commits"][other_player_index][x * game_state["board_size"] + y]
    verify_hash = hashlib.sha256(
        (str(x * game_state["board_size"] + y) + str(hit_or_not) + salt).encode()
    ).hexdigest()
    assert commit == verify_hash, "Invalid reveal"
    assert hit_or_not in [0, 1], "hit_or_not must be 0 or 1"
    game_state["boards"][other_player_index][x][y] = (
        x,
        y,
        hit_or_not,
        salt,
    )  # Updating the board with the reveal
    # Check if the ship is sunk
    # Logic to determine if the ship is sunk based on the updated game state
    # ...
    _set("/games/" + str(game_id), game_state)


def generate_commits(board: TEXTAREA, salts: str, ships: TEXTAREA):
    # Parse the board and salts if provided as JSON strings
    if isinstance(board, str):
        board = json.loads(board)
    if isinstance(salts, str):
        salts = json.loads(salts)
    if isinstance(ships, str):
        ships = json.loads(ships)
    size = len(board)
    if not all([len(row) == size for row in board]) or len(salts) != size ** 2:
        raise ValueError("Invalid board or salts size")

    board_commits = []
    for i, row in enumerate(board):
        for j, position in enumerate(row):
            salt = salts[i * +j]
            commit_hash = hashlib.sha256(
                (str(i * size + j) + str(position) + salt).encode()
            ).hexdigest()
            board_commits.append(commit_hash)

    ship_commits = []
    for ship in ships:
        ship_commit_data = [
            str(x * size + y) + str(board[x][y]) + salts[x * size + y] for x, y in ship
        ]
        ship_commit_hash = hashlib.sha256(
            ",".join(ship_commit_data).encode()
        ).hexdigest()
        ship_commits.append(ship_commit_hash)

    return board_commits, ship_commits

