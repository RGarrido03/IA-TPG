"""Example client."""
import asyncio
import getpass
import json
import os
import websockets
import pprint
import math

from cidades import Cidades
from tree_search import *


class Agent:
    def __init__(self):
        self.state: dict = {}
        self.pos: list[int] = []
        self.enemies: list = []
        self.level: int = 1
        self.lives: int = 3
        self.player: str = ""
        self.rocks: list = []
        self.score: int = 0
        self.step: int = 0
        self.timeout: int = 0

    def get_key(self, state: dict[str, object]):
        self.state = state
        if "digdug" in self.state:
            self.pos = self.state["digdug"]
            self.enemies = self.state["enemies"]
            self.level = self.state["level"]
            self.lives = self.state["lives"]
            self.player = self.state["player"]
            self.rocks = self.state["rocks"]
            self.score = self.state["score"]
            self.step = self.state["step"]
            self.timeout = self.state["timeout"]

            connections = []
            coordinates = {}
            for enemy in self.enemies:
                connections.append(("digdug", enemy["id"], math.hypot(enemy["pos"][0] - self.pos[0], enemy["pos"][1] - self.pos[1])))
                coordinates[enemy["id"]] = tuple(enemy["pos"])
            coordinates["digdug"] = self.pos

            map_points = Cidades(connections, coordinates)

            chosen_enemy = (0, 0, 9999)
            for enemy in self.enemies:
                p = SearchProblem(map_points, 'digdug', enemy["id"])
                t = SearchTree(p, 'a*')
                t.search()
                if t.cost < chosen_enemy[2]:
                    chosen_enemy = (enemy["pos"][0], enemy["pos"][1], t.cost)

            dist = math.hypot(chosen_enemy[0] - self.pos[0], chosen_enemy[1] - self.pos[1])

            if dist <= 3:
                return "A"
            else:
                if chosen_enemy[0] > self.pos[0]:
                    return "d"
                elif chosen_enemy[0] < self.pos[0]:
                    return "a"
                elif chosen_enemy[1] > self.pos[1]:
                    return "s"
                elif chosen_enemy[1] < self.pos[1]:
                    return "w"
                else:
                    return " "
        return " "


async def agent_loop(server_address="localhost:8000", agent_name="student"):
    agent = Agent()
    """Example client loop."""
    async with websockets.connect(f"ws://{server_address}/player") as websocket:
        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        while True:
            try:
                # Receive game update.
                # This must be called timely or your game will get out of sync with the server!
                state: dict[str, object] = json.loads(
                    await websocket.recv()
                )

                # Print state for debug
                pprint.pprint(state)

                key: str = agent.get_key(state)
                await websocket.send(
                    json.dumps({"cmd": "key", "key": key})
                )  # send key command to server - you must implement this send in the AI agent
            except websockets.exceptions.ConnectionClosedOK:
                print("Server has cleanly disconnected us")
                return


# DO NOT CHANGE THE LINES BELLOW
# You can change the default values using the command line, example:
# $ NAME='arrumador' python3 client.py
loop = asyncio.get_event_loop()
SERVER = os.environ.get("SERVER", "localhost")
PORT = os.environ.get("PORT", "8000")
NAME = os.environ.get("NAME", getpass.getuser())
loop.run_until_complete(agent_loop(f"{SERVER}:{PORT}", NAME))
