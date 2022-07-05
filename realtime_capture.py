import win32gui
import win32ui
import win32con


def test_get_screenshot():
    # define your monitor width and height
    w, h = 1920, 1080

    # for now we will set hwnd to None to capture the primary monitor
    #hwnd = win32gui.FindWindow(None, window_name)
    hwnd = None

    # get the window image data
    wDC = win32gui.GetWindowDC(hwnd)
    dcObj = win32ui.CreateDCFromHandle(wDC)
    cDC = dcObj.CreateCompatibleDC()
    dataBitMap = win32ui.CreateBitmap()
    dataBitMap.CreateCompatibleBitmap(dcObj, w, h)
    cDC.SelectObject(dataBitMap)
    cDC.BitBlt((0, 0), (w, h), dcObj, (0, 0), win32con.SRCCOPY)

    # save the image as a bitmap file
    dataBitMap.SaveBitmapFile(cDC, 'debug.bmp')

    # free resources
    dcObj.DeleteDC()
    cDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, wDC)
    win32gui.DeleteObject(dataBitMap.GetHandle())

test_get_screenshot()
