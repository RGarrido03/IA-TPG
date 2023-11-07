"""Example client."""
import asyncio
import getpass
import json
import os
import time

import websockets
import math

import game
from tree_search import *
from consts import *


class PointsGraph(SearchDomain):
    def __init__(self, connections, coordinates):
        self.connections = connections
        self.coordinates = coordinates

    def actions(self, point) -> list:
        actlist = []
        for (P1, P2, C) in self.connections:
            if P1 == point:
                actlist += [(P1, P2)]
            elif P2 == point:
                actlist += [(P2, P1)]
        return actlist

    def result(self, point, action) -> str:
        (P1, P2) = action
        if P1 == point:
            return P2

    def cost(self, point, action) -> int | None:
        (A1, A2) = action

        if A1 != point:
            return None

        for P1, P2, C in self.connections:
            if (P1, P2) in [(A1, A2), (A2, A1)]:
                return C

    def heuristic(self, point, goal_point) -> float:
        return math.dist(self.coordinates[point], self.coordinates[goal_point])

    def satisfies(self, point, goal_point) -> bool:
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

    def get_digdug_direction(self) -> Direction:
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
                return Direction.WEST
            else:
                return Direction.EAST

    def is_digdug_in_front_of_enemy(self, enemy: dict) -> bool:
        direction = self.get_digdug_direction()
        if direction == Direction.EAST and self.pos[1] == enemy["pos"][1] and self.pos[0] < enemy["pos"][0]:
            return True
        if direction == Direction.WEST and self.pos[1] == enemy["pos"][1] and self.pos[0] > enemy["pos"][0]:
            return True
        if direction == Direction.NORTH and self.pos[0] == enemy["pos"][0] and self.pos[1] > enemy["pos"][1]:
            return True
        if direction == Direction.SOUTH and self.pos[0] == enemy["pos"][0] and self.pos[1] < enemy["pos"][1]:
            return True
        return False

    def is_map_digged_to_direction(self, direction: Direction) -> bool:
        if direction == Direction.EAST and self.map[self.pos[0] + 1][self.pos[1]] == 0:
            return True
        if direction == Direction.WEST and self.map[self.pos[0] - 1][self.pos[1]] == 0:
            return True
        if direction == Direction.NORTH and self.map[self.pos[0]][self.pos[1] - 1] == 0:
            return True
        if direction == Direction.SOUTH and self.map[self.pos[0]][self.pos[1] + 1] == 0:
            return True
        return False

    def dig_map(self, direction: Direction) -> str:
        if direction == Direction.EAST:
            self.map[self.pos[0] + 1][self.pos[1]] = 0
            return "d"
        if direction == Direction.WEST:
            self.map[self.pos[0] - 1][self.pos[1]] = 0
            return "a"
        if direction == Direction.SOUTH:
            self.map[self.pos[0]][self.pos[1] + 1] = 0
            return "s"
        if direction == Direction.NORTH:
            self.map[self.pos[0]][self.pos[1] - 1] = 0
            return "w"

    def get_lower_cost_enemy(self) -> dict:
        connections = []
        coordinates = {}
        for enemy in self.enemies:
            connections.append(
                ("digdug", enemy["id"], math.hypot(enemy["pos"][0] - self.pos[0], enemy["pos"][1] - self.pos[1])))
            coordinates[enemy["id"]] = tuple(enemy["pos"])
        coordinates["digdug"] = self.pos

        map_points = PointsGraph(connections, coordinates)

        chosen_enemy = {"pos": [0, 0], "cost": float("inf")}
        for enemy in self.enemies:
            if "traverse" not in enemy or len(self.enemies) == 1:
                p = SearchProblem(map_points, 'digdug', enemy["id"])
                t = SearchTree(p, 'a*')
                t.search()
                if t.cost < chosen_enemy["cost"]:
                    chosen_enemy = enemy
                    chosen_enemy["cost"] = t.cost
        return chosen_enemy

    def get_key(self, state: dict) -> str:
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

            chosen_enemy = self.get_lower_cost_enemy()

            dist = math.hypot(chosen_enemy["pos"][0] - self.pos[0], chosen_enemy["pos"][1] - self.pos[1])
            x_dist = chosen_enemy["pos"][0] - self.pos[0]
            y_dist = chosen_enemy["pos"][1] - self.pos[1]

            # Run away from enemy if it's spilling fire
            if "fire" in chosen_enemy and dist <= 3 and self.is_digdug_in_front_of_enemy(chosen_enemy):
                if chosen_enemy["dir"] > 1:
                    return self.dig_map(chosen_enemy["dir"] - 2)
                return self.dig_map(chosen_enemy["dir"] + 2)

            # Change the direction when it bugs and just follows the enemy
            if "dir" in chosen_enemy and self.get_digdug_direction() == chosen_enemy["dir"]:
                if chosen_enemy["pos"][0] - self.pos[0] == 1:
                    return self.dig_map(Direction.EAST)
                elif chosen_enemy["pos"][0] - self.pos[0] == -1:
                    return self.dig_map(Direction.WEST)
                elif chosen_enemy["pos"][1] - self.pos[1] == 1:
                    return self.dig_map(Direction.SOUTH)
                elif chosen_enemy["pos"][1] - self.pos[1] == -1:
                    return self.dig_map(Direction.NORTH)

            # Try to fire
            if dist <= 3 and self.is_digdug_in_front_of_enemy(chosen_enemy):
                return "A"

            # Run away if the enemy is too close
            if dist < 2:
                print("Run away")
                if chosen_enemy["dir"] == Direction.WEST and chosen_enemy["pos"][0] - 1 == self.pos[0] + 1 and chosen_enemy["pos"][1] == self.pos[1]:
                    return self.dig_map(Direction.WEST)
                elif chosen_enemy["dir"] == Direction.EAST and chosen_enemy["pos"][0] + 1 == self.pos[0] - 1 and chosen_enemy["pos"][1] == self.pos[1]:
                    return self.dig_map(Direction.EAST)
                elif chosen_enemy["dir"] == Direction.NORTH and chosen_enemy["pos"][0] == self.pos[0] and chosen_enemy["pos"][1] - 1 == self.pos[1] + 1:
                    return self.dig_map(Direction.NORTH)
                elif chosen_enemy["dir"] == Direction.SOUTH and chosen_enemy["pos"][0] == self.pos[0] and chosen_enemy["pos"][1] + 1 == self.pos[1] - 1:
                    return self.dig_map(Direction.SOUTH)

                if chosen_enemy["dir"] == Direction.WEST and self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.WEST)
                elif chosen_enemy["dir"] == Direction.EAST and self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.EAST)
                elif chosen_enemy["dir"] == Direction.NORTH and self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.NORTH)
                elif chosen_enemy["dir"] == Direction.SOUTH and  self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.SOUTH)

                if chosen_enemy["dir"] == Direction.WEST and self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.WEST)
                elif chosen_enemy["dir"] == Direction.EAST and self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.EAST)
                elif chosen_enemy["dir"] == Direction.NORTH and self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.NORTH)
                elif  chosen_enemy["dir"] == Direction.SOUTH and self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.SOUTH)

                if chosen_enemy["dir"] == Direction.WEST and self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.WEST)
                elif chosen_enemy["dir"] == Direction.EAST and self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.EAST)
                elif chosen_enemy["dir"] == Direction.NORTH and self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.NORTH)
                elif chosen_enemy["dir"] == Direction.SOUTH and self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                    return self.dig_map(Direction.SOUTH)

            # Move around the map
            if abs(x_dist) >= abs(y_dist):
                if x_dist > 0:
                    return self.dig_map(Direction.EAST)
                elif x_dist < 0:
                    return self.dig_map(Direction.WEST)
            else:
                if y_dist > 0:
                    return self.dig_map(Direction.SOUTH)
                elif y_dist < 0:
                    return self.dig_map(Direction.NORTH)
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
                state: dict = json.loads(
                    await websocket.recv()
                )

                key: str = agent.get_key(state)
                await websocket.send(
                    json.dumps({"cmd": "key", "key": key})
                )

                # 10Hz time sync
                time.sleep((1 / game.GAME_SPEED) - ((time.monotonic() - starttime) % (1 / game.GAME_SPEED)))
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
