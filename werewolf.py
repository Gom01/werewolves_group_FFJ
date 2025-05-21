import os

import openai
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List
import random
import re

# Initialise un client
import openai
from api_key import OPENAI_API_KEY

client = openai.OpenAI(api_key=OPENAI_API_KEY)


class Intent(BaseModel):
    want_to_speak:bool = False
    want_to_interrupt:bool = False
    vote_for:str = None


class WerewolfPlayerInterface(ABC):

    @classmethod
    def create(cls, name: str, role: str, players_names: List[str], werewolves_count: int, werewolves: List[str]) -> 'WerewolfPlayerInterface':
        return cls(name, role, players_names, werewolves_count, werewolves)

    @abstractmethod
    def speak(self) -> str:
        """Generate a response when it's the player's turn to speak."""
        pass

    @abstractmethod
    def notify(self, message: str) -> Intent:
        """Process a notification and determine the player's intent."""
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

    def __init__(self, name: str, role: str, players_names: List[str], werewolves_count: int, werewolves: List[str]) -> None:
        self.name = name
        print(f"WerewolfPlayer {self.name} created")

        beginning_prompt = (""
                            f"Ton role est : {role}"
                            f"Les noms des joueurs sont : {players_names}"
                            f"Il y a {werewolves_count} loup-garou dans cette partie"
                            f"Si ton role est loup-garou les autres loup-garous sont : {werewolves}")

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": beginning_prompt}
            ])

        self.messages = []
        self.playerRest = players_names


    def speak(self) -> str:
        """
        Appelé par le meneur pour donner la parole à un joueur.
        Le joueur doit alors prendre la parole dans le jeu. 
    
        Args:
            Aucun paramètre n'est passé; c'est au joueur de déduire le contexte uniquement depuis ce qu'il a reçu précédemment via notify().
        
        Returns:
            speech: Un message contenant le texte que le joueur dit, par exemple "Je crois que Aline ment car ..."
            Un joueur peut décider de ne pas parler (retourner un `speech` vide)
            
        """
        print(f"{self.name} is given the floor")
        messages_with_index = "\n".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        players_str = ", ".join(self.players_names)
        wolves_str = ", ".join(self.werewolves)

        PROMPT = f"""
        CONTEXTE :\n
        Voici notre jeu et ses règles : {rules}.\n
        Tu es un joueur de ce jeu.\n
        Voici ton nom : {self.name}.\n
        Voici ton rôle : {self.role}.\n
        Voici les noms des autres joueurs au début de la partie : {players_str}.\n
        Voici le nombre de loups au début de la partie : {self.werewolves_count}.\n
        Si tu as le rôle de "loup-garou" , voici la liste des autres : {wolves_str}.\n
        Voici l'historique des messages depuis le début du Jeu :\n
        {messages_with_index}\n
        
        TA TACHE :\n
        Tu dois soit répondre ou ne pas répondre. Tu as 5 secondes au maximum, pour réfléchir et répondre. 
        Ton objectif est de c
    
        """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": PROMPT}
            ])
        # TODO implement me
        return ""


    def notify(self, message: str) -> Intent:
        """
        Appelé par le meneur pour deux objectifs principaux:
    
        1. Informer le joueur sur l'état du jeu:
           - Qui a parlé et ce qui a été dit
           - Si c'est la nuit
           - Les rumeurs
           - Si c'est le moment de voter
           - Le résultat du vote (qui a été éliminé et son rôle)
           - Autres informations pertinentes sur l'état du jeu
    
        Le message est **sous forme de texte uniquement** et c'est au joueur de l'interpréter en fonction du contexte.
        Le message contient uniquement le dernier (nouveau) message du meneur, c'est au joueur de mémoriser les informations des messages précédents.
        
        2. Recevoir en retour les intentions du joueur:
           - Demande de prise de parole
           - Demande d'interruption
           - Vote
    
        La réponse suivra **strictement le schéma** ci-dessous, sans quoi elle sera ignorée par le meneur.
        
        Args:
            message: "C'est le matin, le village se réveille. Aline a été tuée cette nuit. Aline était une villageoise."
        
        Returns:
            Une Intent (voir la classe ci-dessus l. 8) contenant les actions du joueur. Schéma:
                want_to_speak: True | False,
                want_to_interrupt: True | False,
                vote_for: "Aline" | "Benjamin" | ... | None

        """
        print(f"{self.name} received message: {message}")
        # TODO implement me

        self.messages.append("[Meneur de jeu] " + message)


        # donne le nom de la personne la plus suspect dans la liste
        PROMPT = f"""
        
        Par rapport au message, voici toutes les actions possible. Il est possible d'en faire plusieurs à la fois.
        
        1) Si un joueur est mort, dit son nom.
        EXEMPLE : 
            Meneur de jeu : "Aline est mort"
            Toi : "mort:Aline"
            
        2) Si c'est le moment de voter, donne un nom aléatoire dans la liste {self.playerRest}.
        Tu ne peux pas voter pour toi-même.
        EXEMPLE : 
            Meneur de jeu : "Il est temps de voter"
            Toi : "vote:David"
            
        3) Si c'est le résultat du vote, donne le nom de la victime et son rôle.
        EXEMPLE:
            Meneur du jeu : "Ainsi, Frédéric est mort et son rôle était villageois"
        
        """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": PROMPT }
            ]).choices[0].message.content

        if "mort" in response:
            self.playerRest.remove(response.split(":")[1])

        self.messages.append(f"[{self.name}] " + response)

        return Intent(want_to_speak=False, want_to_interrupt=False, vote_for="")
