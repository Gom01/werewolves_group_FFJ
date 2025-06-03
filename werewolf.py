import openai
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import List
import random
import re
from api_key import OPENAI_API_KEY

#API KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)
PLAYER_NAMES = ["Aline", "Benjamin", "Chloe", "David", "Elise", "Frédéric", "Gabrielle", "Hugo", "Inès", "Julien", "Karine", "Léo", "Manon", "Noé"]
PLAYER_ROLES = ["villageois", "voyante", "loup-garou"]


#This function parse the raw message and then find what are the important information (convert them inside a dictionnary)
def parse_message(message: str) -> dict:
    data = {}
    name_pattern = r"(" + "|".join(PLAYER_NAMES) + ")"
    role_pattern = r"(" + "|".join(PLAYER_ROLES) + ")"

    #Voyante
    if message.startswith("La Voyante se réveille"):
        data["type"] = "voyante_wakeup"
    elif message.startswith("Le rôle de"):
        m = re.match(rf"Le rôle de {name_pattern} est {role_pattern}", message)
        if m:
            data["type"] = "voyante_result"
            data["player"] = m.group(1)
            data["role"] = m.group(2)

    #Loup garous
    elif "Les Loups-Garous se réveillent" in message:
        data["type"] = "werewolves_wakeup"
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
        vote_pattern = rf"{name_pattern} a voté pour {name_pattern}"
        data["votes"] = re.findall(vote_pattern, message)
    elif " a dit: " in message:
        m = re.match(rf"{name_pattern} a dit: (.+)", message)
        if m:
            data["type"] = "speech"
            data["speaker"] = m.group(1)
            data["speech"] = m.group(2)
    elif "n'a pas répondu à temps" in message:
        m = re.match(rf"({name_pattern}) avec le rôle ({role_pattern}) n’a pas répondu à temps", message)
        if m:
            data["type"] = "timeout"
            data["player"] = m.group(1)
            data["role"] = m.group(2)
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


        self.messages = []
        self.last_wolf_votes = []
        self.alive_players = set(players_names) - {self.name}
        self.vote_history = []  # list of (voter, voted)
        self.known_roles = {}  # player -> role
        self.speech_count = {p: 0 for p in players_names if p != self.name}
        self.statements = {p: [] for p in players_names if p != self.name} # liste de ce que le joueur dit
        self.interrupt_count = 2  # interruptions restantes autorisées
        self.accusations = {p: set() for p in players_names if p != self.name}  # qui accuse qui
        self.vote_tendency = {p: 0 for p in players_names if p != self.name}  # niveau de suspicion
        self.voted_me_last_round = set()  # pour stocker les gens qui ont voté contre moi au dernier tour
        self.last_vote_target = None  # pour éviter de voter 2x le même


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

    def choose_vote(self) -> str:
        unknown_or_suspects = [p for p in self.alive_players if p not in self.known_roles]
        suspicion = ", ".join(f"{p}: {self.vote_tendency[p]}" for p in unknown_or_suspects)
        recent_attackers = ", ".join(self.voted_me_last_round)
        accusers = ", ".join([p for p in unknown_or_suspects if self.name in self.accusations.get(p, set())])
        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive = ", ".join(self.alive_players)

        vote_freq = {}
        for _, voted in self.vote_history:
            if voted in unknown_or_suspects:
                vote_freq[voted] = vote_freq.get(voted, 0) + 1
        vote_trends = ", ".join(f"{p}: {vote_freq[p]}" for p in sorted(vote_freq, key=vote_freq.get, reverse=True))

        prompt = f"""
                Tu es un joueur villageois dans le jeu des Loups-Garous de Thiercelieux.
            
                Voici les joueurs encore en vie : {alive}.
                Voici ceux dont tu ne connais pas encore le rôle : {', '.join(unknown_or_suspects)}.
                Niveaux de suspicion : {suspicion}.
                T'ont accusé : {accusers}.
                Ont voté contre toi : {recent_attackers}.
                Fréquence à laquelle chaque joueur a été visé par les votes précédents : {vote_trends}.
                Messages précédents : {messages}
            
                TA TÂCHE :
                - Choisis une cible à voter contre.
                - Essaie d'éviter de voter plusieurs fois d'affilée pour la même personne sans bonne raison.
                - Tiens compte des joueurs qui ont déjà été souvent visés (ou au contraire jamais).
                - Donne UNIQUEMENT le nom du joueur choisi.
                """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        # Optionnel : empêcher le vote pour la même personne trois fois d'affilée
        if response == self.last_vote_target:
            alternatives = [p for p in unknown_or_suspects if p != response]
            if alternatives:
                response = random.choice(alternatives)

        self.last_vote_target = response
        return response

    def choose_vote_voyante(self) -> str:
        unknown_players = [p for p in self.alive_players if p not in self.known_roles]
        suspicion = ", ".join(f"{p}: {self.vote_tendency[p]}" for p in unknown_players)
        accusers = ", ".join([p for p in unknown_players if self.name in self.accusations.get(p, set())])
        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive = ", ".join(self.alive_players)

        prompt = f"""
            Tu es la voyante dans une partie de Loups-Garous de Thiercelieux.
        
            Voici les joueurs encore en vie : {alive}.
            Voici les joueurs dont tu NE connais PAS le rôle : {', '.join(unknown_players)}.
            Voici le niveau de suspicion actuel : {suspicion}.
            Voici ceux qui t'ont accusée : {accusers}.
            Messages échangés : {messages}
        
            TA TÂCHE :
            - Choisis une cible à sonder cette nuit parmi ceux dont tu ignores encore le rôle.
            - Priorise les joueurs suspects ou hostiles envers toi.
            - Donne UNIQUEMENT le nom du joueur que tu veux sonder.
            """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        return response

    def choose_vote_wolf(self) -> str:
        eligible_targets = list(self.alive_players - set(self.werewolves) - {self.name})
        wolf_votes = self.last_wolf_votes

        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive = ", ".join(self.alive_players)
        wolves = ", ".join(self.werewolves)
        suspicion = ", ".join(f"{p}: {self.vote_tendency[p]}" for p in eligible_targets)
        recent_attackers = ", ".join(self.voted_me_last_round)
        accusers = ", ".join([p for p in eligible_targets if self.name in self.accusations.get(p, set())])

        if not wolf_votes:
            prompt = f"""
                    Tu es un loup-garou. 
                    Joueurs en vie : {alive}. 
                    Loups : {wolves}. 
                    Niveau de suspicion : {suspicion}.
                    Ont voté contre toi : {recent_attackers}.
                    T'ont accusé dans leurs discours : {accusers}.
                    Messages : {messages}.
                
                    TA TÂCHE :
                    - Choisis une cible parmi les non-loups.
                    - Donne la priorité aux joueurs les plus hostiles envers toi ou les plus suspects.
                    - Donne UNIQUEMENT le nom du joueur que tu veux éliminer.
                    """
        else:
            votes = ", ".join(f"{v} → {t}" for v, t in wolf_votes)
            prompt = f"""
                    Tu es un loup-garou. 
                    Joueurs en vie : {alive}. 
                    Loups : {wolves}. 
                    Votes déjà faits : {votes}. 
                    Ton vote précédent : {self.last_vote_target}.
                    Ont voté contre toi : {recent_attackers}.
                    T'ont accusé : {accusers}.
                    Messages : {messages}.
                
                    TA TÂCHE :
                    - Essaie de coordonner le vote avec les autres loups.
                    - Garde ta cible précédente si elle est populaire.
                    - Sinon, vote pour celle qui est la plus souvent ciblée.
                    - Donne UNIQUEMENT le nom d'un joueur.
                    """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        self.last_vote_target = response
        return response

    def display(self):
        print("\n" + "=" * 40)
        print(f"🔄  INFOS DU TOUR POUR : {self.name.upper()}  🔄")
        print("=" * 40)
        print("\n📩 Messages reçus :")
        for i, msg in enumerate(self.messages[-5:]):
            print(f"[{i}] {msg}")
        print("\n🧍 Joueurs encore en vie :", ", ".join(self.alive_players))
        print("\n🗳️ Historique des votes :")
        for voter, voted in self.vote_history[-5:]:
            print(f"- {voter} a voté pour {voted}")
        print("\n🕵️ Rôles connus :")
        for player, role in self.known_roles.items():
            print(f"- {player} : {role}")
        print("\n📢 Nombre de prises de parole :")
        for player, count in self.speech_count.items():
            print(f"- {player} : {count} fois")
        print("\n💬 Dernières déclarations (1 par joueur) :")
        for player, statements in self.statements.items():
            if statements:
                print(f"- {player} : « {statements[-1]} »")
        print("\n🧠 Vote_tendency (suspicions) :")
        for player, score in sorted(self.vote_tendency.items(), key=lambda x: -x[1]):
            print(f"- {player} : {score}")
        print("\n🗯️ Accusations contre moi :")
        accusers = [p for p, targets in self.accusations.items() if self.name in targets]
        print(", ".join(accusers) if accusers else "Personne")
        print(f"\n🔂 Mon dernier vote ciblait : {self.last_vote_target}")
        print(f"🚨 Loups : {', '.join(self.werewolves)}")
        print(f"❗ Interruptions restantes : {self.interrupt_count}")
        print("=" * 40 + "\n")
        return

    #If dead remove the player
    def remove_player(self, player: str, role: str):
        self.alive_players.discard(player)
        self.known_roles[player] = role
        self.speech_count.pop(player, None)
        self.statements.pop(player, None)
        self.vote_history = [(voter, voted) for (voter, voted) in self.vote_history if voter != player and voted != player]
        self.vote_tendency.pop(player, None)
        self.accusations.pop(player, None)
        self.voted_me_last_round.discard(player)
        if self.last_vote_target == player:
            self.last_vote_target = None

    #All possible actions when getting a message from the game master
    def notify(self, message: str) -> Intent:
        try:
            self.messages.append(message)
            intent = Intent()
            parsed = parse_message(message)
            msg_type = parsed.get("type")


            # VOYANTE
            if msg_type == "voyante_wakeup" and self.role == "voyante":
                intent.vote_for = self.choose_vote_voyante()

            elif msg_type == "voyante_result":
                self.known_roles[parsed["player"]] = parsed["role"]

            # LOUP-GAROU
            elif msg_type == "werewolves_vote" and self.role == "loup-garou":
                self.last_wolf_votes = parsed.get("werewolves_votes", [])
                intent.vote_for = self.choose_vote_wolf()

            elif msg_type == "werewolves_wakeup":
                return intent  # rien à faire

            # PHASE DE NUIT
            elif msg_type == "night_start":
                return intent  # rien à faire

            # RÉSULTATS DE LA NUIT
            elif msg_type == "morning_victim":
                victim = parsed.get("victim")
                role = parsed.get("role")
                self.remove_player(victim, role)
                # TODO : peut parler ou interrompre

            elif msg_type == "morning_no_victim":
                # TODO : peut parler ou interrompre
                pass

            # VOTE IMMINENT
            elif msg_type == "pre_vote":
                # TODO : peut parler ou interrompre
                pass

            elif msg_type == "vote_now":
                intent.vote_for = self.choose_vote()

            # VOTE - PAS DE VICTIME
            elif msg_type == "vote_no_victim":
                self.voted_me_last_round.clear()
                for voter, voted in parsed.get("votes", []):
                    if voted == self.name:
                        self.voted_me_last_round.add(voter)
                        self.vote_tendency[voter] += 1
                    if voter != self.name:
                        self.vote_history.append((voter, voted))

            # VOTE - VICTIME ÉLIMINÉE
            elif msg_type == "vote_result":
                victim = parsed.get("victim")
                role = parsed.get("role")
                self.remove_player(victim, role)
                self.voted_me_last_round.clear()
                for voter, voted in parsed.get("votes", []):
                    if voted == self.name:
                        self.voted_me_last_round.add(voter)
                        self.vote_tendency[voter] += 1
                    if voter != self.name:
                        self.vote_history.append((voter, voted))

            # PRISE DE PAROLE
            elif msg_type == "speech":
                speaker = parsed["speaker"]
                self.speech_count[speaker] += 1
                self.statements[speaker].append(parsed["speech"])

                # Détection d’accusation contre soi
                if self.name in parsed["speech"]:
                    self.accusations[speaker].add(self.name)
                    self.vote_tendency[speaker] += 1

                # Interruption limitée à 2 fois
                if self.interrupt_count > 0 and random.random() < 0.2:
                    intent.want_to_interrupt = True
                    self.interrupt_count -= 1
                # TODO : peut parler ou interrompre

            # TIMEOUT = élimination
            elif msg_type == "timeout":
                player = parsed.get("player")
                role = parsed.get("role")
                self.remove_player(player, role)
                # TODO : peut parler ou interrompre

            if self.name == "Aline":
                self.display()

            return intent

        except Exception as e:
            import traceback
            print(f"[ERROR] Exception in notify() for {self.name}: {e}")
            traceback.print_exc()
            return Intent()

