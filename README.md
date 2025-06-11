# 🐺 LLM Garous

## 💰 Question 1 : Prix de notre modèle

Voici une **estimation approximative** du coût de notre modèle selon les cas d’usage rencontrés pendant les parties.

---

### 📌 Conditions :

- Estimation basée sur un **joueur qui intervient environ 4 fois par jour** (votes compris).
- **Prix par partie estimé** :
  - **Minimum** : 0,03 $
  - **Maximum** : 0,06 $

- Coûts pour 1 000 000 de tokens avec **GPT-4.1** (`gpt-4.1-2025-04-14`) :
  - **Input** : 2,00 $ / 1M tokens
  - **Cached input** : 0,50 $ / 1M tokens
  - **Output** : 8,00 $ / 1M tokens

---

### 🔢 Estimations de conversion des mots en tokens :

- 1 token ≈ 4 caractères en anglais
- 1 token ≈ ¾ mots
- 100 tokens ≈ 75 mots
- 
Formule pratique :
**Nombre de tokens ≈ nombre de mots × 1,33**

---

### 📊 Nombre de mots utilisés selon les cas :

| Cas d’usage            | Mots approx. | Tokens approx. |
|------------------------|--------------|----------------|
| Réponse simple du LLM  | 35 mots      | ~47 tokens     |
| Règles seules          | 250 mots     | ~333 tokens    |
| `speak` ou `interrupt` | 850 mots     | ~1 131 tokens  |
| Voyante                | 350 mots     | ~467 tokens    |
| Loup-garou             | 360 mots     | ~480 tokens    |
| Choix de vote (`choosevote`) | 600 mots | ~800 tokens    |

---

## 📊 2. Calculs détaillés

Ces estimations nous ont permis de dimensionner les coûts par partie en fonction du type d’intervention et de la fréquence des appels API.

### 🔢 Approximation des tokens par type de message

| Type de contenu      | Mots (approx.) | Tokens estimés (×1,33) |
|----------------------|----------------|--------------------------|
| Réponse              | 35             | ≈ 47 tokens              |
| Règles               | 250            | ≈ 333 tokens             |
| Speak ou Interrupt   | 850            | ≈ 1 130 tokens           |
| Voyante              | 350            | ≈ 465 tokens             |
| Loup-garou           | 360            | ≈ 480 tokens             |
| Choose_vote          | 600            | ≈ 800 tokens             |

---

### 🧮 Simulation de deux cas extrêmes

#### 🧑‍💼 Cas 1 : Joueur très actif (rôle important, parle 4× par jour pendant 7 jours)

- **Entrées (cached input)** :
  `7 jours × 4 interventions × 1 130 tokens = 31 640 tokens`

- **Sorties (réponses LLM)** :
  `7 jours × 4 réponses × 47 tokens = 1 316 tokens`

Coût total estimé :
Input (cached) : (0,5 $ / 1 000 000) × 31 640 = 0,01582 $
Output : (8 $ / 1 000 000) × 1 316 = 0,01053 $
👉 Total ≈ **0,02635 $ ≈ 0,03 $**

---

#### 🧑‍🌾 Cas 2 : Joueur peu actif (villageois, ne parle pas, seulement vote)

- **Entrées (standard input)** :
  `7 jours × 4 appels × 800 tokens = 22 400 tokens`

- **Sorties (réponses LLM)** :
  `7 jours × 4 réponses × 47 tokens = 1 316 tokens`

Coût total estimé :
Input (standard) : (2 $ / 1 000 000) × 22 400 = 0,0448 $
Output : (8 $ / 1 000 000) × 1 316 = 0,01053 $
👉 Total ≈ **0,05533 $ ≈ 0,06 $**

---

Source : https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
         https://platform.openai.com/docs/pricing
---
## Question 2 : Comment évaluer notre modèle
Pour évaluer notre modèle, nous avons observé plusieurs parties jouées par les LLM et analysé leur comportement manuellement. L'évaluation s'est faite en deux volets principaux :

1. Vérification des règles du jeu :
- Le modèle vote uniquement pour des joueurs encore en vie.
- Il respecte les règles (pas d’erreur de phase, de rôle ou de prise de parole).
- Il suit les contraintes du jeu (interruption limitée, cohérence des votes, etc.).

2. Vérification des interactions :
- Les discours sont cohérents et adaptés au contexte de la partie.
- Il ne dit pas de choses fausses (ex. : inventer des votes ou des événements).
- Il adapte son comportement à son rôle (discret s’il est loup, affirmatif s’il est voyante, etc.).

Cette méthode, bien que manuelle, nous a permis d’identifier et corriger de nombreuses incohérences, et d'améliorer progressivement le comportement du modèle.

### Limites de l’évaluation :
Un problème majeur est que tous les joueurs étaient contrôlés par le même type de LLM, ce qui rend difficile de juger la performance réelle du modèle face à d’autres IA ou à des humains. Ainsi, on ne peut pas encore prédire comment il réagirait dans un environnement plus varié ou compétitif.












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






