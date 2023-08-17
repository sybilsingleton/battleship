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



def validate_ship_positions(board_size: int, ship_positions: list[list[list[int, int]]], ship_sizes: list[int], seed:int) -> List[List[int]]:    
    """
    ...: board_size = 10
    ...: ship_sizes = [5, 4, 3, 3, 2]
    ...: 
    ...: ship_positions_valid = [
    ...:     [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)],
    ...:     [(1, 0), (1, 1), (1, 2), (1, 3)],
    ...:     [(2, 0), (2, 1), (2, 2)],
    ...:     [(3, 0), (3, 1), (3, 2)],
    ...:     [(4, 0), (4, 1)]
    ...: ]
    ...: 
    ...: # Example usage
    ...: try:
    ...:     positions = validate_ship_positions(board_size, ship_positions_valid, ship_sizes,1)
    ...:     print("Ship positions are valid!")
    ...:     for p in positions:
    ...:         print(p)
    ...: except ValueError as e:
    ...:     print(f"Validation failed: {e}")
    ...: 
    """
    # Initialize an empty grid for validation
    validation_grid = []
    for _ in '1' * board_size:
        row = []
        for _ in '1' * board_size:
            row.append(0)
        validation_grid.append(row)
    
    ship_size_counter = {size: 0 for size in ship_sizes}

    for ship in ship_positions:
        ship_length = len(ship)
        if ship_length not in ship_sizes:
            raise ValueError(f"Invalid ship length: {ship_length}")

        ship_size_counter[ship_length] += 1
        if ship_size_counter[ship_length] > ship_sizes.count(ship_length):
            raise ValueError(f"Too many ships of length {ship_length}")

        x_first, y_first = ship[0]
        horizontal = True
        vertical = True
        contiguous_x = True
        contiguous_y = True
        for i, (x, y) in enumerate(ship):
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
            if validation_grid[x][y] != 0:
                raise ValueError(f"Overlapping ship at coordinates ({x}, {y})")
            # Mark cell as occupied
            validation_grid[x][y] = 1

        if not (horizontal and contiguous_y) and not (vertical and contiguous_x):
            raise ValueError(f"Non-contiguous ship {ship}")

        if not (horizontal or vertical) or (horizontal and vertical):
            raise ValueError(f"Invalid orientation for ship {ship}")

    # Validate the correct number of ships of each size
    for size, count in ship_size_counter.items():
        if count != ship_sizes.count(size):
            raise ValueError(f"Incorrect number of ships of size {size}")

    return validation_grid


