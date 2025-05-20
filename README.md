# LLM Garous

<img src="https://upload.wikimedia.org/wikipedia/fr/thumb/2/2c/Loups-garous_de_Thiercelieux.png/500px-Loups-garous_de_Thiercelieux.png" width="200"/>

Codebase for our project at [ISC](https://isc.hevs.ch/) to play a game of "Loups-Garous" with LLMs.

## How to run

Install dependencies:
```bash
pip install -r requirements.txt
```

Implement your `WerewolfPlayer` in `werewolf.py`

Start the players with:
```bash
python3 werewolf_server.py
```

Start the game leader with:
```bash
python3 game_leader.py
```

# Instructions

[projet_loups_garous.pdf](projet_loups_garous.pdf)


# How to publish using ngrok

## Install ngrok

https://dashboard.ngrok.com/get-started/setup/

## Get an ngrok authtoken

https://dashboard.ngrok.com/get-started/your-authtoken

## Start your player server

For example, to start the player server on port 5021, run:

```bash
python3 werewolf_server.py 5021
```

## Run ngrok

```bash
ngrok http 5021
```

Then copy the ngrok URL and share it with the game leader.
