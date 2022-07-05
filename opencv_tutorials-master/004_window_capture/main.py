import cv2 as cv
import numpy as np
import os
from time import time
from windowcapture import WindowCapture
from PIL import ImageGrab, ImageOps
import pyautogui

# Change the working directory to the folder this script is in.
# Doing this because I'll be putting the files from each video in their own folder on GitHub
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# initialize the WindowCapture class
#wincap = WindowCapture('MTGA')

loop_time = time()
while(True):

    #first method from tutorial
    screenshot = pyautogui.screenshot()

    #method like MTGA tutorial
    #screenshot = ImageOps.grayscale(ImageGrab.grab(bbox=(1000, 630, 1300, 700)))

    #convert needed for above two methods
    screenshot = np.array(screenshot)
    screenshot = cv.cvtColor(screenshot, cv.COLOR_RGB2BGR)

    # get an updated image of the game
    #screenshot = wincap.get_screenshot()

    cv.imshow('Computer Vision', screenshot)

    # debug the loop rate
    print('FPS {}'.format(1 / (time() - loop_time)))
    loop_time = time()

    # press 'q' with the output window focused to exit.
    # waits 1 ms every loop to process key presses
    if cv.waitKey(1) == ord('q'):
        cv.destroyAllWindows()
        break

print('Done.')
