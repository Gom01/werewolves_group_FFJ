import sys
from flask import Flask, request, jsonify
from werewolf import WerewolfPlayer
import logging
import json
from datetime import datetime

def create_app():
    app = Flask(__name__)
    
    # where players are stored. TODO check that not too many players are created; remove "old" players
    app.config['WerewolfPlayers'] = {}
    
    @app.route('/new_game', methods=['POST'])
    def new_game():
        """
        Endpoint appelé par le meneur pour créer une nouvelle partie. 
            
        Args:
            ```json
            {
                "role": "villageois",
                "player_name": "Aline",
                "players_names": ["Aline", "Benjamin", "Chloe", ...],
                "werewolves_count": 2 (the total # of werewolves)
                "werewolves": ["Benjamin", "Chloe"]  # vide si le joueur est un villageois
            }
            ```
    
        Returns: un JSON avec {"ack": True} pour checker que le joueur est bien connecté et un identifiant unique pour le joueur.
        """

        role = request.json.get("role")
        player_name = request.json.get("player_name")
        players_names = request.json.get("players_names")
        werewolves_count = request.json.get("werewolves_count")
        werewolves = request.json.get("werewolves")
        assert role in ["villageois", "voyante", "loup-garou"], "Role invalide"
        assert player_name is not None, f"Nom de joueur manquant, player_name: {player_name}"
        assert players_names is not None, f"Liste de joueurs manquante, players_names: {players_names}"
        assert isinstance(players_names, list), f"Liste de joueurs invalide, players_names: {players_names}"
        assert len(players_names) > 0, f"Liste de joueurs vide, players_names: {players_names}"
        
        player = WerewolfPlayer.create(player_name, role, players_names.copy(), werewolves_count, werewolves.copy())
        if player:
            # add the player to the list of players
            players = app.config['WerewolfPlayers']
            player_id = len(players)
            app.config['WerewolfPlayers'][player_id] = player

            return jsonify({"ack": True, "player_id": player_id})
        else:
            return jsonify({"ack": False})

    
    @app.route('/<int:player_id>/speak', methods=['POST'])
    def speak(player_id):
        """
        Endpoint appelé par le meneur pour donner la parole à un joueur.
        Le joueur doit alors prendre la parole dans le jeu. 
    
        Args:
            player_id: L'identifiant du joueur qui doit parler
        
        Returns:
            Un message contenant le texte que le joueur dit. 
            Un joueur peut décider de ne pas parler (retourner un `speech` vide). Exemple:
            ```json
            {
                "speech": "Je crois que Aline ment car ..."
            }
            ```
        """
        players = app.config['WerewolfPlayers']
        if player_id not in players:
            return jsonify({"error": f"Player {player_id} not found"}), 404
        
        player = players[player_id]
        speech = player.speak()
        return jsonify({"speech": speech})


    @app.route('/<int:player_id>/notify', methods=['POST'])
    def notify(player_id):
        """
        Endpoint appelé par le meneur pour deux objectifs principaux:
    
        1. Informer le joueur sur l'état du jeu:
           - Qui a parlé et ce qui a été dit
           - Si c'est la nuit
           - Les rumeurs
           - Si c'est le moment de voter
           - Le résultat du vote (qui a été éliminé et son rôle)
           - Autres informations pertinentes sur l'état du jeu
    
        Le message est **sous forme de texte uniquement** et c'est au joueur de l'interpréter en fonction du contexte.
        Le message contient uniquement le dernier (nouveau) message du meneur, c'est au joueur de mémoriser les informations des messages précédents.
        
        2. Recevoir les actions du joueur:
           - Demande de prise de parole
           - Demande d'interruption
           - Vote
    
        La réponse suivra **strictement le schéma** ci-dessous, sans quoi elle sera ignorée par le meneur.
        
        Args:
            player_id: L'identifiant du joueur
            message: Un message du meneur. Exemple:
            ```json
            {
                "message": "C'est le matin, le village se réveille. Aline a été tuée cette nuit. Aline était une villageoise."
            }
            ```
        Returns:
            Un message contenant les actions du joueur. Schéma:
            ```json
            {
                "want_to_speak": True | False,
                "want_to_interrupt": True | False,
                "vote_for": "Aline" | "Benjamin" | ... | None
            }
            ```
        """
        players = app.config['WerewolfPlayers']
        if player_id not in players:
            return jsonify({"error": f"Player {player_id} not found"}), 404
        
        player = players[player_id]
        message = request.json.get('message')
        intent = player.notify(message)
        return jsonify(intent.model_dump(mode="json"))
    
    @app.route('/', methods=['GET', 'POST'])
    def ping():
        # prints the current time as a html page
        return f"<html><body><h1>Werewolf server is running, {datetime.now()}</h1></body></html>"


    return app

def run_app(port):
    # Suppress Flask (Werkzeug) access logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)  # or logging.CRITICAL to suppress even more

    app = create_app()
    app.run(debug=False, port=port, host='localhost')

if __name__ == '__main__':

    # if a port is provided, use it
    if len(sys.argv) > 1:
        ports = [int(port) for port in sys.argv[1:]]
        print(f"Using ports: {ports}")
    else:
        # read from players_config.json
        with open("players_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        ports = set()
        for p in config["players"]:
            base_url = p["api_base_url"]
            if base_url.startswith("http://localhost:"):
                port = base_url.split(":")[2].strip("/")
                ports.add(int(port))
            else:
                print(f"WARNING: player {p['name']} not started by werewolf_server.py since it's not on localhost. Make sure it is up!")

    import multiprocessing
    
    processes = []
    
    for port in ports:  
        p = multiprocessing.Process(target=run_app, args=(port,))
        p.start()
        processes.append(p)
        print(f"Started Werewolf server on port {port}")
        print(f"To publish using ngrok:     ngrok http {port}")
    
    # Wait for all processes to complete
    for p in processes:
        p.join() 