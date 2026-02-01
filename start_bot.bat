@echo off
title Music Bot
echo Starting Music Bot...
:restart
python bot.py
echo Bot stopped. Restarting in 5 seconds...
timeout /t 5
goto restart
