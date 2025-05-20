from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from flask_socketio import SocketIO
import json
import os


class GameLogEntry(BaseModel):
    timestamp: datetime = datetime.now(timezone.utc)
    type: str
    actor_name: Optional[str] = "GameLeader"
    target_name: Optional[str] = None
    content: str
    public: bool = True
    context_data: Optional[Dict[str, Any]] = None

    def to_llm_string(self, sequence_number: int = 0) -> str:
        """
        Creates a string representation of the log entry suitable for LLM consumption.
        """
        parts = [f"[{sequence_number}] Event: {self.type}"]
        if self.actor_name:
            parts.append(f"Actor: {self.actor_name}")
        if self.target_name:
            parts.append(f"Target: {self.target_name}")
        parts.append(f"Content: {self.content}")
        if self.context_data:
            context_str = ", ".join([f"{k}: {v}" for k, v in self.context_data.items()])
            parts.append(f"Context: ({context_str})")
        return "\n".join(parts)


class Logger(ABC):
    @abstractmethod
    def log(self, entry: GameLogEntry) -> None:
        pass


class WebLogger(Logger):

    def __init__(self):
        self.entries = []
        # start api server
        self.app = Flask(__name__, static_folder='public', static_url_path='/static')
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Route for the main page
        @self.app.route('/')
        def index():
            return send_from_directory('public', 'index.html')
        
        # Route for log entries via HTTP (in addition to WebSockets)
        @self.app.route('/log', methods=['POST'])
        def handle_log_entry():
            data = request.json
            entry = GameLogEntry(**data)
            return self.log_entry(entry)
        
        # Run the app with SocketIO
        self.socketio.run(self.app, port=4999, debug=True)

    def log_entry(self, entry: GameLogEntry) -> None:
        self.entries.append(entry)
        
        # Convert entry to dict for JSON serialization
        entry_dict = entry.dict()
        # Convert datetime to ISO format string
        entry_dict['timestamp'] = entry.timestamp.isoformat()
        
        # Emit the new log entry to all connected clients
        self.socketio.emit('new_log_entry', entry_dict)
        
        return jsonify({"ack": True})
        
    def log(self, entry: GameLogEntry) -> None:
        self.entries.append(entry)
        
        # Convert entry to dict for JSON serialization
        entry_dict = entry.dict()
        # Convert datetime to ISO format string
        entry_dict['timestamp'] = entry.timestamp.isoformat()
        
        # Emit the new log entry to all connected clients
        self.socketio.emit('new_log_entry', entry_dict)


if __name__ == "__main__":
    # for testing 
    logger = WebLogger()
    
    # add some example log entries
    logger.log(GameLogEntry(
        type="announcement",
        content="Game has started!"
    ))
    # TODO    