#!/bin/bash

zenity --question --title="Moon Phases Setup" --text="Je to prvé spustenie (potrebná inštalácia závislostí)?" \
  --ok-label="First Run" --cancel-label="Classic Run"

if [ $? -eq 0 ]; then
    zenity --info --text="Inštalujem potrebné balíky cez pip…"
    pip install -r requirements.txt 2>&1 | zenity --progress --pulsate --title="Inštalácia" --text="Inštalácia balíkov…" --auto-close
fi

python3 moon_visibility_2025.py
