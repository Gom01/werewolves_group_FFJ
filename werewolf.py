import openai
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List
import random
import re

from api_key import OPENAI_API_KEY

client = openai.OpenAI(api_key=OPENAI_API_KEY)

PLAYER_NAMES = ["Aline", "Benjamin", "Chloe", "David", "Elise", "Frédéric", "Gabrielle", "Hugo", "Inès", "Julien", "Karine", "Léo", "Manon", "Noé"]
PLAYER_ROLES = ["villageois", "voyante", "loup-garou"]

#This function parse the raw message and then find what are the important informations
def parse_message(message: str) -> dict:
    data = {}
    name_pattern = r"(" + "|".join(PLAYER_NAMES) + ")"
    role_pattern = r"(" + "|".join(PLAYER_ROLES) + ")"

    #Voyante info
    if message.startswith("La Voyante se réveille"):
        data["type"] = "voyante_wakeup"
    elif "Le rôle de " in message:
        m = re.search(rf"Le rôle de {name_pattern} est {role_pattern}", message)
        if m:
            data["type"] = "voyante_result"
            data["player"] = m.group(1)
            data["role"] = m.group(2)

    #Loup garous
    #Wake up but nothing to do
    elif "Les Loups-Garous se réveillent" in message:
        data["type"] = "werewolves_wakeup"
    #Should vote for someone
    elif "Les Loups-Garous votent pour une nouvelle victime" in message:
        data["type"] = "werewolves_vote"
        vote_pattern = rf"{name_pattern} a voté pour {name_pattern}"
        data["werewolves_votes"] = re.findall(vote_pattern, message)  # Returns [] if no votes

    #Night
    elif "C'est la nuit" in message:
        data["type"] = "night_start"
    elif "Cette nuit, " in message and "a été mangé.e" in message:
        m = re.search(rf"Cette nuit, {name_pattern} a été mangé\.e.*rôle était {role_pattern}", message)
        if m:
            data["type"] = "morning_victim"
            data["victim"] = m.group(1)
            data["role"] = m.group(2)
    elif "Cette nuit, personne n'a été mangé.e" in message:
        data["type"] = "morning_no_victim"

    #Starting voting
    elif message.startswith("Le vote va bientôt commencer"):
        data["type"] = "pre_vote"
    elif message.startswith("Il est temps de voter"):
        data["type"] = "vote_now"
    elif "est mort(e) et son rôle était" in message:
        m = re.search(rf"Ainsi, {name_pattern} est mort\(e\) et son rôle était {role_pattern}", message)
        if m:
            data["type"] = "vote_result"
            data["victim"] = m.group(1)
            data["role"] = m.group(2)
        vote_pattern = rf"{name_pattern} a voté pour {name_pattern}"
        data["votes"] = re.findall(vote_pattern, message)
    elif "Il n'y a pas de victime" in message:
        data["type"] = "vote_no_victim"
    elif " a dit: " in message:
        m = re.match(rf"{name_pattern} a dit: (.+)", message)
        if m:
            data["type"] = "speech"
            data["speaker"] = m.group(1)
            data["speech"] = m.group(2)
    elif "n'a pas répondu à temps" in message:
        m = re.match(rf"{name_pattern} n'a pas répondu à temps", message)
        if m:
            data["type"] = "timeout"
            data["player"] = m.group(1)
    return data


class Intent(BaseModel):
    want_to_speak: bool = False
    want_to_interrupt: bool = False
    vote_for: str = None


class WerewolfPlayerInterface(ABC):

    @classmethod
    def create(cls, name: str, role: str, players_names: List[str], werewolves_count: int,
               werewolves: List[str]) -> 'WerewolfPlayerInterface':
        return cls(name, role, players_names, werewolves_count, werewolves)

    @abstractmethod
    def speak(self) -> str:
        pass

    @abstractmethod
    def notify(self, message: str) -> Intent:
        pass


class WerewolfPlayer(WerewolfPlayerInterface):
    rules = """"
           Bienvenue dans LLMs-Garous, une version adaptée du jeu "Les Loups-Garous de Thiercelieux".

           🎯 Objectif :
           - Il y a 7 joueurs : 2 loups-garous, 1 voyante, 4 villageois.
           - Les loups-garous doivent éliminer tous les villageois et la voyante.
           - Les villageois et la voyante doivent identifier et éliminer les loups-garous.

           🕓 Déroulement d’un tour :
           Le jeu alterne entre deux phases : la nuit et le jour.

           🌙 Phase de nuit :
           - Le meneur annonce "C'est la nuit, tout le village s'endort, les joueurs ferment les yeux."
           - Les loups-garous se réveillent, se reconnaissent et votent pour une victime.
           - La voyante se réveille et peut sonder un joueur pour connaître son rôle.
           - Les villageois dorment et ne font rien.

           🌞 Phase de jour :
           - Le meneur annonce le résultat de la nuit : s’il y a une victime et son rôle.
           - Les joueurs prennent la parole, s’accusent, défendent ou se taisent.
           - Chaque joueur peut :
               - demander à parler
               - interrompre quelqu’un (max 2 fois par partie, peut être refusé par le meneur)
               - voter pendant la phase de vote
           - Après les discussions, un vote a lieu. Le joueur ayant le plus de votes est éliminé (en cas d’égalité : personne n’est éliminé).
           - Le rôle du joueur éliminé est révélé.

           🗣️ Gestion de la parole :
           - Le meneur accorde la parole à ceux qui la demandent.
           - Les joueurs silencieux depuis plusieurs tours ont plus de chances d’être sélectionnés.
           - Un même joueur ne peut pas parler deux fois de suite.

           Ton but en tant que joueur est de survivre le plus longtemps possible... ou de faire gagner ton camp.
           """

    #This code is exectuted only at the beginning of the game
    def __init__(self, name: str, role: str, players_names: List[str], werewolves_count: int, werewolves: List[str]) -> None:
        #Basics informations
        self.name = name
        self.role = role
        self.players_names = players_names
        self.werewolves_count = werewolves_count
        self.werewolves = werewolves

        #Updated informations
        self.messages = []
        self.alive_players = set(players_names) - {self.name}
        self.vote_history = []  # list of (voter, voted)
        self.known_roles = {}   # player -> role
        self.speech_count = {p: 0 for p in players_names if p != self.name}
        self.statements = {p: [] for p in players_names if p != self.name}

        if self.name == "Aline":
            print(f"Beggining of the game :"
                  f"-name: {self.name}\n"
                  f"-role: {self.role}\n"
                  f"-other player : {self.alive_players}\n"
                  f"-num of loup-garous: {self.werewolves_count}\n"
                  f"-names of loup-garous {self.werewolves}\n")
            print()

    #When I can speak :
    ##Here add the logic to speak using OpenIA
    def speak(self) -> str:

        # TODO : Print information + supprimer le je demande la parole !
        # TODO : Voyante : dire qui est quoi !

        print(f"{self.name} is given the floor")
        messages_with_index = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive_players_str = ", ".join(self.alive_players)
        wolves_str = ", ".join(self.werewolves)
        PROMPT = f"""    CONTEXTE :    Voici notre jeu et ses règles : {self.rules}.
                Tu es un joueur de ce jeu.    
                Voici ton nom : {self.name}.
                Voici ton rôle : {self.role}.
                Voici Les rôles connu : {self.known_roles}. 
                Voici l'historique des votes : {self.vote_history}.
                Voici les noms des autres joueurs encore dans la partie : {alive_players_str}.
                Voici le nombre de loups-garous au début de la partie : {self.werewolves_count}.    
                Si tu as le rôle de "loup-garou", voici la liste du ou des autres "loups-garous" : {wolves_str}.    
                Voici l'historique des messages depuis le début du jeu :    {messages_with_index}    
                TA TÂCHE :    
                    - Si tu es un "loup-garou", tu ne dois pas te révéler !    
                    - Tu peux mentir pour gagner !    
                    - Nombre de mots maximum pour la réponse : 1000 mots
                    - Selon le context, défend toi ou attaque.
                    - Soit très bref dans tes réponses
        """

        response = client.chat.completions.create(model="gpt-4.1", messages=[{"role": "user", "content": PROMPT}]).choices[0].message.content

        self.messages.append(f"{self.name} a dit : " + response)

        return response


    def choose_vote(self) -> str:  # Florian

        messages_with_index = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive_players_str = ", ".join(self.alive_players)
        wolves_str = ", ".join(self.werewolves)

        PROMPT = f"""    CONTEXTE :    Voici notre jeu et ses règles : {self.rules}.
                Tu es un joueur de ce jeu.    
                Voici ton nom : {self.name}.
                Voici ton rôle : {self.role}.
                Voici Les rôles connu : {self.known_roles}. 
                Voici l'historique des votes : {self.vote_history}.
                Voici les noms des autres joueurs encore dans la partie : {alive_players_str}.
                Voici le nombre de loups-garous au début de la partie : {self.werewolves_count}.    
                Si tu as le rôle de "loup-garou", voici la liste du ou des autres "loups-garous" : {wolves_str}.    
                Voici l'historique des messages depuis le début du jeu :    {messages_with_index}    
                TA TÂCHE :    
                    Donne moi uniquement le nom du joueur que tu veux éliminer
        """

        response = client.chat.completions.create(model="gpt-4.1", messages=[{"role": "user", "content": PROMPT}]).choices[0].message.content

        return response

    def choose_vote_voyante(self) -> str:  # Josh

        messages_with_index = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive_players_str = ", ".join(self.alive_players)
        wolves_str = ", ".join(self.werewolves)

        PROMPT = f"""    
                CONTEXTE :    Voici notre jeu et ses règles : {self.rules}.
                Voici ton nom : {self.name}.
                Voici ton rôle : {self.role}.
                Voici Les rôles connu : {self.known_roles}. 
                Voici l'historique des votes : {self.vote_history}.
                Voici les noms des autres joueurs encore dans la partie : {alive_players_str}.
                Voici le nombre de loups-garous au début de la partie : {self.werewolves_count}.
                Voici l'historique des messages depuis le début du jeu : {messages_with_index}
                TA TÂCHE :
                    D'après l'historique des messages, trouve le joueur le plus suspect dont tu ne connais pas le rôle
                    puis donne moi uniquement son nom.
                    
        """

        # DEBUG : et explique moi pourquoi ce joueur

        response = client.chat.completions.create(model="gpt-4.1", messages=[{"role": "user", "content": PROMPT}]).choices[0].message.content

        return response

    def choose_vote_wolf(self) -> str: # Flavien

        messages_with_index = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive_players_str = ", ".join(self.alive_players)
        wolves_str = ", ".join(self.werewolves)

        PROMPT = f"""    CONTEXTE :    Voici notre jeu et ses règles : {self.rules}.
                Tu es un joueur de ce jeu.    
                Voici ton nom : {self.name}.
                Voici ton rôle : {self.role}.
                Voici Les rôles connu : {self.known_roles}. 
                Voici l'historique des votes : {self.vote_history}.
                Voici les noms des autres joueurs encore dans la partie : {alive_players_str}.
                Voici le nombre de loups-garous au début de la partie : {self.werewolves_count}.    
                Si tu as le rôle de "loup-garou", voici la liste du ou des autres "loups-garous" : {wolves_str}.    
                Voici l'historique des messages depuis le début du jeu :    {messages_with_index}    
                TA TÂCHE :    
                    Si tu es le premier loup à voter, donne moi uniquement de nom de la victime
                    Sinon, donne moi uniquement le nom d'une victime déjà voté dans cette nuit.
                    
        """



        response = client.chat.completions.create(model="gpt-4.1", messages=[{"role": "user", "content": PROMPT}]).choices[0].message.content

        return response


    #If dead remove the player
    def remove_player(self, player: str, role: str):
        self.alive_players.discard(player)
        self.known_roles[player] = role
        self.speech_count.pop(player, None)
        self.statements.pop(player, None)
        self.vote_history = [(voter, voted) for (voter, voted) in self.vote_history if
                             voter != player and voted != player]

    # When receiving a message from the game master
    def notify(self, message: str) -> Intent:
        try:
            if self.name == "Aline":
                print("I have been notified...")

            self.messages.append(message)
            intent = Intent()
            parsed = parse_message(message)
            msg_type = parsed.get("type")

            #VOYANTE
            #Voyante vote for a random person (must return intent.vote_for)
            if msg_type == "voyante_wakeup" and self.role == "voyante":
                if self.name == "Aline":
                    print(f"I'm the voyante and I can find out the role of a person")
                intent.vote_for = self.choose_vote_voyante()

            #Voyante get the role from the other player
            elif msg_type == "voyante_result":
                self.known_roles[parsed["player"]] = parsed["role"]
                if self.name == "Aline":
                    print(f"I learned the role of this player : {parsed['player']} role : {parsed['role']}")

            #LOUP GAROUS
            #Loup garou vote for a random person
            elif msg_type == "werewolves_vote" and self.role == "loup-garou":
                eligible = list(self.alive_players - set(self.werewolves) - {self.name})
                if self.name == "Aline":
                    print(f"I can vote only for : {eligible}")

                intent.vote_for = self.choose_vote_wolf()

            #End of the night morning victim
            elif msg_type == "morning_victim":
                victim = parsed.get("victim")
                role = parsed.get("role")
                if victim and role:
                    self.remove_player(victim, role)
                    if self.name == "Aline":
                        print(f"{victim} was killed with the role of {role}")
                intent.want_to_speak = False

            elif msg_type == "morning_no_victim":
                if self.name == "Aline":
                    print("Nobody died this morning")
                intent.want_to_speak = False

            #Voting
            elif msg_type == "pre_vote":
                if self.name == "Aline":
                    print("I can speak or interrupt we are voting")
                intent.want_to_speak = True

            elif msg_type == "vote_now":
                intent.vote_for = self.choose_vote()

            elif msg_type == "vote_no_victim":
                if self.name == "Aline":
                    print("No victim after the vote")

            elif msg_type == "vote_result":
                victim = parsed.get("victim")
                role = parsed.get("role")
                if victim and role:
                    self.remove_player(victim, role)
                    if self.name == "Aline":
                        print(f"{victim} was killed role {role}")
                for voter, voted in parsed.get("votes", []):
                    if voter != self.name:  # Ne pas enregistrer son propre vote
                        self.vote_history.append((voter, voted))
                        if self.name == "Aline":
                            print(f"Added vote: {voter} -> {voted}")
                    elif self.name == "Aline":
                        print(f"Ignored my own vote: {voter} -> {voted}")

            elif msg_type == "speech":
                        speaker = parsed["speaker"]
                        self.speech_count[speaker] += 1
                        self.statements[speaker].append(parsed["speech"])
                        intent.want_to_interrupt = random.random() < 0.2

            elif msg_type == "timeout":
                intent.want_to_speak = False


            if self.name == "Aline":
                print("Turn infos : ")
                print(self.messages)
                print(self.alive_players)
                print(self.vote_history)
                print(self.known_roles)
                print(self.speech_count)
                print(self.statements)
                print()


            return intent
        except Exception as e:
            import traceback
            print(f"[ERROR] Exception in notify() for {self.name}: {e}")
            traceback.print_exc()
            return Intent()  # safe fallback
