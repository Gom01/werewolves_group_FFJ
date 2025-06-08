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

#Rules for caching
rules = """"
       Tu joues à "LLMs-Garous", une adaptation LLM du jeu Les Loups-Garous de Thiercelieux.
        🎯 Objectif :
        - 14 joueurs : 3 loups-garous, 1 voyante, 10 villageois.
        - Loups-garous : éliminer tous les villageois et la voyante.
        - Villageois + voyante : identifier et éliminer les loups-garous.
        
        🕓 Déroulement des tours :
        Chaque tour comporte deux phases : nuit et jour.
        
        🌙 Nuit :
        - Meneur : "C’est la nuit, tout le village s’endort."
        - Loups-garous se réveillent, se reconnaissent, votent une victime.
        - Voyante se réveille et peut sonder un joueur.
        - Villageois dorment.
        
        🌞 Jour :
        - Meneur annonce la victime et son rôle.
        - Il peut diffuser des rumeurs (vraies ou fausses).
        - Les joueurs discutent, accusent, défendent ou se taisent.
        - Actions possibles : demander à parler, interrompre (max 2 fois), voter.
        - Vote final : le joueur avec le plus de voix est éliminé (égalité = personne).
        - Le rôle du joueur éliminé est révélé.
        
        🗣️ Règles de parole :
        - Le meneur distribue la parole (favorise ceux qui n’ont pas parlé récemment).
        - Un joueur ne peut pas parler deux fois de suite.
        
        ℹ️ Infos importantes :
        - Tous les joueurs sont des GPT.
        - Tu peux mentir.
        - Ton but est de faire gagner ton camp.
       """

#This function parse the raw message (given by the game leader) and find the important informations
def parse_message(message: str) -> dict:
    data = {}
    name_pattern = r"(" + "|".join(PLAYER_NAMES) + ")"
    role_pattern = r"(" + "|".join(PLAYER_ROLES) + ")"

    # Voyante
    if message.startswith("La Voyante se réveille"):
        data["type"] = "voyante_wakeup"
    elif message.startswith("Le rôle de"):
        m = re.match(rf"Le rôle de {name_pattern} est {role_pattern}", message)
        if m:
            data["type"] = "voyante_result"
            data["player"] = m.group(1)
            data["role"] = m.group(2)

    # Loups-garous
    elif "Les Loups-Garous se réveillent" in message:
        data["type"] = "werewolves_wakeup"
    elif "Les Loups-Garous votent pour une nouvelle victime" in message:
        data["type"] = "werewolves_vote"
        vote_pattern = rf"{name_pattern} a voté pour {name_pattern}"
        data["werewolves_votes"] = re.findall(vote_pattern, message)

    # Nuit
    elif "C'est la nuit" in message:
        data["type"] = "night_start"
    elif "Cette nuit, personne n'a été mangé.e" in message:
        m = re.search(r"Cette nuit, personne n'a été mangé\.e par les loups‑garous\.\s*(.*)", message)
        data["type"] = "morning_no_victim"
        rumor_text = m.group(1).strip() if m and m.group(1) else ""
        if rumor_text:
            data["rumor"] = rumor_text # type: ignore
    elif "Cette nuit, " in message and "a été mangé.e" in message:
        m = re.search(rf"Cette nuit, {name_pattern} a été mangé\.e par les loups‑garous\. Son rôle était {role_pattern}\.\s*(.*)", message)
        if m:
            data["type"] = "morning_victim"
            data["victim"] = m.group(1)
            data["role"] = m.group(2)
            rumor_text = m.group(3).strip()
            if rumor_text:
                data["rumor"] = rumor_text

    # Vote
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

    # Discours
    elif " a dit: " in message:
        m = re.match(rf"{name_pattern} a dit: (.+)", message)
        if m:
            data["type"] = "speech"
            data["speaker"] = m.group(1)
            data["speech"] = m.group(2)

    # Timeout
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
        #Information about myself and my role
        self.name = name
        self.role = role
        self.players_names = players_names
        self.werewolves_count = werewolves_count
        self.werewolves = werewolves

        #Information updated during the game
        self.messages = []
        self.last_wolf_votes = [] #votes des loup-garous
        self.alive_players = set(players_names) - {self.name}
        self.dead_players = []
        self.vote_history = []  # list of (voter, voted)
        self.known_roles = {}  # player -> role
        self.speech_count = {p: 0 for p in players_names if p != self.name}
        self.statements = {p: [] for p in players_names if p != self.name} # liste de ce que le joueur dit
        self.interrupt_count = 2  # interruptions restantes autorisées
        self.accusations = {p: set() for p in players_names if p != self.name}  # qui accuse qui
        self.voted_me_last_round = set()  # pour stocker les gens qui ont voté contre moi au dernier tour
        self.last_vote_target = None  # pour éviter de voter 2x le même
        self.msg_to_say = "" # message à dire lorsque je speak
        self.speech_count_myself = 0
        self.last_rumor = ""  # dernière rumeur prononcée par le meneur
        self.my_actions = []  # ex: [('speak', message), ('vote', 'Alice')]
        self.suspected_werewolves = set()
        self.suspected_villagers = set()

    #This function say the last message written in msg_to_say
    def speak(self) -> str:
        self.speech_count_myself += 1
        self.my_actions.append(("speak", self.msg_to_say))
        return self.msg_to_say

    def choose_to_speak_interrupt(self, msg_type: str, intent: Intent):
        # Formatage des infos de jeu
        alive = ", ".join(sorted(self.alive_players))
        dead = ", ".join(sorted(self.dead_players))
        roles = ", ".join(f"{k}: {v}" for k, v in self.known_roles.items())
        accusations_against_me = ", ".join([p for p, targets in self.accusations.items() if self.name in targets])
        last_votes = ", ".join(f"{voter}→{voted}" for voter, voted in self.vote_history[-5:])
        voted_me = ", ".join(self.voted_me_last_round)
        wolf_votes = ", ".join(f"{voter}→{voted}" for voter, voted in self.last_wolf_votes)
        speech_counts = ", ".join(f"{p}: {self.speech_count.get(p, 0)}" for p in self.players_names if p != self.name)
        statements = "\n".join(f"{p}: « {lines[-1]} »" for p, lines in self.statements.items() if lines)
        messages = "\n".join(f"[{i}] {line}" for i, line in enumerate(self.messages[-5:]))
        my_actions = ", ".join(f"{action}({target})" for action, target in self.my_actions[-5:])
        suspected_wolves = ", ".join(self.suspected_werewolves)
        trusted_players = ", ".join(self.suspected_villagers)
        last_vote = self.last_vote_target or "Aucun"
        if last_vote in dead : "Aucun"
        last_rumor = self.last_rumor or "Aucune"
        random_prob = random.randint(0, 3)

        # 🎯 Prompt enrichi
        prompt = f"""
            {rules}
            🎮 CONTEXTE DU JOUEUR :
            - Nom : {self.name}
            - Rôle : {self.role}
            - Phase actuelle (type de message) : {msg_type}
        
            🧍 JOUEURS :
            - Vivants : {alive}
            - Morts : {dead}
            - Rôles connus (par voyante ou élimination) : {roles}
        
            🗳️ VOTES :
            - Derniers votes (jour) : {last_votes}
            - Joueurs qui ont voté contre moi au dernier tour : {voted_me}
            - Mon dernier vote : {last_vote}
        
            📣 COMMUNICATION :
            - Nombre de fois que chaque joueur a parlé : {speech_counts}
            - Nombre de fois que moi j’ai parlé : {self.speech_count_myself}
            - Derniers messages du meneur : {messages}
            - Dernières déclarations par joueur : {statements}
        
            🔍 INTERACTIONS :
            - Accusations contre moi : {accusations_against_me}
            - Rumeur actuelle : {last_rumor}
            - Interruptions restantes : {self.interrupt_count}
        
            🧠 MÉMOIRE INTERNE :
            - Actions récentes de moi : {my_actions}
            - Joueurs que je soupçonne : {suspected_wolves}
            - Joueurs en qui j’ai confiance : {trusted_players}
            - Probabilité aléatoire : {random_prob}
        
            📌 STRATÉGIE :
            - Attention je n'accuse, questionne pas des personne mortes. 
            - Si je suis loup-garou : éviter de défendre ouvertement mes alliés, cibler subtilement, survivre.
            - Si je suis loup-garou et que j'ai l'impression que tout le monde va voter pour un loup-garou alors je le fais aussi.
            - Si je suis loup-garou : je ne parle jamais des votes qui ont eu lieu pendant la nuit
            - Si je suis voyante et que je connais un rôle important (ex : loup-garou), je le révèle clairement.
            - Si j'apprends le rôle de quelqu'un qui n'est pas dans mon équipe alors j'essaie de voter contre lui.
            - Si je suspecte un joueur (suspected_werewolves), je peux l’accuser avec raison.
            - Si je fais confiance à un joueur (suspected_villagers), je peux le défendre.
            - Je ne parle que si utile, sauf si proba = 0 ou si on m’accuse.
            - Je peux interrompre si je suis accusé ou qu’un joueur semble très suspect.
            - Si une personne m'accuse alors je l'interrupt.
            - Je ne me répète pas : je consulte mes actions et les derniers discours.
            - Je reste silencieux si j’ai trop parlé ou si la situation ne l’exige pas.
            - Si il s'agit du premier matin (une seule victime) alors je n'accuse personne. 
        
            🗣️ RÉPONDS PAR :
            - Ne demande pas à parler. Dit directement ce que tu veux dire. (n'utilise pas Je prends la parole : ...)
            - Uniquement ton message (1 phrase courte) si tu veux parler.
            - "INTERRUPT: <message>" si tu veux interrompre.
            - "SILENT" si tu ne dis rien.
        """
        # Appel à GPT
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip().replace('\u202f', ' ')

        # 🎮 Interprétation
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

    #Elimination d'un joueur (matin)
    def choose_vote(self) -> str:
        # Nettoyer l'ancien vote s'il est mort
        if self.last_vote_target not in self.alive_players:
            self.last_vote_target = None

        # Cibles valides : vivants, pas soi-même
        valid_targets = [p for p in self.alive_players if p != self.name]

        # Préparer prompt GPT (tronqué pour rapidité)
        messages = "\n".join(f"[{i}] {line}" for i, line in enumerate(self.messages[-2:]))
        statements = "\n".join(
            f"{p}: « {lines[-1]} »" for p, lines in self.statements.items() if lines and p in self.alive_players)

        vote_freq = {}
        for _, voted in self.vote_history:
            if voted in self.alive_players:
                vote_freq[voted] = vote_freq.get(voted, 0) + 1
        vote_trends = ", ".join(f"{p}: {vote_freq[p]}" for p in sorted(vote_freq, key=vote_freq.get, reverse=True))

        prompt = f"""
        {rules}
        👤 Ton nom : {self.name}
        🎭 Ton rôle : {self.role}
        🧍 Joueurs en vie : {', '.join(sorted(self.alive_players))}
        💀 Joueurs morts : {', '.join(sorted(self.dead_players))}
        📨 Messages : {messages}
        💬 Déclarations : {statements}
        🔁 Tendances de vote : {vote_trends}

        🎯 STRATÉGIE :
        - Vote pour un joueur vivant et différent de toi.
        - Ne vote jamais pour un mort.
        - Ne vote pas deux fois de suite pour le même joueur sans bonne raison.
        - Réponds uniquement par un NOM de joueur (1 mot).
        """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip().replace('\u202f', ' ')

        if response not in valid_targets:
            print(f"⚠️ GPT a voté pour {response} (mort/invalide). Redirection aléatoire.")
            response = random.choice(valid_targets)

        self.last_vote_target = response
        return response

    def choose_vote_voyante(self) -> str:
        # Cibles valides : vivants, pas moi, rôle inconnu
        unknown_players = [p for p in self.alive_players if p not in self.known_roles and p != self.name]

        prompt = f"""
        {rules}
        🔮 Tu es la VOYANTE.

        👤 Ton nom : {self.name}
        👁️ Joueurs à sonder : {', '.join(unknown_players)}

        🎯 STRATÉGIE :
        - Ne choisis qu’un joueur vivant, inconnu, pas toi-même.
        - Réponds uniquement par le NOM du joueur à sonder.
        """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip().replace('\u202f', ' ')

        if response not in unknown_players:
            print(f"⚠️ GPT a sondé {response} (mort ou connu). Choix corrigé.")
            response = random.choice(unknown_players)

        return response

    def choose_vote_wolf(self) -> str:
        # Cibles valides : vivants, non-loups, pas moi
        eligible_targets = list(self.alive_players - set(self.werewolves) - {self.name})

        if self.last_vote_target not in self.alive_players:
            self.last_vote_target = None

        prompt = f"""
        {rules}
        🐺 Tu es un loup-garou. Tu votes avec les autres loups pour éliminer un joueur.

        👤 Ton nom : {self.name}
        🧍 Cibles possibles : {', '.join(eligible_targets)}
        🐺 Autres loups : {', '.join(self.werewolves)}
        🎯 Ton dernier vote : {self.last_vote_target or "Aucun"}

        🎯 STRATÉGIE :
        - Vote pour un joueur vivant et non-loup.
        - Ne vote pas pour toi-même ni un loup-garou.
        - Réponds uniquement par le NOM de la cible.
        """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip().replace('\u202f', ' ')

        if response not in eligible_targets:
            print(f"⚠️ GPT a voté pour {response} (mort ou loup). Choix corrigé.")
            response = random.choice(eligible_targets)

        self.last_vote_target = response
        return response

    def display(self):
        print("\n" + "=" * 50)
        print(f"🎭 RÔLE DE {self.name.upper()} : {self.role}")
        print("=" * 50)

        # 🔄 État global
        print(f"🚨 Loups-garous (connus) : {', '.join(self.werewolves)}")
        print(f"❗ Interruptions restantes : {self.interrupt_count}")
        print(f"🗳️ Dernier vote effectué : {self.last_vote_target}")
        print(f"🧠 Actions personnelles récentes : {', '.join(f'{a[0]}({a[1]})' for a in self.my_actions[-5:])}")

        # 🧍 Joueurs
        print("\n🧍 Joueurs encore en vie :", ", ".join(sorted(self.alive_players)))
        print("💀 Joueurs morts :", ", ".join(sorted(self.dead_players)) or "Aucun")

        # 📩 Messages
        print("\n📩 Derniers messages reçus :")
        for i, msg in enumerate(self.messages[-5:]):
            print(f"[{i}] {msg}")

        # 🗳️ Votes
        print("\n🗳️ Historique des votes (5 derniers) :")
        for voter, voted in self.vote_history[-5:]:
            print(f"- {voter} a voté pour {voted}")
        if self.last_wolf_votes:
            print("\n🐺 Derniers votes des loups-garous :")
            for voter, voted in self.last_wolf_votes:
                print(f"- {voter} → {voted}")

        # 🕵️ Informations sociales
        print("\n🕵️ Rôles connus :")
        if self.known_roles:
            for player, role in self.known_roles.items():
                print(f"- {player} : {role}")
        else:
            print("Aucun")

        print("\n📢 Nombre de prises de parole :")
        for player, count in self.speech_count.items():
            print(f"- {player} : {count} fois")

        print("\n💬 Dernières déclarations (1 par joueur) :")
        for player, statements in self.statements.items():
            if statements:
                print(f"- {player} : « {statements[-1]} »")

        print("\n🗯️ Accusations contre moi :")
        accusers = [p for p, targets in self.accusations.items() if self.name in targets]
        print(", ".join(accusers) if accusers else "Personne")

        print("\n👀 Suspects (loups potentiels) :")
        print(", ".join(self.suspected_werewolves) or "Aucun")

        print("\n🤝 Joueurs de confiance (villageois supposés) :")
        print(", ".join(self.suspected_villagers) or "Aucun")

        print("=" * 50 + "\n")
        return

    #If dead remove the player
    def remove_player(self, player: str, role: str):
        self.alive_players.discard(player)
        self.dead_players.append(player)
        self.known_roles[player] = role
        self.speech_count.pop(player, None)
        self.statements.pop(player, None)
        self.vote_history = [(voter, voted) for (voter, voted) in self.vote_history if voter != player and voted != player]
        self.accusations.pop(player, None)
        self.voted_me_last_round.discard(player)
        self.suspected_werewolves.discard(player)
        self.suspected_villagers.discard(player)
        if self.last_vote_target == player:
            self.last_vote_target = "Aucun"
        self.my_actions = [(a, t) for (a, t) in self.my_actions if t != player]

    def notify(self, message: str) -> Intent:
        self.messages.append(message)
        intent = Intent()
        parsed = parse_message(message)
        msg_type = parsed.get("type")

        # -- VOYANTE --
        if msg_type == "voyante_wakeup" and self.role == "voyante":
            intent.vote_for = self.choose_vote_voyante()
            self.my_actions.append(("vote", intent.vote_for))

        elif msg_type == "voyante_result":
            self.known_roles[parsed["player"]] = parsed["role"]

        # -- LOUPS-GAROUS --
        elif msg_type == "werewolves_wakeup":
            self.last_wolf_votes = []  # Réinitialiser à chaque nuit
            return intent

        elif msg_type == "werewolves_vote" and self.role == "loup-garou":
            self.last_wolf_votes = parsed.get("werewolves_votes", [])
            intent.vote_for = self.choose_vote_wolf()
            self.my_actions.append(("vote", intent.vote_for))

        # -- PHASE DE NUIT --
        elif msg_type == "night_start":
            return intent

        # -- MATIN (résultats de la nuit) --
        elif msg_type == "morning_victim":
            victim = parsed.get("victim")
            role = parsed.get("role")
            self.last_rumor = parsed.get("rumor", "")
            self.remove_player(victim, role)
            self.choose_to_speak_interrupt("morning_victim", intent)

        elif msg_type == "morning_no_victim":
            self.last_rumor = parsed.get("rumor", "")
            self.choose_to_speak_interrupt("morning_no_victim", intent)

        # -- PRÉPARATION DU VOTE --
        elif msg_type == "pre_vote":
            self.choose_to_speak_interrupt("pre_vote", intent)

        elif msg_type == "vote_now":
            intent.vote_for = self.choose_vote()
            self.my_actions.append(("vote", intent.vote_for))

        # -- VOTE SANS VICTIME --
        elif msg_type == "vote_no_victim":
            self.voted_me_last_round.clear()
            for voter, voted in parsed.get("votes", []):
                if voted == self.name:
                    self.voted_me_last_round.add(voter)
                    if self.role != "loup-garou":
                        self.suspected_werewolves.add(voter)
                if voter != self.name:
                    self.vote_history.append((voter, voted))

        # -- VOTE AVEC ÉLIMINATION --
        elif msg_type == "vote_result":
            victim = parsed.get("victim")
            role = parsed.get("role")
            self.remove_player(victim, role)
            self.voted_me_last_round.clear()
            for voter, voted in parsed.get("votes", []):
                if voted == self.name:
                    self.voted_me_last_round.add(voter)
                    if self.role != "loup-garou":
                        self.suspected_werewolves.add(voter)
                if voter != self.name:
                    self.vote_history.append((voter, voted))

        # -- PRISE DE PAROLE --
        elif msg_type == "speech":
            speaker = parsed["speaker"]
            speech = parsed["speech"]
            self.speech_count[speaker] += 1
            self.statements[speaker].append(speech)
            self.choose_to_speak_interrupt("speech", intent)
            if intent.want_to_speak:
                self.my_actions.append(("speak", self.msg_to_say))

        # -- ÉLIMINATION PAR TIMEOUT --
        elif msg_type == "timeout":
            player = parsed.get("player")
            role = parsed.get("role")
            self.remove_player(player, role)
            self.choose_to_speak_interrupt("timeout", intent)

        # -- INTERRUPTION --
        if intent.want_to_interrupt:
            self.interrupt_count -= 1
            self.my_actions.append(("interrupt", self.msg_to_say))

        return intent