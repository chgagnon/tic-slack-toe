import os
from shutil import move
from tracemalloc import start
from urllib import response
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import re
import logging
from enum import Enum
import psycopg2

class TicTacMove(Enum):
    OPEN = 1
    X = 2
    O = 3

    @staticmethod
    def get_opposite(e):
        if e == TicTacMove.X:
            return TicTacMove.O
        elif e == TicTacMove.O:
            return TicTacMove.X
        else:
            return TicTacMove.OPEN


logging.basicConfig(level=logging.INFO)

# usernames are received by the server as <123ABC>
USRNAME_PATTERN = "<.+>"
USRNAME_REGEX = re.compile(USRNAME_PATTERN)

# for tic tac toe game
BOARD_HEIGHT = 3
BOARD_WIDTH = 3
# backticks escape Slack markdown formatting (by formatting as "code")
BLANK_BOARD_STR = "`_|_|_`\n`_|_|_`\n` | | `"
TIC_TAC_CHANNEL_NAMES = ["tic-tac-toe-test", "tic-tac-tolympics"]
TIE_STR = "TIE"


def test_database_connection():
    """Connect to the PostgreSQL database server"""
    conn = None
    try:
        # connect to the PostgreSQL server
        print("Connecting to the PostgreSQL database...")
        conn = psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

        # create a cursor
        cur = conn.cursor()

        # execute a statement
        print("PostgreSQL database version:")
        cur.execute("SELECT version()")

        # display the PostgreSQL database server version
        db_version = cur.fetchone()
        print(db_version)

        # close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")

# Initializes your app with your bot token and socket mode handler
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET"),
)


@app.event("app_mention")
def action_button_click(event, say):
    say("dude what do you want")


def translate_user_id_to_name(user_id):
    # token should be passed automatically
    # (specified token when initializing app)
    users_list = app.client.users_list()
    for user in users_list["members"]:
        if user["id"] == user_id:
            return (user["id"], user["real_name"])
    return ("aw shucks", "could not find a user name for this user ID")

@app.command("/tictacmove")
def handle_tictacmove(ack, respond, command):
    ack()
    if command["channel_name"] not in TIC_TAC_CHANNEL_NAMES:
        respond("You can't do that in this channel.")
    else:
        move_data = command["text"].split()
        if len(move_data) == 2:
            row_num = int(move_data[0])
            col_num = int(move_data[1])
            if (
                row_num >= 0
                and row_num < BOARD_HEIGHT
                and col_num >= 0
                and col_num < BOARD_WIDTH
            ):
                player = command["user_id"]
                prev_player = lookup_prev_player()
                if prev_player == player:
                    respond("You're not allowed to move twice in a row. Find someone to play with you!")
                else:
                    update_prev_player(player)
                    make_tic_tac_toe_move(player, row_num, col_num, respond)
            else:
                respond(
                    "Try again - your move row and column were too large or too small."
                )
        else:
            respond("Try again - you didn't provide a move in proper format.")


# used for debugging the reset function - this slack command
# will be disabled before the app is put to use by the public
@app.command("/restart-tic-tac")
def handle_tic_tac_restart(ack, respond, command):
    ack()
    if command["channel_name"] not in TIC_TAC_CHANNEL_NAMES:
        respond("You can't do that in this channel.")
    else:
        reset_board_state()
        respond("Board should be reset now.")


@app.command("/tictacscoreboard")
def handle_tic_tac_scoreboard(ack, respond, command):
    ack()
    # allow in any channel
    sql = """SELECT player_id, num_wins from tic_tac_win ORDER BY num_wins DESC"""
    slack_msg = "===CURRENT TIC TAC TOE SCOREBOARD===\n"
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(sql)
        conn.commit()

        print(f"Getting win count")

        row = cur.fetchone()

        while row is not None:
            target_str = f"*PLAYER:* <@{row[0]}>"
            numvotes_str = f"| *WINS:* {row[1]}"
            slack_msg += target_str.ljust(30) + numvotes_str.rjust(14) + "\n"
            row = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
    respond(slack_msg)


def convert_move_str_to_enum(move_str):
    if move_str == "OPEN":
        return TicTacMove.OPEN
    elif move_str == "X":
        return TicTacMove.X
    elif move_str == "O":
        return TicTacMove.O
    else:
        print(
            f"ERROR: move_str was none of the permitted types - it was instead {move_str}"
        )


def update_curr_move_team(team_letter_str):
    conn = None
    sql = """UPDATE tic_tac_curr_team
                SET letter = %s;"""
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(sql, [team_letter_str])
        conn.commit()

        print(f"Updating curr team to be {team_letter_str}")

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


# looks up whether the current turn is for O or X
# then sets the other team to be the team for the next turn
def get_and_update_curr_move_team():
    conn = None
    curr_team_str = None
    try:
        """look up whether it is a turn for team X or team O"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM tic_tac_curr_team;")

        print("Getting team for current move")

        row = cur.fetchone()

        while row is not None:
            curr_team_str = row[0]
            row = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

        if curr_team_str == "X":
            print(f"Current team is {curr_team_str}")
            update_curr_move_team("O")
            return TicTacMove.X
        elif curr_team_str == "O":
            print(f"Current team is {curr_team_str}")
            update_curr_move_team("X")
            return TicTacMove.O
        else:
            print("ERROR: constructed move type was neither X nor O")


# returns (whether_game_won, winner)
# winner is arbitrary if whether_game_won is False
def whether_triple(board_state, start_index, offset):
    if (
        (board_state[start_index] != TicTacMove.OPEN)
        and (board_state[start_index] == board_state[start_index + offset])
        and (board_state[start_index] == board_state[start_index + 2 * offset])
    ):
        return True, board_state[start_index]
    else:
        for tile in board_state:
            if tile == TicTacMove.OPEN:
                return False, TicTacMove.OPEN
        # in this case, there's no winner, and the board is full
        return TIE_STR, TicTacMove.OPEN


# lst_of_checked_triples is a list of the form (whether_game_won, winner)
# in tic tac toe, it is NOT possible for more than one player to be a winner at the same time
def get_winner(lst_of_checked_triples):
    for result in lst_of_checked_triples:
        # check if there are any wins
        if result[0] == True:
            return result
    for result in lst_of_checked_triples:
        # now check if there is a tie (only valid when there is no win)
        if result[0] == TIE_STR:
            return result
    return False, TicTacMove.OPEN


def check_for_vert_win(board_state):
    offset = 3
    # vert win states start from tiles 0, 1, 2
    lst_to_check = [whether_triple(board_state, i, offset) for i in range(3)]
    return get_winner(lst_to_check)


def check_for_horiz_win(board_state):
    offset = 1
    # horiz win states start from tiles 0, 3, 6
    lst_to_check = [whether_triple(board_state, i, offset) for i in [0, 3, 6]]
    return get_winner(lst_to_check)


def check_for_diag_win(board_state):
    return get_winner(
        [whether_triple(board_state, 0, 4), whether_triple(board_state, 2, 2)]
    )


def check_for_win(board_state):
    return get_winner(
        [
            check_for_vert_win(board_state),
            check_for_horiz_win(board_state),
            check_for_diag_win(board_state),
        ]
    )


def record_win(player):
    conn = None
    try:
        """record 1 additional tic tac toe win for player"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        sql = """INSERT INTO tic_tac_win(player_id, num_wins)
             VALUES(%s, %s)
             ON CONFLICT (player_id)
             DO UPDATE
                SET num_wins = tic_tac_win.num_wins + 1;"""
        cur.execute(sql, [player, 1])

        # commit the changes to the database
        conn.commit()

        print(f"Recording a win for {player}")

        row = cur.fetchone()

        while row is not None:
            curr_team_str = row[0]
            row = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


def update_board_state(row_num, col_num, curr_team):
    conn = None
    try:
        """record new state induced by current move"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        sql = """INSERT INTO tic_tac_board(tile_state, square_id)
             VALUES(%s, %s)
             ON CONFLICT (square_id)
             DO UPDATE
                SET tile_state = excluded.tile_state;"""
        cur.execute(
            sql, [convert_move_enum_to_str(curr_team), row_num * BOARD_WIDTH + col_num]
        )

        # commit the changes to the database
        conn.commit()

        print(
            f"Updating board state at row {row_num} and col {col_num} to be {curr_team}"
        )

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()


def convert_move_enum_to_str(tile):
    if tile == TicTacMove.OPEN:
        return "_"
    elif tile == TicTacMove.X:
        return "X"
    elif tile == TicTacMove.O:
        return "O"
    else:
        print(
            "ERROR: When constructing board string, a tile was neither X nor O nor OPEN"
        )


def get_board_str(board_state):
    board_str = ""
    for i in range(BOARD_HEIGHT):
        curr_row_str = "`"
        for j in range(BOARD_WIDTH):
            curr_row_str += convert_move_enum_to_str(board_state[j + BOARD_WIDTH * i])
            curr_row_str += "|"
        # replace last-column | with `\n
        curr_row_str = curr_row_str[:-1]
        curr_row_str += "`\n"
        board_str += curr_row_str
    return board_str


def reset_board_state():
    print("Reached beginning of func reset_board_state()")
    conn = None
    values_str = "(%s, %s)," * BOARD_WIDTH * BOARD_HEIGHT
    # remove final comma
    values_str = values_str[:-1]
    sql = (
        """INSERT INTO tic_tac_board(square_id, tile_state)
             VALUES """
        + values_str
        + """ ON CONFLICT (square_id)
             DO UPDATE
                SET tile_state = excluded.tile_state;"""
    )
    rows_to_insert = [(i, "OPEN") for i in range(BOARD_HEIGHT * BOARD_WIDTH)]
    values_to_insert = []
    for i in rows_to_insert:
        values_to_insert.append(i[0])
        values_to_insert.append(i[1])
    print("rows_to_insert has len", len(rows_to_insert))
    print("rows to insert is", rows_to_insert)
    print("values to insert is", values_to_insert)
    print("sql str is", sql)
    try:
        """set all board tiles to state OPEN"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(sql, values_to_insert)

        # commit the changes to the database
        conn.commit()

        print("Resetting board state for a new game")

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def lookup_prev_player():
    conn = None
    last_player_id = None
    try:
        """look up who moved last"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM tic_tac_prev_player;")

        print("Getting player who made previous move")

        row = cur.fetchone()

        while row is not None:
            last_player_id = row[0]
            row = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

        return last_player_id

def update_prev_player(player_id):
    conn = None
    sql = """UPDATE tic_tac_prev_player
                SET player_id = %s;"""
    try:
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(sql, [player_id])
        conn.commit()

        print(f"Updating prev player to be {player_id}")

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

def make_tic_tac_toe_move(player, row_num, col_num, respond):

    slack_msg = f"====CURRENT BOARD===\n"
    last_move_by_str = f"Last move made by <@{player}>\n"
    board_state = []
    board_index = row_num * BOARD_WIDTH + col_num
    conn = None
    try:
        """query data from the tic tac toe table"""
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute(f"SELECT tile_state FROM tic_tac_board ORDER BY square_id ASC")

        print("Getting existing tic tac toe board")

        r = cur.fetchone()

        while r is not None:
            board_state.append(convert_move_str_to_enum(r[0]))
            r = cur.fetchone()

        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

        if len(board_state) != BOARD_HEIGHT * BOARD_WIDTH:
            print("ERROR: board_state was not the correct length")
        else:

            if board_state[board_index] != TicTacMove.OPEN:
                respond("Try again - that space is already taken.")
            else:
                curr_team = get_and_update_curr_move_team()
                board_state[board_index] = curr_team

                # get next team to use in Slack msg response
                next_team = TicTacMove.get_opposite(curr_team)
                next_team_str = f"Next move will be for team `{convert_move_enum_to_str(next_team)}`\n"

                # winner currently not used because X and O team assignments don't matter
                whether_won, winner = check_for_win(board_state)
                if whether_won == True:
                    # record a win for the current player
                    record_win(player)
                    # reset the (database) board state
                    reset_board_state()
                    # print a blank board to the chat
                    slack_msg += (
                        f"This is a new game - <@{player}> won the previous game.\n"
                    )
                    slack_msg += next_team_str
                    slack_msg += BLANK_BOARD_STR
                    respond(slack_msg, response_type="in_channel")
                elif whether_won == TIE_STR:
                    # I know using a string as an third boolean is very
                    # silly - I'm sorry

                    # reset the (database) board state
                    reset_board_state()

                    slack_msg += f"The previous game ended in a tie - nobody won.\n"
                    slack_msg += last_move_by_str
                    slack_msg += next_team_str
                    slack_msg += BLANK_BOARD_STR
                    respond(slack_msg, response_type="in_channel")
                else:
                    slack_msg += last_move_by_str
                    slack_msg += next_team_str
                    # add a tile and print out the new board
                    update_board_state(row_num, col_num, curr_team)
                    board_str = get_board_str(board_state)
                    slack_msg += board_str
                    respond(slack_msg, response_type="in_channel")


# Start your app
if __name__ == "__main__":
    # test_database_connection()
    app.start(port=int(os.environ.get("PORT", 3000)))
    print("started up the Bolt server")
