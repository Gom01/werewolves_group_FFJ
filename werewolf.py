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
        m = re.search(r"Cette nuit, personne n'a été mangé\.e par les", message)
        data["type"] = "morning_no_victim"
        rumor_text = m.group(1).strip() if m and m.group(1) else ""
        if rumor_text:
            data["rumor"] = rumor_text # type: ignore
    elif "Cette nuit, " in message and "a été mangé.e" in message:
        m = re.search(
            rf"Cette nuit, {name_pattern} a été mangé\.e par les loups.?garous\. Son rôle était {role_pattern}\.(.*)",
            message)
        if m:
            data["type"] = "morning_victim"
            data["victim"] = m.group(1)
            data["role"] = m.group(2)
            rumor_text = m.group(3).strip() if m.lastindex >= 3 and m.group(3) else ""
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
        self.voted_me_last_round = set()  # pour stocker les gens qui ont voté contre moi au dernier tour
        self.last_vote_target = None  # pour éviter de voter 2x le même
        self.msg_to_say = "" # message à dire lorsque je speak
        self.speech_count_myself = 0
        self.last_rumor = ""  # dernière rumeur prononcée par le meneur
        self.my_actions = []  # ex: [('speak', message), ('vote', 'Alice')]
        self.suspected_player = set()
        self.number_tour = 0

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
        last_votes = ", ".join(f"{voter}→{voted}" for voter, voted in self.vote_history[-5:])
        voted_me = ", ".join(self.voted_me_last_round)
        wolf_votes = ", ".join(f"{voter}→{voted}" for voter, voted in self.last_wolf_votes)
        speech_counts = ", ".join(f"{p}: {self.speech_count.get(p, 0)}" for p in self.players_names if p != self.name)
        statements = "\n".join(f"{p}: « {lines[-1]} »" for p, lines in self.statements.items() if lines)
        messages = "\n".join(f"[{i}] {line}" for i, line in enumerate(self.messages[-5:]))
        my_actions = ", ".join(f"{action}({target})" for action, target in self.my_actions[-5:])
        suspected_player = ", ".join(p for p in self.suspected_player if p in self.alive_players)
        last_vote = self.last_vote_target or "Aucun"
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
            - Rumeur actuelle : {last_rumor}
            - Interruptions restantes : {self.interrupt_count}
        
            🧠 MÉMOIRE INTERNE :
            - Actions récentes de moi : {my_actions}
            - Joueurs que je soupçonne : {suspected_player}
            - Probabilité aléatoire : {random_prob}
            - Tour numéro : {self.number_tour}
        
            📌 STRATÉGIE :
            - Attention je n'accuse, questionne pas des personne mortes. 
            - Si je suis loup-garou : éviter de défendre ouvertement mes alliés, cibler subtilement, survivre.
            - Si je suis loup-garou et que j'ai l'impression que tout le monde va voter pour un loup-garou alors je le fais aussi.
            - Si je suis loup-garou : je ne parle jamais des votes qui ont eu lieu pendant la nuit
            - Si je suis voyante et que je connais un rôle important (ex : loup-garou), je le révèle clairement. (en disant que je suis voyante) interromps
            - Si j'apprends le rôle de quelqu'un qui n'est pas dans mon équipe alors j'essaie de voter contre lui.
            - Si je suspecte un joueur (suspected_player), je peux l’accuser avec une raison.
            - Tu peux accuser des gens si tu le penses nécessaire
            - Si on parle de toi alors parle.
            - Je ne parle que si utile ou si on m’accuse.
            - Je dois parler si la probabilité est égale à 0 (au tour 1 seulement)
            - Je peux interrompre si je suis accusé ou qu’un joueur semble très suspect.
            - Si une personne m'accuse alors je veux l'interrompre.
            - Je ne me répète pas : je consulte mes actions et les derniers discours.
            - Je reste silencieux si j’ai trop parlé ou si la situation ne l’exige pas.
            - Si il s'agit du premier matin (une seule victime) alors je n'accuse personne.
            - Base toi sur les votes du matin pour accuser qqn
            - Interromps le message si interruptions != 0 et que tu dois te défendre
            - S'il reste seulement 3 joueurs dans la partie et que je suis loup-garou et que la voyante n'est pas morte, j'accuse un villageois d'être un loup-garou.
        
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
        response = response.replace('\u2009', ' ')

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
        last_vote = self.last_vote_target or "Aucun"
        # Préparer les données utiles
        unknown_or_suspects = [p for p in self.alive_players if p not in self.known_roles and p != self.name]
        alive = ", ".join(sorted(self.alive_players))
        dead = ", ".join(sorted(self.dead_players))
        known_roles_str = ", ".join(f"{p}: {r}" for p, r in self.known_roles.items())

        # Ennemis explicites (connus)
        known_enemy_roles = []
        for p, r in self.known_roles.items():
            if self.role in ["voyante", "villageois"] and r == "loup-garou":
                known_enemy_roles.append(p)
            elif self.role == "loup-garou" and r in ["voyante", "villageois"]:
                known_enemy_roles.append(p)
        enemies_str = ", ".join(known_enemy_roles)

        # Accusateurs + votes contre moi
        recent_attackers = ", ".join(self.voted_me_last_round)

        # Historique des votes
        vote_freq = {}
        for _, voted in self.vote_history:
            if voted in unknown_or_suspects:
                vote_freq[voted] = vote_freq.get(voted, 0) + 1
        vote_trends = ", ".join(f"{p}: {vote_freq[p]}" for p in sorted(vote_freq, key=vote_freq.get, reverse=True))

        # Messages, discours, actions
        messages = "\n".join(f"[{i}] {line}" for i, line in enumerate(self.messages[-5:]))
        statements = "\n".join(f"{p}: « {lines[-1]} »" for p, lines in self.statements.items() if lines)
        speech_counts = ", ".join(f"{p}: {self.speech_count[p]}" for p in sorted(self.speech_count)if p in self.alive_players)
        my_actions = ", ".join(f"{action}({target})" for action, target in self.my_actions[-5:])
        last_vote = self.last_vote_target or "Aucun"
        suspected_player = ", ".join(p for p in self.suspected_player if p in self.alive_players)

        # 🎯 Construction du prompt complet
        prompt = f"""
            {rules}
        
            🎭 Ton rôle : {self.role}
            👤 Ton nom : {self.name}
        
            🧍 Joueurs en vie : {alive}
            💀 Joueurs morts : {dead}
            🧠 Rôles connus : {known_roles_str}
            ⚔️ Ennemis connus (à cibler) : {enemies_str}
            🫥 Joueurs dont le rôle est inconnu : {', '.join(unknown_or_suspects)}
        
            🗳️ Ont voté contre toi : {recent_attackers}
            🔁 Fréquence des votes précédents : {vote_trends}
            🗣️ Parole des autres : {speech_counts}
            🧾 Dernières déclarations :
            {statements}
            📨 Messages du meneur :
            {messages}
        
            🤖 Tes dernières actions : {my_actions}
            🎯 Ton dernier vote : {last_vote}
               Tes suspects : {suspected_player}

        
            🧠 STRATÉGIE POUR LE VOTE :
            - Si tu connais un **ennemi confirmé**, vote contre lui en priorité.
            - Sinon, cible celui qui t’accuse, ou qui est le plus suspect.
            - Ne vote pas 2 fois d'affilée pour le même joueur sans nouvelle raison.
            - Ne vote jamais contre toi-même.
            - Si tu pense savoir qui c'est la voyante (donne une piste) alors vote pour la personne qu'elle a désignée
            - Si tu es loup-garou et que un de tes alliés (loup-garou) a été démasqué vote contre lui (suis la tendance)
            - Si la voyante a accusé une personne comme loup-garou et que la voyante est morte alors suit son vote
            - Si tu es loup-garou : ne vote pas contre un autre loup sauf si tu penses que les gens vont voter contre lui.
            - Si tu es loup-garou : suit les votes du groupes de temps en temps (pour ne pas te faire démasquer)
            - Si tu es villageois ou voyante : ne vote jamais contre un autre villageois ou la voyante.
            - Prends en compte les votes passés et les contradictions.
            - Donne **UNIQUEMENT le nom du joueur que tu veux éliminer**.
    """

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip().replace('\u202f', ' ')

        response = response.replace('\u2009', ' ')

        self.last_vote_target = response
        print(response)
        return response

    def choose_vote_voyante(self) -> str:
        if self.last_vote_target not in self.alive_players:
            self.last_vote_target = None
        unknown_players = [p for p in self.alive_players if p not in self.known_roles and p != self.name]
        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive = ", ".join(self.alive_players)
        suspected_player = ", ".join(p for p in self.suspected_player if p in self.alive_players)

        prompt = f"""
            {rules}

            Tu es la voyante dans une partie de Loups-Garous de Thiercelieux.

            Voici ton nom : {self.name}
            Voici les joueurs encore en vie : {alive}.
            Voici les joueurs dont tu NE connais PAS le rôle : {', '.join(unknown_players)}.
            Suspects : {suspected_player}
            Messages échangés : {messages}

            TA TÂCHE :
            - Ne vote pas pour toi
            - Choisis une cible à sonder cette nuit parmi ceux dont tu ignores encore le rôle.
            - Priorise les joueurs suspects ou hostiles envers toi.
            - Donne UNIQUEMENT le nom du joueur que tu veux sonder.
            """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        response = response.replace('\u202f', ' ')
        response = response.replace('\u2009', ' ')

        print(response)
        return response

    def choose_vote_wolf(self) -> str:
        if self.last_vote_target not in self.alive_players:
            self.last_vote_target = None

        eligible_targets = list(self.alive_players - set(self.werewolves) - {self.name})
        wolf_votes = self.last_wolf_votes
        statements = "\n".join(f"{p}: « {lines[-1]} »" for p, lines in self.statements.items()if p in eligible_targets and lines)
        messages = "".join(f"[{i}] {line}" for i, line in enumerate(self.messages))
        alive = ", ".join(self.alive_players)
        wolves = ", ".join(self.werewolves)
        recent_attackers = ", ".join(self.voted_me_last_round)
        suspected_player = ", ".join(p for p in self.suspected_player if p in self.alive_players)

        if not wolf_votes:
            prompt = f"""

                      {rules}
                      Ton nom : {self.name}
                      Tu es un loup-garou. 
                      Joueurs en vie : {alive}. 
                      Loups : {wolves}. 
                      Ont voté contre toi : {recent_attackers}.
                      Suspects : {suspected_player}
                      Speeches : {statements}
                      Messages : {messages}.

                      TA TÂCHE :
                      - Choisis une cible parmi les non-loups.
                      - Si tu penses savoir qui est la voyante vote pour elle.
                      - Ne vote jamais pour des loups
                      - Donne la priorité aux joueurs les plus hostiles envers toi ou les plus suspects.
                      - Si tu n'as aucune information vote pour la personne qui à le plus parler et qui n'est pas un loup-garou
                      - Donne UNIQUEMENT le nom du joueur que tu veux éliminer.
                      """
        else:
            votes = ", ".join(f"{v} → {t}" for v, t in wolf_votes)
            prompt = f"""

                      {rules}
                      Ton nom : {self.name}
                      Tu es un loup-garou. 
                      Joueurs en vie : {alive}. 
                      Loups : {wolves}. 
                      Votes déjà faits : {votes}. 
                      Ton vote précédent : {self.last_vote_target}.
                      Ont voté contre toi : {recent_attackers}.
                      Speeches : {statements}
                      Messages : {messages}.

                      TA TÂCHE :
                      - Coordonne le vote avec les autres loups.
                      - Si vous n'êtes que deux loup alors change le vote et prends celui de ton allié
                      - Suis la majorité. (nombre de votes)
                      - Ne vote jamais pour des loups
                      - Garde ta cible précédente si elle est populaire.
                      - Sinon, vote pour celle qui est la plus souvent ciblée.
                      - Donne UNIQUEMENT le nom d'un joueur.
                      """
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}]
        ).choices[0].message.content.strip()

        response = response.replace('\u202f', ' ')
        response = response.replace('\u2009', ' ')

        print(response)
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

        print("\n👀 Suspects :")
        print(", ".join(self.suspected_player) or "Aucun")

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
        self.voted_me_last_round.discard(player)
        self.suspected_player.discard(player)
        if self.last_vote_target == player:
            self.last_vote_target = None
        self.my_actions = [(a, t) for (a, t) in self.my_actions if t != player]

    def notify(self, message: str) -> Intent:
        self.messages.append(message)
        intent = Intent()
        parsed = parse_message(message)
        msg_type = parsed.get("type")


        # -- VOYANTE --
        if msg_type == "voyante_wakeup" and self.role == "voyante":
            self.number_tour += 1
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
                if voter != self.name:
                    self.vote_history.append((voter, voted))
                if voted == self.name:
                    self.voted_me_last_round.add(voter)
                    self.suspected_player.add(voter)

        # -- VOTE AVEC ÉLIMINATION --
        elif msg_type == "vote_result":
            victim = parsed.get("victim")
            role = parsed.get("role")
            if victim and role:
                self.remove_player(victim, role)
            self.voted_me_last_round.clear()
            for voter, voted in parsed.get("votes", []):
                if voter != self.name:
                    self.vote_history.append((voter, voted))
                if voted == self.name:
                    self.voted_me_last_round.add(voter)
                    self.suspected_player.add(voter)


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


        self.display()

        return intent