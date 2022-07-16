import cv2 as cv
import numpy as np
import os
import time
from windowcapture import WindowCapture
from detection import Detection
from vision import Vision
from bot import MTGABot, BotState
import pyautogui
import pydirectinput


# Change the working directory to the folder this script is in.
# Doing this because I'll be putting the files from each video in their
# own folder on GitHub
os.chdir(os.path.dirname(os.path.abspath(__file__)))


DEBUG = True

# initialize the WindowCapture class
wincap = WindowCapture('MTGA')
# load the detector
detector = Detection()  # 'limestone_model_final.xml')
# load an empty Vision class
vision = Vision()
# initialize the bot
bot = MTGABot((wincap.offset_x, wincap.offset_y), (wincap.w, wincap.h))

wincap.start()
detector.start()
bot.start()

while(True):

    # get an updated image of the game
    screenshot = wincap.get_screenshot()

    # do object detection
    rectangles = cascade.detectMultiScale(screenshot)

    # draw the detection results onto the original image
    detection_image = vision.draw_rectangles(screenshot, rectangles)

    # display the images
    cv.imshow('Matches', detection_image)

    # take bot actions
    if len(rectangles) > 0:
        # just grab the first objects detection in the list and find the place
        # to click
        targets = vision.get_click_points(rectangles)
        target = wincap.get_screen_position(targets[0])
        pyautogui.moveTo(x=target[0], y=target[1])
        pyautogui.click()
        # wait 5 seconds for the mining to complete
        sleep(5)

    # press 'q' with the output window focused to exit.
    # waits 1 ms every loop to process key presses
    key = cv.waitKey(1)
    if key == ord('q'):
        cv.destroyAllWindows()
        break

print('Done.')
