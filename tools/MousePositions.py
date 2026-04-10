import keyboard
import pyautogui
import pygetwindow
import os
import time


for window in pygetwindow.getAllWindows():
    if window.title == "Roblox":
        rb_window = window
        break
if not rb_window:
    os._exit(0)
dx,dy = (rb_window.left,rb_window.top)

IS_ON = True
MOUSE_POSITIONS = []
POS_COLOR = []

def add_pos():
    global POS_COLOR
    global MOUSE_POSITIONS
    print("Position Added")
    c_pos = pyautogui.position()
    POS_COLOR += [pyautogui.pixel(c_pos.x,c_pos.y)]
    MOUSE_POSITIONS+=[(c_pos.x-dx,c_pos.y-dy)]

def toggle():
    global IS_ON
    IS_ON = not IS_ON

keyboard.add_hotkey(".",add_pos)
keyboard.add_hotkey(",",toggle)


while IS_ON:
    time.sleep(0.5)

for ind,pos in enumerate(MOUSE_POSITIONS):
    print(f"{pos} : {POS_COLOR[ind]}")