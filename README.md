# Battleship - A strategy game on Dyson Protocol

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

-   `create_game(player_a_address, player_b_address, board_size, ship_sizes)`: Initializes a new game with two players and optional board size and ship sizes.

### Ship Placement

-   `set_ship_commits(game_id, ship_commits)`: Players commit their ships' positions using cryptographic hashes.
-   `generate_ship_commit(ship_x_y_salts)`: A utility function to generate the cryptographic commit for a ship.

### Firing and Revealing

-   `fire_at_position(game_id, x, y)`: A player fires at a specific position on the opponent's grid.
-   `reveal_position(game_id, x, y, miss_or_salt)`: The opponent reveals whether the shot was a hit or miss.

### Ending the Game

-   `reveal_ships(game_id, ship_positions)`: Players reveal their ships to validate the game and determine the winner.
-   `_game_over(game_state)`: A private function to handle the end of the game and declare the winner.

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

Security Considerations
-----------------------

-   Commit-Reveal Scheme: Ensures that the initial placement of ships is confidential and verifiable.
-   Access Control: Only the players participating in the game can make moves or modify the game state.
-   Verification: All moves and reveals are verified to prevent cheating.

Conclusion
----------

Battleship on Dyson Protocol is a secure and transparent adaptation of the classic game using decentralized technology. Using the unique features of Dyson Protocol, the game provides an engaging and fair gaming experience.
