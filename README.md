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


# How to publish 



## Using ngrok

### Install ngrok

https://dashboard.ngrok.com/get-started/setup/

### Get an ngrok authtoken

https://dashboard.ngrok.com/get-started/your-authtoken

### Start your player server

For example, to start the player server on port 5021, run:

```bash
python werewolf_server.py 5021
```

This will start a _single player_ server on port 5021.

### Run ngrok

```bash
ngrok http 5021
```

Then copy the ngrok URL and share it with the game leader.

## Using pagekite

- one person of the group should register at [https://pagekite.net/signup/](https://pagekite.net/signup/), specify a kite name like `loupgarousgroupe{your group letter}`
- click on the activation email link and note your password
- download the pagekite client (see [https://pagekite.net/downloads](https://pagekite.net/downloads))


### Start your player server

For example, to start the player server on port 5021, run:

```bash
python werewolf_server.py 5021
```

This will start a _single player_ server on port 5021.


### Run the pagekite client

The format is:

```bash
python pagekite.py {port} {player1}.loupgarousgroupe{your group letter}.pagekite.me
```

For example, if you are player 1 in group ZZZ, you should run:

```bash
python pagekite.py 5021 player1.loupgarousgroupezzz.pagekite.me
```

Then, test that your player server is up and running at the ip that pagekite provides, and share it with the game leader.






