from flask import Flask, request, jsonify
from werewolf import WerewolfPlayer

def create_app():
    app = Flask(__name__)
    
    app.config['WerewolfPlayer'] = None
    
    @app.route('/new_game', methods=['POST'])
    def new_game():
        """
        Endpoint appelé par le meneur pour créer une nouvelle partie. 
            
        Args:
            ```json
            {
                "role": "villageois",
                "player_name": "Aline",
                "players_names": ["Aline", "Benjamin", "Chloe"],
                "werewolves": ["Benjamin", "Chloe"]  # vide si le joueur est un villageois
            }
            ```
    
        Returns: un JSON avec {"ack": True} pour checker que le joueur est bien connecté.
        """

        role = request.json.get("role")
        player_name = request.json.get("player_name")
        players_names = request.json.get("players_names")
        werewolves = request.json.get("werewolves")
        assert role in ["villageois", "voyante", "loup-garou"], "Role invalide"
        assert player_name is not None, "Nom de joueur manquant"

        app.config['WerewolfPlayer'] = WerewolfPlayer.create(player_name, role, players_names, werewolves.copy())

        return jsonify({"ack": True})
    
    
    @app.route('/speak', methods=['POST'])
    def speak():
        """
        Endpoint appelé par le meneur pour donner la parole à un joueur.
        Le joueur doit alors prendre la parole dans le jeu. 
    
        Args:
            Aucun paramètre n'est passé; c'est au joueur de déduire le contexte uniquement depuis ce qu'il a reçu via /notify.
        
        Returns:
            Un message contenant le texte que le joueur dit. 
            Un joueur peut décider de ne pas parler (retourner un `speech` vide). Exemple:
            ```json
            {
                "speech": "Je crois que Aline ment car ..."
            }
            ```
        """
        speech = app.config['WerewolfPlayer'].speak()
        return jsonify({"speech": speech})


    @app.route('/notify', methods=['POST'])
    def notify():
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
                "vote_for": "Aline" | "Benjamin" | "Chloe" | "David" | "Elise" | "Frédéric" | "Gabrielle" | None
            }
            ```
        """
        message = request.json.get('message')
        intent = app.config['WerewolfPlayer'].notify(message)
        return jsonify(intent.model_dump(mode="json"))
    
    return app

def run_app(port):
    app = create_app()
    app.run(debug=False, port=port, host='localhost')

if __name__ == '__main__':
    import multiprocessing
    
    processes = []
    
    for port in range(5021, 5028):  # Ports 5021 to 5027 inclusive
        p = multiprocessing.Process(target=run_app, args=(port,))
        p.start()
        processes.append(p)
        print(f"Started server on port {port}")
    
    # Wait for all processes to complete
    for p in processes:
        p.join() 