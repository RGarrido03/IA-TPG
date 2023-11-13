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
        x1, y1 = self.coordinates[point]
        x2, y2 = self.coordinates[goal_point]
        return (x2 - x1) + (y2 - y1)

    def satisfies(self, point, goal_point) -> bool:
        return goal_point == point


class Agent:
    def __init__(self):
        self.state: dict = {}
        self.pos: list[int] = []
        self.last_pos: list[int] = []
        self.dir: Direction = Direction.EAST
        self.enemies: list = []
        self.level: int = 1
        self.lives: int = 3
        self.player: str = ""
        self.score: int = 0
        self.step: int = 0
        self.timeout: int = 0
        self.map: list = []
        self.map_size: list = []
        self.pos_rocks: list = []

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

    def will_enemy_fire_at_digdug(self, enemy: dict, digdug_new_pos: list[int]) -> bool:
        if "name" not in enemy or enemy["name"] != "Fygar":
            return False

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

    def get_key(self, state: dict) -> str:
        if "digdug" in state:
            self.last_pos = self.pos
            self.pos = state["digdug"]
            self.dir = self.get_digdug_direction()
            self.enemies = state["enemies"]
            if 'rocks' in state:
                self.pos_rocks = [rock["pos"] for rock in state["rocks"]]

            chosen_enemy = self.get_lower_cost_enemy()

            print("pos enemy: ", chosen_enemy["pos"])
            print("pos digdug: ", self.pos)

            x_dist: int = chosen_enemy["pos"][0] - self.pos[0]
            y_dist: int = chosen_enemy["pos"][1] - self.pos[1]
            dist: int = x_dist + y_dist

            # Change the direction when it bugs and just follows the enemy
            if "dir" in chosen_enemy and self.dir == chosen_enemy["dir"]:
                print("BUG")
                if x_dist == 1 and ([self.pos[0] + 1, self.pos[1]] or [self.pos[0], self.pos[1] - 1] or [self.pos[0], self.pos[1] + 1]) not in self.pos_rocks:
                    print("EAST")
                    if y_dist in (0, -1, 1):
                        if self.pos[1] - 1 >= 0 and [self.pos[0], self.pos[1] - 1] not in self.pos_rocks and y_dist != -1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            return self.dig_map(Direction.NORTH)
                        elif ([self.pos[0], self.pos[1] + 1]) not in self.pos_rocks and y_dist != 1 and self.pos[1] + 1 <= self.map_size[1] - 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                        elif ([self.pos[0] - 1, self.pos[1]]) not in self.pos_rocks and self.pos[0] - 1 >= 0 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                    return self.dig_map(Direction.EAST)

                elif x_dist == -1 and ([self.pos[0] - 1, self.pos[1]] or [self.pos[0], self.pos[1] - 1] or [self.pos[0], self.pos[1] + 1]) not in self.pos_rocks:
                    print("WEST")
                    if y_dist in (-1, 0, 1):
                        if self.pos[1] + 1 <= self.map_size[1] - 1 and [self.pos[0], self.pos[1] + 1] not in self.pos_rocks and y_dist != 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                        elif ([self.pos[0], self.pos[1] - 1]) not in self.pos_rocks and y_dist != -1 and self.pos[1] - 1 >= 0 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            return self.dig_map(Direction.NORTH)
                        elif ([self.pos[0] + 1, self.pos[1]]) not in self.pos_rocks and self.pos[0] + 1 <= self.map_size[0] - 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                    return self.dig_map(Direction.WEST)

                elif y_dist == 1 :
                    print("SOUTH")
                    if x_dist in (-1, 0, 1) and ([self.pos[0] - 1, self.pos[1]] or [self.pos[0] + 1, self.pos[1]] or [self.pos[0], self.pos[1] + 1]) not in self.pos_rocks:
                        if [self.pos[0] + 1, self.pos[1]] not in self.pos_rocks and x_dist != 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                        elif ([self.pos[0] - 1, self.pos[1]]) not in self.pos_rocks and x_dist != -1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                        elif ([self.pos[0], self.pos[1] - 1]) not in self.pos_rocks and self.pos[1] - 1 >= 0 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            self.dig_map(Direction.NORTH)
                    return self.dig_map(Direction.SOUTH)

                elif y_dist == -1:
                    print("NORTH")
                    if x_dist in (-1, 0, 1) and ([self.pos[0] - 1, self.pos[1]] or [self.pos[0] + 1, self.pos[1]] or [self.pos[0], self.pos[1] - 1]) not in self.pos_rocks:
                        if self.pos[0] - 1 not in self.pos_rocks and x_dist != -1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                        elif ([self.pos[0] + 1, self.pos[1]]) not in self.pos_rocks and x_dist != 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                        elif ([self.pos[0], self.pos[1] + 1]) not in self.pos_rocks and self.pos[1] + 1 <= self.map_size[1] - 1 and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                    return self.dig_map(Direction.NORTH)

            # Move around the map
            if abs(x_dist) >= abs(y_dist):
                print("X")
                if x_dist > 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) and self.is_map_digged_to_direction(Direction.EAST):
                            print("1 - A")
                            return "A"
                        if ((x_dist != 1 or y_dist not in (-1, 0, 1)) and (x_dist != 2 or y_dist != 0)) and [self.pos[0]+1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                        elif (x_dist != 1 or y_dist != -1) and self.pos[1] - 1 >= 0 and [self.pos[0], self.pos[1] - 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            return self.dig_map(Direction.NORTH)
                        elif (x_dist != 1 or y_dist != 1) and self.pos[1] +1 <= self.map_size[1] - 1 and [self.pos[0], self.pos[1] + 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                        elif (x_dist != 1 or y_dist != 0):
                            return self.dig_map(Direction.WEST)
                    print("EAST")
                    if [self.pos[0]+1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.EAST)
                    elif [self.pos[0], self.pos[1] + 1] not in self.pos_rocks:
                        return self.dig_map(Direction.SOUTH)
                    elif [self.pos[0], self.pos[1] - 1] not in self.pos_rocks:
                        return self.dig_map(Direction.NORTH)
                    elif self.pos[0] - 1 >= 0:
                        return self.dig_map(Direction.WEST)
                elif x_dist < 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) and self.is_map_digged_to_direction(Direction.WEST):
                            print("2 - A")
                            return "A"
                        if ((x_dist != -1 or y_dist not in (-1, 0, 1)) and (x_dist != -2 or y_dist != 0)) and [self.pos[0]-1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                        elif (x_dist != -1 or y_dist != -1) and self.pos[1] - 1 >= 0 and [self.pos[0], self.pos[1] - 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            return self.dig_map(Direction.NORTH)
                        elif (x_dist != -1 or y_dist != 1) and self.pos[1] + 1 <= self.map_size[1] - 1 and [self.pos[0], self.pos[1] + 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                        elif self.pos[0] + 1 <= self.map_size[0] - 1:
                            return self.dig_map(Direction.EAST)
                    print("WEST")
                    if [self.pos[0]-1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.WEST)
                    elif [self.pos[0], self.pos[1] + 1] not in self.pos_rocks:
                        return self.dig_map(Direction.SOUTH)
                    elif [self.pos[0], self.pos[1] - 1] not in self.pos_rocks:
                        return self.dig_map(Direction.NORTH)
                    elif self.pos[0] + 1 <= self.map_size[0] - 1:
                        return self.dig_map(Direction.EAST)
            else:
                if y_dist > 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) and self.is_map_digged_to_direction(Direction.SOUTH):
                            print("3 - A")
                            return "A"
                        if ((y_dist != 1 or x_dist not in (-1, 0, 1)) and (y_dist != 2 or x_dist != 0)) and [self.pos[0], self.pos[1] + 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] + 1]):
                            return self.dig_map(Direction.SOUTH)
                        elif (y_dist != 1 or x_dist != 1) and self.pos[0] + 1 <= self.map_size[0] - 1 and [self.pos[0] + 1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                        elif (y_dist != 1 or x_dist != -1) and self.pos[0] -1 >= 0 and [self.pos[0] - 1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                        elif self.pos[0] - 1 >= 0:
                            return self.dig_map(Direction.NORTH)
                    print("SOUTH")
                    if [self.pos[0], self.pos[1]+1] not in self.pos_rocks:
                        return self.dig_map(Direction.SOUTH)
                    elif [self.pos[0] + 1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.EAST)
                    elif [self.pos[0] - 1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.WEST)
                    elif self.pos[0] - 1 >= 0:
                        return self.dig_map(Direction.NORTH)
                elif y_dist < 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy)  and self.is_map_digged_to_direction(Direction.NORTH):
                            print("4 - A")
                            return "A"
                        if ((y_dist != -1 or x_dist not in (-1, 0, 1)) and (y_dist != -2 or x_dist != 0)) and [self.pos[0], self.pos[1] - 1] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0], self.pos[1] - 1]):
                            return self.dig_map(Direction.NORTH)
                        elif (y_dist != -1 or x_dist != 1) and self.pos[0] + 1 <= self.map_size[0] - 1 and [self.pos[0] + 1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] + 1, self.pos[1]]):
                            return self.dig_map(Direction.EAST)
                        elif (y_dist != -1 or x_dist != -1) and self.pos[0] -1 >= 0 and [self.pos[0] - 1, self.pos[1]] not in self.pos_rocks and not self.will_enemy_fire_at_digdug(chosen_enemy, [self.pos[0] - 1, self.pos[1]]):
                            return self.dig_map(Direction.WEST)
                        elif self.pos[1] + 1 <= self.map_size[1] - 1:
                            return self.dig_map(Direction.SOUTH)
                    print("NORTH")
                    if [self.pos[0], self.pos[1]-1] not in self.pos_rocks:
                        return self.dig_map(Direction.NORTH)
                    elif [self.pos[0] + 1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.EAST)
                    elif [self.pos[0] - 1, self.pos[1]] not in self.pos_rocks:
                        return self.dig_map(Direction.WEST)
                    elif self.pos[1] + 1 <= self.map_size[1] - 1:
                        return self.dig_map(Direction.SOUTH)
        else:
            self.map = state["map"]
            self.map_size = state["size"]

        print("Nothing to do")
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

                #print("Received game update: ", state)

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
