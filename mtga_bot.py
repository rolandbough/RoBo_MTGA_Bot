"""
Magic The Gathering Arena bot that auto-plays to brute force daily and weekly rewards for gold/XP.
MTGA must be in full screen mode, 1920 x 1080, on primary monitor, and graphics adjusted to low. MTGA client needs to
be already launched and signed into (or you can use a BAT file to launch this script and game simultaneously as a
scheduled task).
This bot will not work out of the box if you run it now. It's dependant on grayscale values at various points on
the screen. I'm not providing the values I used in the code, firstly because it's dependant on screen resolution and
untested on any machine other than my own, and second because I don't want just anybody who comes across this to be
able to take advantage and run a MTGA bot. I'm posting this primarily as a record of the code, not because I want to
distribute a bot. You will have to figure out the grayscale values in the Range class for yourself. I've left some
in for reference.
~ defaultroot - 8th Feb 2020
"""

from PIL import ImageGrab, ImageOps
from numpy import *
import time
import win32api
import win32con
import win32gui
from random import randrange
from datetime import datetime
import logging
import cv2 as cv
import numpy as np
import re

# ----- SETTINGS -----
# These settings can be used to fine tune how the bot acts. It may be the case that the bot is clicking too fast or slow
# on your machine, resulting in loops being broken. Below are the settings that worked on my own machine.

# Percentage chance that the bot will attack with all creatures
ATTACK_PROBABILITY = 100

# Maximum number of times the bot will cycle through cards attempting to play them
MAX_CARD_CYCLES = 2

# How many full games will be played in a rotation before going to slow play mode
DAILY_FULL_GAMES = 30
# How often the bot will switch from slow play mode (86400 = 1 day, 3600 = 1 hour)
SECONDS_UNTIL_ROTATION = 43200

SPEED_PLAY_CARD = 0.5               # Delay between attempting to play a card
SPEED_DECK_SELECT = 1               # Delay between clicks on deck select screen
# Delay between clicking Resolve button during opponents turn
SPEED_OPPONENT_TURN_CLICK = 1

# When True, don't accept draw at Mulligan and don't play (STATIC_CLICK_DRAW_ACCEPT must be False)
SLOW_PLAY_MODE = False
# A fix for difficulty detecting draw accept. Clicks Accept after x seconds delay.
STATIC_CLICK_DRAW_ACCEPT = True
# Delay before pressing the accept draw button (may not always hit)
SLOW_DRAW_BUT_PLAY_MULLIGAN_PRESS_DELAY = 10

CLICKS_DISABLED = False             # Mouse clicks will not register, for testing

LOG_LEVEL = logging.INFO


# ----- GLOBALS -----

DECK_COLOURS = ['Green', 'Black', 'White',
                'Blue', 'Red']       # Decks for auto select
# Keep track of full games
GAME_COUNT = 0
# Keep track of when rotation time has elapsed
start = (datetime.today()).timestamp()

# ----- SET UP LOGGING -----

logger = logging.getLogger('mtgalog')
hdlr = logging.FileHandler('mtgalog.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(LOG_LEVEL)

# -------------------


class WindowMgr:
    """Encapsulates some calls to the winapi for window management"""

    def __init__(self):
        """Constructor"""
        self._handle = None

    def find_window(self, class_name, window_name=None):
        """find a window by its class_name"""
        self._handle = win32gui.FindWindow(class_name, window_name)

    def _window_enum_callback(self, hwnd, wildcard):
        """Pass to win32gui.EnumWindows() to check all the opened windows"""
        if re.match(wildcard, str(win32gui.GetWindowText(hwnd))) is not None:
            self._handle = hwnd

    def find_window_wildcard(self, wildcard):
        """find a window whose title matches the wildcard regex"""
        self._handle = None
        win32gui.EnumWindows(self._window_enum_callback, wildcard)

    def set_foreground(self):
        """put the window in the foreground"""
        win32gui.SetForegroundWindow(self._handle)


class Cord:

    # Maintain co-ordinates of locations to mouse click

    # The play button on the dashboard, bottom right
    play_button = (1108, 673)
    # Clicking (almost) anywhere in the screen to advance (usually after a match)
    click_to_continue = (167, 133)

    # Card positions to play. Remove [::2] for all positions (less likely to need a 2nd cycle, but slower)
    cards_in_hand = ((667, 719), (593, 719), (700, 719), (560, 719), (773, 719), (480, 719), (817, 719),
                     (440, 719), (883, 719), (360, 719), (950, 719), (327, 719), (1033, 719), (240, 719))

    #1080P = ((1000, 1079), (890, 1079), (1050, 1079), (840, 1079), (1160, 1079), (720, 1079), (1225, 1079), (660, 1079), (1325, 1079), (540, 1079), (1425, 1079), (490, 1079), (1550, 1079), (360, 1079))

    undo_button = (1247, 560)           # Undo button when casting a spell
    # During combat phase, the No Attacks button
    no_attacks_button = (1180, 587)
    # Click done to auto-assign damage to multiple blockers
    order_blockers_done = (647, 560)
    # Resolve button, also No Blocks during opponent combat
    resolve_button = (1180, 633)
    keep_draw = (760, 580)             # Accept drawn cards at start of match
    # Pass turn button (during both player's turns)
    pass_turn = (1233, 687)
    deck_select = (1167, 533)           # Click to select which deck to use
    white_deck = (300, 333)
    green_deck = (507, 333)
    black_deck = (703, 333)
    blue_deck = (900, 333)
    # Above decks not actually required, this cord always selects the next in cycle
    red_deck = (113, 457)
    smiley_face_continue = (640, 567)   # Skip on smiley face screen
    # To select when attacking in case opponent has Planeswalker in play
    opponent_avatar = (637, 70)
    cancel_area = (1153, 687)          # Just a blank area to click to cancel


class Zone:

    # Maintain co-ordinates of zones/boxes that will be analysed for grayscale value

    # On opening screen at game launch
    but_play = (1137, 667, 1139, 670)
    # After you press play to choose deck
    but_play_sidebar = (1267, 447, 1270, 450)
    # In match, Match Victory, or Match Defeat
    friends_icon = (20, 670, 23, 677)
    # Match is over and awaiting click
    match_result = (1223, 680, 1245, 692)
    # Undo button, appears when not sufficient mana to cast card
    undo_but = (1240, 553, 1247, 560)
    # Main phase icon, indicating your turn, or not first main
    p1_main_phase = (553, 581, 560, 588)
    p1_second_phase = (720, 580, 727, 587)    # Second phase icon
    p2_main_phase = (567, 79, 573, 85)        # Opponent Main phase icon
    p2_second_phase = (705, 79, 712, 85)    # Opponent Second phase icon
    # Confirms start of match Mulligan/Keep
    mulligan_button = (509, 571, 511, 585)
    # Shield icon, black when having to choose No/All Attack
    shield_icon = (1180, 549, 1187, 556)
    # Screen when opponent chooses multiple blockers
    block_order = (877, 522, 886, 523)
    # Player name at bottom left of combat screen
    harmonix_name = (65, 687, 66, 693)
    # Last 'h' on smiley face "Did you have fun" screen
    smiley_face = (824, 284, 827, 303)


class Range:

    # Range of values that a Zone should fall within to trigger a positive match
    # Any (0, 0) values need to be amended with the correct range

    play_button = (250, 270)
    play_button_sidebar = (38, 40)
    friends_icon_match_result = (0, 0)
    friends_icon_rewards = (0, 0)
    friends_icon_in_match = (1400, 9999)
    p1_main_phase = (153, 155)
    p1_second_phase = (153, 155)
    p2_main_phase = (0, 0)
    p2_second_phase = (0, 0)
    mulligan_button = (0, 0)
    combat_shield_icon = (138, 155)
    undo_button = (558, 560)
    block_order = (0, 0)
    smiley_face = (0, 0)


def check_if_new_day(start_time):

    split = (datetime.today()).timestamp()

    print(f"The last mode change was {start_time}")
    print(f"The current time is {split}")
    print(f"The difference is {split - start_time} seconds")

    if split - start_time > SECONDS_UNTIL_ROTATION:
        global start
        start = (datetime.today()).timestamp()
        return True
    else:
        print("It hasn't been a day yet")
        return False


def new_day_actions():
    global SLOW_PLAY_MODE
    print(f"SLOW_PLAY_MODE pre function: {SLOW_PLAY_MODE}")
    if SLOW_PLAY_MODE == False:
        SLOW_PLAY_MODE = True
    else:
        SLOW_PLAY_MODE = False

    print(f"SLOW_PLAY_MODE post function: {SLOW_PLAY_MODE}")


def leftClick():
    if CLICKS_DISABLED:
        pass
    else:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)


def doubleLeftClick():
    if CLICKS_DISABLED:
        pass
    else:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)


def mousePos(cord):
    if MOUSE_MOVE_DISABLE:
        pass
    else:
        win32api.SetCursorPos((cord[0], cord[1]))


def get_greyscale_value(box):
    im = ImageOps.grayscale(ImageGrab.grab(box))
    a = array(im.getcolors())
    a = a.sum()
    return a


def scan_screen():
    w = WindowMgr()
    w.find_window_wildcard("MTGA")
    w.set_foreground()

    but_play_value = get_greyscale_value(Zone.but_play)
    print("but_play_value: {}".format(but_play_value))

    but_play_sidebar_value = get_greyscale_value(Zone.but_play_sidebar)
    print("but_play_sidebar_value: {}".format(but_play_sidebar_value))

    friends_icon_value = get_greyscale_value(Zone.friends_icon)
    print("friends_icon_value: {}".format(friends_icon_value))

    undo_button_value = get_greyscale_value(Zone.undo_but)
    print("undo_but_value: {}".format(undo_button_value))

    p1_main_phase_value = get_greyscale_value(Zone.p1_main_phase)
    print("p1_main_phase_value: {}".format(p1_main_phase_value))

    p1_second_phase_value = get_greyscale_value(Zone.p1_second_phase)
    print("p1_second_phase_value: {}".format(p1_second_phase_value))

    p2_main_phase_value = get_greyscale_value(Zone.p2_main_phase)
    print("p2_main_phase_value: {}".format(p2_main_phase_value))

    p2_second_phase_value = get_greyscale_value(Zone.p2_second_phase)
    print("p2_second_phase_value: {}".format(p2_second_phase_value))

    mulligan_button_value = get_greyscale_value(Zone.mulligan_button)
    print("mulligan_button_value: {}".format(mulligan_button_value))

    shield_icon_value = get_greyscale_value(Zone.shield_icon)
    print("shield_icon_value: {}".format(shield_icon_value))

    block_order_value = get_greyscale_value(Zone.block_order)
    print("block_order_value: {}".format(block_order_value))

    smiley_face_value = get_greyscale_value(Zone.smiley_face)
    print("smiley_face_value: {}".format(smiley_face_value))

    if (but_play_value in range(Range.play_button[0], Range.play_button[1])) and \
            (but_play_sidebar_value not in range(Range.play_button_sidebar[0], Range.play_button_sidebar[1])):
        print("On start screen with Play button")
        return("Start")

    elif (but_play_value in range(Range.play_button[0], Range.play_button[1])) and \
            but_play_sidebar_value in range(Range.play_button_sidebar[0], Range.play_button_sidebar[1]):
        print("On deck select screen with Play button")
        return("Deck Select")

    elif check_in_match():
        print("In match")
        return("In Match")

    elif (smiley_face_value in range(Range.smiley_face[0], Range.smiley_face[1])):
        print("On smiley face fun screen!")
        mousePos(Cord.smiley_face_continue)
        time.sleep(1)
        leftClick()

    elif (friends_icon_value in range(Range.friends_icon_match_result[0], Range.friends_icon_match_result[1])):
        print("On match result screen")
        return("Match Result")

    elif friends_icon_value in range(Range.friends_icon_rewards[0], Range.friends_icon_rewards[1]):
        print("On Rewards Screen")
        return("Rewards")


def start_screen_actions():

    # Currently just click start, in future maybe cycle daily if not 750, confirm low graphics at startup

    print("Clicking Play Button")
    mousePos(Cord.play_button)
    #time.sleep(0.1)
    leftClick()


def deck_select_actions():

    # Currently just click start, in future select decks to fulfil daily challenges

    DECK_COLOURS.append(DECK_COLOURS[0])
    DECK_COLOURS.pop(0)
    next_deck = DECK_COLOURS[0]
    print("Next deck will be {} --- {}".format(next_deck, DECK_COLOURS))

    mousePos(Cord.deck_select)
    time.sleep(SPEED_DECK_SELECT)
    leftClick()

    mousePos(Cord.red_deck)
    time.sleep(SPEED_DECK_SELECT)
    leftClick()

    time.sleep(SPEED_DECK_SELECT)

    print("Clicking Play Button")
    mousePos(Cord.play_button)
    #time.sleep(0.1)
    leftClick()


def match_result_actions():

    # Just click anywhere to proceed

    print("Clicking to continue")
    mousePos(Cord.click_to_continue)
    leftClick()


def rewards_actions():

    # Click Start (Claim Prize)

    print("Clicking Play (Claim) Button")
    mousePos(Cord.play_button)
    leftClick()


def check_if_my_turn():
    p1_main_phase_grayscale = get_greyscale_value(Zone.p1_main_phase)
    p1_second_phase_grayscale = get_greyscale_value(Zone.p1_second_phase)
    p2_main_phase_value = get_greyscale_value(Zone.p2_main_phase)
    p2_second_phase_value = get_greyscale_value(Zone.p2_second_phase)

    mulligan_button_value = get_greyscale_value(Zone.mulligan_button)
    print("mulligan_button_value: {}".format(mulligan_button_value))

    print("Checking if my turn...")

    if ((p2_main_phase_value in range(Range.p2_main_phase[0], Range.p2_main_phase[1]))
        or (p2_second_phase_value in range(Range.p2_second_phase[0], Range.p2_second_phase[1]))) \
            and ((p1_main_phase_grayscale not in range(Range.p1_main_phase[0], Range.p1_main_phase[1]))
                 or (p1_second_phase_grayscale not in range(Range.p1_second_phase[0], Range.p1_second_phase[1]))):
        print("*** OPPONENT TURN ***")
        return False
    else:
        print("*** MY TURN ***")
        return True


def check_in_match():
    in_match = get_greyscale_value(Zone.friends_icon)
    print("Checking if in match: friends_icon was {}, in match usually 1304 - 1410".format(in_match))

    if (in_match in range(Range.friends_icon_in_match[0], Range.friends_icon_in_match[1])):
        print("Still in match...")
        return True
    else:
        print("Not in match, returning False. friend_icon value of {}".format(in_match))
        return False


def match_actions():
    global GAME_COUNT
    print("Starting match_actions...")

    time.sleep(2)

    if not STATIC_CLICK_DRAW_ACCEPT:
        mulligan_timeout = 0
        mulligan_button_value = get_greyscale_value(Zone.mulligan_button)
        while ((mulligan_button_value not in range(Range.mulligan_button[0], Range.mulligan_button[1]))):
            print("Not seeing Mulligan button, will keep looking...")
            print(f"mulligan_button_value: {mulligan_button_value}")
            mulligan_timeout += 1
            if mulligan_timeout > 50:
                break
            time.sleep(1)

        print("Found Mulligan button")

        # If SLOW_PLAY_MODE is enabled, wait until timer runs out for deck selection, to see if opponent will quit
        if GAME_COUNT < MAX_CARD_CYCLES:
            mousePos(Cord.keep_draw)
            leftClick()
            print("Accepted Draw")
        else:
            return

    if STATIC_CLICK_DRAW_ACCEPT:
        time.sleep(SLOW_DRAW_BUT_PLAY_MULLIGAN_PRESS_DELAY)
        mousePos(Cord.keep_draw)
        leftClick()
        print("Attempted to accept Draw as part of STATIC_CLICK_DRAW_ACCEPT mode")

    while(check_in_match() == True):
        print("Beginning In-Match Loop")

        while(check_if_my_turn() == False):
            print("Waiting for my turn...")

            mousePos(Cord.resolve_button)
            print("Pressing Resolve while waiting for my turn...")
            leftClick()
            time.sleep(SPEED_OPPONENT_TURN_CLICK)

        card_cycles = 1
        print("Card cycles is set to {}".format(card_cycles))

        while(card_cycles <= MAX_CARD_CYCLES):

            print("Beginning card cycle phase...")

            for cord in (Cord.cards_in_hand):

                if check_in_match() == False:
                    break

                print("Checking for combat phase...")
                shield_icon_value = get_greyscale_value(Zone.shield_icon)
                print(f"shield_icon_value: {shield_icon_value}")
                if ((shield_icon_value in range(Range.combat_shield_icon[0], Range.combat_shield_icon[1]))):
                    print("Confirmed combat phase")
                    time.sleep(1)

                    x = randrange(1, 101)
                    if x < ATTACK_PROBABILITY:
                        print(f"Attacking with all creatures (roll of {x}")
                        mousePos(Cord.resolve_button)
                        leftClick()
                        time.sleep(1)
                        mousePos(Cord.opponent_avatar)
                        leftClick()
                    else:
                        print("Clicking No Attack Button")
                        mousePos(Cord.no_attacks_button)
                        leftClick()

                    print("Incrementing card_cycles by 99 and breaking")
                    card_cycles += 99
                    break

                elif (check_if_my_turn() == False):
                    print(
                        "My opponent's turn, so incrementing card_cycles by 99 and breaking")
                    card_cycles += 99
                    break

                time.sleep(SPEED_PLAY_CARD)
                mousePos(cord)
                doubleLeftClick()
                time.sleep(1)
                undo_button_value = get_greyscale_value(Zone.undo_but)
                print(f"undo_button_value: {undo_button_value}")
                if (undo_button_value in range(Range.undo_button[0], Range.undo_button[1])):
                    print("Detected Undo button, so pressing it...")
                    mousePos(Cord.undo_button)
                    print("Attempting to play card in cycle {}".format(card_cycles))
                    leftClick()

            print("Gone through all cards in hand, so incrementing card_cycles by 1")
            card_cycles += 1
            print("Card cycles is now {}/{}".format(card_cycles, MAX_CARD_CYCLES))
            #time.sleep(1)

        print("Should have completed all card_cycles, so now clicking resolve_button")
        mousePos(Cord.resolve_button)
        leftClick()

        block_order_value = get_greyscale_value(Zone.block_order)
        print(f"block_order_value: {block_order_value}")
        if block_order_value in range(Range.block_order[0], Range.block_order[1]):
            print("Detected Block Order, clicking done...")
            mousePos(Cord.order_blockers_done)
            leftClick()

        print("Checking if the match is over...")
        if not check_in_match():
            print("Match is over, going back to main loop")
            break


logger.info("*** Started mgta_bot ***")

while True:
    screen = scan_screen()

    if screen == "Start":
        start_screen_actions()

    elif screen == "Deck Select":
        deck_select_actions()

    elif (screen == "In Match"):
        if (SLOW_PLAY_MODE and not STATIC_CLICK_DRAW_ACCEPT):
            pass
            if check_if_new_day(start):
                SLOW_PLAY_MODE = False
        else:
            match_actions()
            GAME_COUNT += 1
            logger.info(
                f"Incremented GAME_COUNT to {GAME_COUNT}/{DAILY_FULL_GAMES}")
            if GAME_COUNT >= DAILY_FULL_GAMES:
                SLOW_PLAY_MODE = True
                GAME_COUNT = 0

    elif screen == "Match Result":
        logger.info("Match end")
        match_result_actions()

    elif screen == "Rewards":
        rewards_actions()

    print(
        f"***** GAME COUNT: {GAME_COUNT} / {DAILY_FULL_GAMES} ***** SLOW MODE: {SLOW_PLAY_MODE} *****")

    time.sleep(1)
