# tic-slack-toe
Competitive tic tac toe app for Slack workspaces

# Config Variables
- SLACK_BOT_TOKEN
- DATABASE_URL - set by Heroku, often updated while app is deployed
- PORT - set by Heroku, often updated while app is deployed
- SLACK_APP_TOKEN - needed only for Slack app Socket Mode (and so not used in this version of `app.py`)

# Heroku Files
- `Procfile` - specifies command for app start-up
- `requirements.txt` - specifies Python packages to install when app is first deployed
- `.env` - contains environment variables that are used when running `heroku local`
  - this is included in `.gitignore` to avoid posting tokens to GitHub
  - since it's not possible to run the Slack app in testing mode and point it to
    a local server and then easily switch back to pointing to Heroku, local tetsing
    doesn't really work

# Postgres Tables
This app interacts with a Postgres database.
The URL access point for the database should be given by the `DATABASE_URL`
environment variable.
The database should be configured with the following sequence of commands:
- `CREATE TABLE tic_tac_win (player_id TEXT UNIQUE, num_wins INT);` - create a table for 
  Slack ID and corresponding win count for each player
- `CREATE TYPE tictactile AS ENUM ('X', 'O', 'OPEN');` - create enum in Postgres to
  represent possible tile states
- `CREATE TABLE tic_tac_curr_team (letter tictactile);` - create a table to store a single
  row that tracks whether the next move will be an X or an O
- `CREATE TABLE tic_tac_board (tile_state tictactile, square_id int UNIQUE);` - create 
  table to record states of all tiles on the board
- `CREATE TABLE tic_tac_prev_player (player_id text);` - create table to record
  Slack ID of the player who made the last move
- `INSERT INTO tic_tac_board(square_id, tile_state)
    VALUES (0, 'OPEN'), (1, 'OPEN'), (2, 'OPEN'),
      (3, 'OPEN'), (4, 'OPEN'), (5, 'OPEN'),
      (6, 'OPEN'), (7, 'OPEN'), (8, 'OPEN');` - initialize the board state so that
      all tiles are OPEN
- `INSERT INTO tic_tac_curr_team(letter) VALUES ('X');` - sets the very first move to
  be for team X (this could be changed to O if you like)
- `INSERT INTO tic_tac_prev_player(player_id) VALUES ('');` - adds
  a row to the table so that it can be updated once a move is made

I configured these tables manually, using the Heroku Postgres CLI, but their setup
could be configured with a script.

# Slack Setup
- slash commands: /tictacmove and /tictacscoreboard
- permissions and event subscriptions
- setting Heroku env variables