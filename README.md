# Cid-Macro-But-Better

## Just double click `run.bat` to start
## Have click to move `On`
## `0.2 Sens` in roblox
## Auto-Replay `On` in AV settings
## Rolbox window *needs* to be the `SMALLEST` size
## TAKE ALL COSMETICS `OFF`

- This is a heavily edited version of Requim's macro, which was built off of Lox's

### Things to know before using this:

- Some things may not work as intended, bugs are still possible, I'm somewhat new to python
- There are still some things to work on
- It *should* work in RDP but it's very hard to get it working consistantly with how its set up because of RDP compression - it should work just fine on your regular desktop

#### Update `0.1`
- Super Simple GUI
- Auto Position
- Auto Rejoin
- Most Softlocks Fixed
- Many Other Little Things I Can't Remember

#### Update `0.2`
- Fixed Leaderboard
- Hopefully Fixed Chat Detection
- Added Auto Updater

#### Update `0.3`
- Fixed cancel popup bricking the macro
- Lobby pathing now retries on failure

#### Update `0.35`
- Fixed lobby path retry - wasnt working after rejoin

### Known issues
- Loss counter not needed - Very hard to detect losses with auto play on
- Webhooks not updated yet - gonna be way simpler
- Closing chat is incosistant - working on a more consitant method
- Some users run into Brook Buff lasting too long or not long enough - Fix (Maybe???): <img width="589" height="142" alt="image" src="https://github.com/user-attachments/assets/1ff9720b-7594-4b15-806f-b3acc4cb9368" />
- Some players are getting the problem with Sokura's ability clicking twice and it softlocking - I thought I fixed this but idk anymore.. I added a timer (5 mins) if a run doesn't win or happen at all in that time, the roblox client restarts completely and it goes into the gamemode, hopefully that fixes it.
<img width="450" height="280" alt="image" src="https://github.com/user-attachments/assets/fcc4c7bd-b989-4cdd-9017-15dfeb9650c2" />

- If your macro teleports way too fast and goes to the wrong place - change line 1521 from sleep .5 to 1 or 1.5 or whatever works for you



## Huge thanks to Lox for making the base for the macro, and Requiem for making it better.
