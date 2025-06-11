# Réponses aux questions :

Nombre de tokens utilisés pour :

- 1 token ~= 4 chars in English
- 1 token ~= ¾ words
- 100 tokens ~= 75 words

Ou 

- 1-2 sentence ~= 30 tokens
- 1 paragraph ~= 100 tokens
- 1,500 words ~= 2048 tokens

Nous utilisons :
- réponse du LLm : 35 mots
- règles : 250 mots 
- speak ou interrupt : 600 mots + règles = 850 mots
- voyante : 100 + règles = 350 mots
- loup-garou : 110 + règles = 360 mots
- choosevote : 350 + règles =  600 mots
 
Voici l’estimation du nombre de tokens pour chacun de tes cas, en utilisant la règle :
Nombre de tokens ≈ nombre de mots ÷ 0,75
(ou, plus rapide : nombre de mots × 1,33)

Calculs détaillés
- Réponse : Tokens ≈ 35 × 1,33 ≈  47 tokens
- Règles : Tokens ≈ 250 × 1,33 ≈ 333 tokens
- Speak ou interrupt : Tokens ≈ 850 × 1,33 ≈ 1130 tokens
- Voyante : Tokens ≈ 350 × 1,33 ≈ 465 tokens
- Loup-garou : Tokens ≈ 360 × 1,33 ≈ 480 tokens
- Choose_vote : Tokens ≈ 600 × 1,33 ≈ 800 tokens

7 tours, pour un joueur au maximum, en parlant 4 fois au tour au maximum (speak ou vote) :

Entrées :
- 7 * 4 * 1130 = 31 640 tokens (pire des cas, que de parler 4 fois, jusqu'à la fin) (Cached)
- 7 * 4 * 800 = 22 400 tokens (parle pas et rôle villageois)

Sorties : 
- 7 * 4 * 47 = 1316 tokens pour les sorties.

Coûts pour 1 000 000 de tokens:
gpt-4.1 (gpt-4.1-2025-04-14) : \$ 2.00 Input, \$ 0.50 Cached input , \$ 8,00 Output 


Donc (joueur va jusqu^à la fin de partie):
(0,5 / (1 000 000)) * 31 640 + (8 / (1 000 000)) * 1 316 =  0,03 \$  (pire des cas, que de parler 4 fois, jusqu'à la fin) (Cached)
(2,0 / (1 000 000)) * 22 400 + (8 / (1 000 000)) * 1 316 =  0,06 \$  (parle pas et rôle villageois)


Source : https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
         https://platform.openai.com/docs/pricing




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






