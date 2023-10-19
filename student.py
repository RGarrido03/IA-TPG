"""Example client."""
import asyncio
import getpass
import json
import os
import time

import websockets
import pprint
import math

import mapa
from tree_search import *
from consts import *


class PointsGraph(SearchDomain):
    def __init__(self, connections, coordinates):
        self.connections = connections
        self.coordinates = coordinates

    def actions(self, point):
        actlist = []
        for (P1, P2, C) in self.connections:
            if (P1 == point):
                actlist += [(P1, P2)]
            elif (P2 == point):
                actlist += [(P2, P1)]
        return actlist

    def result(self, point, action):
        (P1, P2) = action
        if P1 == point:
            return P2

    def cost(self, point, action):
        (A1, A2) = action

        if A1 != point:
            return None

        for P1, P2, C in self.connections:
            if (P1, P2) in [(A1, A2), (A2, A1)]:
                return C

    def heuristic(self, point, goal_point):
        return math.dist(self.coordinates[point], self.coordinates[goal_point])

    def satisfies(self, point, goal_point):
        return goal_point == point


class Agent:
    def __init__(self):
        self.state: dict = {}
        self.pos: list[int] = []
        self.last_pos: list[int] = []
        self.enemies: list = []
        self.level: int = 1
        self.lives: int = 3
        self.player: str = ""
        self.rocks: list = []
        self.score: int = 0
        self.step: int = 0
        self.timeout: int = 0
        self.map: list = []

    def get_digdug_direction(self):
        # When the game/level starts, it usually goes to East
        if not self.last_pos:
            return Direction.EAST

        # Vertical direction
        if self.pos[0] == self.last_pos[0]:
            if self.pos[1] < self.last_pos[1]:
                return Direction.NORTH
            else:
                return Direction.SOUTH

        # Horizontal direction
        else:
            if self.pos[0] < self.last_pos[0]:
                return Direction.EAST
            else:
                return Direction.WEST

    def get_key(self, state: dict[str, object]):
        if "digdug" in state:
            self.last_pos = self.pos
            self.pos = state["digdug"]
            self.enemies = state["enemies"]
            self.rocks = state["rocks"]
            # self.level = state["level"]
            # self.lives = state["lives"]
            # self.player = state["player"]
            # self.score = state["score"]
            # self.step = state["step"]
            # self.timeout = state["timeout"]

            connections = []
            coordinates = {}
            for enemy in self.enemies:
                connections.append(
                    ("digdug", enemy["id"], math.hypot(enemy["pos"][0] - self.pos[0], enemy["pos"][1] - self.pos[1])))
                coordinates[enemy["id"]] = tuple(enemy["pos"])
            coordinates["digdug"] = self.pos

            map_points = PointsGraph(connections, coordinates)

            chosen_enemy = (0, 0, float('inf'))
            for enemy in self.enemies:
                p = SearchProblem(map_points, 'digdug', enemy["id"])
                t = SearchTree(p, 'a*')
                t.search()
                if t.cost < chosen_enemy[2]:
                    chosen_enemy = (enemy["pos"][0], enemy["pos"][1], t.cost)

            dist = math.hypot(chosen_enemy[0] - self.pos[0], chosen_enemy[1] - self.pos[1])
            x_dist = chosen_enemy[0] - self.pos[0]
            y_dist = chosen_enemy[1] - self.pos[1]

            if abs(x_dist) >= abs(y_dist):
                if x_dist > 0:
                    if dist <= 3 and self.map[self.pos[0] + 1][self.pos[1]] == 0:
                        return "A"
                    self.map[self.pos[0] + 1][self.pos[1]] = 0
                    return "d"
                elif x_dist < 0:
                    if dist <= 3 and self.map[self.pos[0] - 1][self.pos[1]] == 0:
                        return "A"
                    self.map[self.pos[0] - 1][self.pos[1]] = 0
                    return "a"
            else:
                if y_dist > 0:
                    if dist <= 3 and self.map[self.pos[0]][self.pos[1] + 1] == 0:
                        return "A"
                    self.map[self.pos[0]][self.pos[1] + 1] = 0
                    return "s"
                elif y_dist < 0:
                    if dist <= 3 and self.map[self.pos[0]][self.pos[1] - 1] == 0:
                        return "A"
                    self.map[self.pos[0]][self.pos[1] - 1] = 0
                    return "w"
        else:
            self.map = state["map"]

        return " "


async def agent_loop(server_address="localhost:8000", agent_name="student"):
    agent = Agent()
    """Example client loop."""
    async with websockets.connect(f"ws://{server_address}/player") as websocket:
        # Receive information about static game properties
        await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

        starttime = time.monotonic()
        while True:
            try:
                # Receive game update.
                state: dict[str, object] = json.loads(
                    await websocket.recv()
                )

                # Print state for debug
                # pprint.pprint(state)

                key: str = agent.get_key(state)
                await websocket.send(
                    json.dumps({"cmd": "key", "key": key})
                )

                # 10Hz time sync
                time.sleep(0.1 - ((time.monotonic() - starttime) % 0.1))
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
