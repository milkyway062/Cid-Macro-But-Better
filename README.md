# Cid-Macro-But-Better - Fork Of [CidTutorial by Lox](https://github.com/loxerex/MacroTutorials)

## Settings
- Just double click `run.bat` to start
- Have click to move `On`
- `0.2 Sens` in roblox
- Auto-Replay `On` in AV settings
- Rolbox window *needs* to be the `SMALLEST` size
- TAKE ALL COSMETICS `OFF`
- Brook keybinds are `ASDFG`

### Check [updates.md](https://github.com/milkyway062/Cid-Macro-But-Better/blob/main/updates.md) for updates

## Things to know before using this:

- Some things may not work as intended, bugs are still possible, I'm somewhat new to python
- There are still some things to work on
- It *should* work in RDP but it's very hard to get it working consistantly with how its set up because of RDP compression - it should work just fine on your regular desktop

### Known issues and fixes
- Loss counter not needed - Very hard to detect losses with auto play on
- Webhooks not updated yet - gonna be way simpler
- Some users run into Brook Buff lasting too long or not long enough - Fix:
  - The buff loop runs until a wave skip is detected. `The 6 on line 100 in core\actions.py` is the minimum time (in seconds) before it checks for wave skip — effectively how long the buff holds. Change that value to adjust the duration.
- Some players are getting the problem with Sokura's ability clicking twice and it softlocking - I thought I fixed this but idk anymore.. I added a timer (5 mins) if a run doesn't win or happen at all in that time, the roblox client restarts completely and it goes into the gamemode, hopefully that fixes it. Try this also:
  - `line 284 in Main.py` — `InputHandler.Click(\*state.ABILITY1, delay=0.1)` — delay after clicking the ability button.

- If your macro teleports way too fast and goes to the wrong place - Change `line 217 in core\lobby.py` from sleep 1 to 1.5 or 2 or whatever works for you - Values are in seconds

<hr>

## Huge thanks to Lox for making the base for the macro, and Requiem for making it better.
