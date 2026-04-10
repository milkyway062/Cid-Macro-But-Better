import keyboard
import pyautogui
import pygetwindow
import os
import time

# Find Roblox window
rb_window = None
for window in pygetwindow.getAllWindows():
    if window.title == "Roblox":
        rb_window = window
        break
if not rb_window:
    print("Roblox window not found!")
    os._exit(0)

dx, dy = (rb_window.left, rb_window.top)

IMAGE_PATH = "Images/settings.png"
CONFIDENCE = 0.8

IS_ON = True
recorded = []

def add_pos():
    # Find image on screen
    match = pyautogui.locateOnScreen(IMAGE_PATH, confidence=CONFIDENCE)
    if match is None:
        print("Image NOT found on screen right now.")
        return

    img_center_x = match.left + match.width // 2
    img_center_y = match.top + match.height // 2

    mouse = pyautogui.position()
    offset_x = mouse.x - img_center_x
    offset_y = mouse.y - img_center_y

    # Also relative to window
    rel_mouse_x = mouse.x - dx
    rel_mouse_y = mouse.y - dy
    rel_img_x = img_center_x - dx
    rel_img_y = img_center_y - dy

    print(f"Image center (screen): ({img_center_x}, {img_center_y})")
    print(f"Image center (window-relative): ({rel_img_x}, {rel_img_y})")
    print(f"Mouse pos (screen): ({mouse.x}, {mouse.y})")
    print(f"Mouse pos (window-relative): ({rel_mouse_x}, {rel_mouse_y})")
    print(f"Offset from image center to mouse: ({offset_x}, {offset_y})  <-- use this")
    print("-" * 50)
    recorded.append((offset_x, offset_y))

def toggle():
    global IS_ON
    IS_ON = not IS_ON
    print(f"{'Running' if IS_ON else 'Paused'}")

keyboard.add_hotkey(".", add_pos)
keyboard.add_hotkey(",", toggle)

print("FindOffset.py running.")
print("  Press '.' to record current mouse position relative to settings.png")
print("  Press ',' to pause/resume")
print("  Press Ctrl+C to quit")
print("-" * 50)

# Live detection loop
try:
    while True:
        time.sleep(1)
        match = pyautogui.locateOnScreen(IMAGE_PATH, confidence=CONFIDENCE)
        if match:
            cx = match.left + match.width // 2 - dx
            cy = match.top + match.height // 2 - dy
            print(f"[DETECTED] settings.png center (window-relative): ({cx}, {cy})", end="\r")
        else:
            print("[ ] settings.png not on screen                              ", end="\r")
except KeyboardInterrupt:
    pass

print("\n\nAll recorded offsets (offset from image center to mouse):")
for i, o in enumerate(recorded):
    print(f"  {i+1}: {o}")
