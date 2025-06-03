from operator import truediv

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

        self.msg_to_say = "" # message à dire lorsque je speak
        self.speech_count_myself = 0


    #When I can speak :
    ##Here add the logic to speak using OpenIA
    def speak(self) -> str:
        self.speech_count_myself += 1
        return self.msg_to_say

    def choose_to_speak_interrupt(self, msg_type: str, intent: Intent):
        alive = ", ".join(self.alive_players)
        roles = ", ".join(f"{k}: {v}" for k, v in self.known_roles.items())
        accusations = ", ".join([p for p, targets in self.accusations.items() if self.name in targets])
        suspicion = ", ".join(f"{p}: {self.vote_tendency[p]}" for p in self.alive_players if p in self.vote_tendency)
        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages[-6:]))
        speech_counts = ", ".join(f"{p}: {self.speech_count.get(p, 0)}" for p in self.alive_players)
        statements = "\n".join(f"{p}: « {lines[-1]} »" for p, lines in self.statements.items() if lines)
        vote_history = ", ".join(f"{voter}→{voted}" for voter, voted in self.vote_history[-5:])
        last_vote = self.last_vote_target or "Aucun"
        speech_count_myself = self.speech_count.get(self.name, 0)
        random_prob = random.randint(0, 2)

        prompt = f"""
        Tu es un joueur du jeu des Loups-Garous de Thiercelieux.

        📍 Situation actuelle : {msg_type}
        🧍 Joueurs encore en vie : {alive}
        ❗ Interruptions restantes : {self.interrupt_count}
        🕵️ Rôles connus : {roles}
        🔍 Niveau de suspicion : {suspicion}
        🗣️ Nombre de fois que chaque joueur a parlé : {speech_counts}
        🧠 Dernières déclarations des autres joueurs :
        {statements}
        🗳️ Historique récent des votes : {vote_history}
        🎯 Mon dernier vote : {last_vote}
        💬 Accusations contre moi : {accusations}
        📩 Derniers messages reçus :
        {messages}
        🗣️ Nombre de fois que MOI j’ai parlé : {speech_count_myself}
        🎲 Probabilité aléatoire pour parler : {random_prob}

        TA TÂCHE :
        - Tu veux survivre et aider ton camp à gagner.
        - Ne répète pas ce que d'autres ont déjà dit dans les messages ou déclarations.
        - Parle si tu as une info, une idée utile.
        - Parle aussi si la probabilité est 0. (uniquement tant que tu n'as pas parlé)
        - Si tu as parlé récemment arrête de parler.
        - Ne parle pas trop : compare combien de fois tu as parlé par rapport aux autres.
        - Tu peux INTERRUPT uniquement si on t'accuse ou si quelqu’un est très suspect, et si tu as encore des interruptions.
        - Sinon, reste SILENCIEUX.
        - N'accuse personne si aucun vote n'a été fait.

        Réponds avec :
        - Uniquement ton message (1 phrase) si tu veux parler.
        - "INTERRUPT: <message>" si tu veux interrompre.
        - "SILENT" si tu ne dis rien.
        """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        if response.startswith("INTERRUPT:") and self.interrupt_count > 0:
            intent.want_to_interrupt = True
            self.msg_to_say = response[len("INTERRUPT:"):].strip()
        elif response.upper() == "SILENT" or response.strip() == "":
            intent.want_to_speak = False
            intent.want_to_interrupt = False
            self.msg_to_say = ""
        else:
            intent.want_to_speak = True
            self.msg_to_say = response.strip()

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
                    - Ne repète pas ce que dise les autres joueurs (sauf si tu veux confirmer qqch)
                    - Si tu es la voyante donne les role et le nom des personne que tu connais
                    -
                    """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        self.last_vote_target = response
        return response

    def display(self):
        print("\n" + "=" * 40)
        print(f"Mon rôle {self.role}")
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
                self.choose_to_speak_interrupt("morning_victim", intent)

            elif msg_type == "morning_no_victim":
                self.choose_to_speak_interrupt("morning_no_victim", intent)

            # VOTE IMMINENT
            elif msg_type == "pre_vote":
                self.choose_to_speak_interrupt("pre_vote", intent)

            elif msg_type == "vote_now":
                intent.vote_for = self.choose_vote()

            # VOTE - PAS DE VICTIME
            elif msg_type == "vote_no_victim":
                self.voted_me_last_round.clear()
                for voter, voted in parsed.get("votes", []):
                    if voted == self.name and voter in self.vote_tendency:
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
                    if voted == self.name and voter in self.vote_tendency:
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
                if self.name in parsed["speech"] and speaker in self.vote_tendency:
                    self.accusations[speaker].add(self.name)
                    self.vote_tendency[speaker] += 1

                # Interruption limitée à 2 fois
                if self.interrupt_count > 0 and random.random() < 0.2:
                    intent.want_to_interrupt = True
                    self.interrupt_count -= 1
                self.choose_to_speak_interrupt("speech", intent)

            # TIMEOUT = élimination
            elif msg_type == "timeout":
                player = parsed.get("player")
                role = parsed.get("role")
                self.remove_player(player, role)
                self.choose_to_speak_interrupt("timeout", intent)

            if self.name == "Aline":
                self.display()

            if intent.want_to_interrupt:
                self.interrupt_count -= 1

            return intent

        except Exception as e:
            import traceback
            print(f"[ERROR] Exception in notify() for {self.name}: {e}")
            traceback.print_exc()
            return Intent()

