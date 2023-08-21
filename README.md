Battleship - A strategy game on Dyson Protocol
==============================================

Overview
--------

Battleship is a decentralized implementation of the classic game on the Dyson Protocol. This document provides an overview of the game's states, gameplay mechanics, and functions to interact with the game.

Game States
-----------

1.  PRECOMMIT: Players commit their ships' positions using cryptographic hashes.
2.  FIRE: Players take turns firing at each other's grid, guessing the positions of the opponent's ships.
3.  REVEAL_POSITION: Players reveal whether a shot was a hit or miss.
4.  REVEAL_SHIPS: The players reveal their ships to validate the game.
5.  OVER: The game has ended, and a winner is declared.

Gameplay Mechanics
------------------

### Game Creation

-   `create_game(player_a_address, player_b_address, board_size=10, ship_sizes=[5, 4, 3, 3, 2], max_block_time=100)`: Initializes a new game with two players and optional board size, ship sizes, and maximum block time for each turn.

### Ship Placement

-   `set_ship_commits(game_id, ship_commits)`: Players commit their ships' positions using cryptographic hashes.
-   `generate_ship_commit(ship_x_y_salts)`: A utility function to generate the cryptographic commit for a ship.

### Firing and Revealing

-   `fire_at_position(game_id, x, y)`: A player fires at a specific position on the opponent's grid.
-   `reveal_position(game_id, x, y, miss_or_salt)`: The opponent reveals whether the shot was a hit or miss.

### Ending the Game

-   `reveal_ships(game_id, ship_positions)`: Players reveal their ships to validate the game and determine the winner.
-   `game_over(game_id)`: Handles the end of the game and declares the winner.

### Retrieving Game Data

-   `get(index)`: Retrieves a single storage at the index.

Commit-Reveal Scheme
--------------------

-   Players commit to their ships' positions with a hash of the coordinates and a random salt.
-   During the REVEAL_SHIPS phase, players reveal the actual coordinates and salts, and the game validates that they match the original commits.

Error Handling
--------------

-   The game includes checks for invalid moves, incorrect reveals, and other game violations.
-   Custom exceptions and assertions are used to ensure that the game progresses through the correct states.

Game Constraints
----------------

-   Board size must be between 2 and 10.
-   The total number of ship cells must not exceed half the total grid cells.
-   No ship can be larger than the board size.

Winning Conditions
------------------

-   The winner is the player who hits all the opponent's ships first.
-   A tie occurs if both players hit all the opponent's ships simultaneously.
-   A player may forfeit, leading to an automatic win for the opponent.
-   If both players run out of time, the game ends in a tie.

Timing
------

Each player has a maximum block time to make their move. If they exceed this time, they forfeit the game.

Security Considerations
-----------------------

-   Commit-Reveal Scheme: Ensures that the initial placement of ships is confidential and verifiable.
-   Access Control: Only the players participating in the game can make moves or modify the game state.
-   Verification: All moves and reveals are verified to prevent cheating.

Example Gameplay
----------------

```python
import random
#random.seed(1)
# Player Addresses
player_a_address = "dys1player_a"
player_b_address = "dys1player_b"

# Game Initialization
CALLER = SCRIPT_ADDRESS  # Only the script can create a game
game_id = create_game(
    player_a_address,
    player_b_address,
    ship_sizes=[2],
    board_size=2,
    max_block_time=100)

# Precommit Phase
# Player A's Ship Commits
CALLER = player_a_address
player_a_ships = [
    [[1, 0, 54321], [1, 1, 54321]]
]

a_positions = [player_a_ships[0][0], player_a_ships[0][1], [0,0,""], [0,1,""]]
random.shuffle(a_positions)

player_a_ship_commits = [generate_ship_commit(ship) for ship in player_a_ships]
set_ship_commits(game_id, player_a_ship_commits)

# NEXT BLOCK
BLOCK_HEIGHT += 1

# Player B's Ship Commits
CALLER = player_b_address
player_b_ships = [
    [[0, 1, 56789], [1, 1, 56789]]
]
b_positions = [player_b_ships[0][0], player_b_ships[0][1], [0,0,""], [1,0,""]]
random.shuffle(b_positions)

player_b_ship_commits = [generate_ship_commit(ship) for ship in player_b_ships]
set_ship_commits(game_id, player_b_ship_commits)

# NEXT BLOCK
BLOCK_HEIGHT += 1


# Simulate the complete game by taking turns firing at each other's ships
player_a_turn = True

for i in '123456':
    print(f'round: {i}')
    
    # NEXT BLOCK
    BLOCK_HEIGHT += 1

    ax, ay, asalt = a_positions.pop()
    bx, by, bsalt = b_positions.pop()
    
    CALLER = player_a_address
    fire_at_position(game_id, bx, by)

    CALLER = player_b_address
    fire_at_position(game_id, ax, ay)
    

    # Player A reveals
    CALLER = player_a_address
    reveal_position(game_id, ax, ay, asalt)
    
    # Player B reveals
    CALLER = player_b_address
    reveal_position(game_id, bx, by, bsalt)

        
    # Check if the game is over
    game_state = get("games/" + str(game_id))
    print("game_state['state']", game_state['state'])
    if game_state['state'] != FIRE:
        break

# NEXT BLOCK
BLOCK_HEIGHT += 1

CALLER = player_a_address
reveal_ships(game_id, player_a_ships)

# Player B reveals their ships
CALLER = player_b_address
reveal_ships(game_id, player_b_ships)


# Check the Winner
game_state = get("games/" + str(game_id))
print("Winner:", game_state['winner'])
```
Output:

```
round: 1
dys1player_a fired at 1, 0
dys1player_b fired at 0, 0
dys1player_a was MISSED at 0, 0
dys1player_b was MISSED at 1, 0
game_state['state'] fire
round: 2
dys1player_a fired at 0, 1
dys1player_b fired at 1, 0
dys1player_a was HIT at 1, 0
dys1player_b was HIT at 0, 1
game_state['state'] fire
round: 3
dys1player_a fired at 0, 0
dys1player_b fired at 1, 1
dys1player_a was HIT at 1, 1
dys1player_b was MISSED at 0, 0
game_state['state'] reveal_ships
Winner: dys1player_b
```
