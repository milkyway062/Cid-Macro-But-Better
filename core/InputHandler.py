import ctypes
import time
#Type
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
#Keyboard
KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
#Mouse
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_ABSOLUTE = 0x8000
SendInput = ctypes.windll.user32.SendInput
ulong_pointer = ctypes.POINTER(ctypes.c_ulong)

class KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk",ctypes.c_ushort),("wScan",ctypes.c_ushort),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",ulong_pointer)]
class MouseInput(ctypes.Structure):
    _fields_ = [("dx",ctypes.c_long),("dy",ctypes.c_long),("mouseData",ctypes.c_ulong),("dwFlags",ctypes.c_ulong),("time",ctypes.c_ulong),("dwExtraInfo",ulong_pointer)]
class InputUnion(ctypes.Union):
    _fields_ = [("ki", KeyboardInput), ("mi", MouseInput)]
class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("iu",InputUnion)]

def KeyDown(hexKeyCode):
    extra = ctypes.c_ulong(0)
    _iu = InputUnion()
    _iu.ki = KeyboardInput(0,hexKeyCode, KEYEVENTF_SCANCODE, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_KEYBOARD),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))

def KeyUp(hexKeyCode):
    extra = ctypes.c_ulong(0)
    _iu = InputUnion()
    _iu.ki = KeyboardInput(0,hexKeyCode, KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_KEYBOARD),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))

def PositionVerify():
    ctypes.windll.user32.mouse_event(0x0001, 0, 1, 0, 0)
    time.sleep(0.01)
    ctypes.windll.user32.mouse_event(0x0001, 0, -1, 0, 0)

def MoveTo(dx,dy):
    extra = ctypes.c_ulong(0)

    sw = ctypes.windll.user32.GetSystemMetrics(0)
    sh = ctypes.windll.user32.GetSystemMetrics(1)

    abs_x = int(dx * 65535 / (sw - 1))
    abs_y = int(dy * 65535 / (sh - 1))

    _iu = InputUnion()
    _iu.mi = MouseInput(abs_x,abs_y,0,MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_MOUSE),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))
    PositionVerify()

def Click(dx,dy,delay):
    extra = ctypes.c_ulong(0)
    MoveTo(dx,dy)
    time.sleep(delay)
    _iu = InputUnion()
    _iu.mi = MouseInput(0,0,0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_MOUSE),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))
    _iu = InputUnion()
    _iu.mi = MouseInput(0,0,0,MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_MOUSE),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))

def RightClick(dx,dy,delay):
    extra = ctypes.c_ulong(0)
    MoveTo(dx,dy)
    time.sleep(delay)
    _iu = InputUnion()
    _iu.mi = MouseInput(0,0,0, MOUSEEVENTF_RIGHTDOWN, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_MOUSE),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))
    _iu = InputUnion()
    _iu.mi = MouseInput(0,0,0,MOUSEEVENTF_RIGHTUP, 0, ctypes.pointer(extra))
    x = Input(ctypes.c_ulong(INPUT_MOUSE),_iu)
    SendInput(1,ctypes.pointer(x),ctypes.sizeof(x))

