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
    def __init__(self, connections, coordinates, map):
        self.connections = connections
        self.coordinates = coordinates
        self.map = map

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
        x1, y1 = self.coordinates[point]
        x2, y2 = self.coordinates[goal_point]
        return abs(x2 - x1) + abs(y2 - y1)

    def satisfies(self, point, goal_point) -> bool:
        return goal_point == point


class Agent:
    def __init__(self):
        self.state: dict = {}
        self.pos: list[int] = []
        self.last_pos: list[int] = []
        self.dir: Direction = Direction.EAST
        self.enemies: list[dict] = []
        self.ts: float = 0.0
        self.map: list = []
        self.map_size: list = []
        self.pos_rocks: list = []
        self.previous_positions: list[list[int]] = []

    def get_digdug_direction(self) -> Direction:
        # When the game/level starts, it has no last position
        if not self.last_pos:
            return self.dir

        # Vertical direction
        if self.pos[0] == self.last_pos[0]:
            if self.pos[1] < self.last_pos[1]:
                return Direction.NORTH
            elif self.pos[1] > self.last_pos[1]:
                return Direction.SOUTH
            else:
                return self.dir

        # Horizontal direction
        else:
            if self.pos[0] < self.last_pos[0]:
                return Direction.WEST
            elif self.pos[0] > self.last_pos[0]:
                return Direction.EAST
            else:
                return self.dir

    def is_digdug_in_front_of_enemy(self, enemy: dict) -> bool:
        direction = self.dir
        if direction == Direction.EAST and self.pos[1] == enemy["pos"][1] and self.pos[0] < enemy["pos"][0]:
            return True
        if direction == Direction.WEST and self.pos[1] == enemy["pos"][1] and self.pos[0] > enemy["pos"][0]:
            return True
        if direction == Direction.NORTH and self.pos[0] == enemy["pos"][0] and self.pos[1] > enemy["pos"][1]:
            return True
        if direction == Direction.SOUTH and self.pos[0] == enemy["pos"][0] and self.pos[1] < enemy["pos"][1]:
            return True
        return False

    def are_digdug_and_enemy_facing_each_other(self, enemy: dict) -> bool:
        digdug_direction: Direction = self.dir
        enemy_direction: Direction = enemy["dir"]

        if enemy_direction > 1:
            return digdug_direction == enemy_direction - 2
        return digdug_direction == enemy_direction + 2

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

    def dig_map(self, direction: Direction | None, fallback=None) -> str:
        if direction is None:
            return ""
        if fallback is None:
            fallback = []

        direction_mapping: dict[Direction, tuple[int, int, str]] = {
            Direction.NORTH: (0, -1, "w"),
            Direction.SOUTH: (0, 1, "s"),
            Direction.WEST: (-1, 0, "a"),
            Direction.EAST: (1, 0, "d"),
        }

        dx, dy, key = direction_mapping[direction]
        x = self.pos[0] + dx
        y = self.pos[1] + dy

        if (0 <= x < self.map_size[0] and 0 <= y < self.map_size[1]
                and not self.will_enemy_fire_at_digdug([x, y])
                and [x, y] not in self.pos_rocks) and not self.check_dist_all_enemies([x, y]):
            self.map[x][y] = 0

            print("Real move after checks: ", direction.name)
            return key
                
        return self.dig_map(fallback[0] if len(fallback) > 0 else None, fallback[1:])
    
    def check_dist_all_enemies(self, digdug_pos) -> bool:
        too_close = False
        x = digdug_pos[0]
        y = digdug_pos[1]
        for enemy in self.enemies:
            if enemy["name"] == "Fygar" and self.map[x][y] == 1 and not self.will_enemy_fire_at_digdug([x, y]):
                too_close = False
            elif Direction.NORTH and ((enemy["pos"][0] == x and enemy["pos"][1] == y) or (enemy["pos"][0] + 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] - 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] == x and enemy["pos"][1] + 1 == y)):
                too_close = True
            elif Direction.SOUTH and ((enemy["pos"][0] == x and enemy["pos"][1] == y) or (enemy["pos"][0] + 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] - 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] == x and enemy["pos"][1] - 1 == y)):
                too_close = True
            elif Direction.EAST and ((enemy["pos"][0] == x and enemy["pos"][1] == y) or (enemy["pos"][0] - 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] == x and enemy["pos"][1] + 1 == y) or (enemy["pos"][0] == x and enemy["pos"][1] - 1 == y)):
                too_close = True
            elif Direction.WEST and ((enemy["pos"][0] == x and enemy["pos"][1] == y) or (enemy["pos"][0] + 1 == x and enemy["pos"][1] == y) or (enemy["pos"][0] == x and enemy["pos"][1] + 1 == y) or (enemy["pos"][0] == x and enemy["pos"][1] - 1 == y)):
                too_close = True

        return too_close

    def get_lower_cost_enemy(self) -> dict:
        connections = []
        coordinates = {}
        for enemy in self.enemies:
            connections.append(
                ("digdug", enemy["id"], math.hypot(enemy["pos"][0] - self.pos[0], enemy["pos"][1] - self.pos[1])))
            coordinates[enemy["id"]] = tuple(enemy["pos"])
        coordinates["digdug"] = self.pos

        map_points = PointsGraph(connections, coordinates, self.map)

        chosen_enemy = {"pos": [0, 0], "cost": float("inf")}

        for enemy in self.enemies:
            if "traverse" not in enemy or len(self.enemies) == 1:
                p = SearchProblem(map_points, 'digdug', enemy["id"])
                t = SearchTree(p, 'a*')
                t.search()

                enemy["x_dist"]: int = enemy["pos"][0] - self.pos[0]
                enemy["y_dist"]: int = enemy["pos"][1] - self.pos[1]
                enemy["dist"]: int = abs(enemy["x_dist"]) + abs(enemy["y_dist"])
                enemy["cost"] = t.cost

                if enemy["cost"] < chosen_enemy["cost"]:
                    chosen_enemy = enemy
        return chosen_enemy

    def will_enemy_fire_at_digdug(self, digdug_new_pos: list[int]) -> bool:
        for enemy in self.enemies:
            if "name" in enemy and enemy["name"] == "Fygar":
                if enemy["dir"] == Direction.NORTH and \
                        digdug_new_pos[0] == enemy["pos"][0] and \
                        digdug_new_pos[1] in (enemy["pos"][1] - 1, enemy["pos"][1] - 2, enemy["pos"][1] - 3, enemy["pos"][1] - 4):
                    return True

                if enemy["dir"] == Direction.SOUTH and \
                        digdug_new_pos[0] == enemy["pos"][0] and \
                        digdug_new_pos[1] in (enemy["pos"][1] + 1, enemy["pos"][1] + 2, enemy["pos"][1] + 3, enemy["pos"][1] + 4):
                    return True

                if enemy["dir"] == Direction.EAST and \
                        digdug_new_pos[1] == enemy["pos"][1] and \
                        digdug_new_pos[0] in (enemy["pos"][0] + 1, enemy["pos"][0] + 2, enemy["pos"][0] + 3, enemy["pos"][0] + 4):
                    return True

                if enemy["dir"] == Direction.WEST and \
                        digdug_new_pos[1] == enemy["pos"][1] and \
                        digdug_new_pos[0] in (enemy["pos"][0] - 1, enemy["pos"][0] - 2, enemy["pos"][0] - 3, enemy["pos"][0] - 4):
                    return True
                
        return False
            
    def is_in_loop(self) -> bool:
        return self.previous_positions.count(self.pos) > 5

    def get_key(self, state: dict) -> str:
        if "digdug" in state:
            self.ts: float = state["ts"]
            self.last_pos: list[int] = self.pos
            self.pos: list[int] = state["digdug"]
            self.dir: Direction = self.get_digdug_direction()
            self.enemies: list[dict] = state["enemies"]
            self.previous_positions.append(self.pos)
            if 'rocks' in state:
                self.pos_rocks: list = [rock["pos"] for rock in state["rocks"]]

            chosen_enemy = self.get_lower_cost_enemy()

            print("\n--------------------")
            print("\npos digdug: ", self.pos)
            print("\nenemies: " + str(self.enemies))
            print("\nchosen enemy:", chosen_enemy)
            print("\nprevious positions: ", self.previous_positions)

            if "dist" not in chosen_enemy:
                return ""

            x_dist: int = chosen_enemy["x_dist"]
            y_dist: int = chosen_enemy["y_dist"]
            dist: int = chosen_enemy["dist"]

            # Change the direction when it bugs and just follows the enemy
            if "dir" in chosen_enemy and self.dir == chosen_enemy["dir"]:
                if x_dist == 1:
                    if y_dist in (0, -1, 1):
                        return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.WEST, Direction.EAST])
                    return self.dig_map(Direction.EAST, [Direction.WEST, Direction.NORTH, Direction.SOUTH])

                elif x_dist == -1:
                    if y_dist in (-1, 0, 1):
                        return self.dig_map(Direction.SOUTH, [Direction.NORTH, Direction.EAST, Direction.WEST])
                    return self.dig_map(Direction.WEST, [Direction.EAST, Direction.SOUTH, Direction.NORTH])

                elif y_dist == 1:
                    if x_dist in (-1, 0, 1):
                        return self.dig_map(Direction.EAST, [Direction.WEST, Direction.NORTH, Direction.SOUTH])
                    return self.dig_map(Direction.SOUTH, [Direction.NORTH, Direction.EAST, Direction.WEST])

                elif y_dist == -1:
                    if x_dist in (-1, 0, 1):
                        return self.dig_map(Direction.WEST, [Direction.EAST, Direction.SOUTH, Direction.NORTH])
                    return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.EAST, Direction.WEST])
                
            if self.is_in_loop():
                self.previous_positions = []
                if self.dir == Direction.EAST:
                    return self.dig_map(Direction.EAST, [Direction.WEST, Direction.NORTH, Direction.SOUTH])
                elif self.dir == Direction.WEST:
                    return self.dig_map(Direction.WEST, [Direction.EAST, Direction.NORTH, Direction.SOUTH])
                elif self.dir == Direction.NORTH:
                    return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.WEST, Direction.EAST])
                elif self.dir == Direction.SOUTH:   
                    return self.dig_map(Direction.SOUTH, [Direction.NORTH, Direction.WEST, Direction.EAST])

            # Move around the map
            def direction_mapping() -> tuple:
                if abs(x_dist) >= abs(y_dist):
                    if x_dist > 0:
                        return Direction.EAST, [Direction.SOUTH, Direction.NORTH, Direction.WEST]
                    return Direction.WEST, [Direction.NORTH, Direction.SOUTH, Direction.EAST]
                else:
                    if y_dist > 0:
                        return Direction.SOUTH, [Direction.EAST, Direction.WEST, Direction.NORTH]
                    return Direction.NORTH, [Direction.EAST, Direction.WEST, Direction.SOUTH]

            chosen_dir, fallback = direction_mapping()

            if dist <= 3:
                if self.is_digdug_in_front_of_enemy(chosen_enemy) \
                        and self.is_map_digged_to_direction(chosen_dir) \
                        and not self.will_enemy_fire_at_digdug([self.pos[0], self.pos[1]]) and not self.check_dist_all_enemies(self.pos):
                    self.previous_positions = []
                    return "A"
            return self.dig_map(chosen_dir, fallback)
                
        else:
            self.map = state["map"]
            self.map_size = state["size"]
            self.previous_positions = []

        return ""


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

                # Time sync
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
