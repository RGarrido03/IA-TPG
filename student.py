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
        self.enemies: list[dict] = []
        self.level: int = 1
        self.lives: int = 3
        self.player: str = ""
        self.score: int = 0
        self.step: int = 0
        self.timeout: int = 0
        self.ts: float = 0.0
        self.map: list = []
        self.map_size: list = []
        self.pos_rocks: list = []
        self.previous_pos: list = []
        self.previous_dir: list = []

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
                and not self.will_enemy_fire_at_digdug(self.enemies, [x, y])
                and [x, y] not in self.pos_rocks):
            self.map[x][y] = 0
            print("Real move after checks: ", direction.name)
            return key
        return self.dig_map(fallback[0] if len(fallback) > 0 else None, fallback[1:])

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
            #if "traverse" not in enemy or len(self.enemies) == 1:
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

    def will_enemy_fire_at_digdug(self, enemies: [], digdug_new_pos: list[int]) -> bool:
        
        res = False
        for enemy in enemies:
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

            if  "name" in enemy and enemy["name"] == "Fygar" and  enemy["dir"] == Direction.EAST and \
                    digdug_new_pos[1] == enemy["pos"][1] and \
                    digdug_new_pos[0] in (enemy["pos"][0] + 1, enemy["pos"][0] + 2, enemy["pos"][0] + 3, enemy["pos"][0] + 4):
                res = True

            if  "name" in enemy and enemy["name"] == "Fygar" and enemy["dir"] == Direction.WEST and \
                    digdug_new_pos[1] == enemy["pos"][1] and \
                    digdug_new_pos[0] in (enemy["pos"][0] - 1, enemy["pos"][0] - 2, enemy["pos"][0] - 3, enemy["pos"][0] - 4):
                res = True

        return res

    def get_key(self, state: dict) -> str:
        if "digdug" in state:
            self.ts: float = state["ts"]
            print("\nTimestamp from server:", self.ts)
            print("Timestamp before tree search:", time.time())
            self.last_pos: list[int] = self.pos
            self.pos: list[int] = state["digdug"]
            self.dir: Direction = self.get_digdug_direction()
            self.enemies: list[dict] = state["enemies"]
            if 'rocks' in state:
                self.pos_rocks: list = [rock["pos"] for rock in state["rocks"]]

            chosen_enemy = self.get_lower_cost_enemy()
            other_enemies = [enemy for enemy in self.enemies if enemy["id"] != chosen_enemy["id"]]

            print("Timestamp after tree search:", time.time())
            print("pos digdug: ", self.pos)
            print("pos enemy: ", chosen_enemy["pos"])
            print("pos other enemies: ", [enemy["pos"] for enemy in other_enemies])
            print("enemies: " + str(self.enemies))
            print("chosen enemy:", chosen_enemy)
            
            if len(self.previous_pos) == 6:
                print("pos: ", str(self.pos))
                self.previous_pos.pop(0)
                self.previous_dir.pop(0)
                self.previous_pos.append(self.pos)  
                self.previous_dir.append(self.dir)
            else:
                print("pos: ", str(self.pos))
                self.previous_pos.append(self.pos)
                self.previous_dir.append(self.dir)

            if "dist" not in chosen_enemy:
                print("-> No enemy")
                return ""
            
            print("dir enemy: ", chosen_enemy["dir"])

            x_dist: int = chosen_enemy["x_dist"]
            y_dist: int = chosen_enemy["y_dist"]
            dist: int = chosen_enemy["dist"]

            # Run away when there are multiple enemies
            left = [enemy for enemy in other_enemies if enemy["dist"] <= 3 and enemy["pos"][0] < self.pos[0] and enemy["pos"][1] == self.pos[1]]
            right = [enemy for enemy in other_enemies if enemy["dist"] <= 3 and enemy["pos"][0] > self.pos[0] and enemy["pos"][1] == self.pos[1]]
            top = [enemy for enemy in other_enemies if enemy["dist"] <= 3 and enemy["pos"][0] == self.pos[0] and enemy["pos"][1] < self.pos[1]]
            bottom = [enemy for enemy in other_enemies if enemy["dist"] <= 3 and enemy["pos"][0] == self.pos[0] and enemy["pos"][1] > self.pos[1]]

            if len(left + right + top + bottom) >= 1:
                print("-> Multiple enemies")
                sorted_enemies = sorted([(Direction.SOUTH, len(bottom)), (Direction.WEST, len(left)), (Direction.EAST, len(right)), (Direction.NORTH, len(top))], key=lambda x: x[1])
                for new_dir, length in sorted_enemies:
                    if ((new_dir == Direction.SOUTH and self.pos[1] + 1 <= self.map_size[1] - 1) or
                            (new_dir == Direction.WEST and self.pos[0] - 1 >= 0) or
                            (new_dir == Direction.EAST and self.pos[0] + 1 <= self.map_size[0] - 1) or
                            (new_dir == Direction.NORTH and self.pos[1] - 1 >= 0)):
                        print("   " + sorted_enemies[0][0].name)
                        print("2º - dig new dir: ", new_dir)
                        return self.dig_map(new_dir)

            # Change the direction when it bugs and just follows the enemy
            if "dir" in chosen_enemy and self.dir == chosen_enemy["dir"]:
                print("BUG")
                if x_dist == 1:
                    print("EAST")
                    if y_dist in (0, -1, 1):
                        if y_dist != -1:
                            print("3º - NORTH")
                            return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.WEST, Direction.EAST])
                        if y_dist != 1:
                            print("3º - SOUTH")
                            return self.dig_map(Direction.SOUTH, [Direction.WEST, Direction.EAST])
                        print("3º - WEST")
                        return self.dig_map(Direction.WEST, [Direction.EAST])
                    print("3º - EAST")
                    return self.dig_map(Direction.EAST)

                elif x_dist == -1:
                    print("WEST")
                    if y_dist in (-1, 0, 1):
                        if y_dist != 1:
                            print("4º - SOUTH")
                            return self.dig_map(Direction.SOUTH, [Direction.NORTH, Direction.EAST, Direction.WEST])
                        if y_dist != -1:
                            print("4º - NORTH")
                            return self.dig_map(Direction.NORTH, [Direction.EAST, Direction.WEST])
                        print("4º - EAST")
                        return self.dig_map(Direction.EAST, [Direction.WEST])
                    print("4º - WEST")
                    return self.dig_map(Direction.WEST)

                elif y_dist == 1:
                    print("SOUTH")
                    if x_dist in (-1, 0, 1):
                        if x_dist != 1:
                            print("5º - EAST")
                            return self.dig_map(Direction.EAST, [Direction.WEST, Direction.NORTH, Direction.SOUTH])
                        elif x_dist != -1:
                            print("5º - WEST")
                            return self.dig_map(Direction.WEST, [Direction.NORTH, Direction.SOUTH])
                        print("5º - NORTH")
                        return self.dig_map(Direction.NORTH, [Direction.SOUTH])
                    print("5º - SOUTH")
                    return self.dig_map(Direction.SOUTH)

                elif y_dist == -1:
                    print("NORTH")
                    if x_dist in (-1, 0, 1):
                        if x_dist != -1:
                            print("6º - WEST")
                            return self.dig_map(Direction.WEST, [Direction.EAST, Direction.SOUTH, Direction.NORTH])
                        elif x_dist != 1:
                            print("6º - EAST")
                            return self.dig_map(Direction.EAST, [Direction.SOUTH, Direction.NORTH])
                        print("6º - SOUTH")
                        return self.dig_map(Direction.SOUTH, [Direction.NORTH])
                    print("6º - NORTH")
                    return self.dig_map(Direction.NORTH)

            # Move around the map
            if abs(x_dist) >= abs(y_dist):
                print("X")
                if x_dist > 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) \
                                and self.is_map_digged_to_direction(Direction.EAST) \
                                and not self.will_enemy_fire_at_digdug(self.enemies, [self.pos[0], self.pos[1]]):
                            print("1 - A")
                            return "A"
                        if (x_dist != 1 or y_dist not in (-1, 0, 1)) and (x_dist != 2 or y_dist != 0):
                            print("7º - EAST")
                            return self.dig_map(Direction.EAST, [Direction.NORTH, Direction.SOUTH, Direction.WEST])
                        elif x_dist != 1 or y_dist != -1:
                            print("7º - NORTH")
                            return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.WEST])
                        elif x_dist != 1 or y_dist != 1:
                            print("7º - SOUTH")
                            return self.dig_map(Direction.SOUTH, [Direction.WEST])
                        elif x_dist != 1 or y_dist != 0:
                            print("7º - WEST")
                            return self.dig_map(Direction.WEST)
                    print("8º - EAST")
                    return self.dig_map(Direction.EAST, [Direction.SOUTH, Direction.NORTH, Direction.WEST])
                elif x_dist < 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) \
                                and self.is_map_digged_to_direction(Direction.WEST) \
                                and not self.will_enemy_fire_at_digdug(self.enemies, [self.pos[0], self.pos[1]]):
                            print("2 - A")
                            return "A"
                        if (x_dist != -1 or y_dist not in (-1, 0, 1)) and (x_dist != -2 or y_dist != 0):
                            print("9º - WEST")
                            return self.dig_map(Direction.WEST, [Direction.NORTH, Direction.SOUTH, Direction.EAST])
                        elif x_dist != -1 or y_dist != -1:
                            print("9º - NORTH")
                            return self.dig_map(Direction.NORTH, [Direction.SOUTH, Direction.EAST])
                        elif x_dist != -1 or y_dist != 1:
                            print("9º - SOUTH")
                            return self.dig_map(Direction.SOUTH, [Direction.EAST])
                        print("9º - EAST")
                        return self.dig_map(Direction.EAST)
                    print("10º - WEST")
                    return self.dig_map(Direction.WEST, [Direction.NORTH, Direction.SOUTH, Direction.EAST])
            else:
                if y_dist > 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) \
                                and self.is_map_digged_to_direction(Direction.SOUTH) \
                                and not self.will_enemy_fire_at_digdug(self.enemies, [self.pos[0], self.pos[1]]):
                            print("3 - A")
                            return "A"
                        if (y_dist != 1 or x_dist not in (-1, 0, 1)) and (y_dist != 2 or x_dist != 0):
                            print("11º - SOUTH")
                            return self.dig_map(Direction.SOUTH, [Direction.EAST, Direction.WEST, Direction.NORTH])
                        elif y_dist != 1 or x_dist != 1:
                            print("11º - EAST")
                            return self.dig_map(Direction.EAST, [Direction.WEST, Direction.NORTH])
                        elif y_dist != 1 or x_dist != -1:
                            print("11º - WEST")
                            return self.dig_map(Direction.WEST, [Direction.NORTH])
                        print("11º - NORTH")
                        return self.dig_map(Direction.NORTH)
                    print("12º - SOUTH")
                    return self.dig_map(Direction.SOUTH, [Direction.EAST, Direction.WEST, Direction.NORTH])
                elif y_dist < 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) \
                                and self.is_map_digged_to_direction(Direction.NORTH) \
                                and not self.will_enemy_fire_at_digdug(self.enemies, [self.pos[0], self.pos[1]]):
                            print("4 - A")
                            return "A"
                        if (y_dist != -1 or x_dist not in (-1, 0, 1)) and (y_dist != -2 or x_dist != 0):
                            print("13º - NORTH")
                            return self.dig_map(Direction.NORTH)
                        elif y_dist != -1 or x_dist != 1:
                            print("13º - EAST")
                            return self.dig_map(Direction.EAST)
                        elif y_dist != -1 or x_dist != -1:
                            print("13º - WEST")
                            return self.dig_map(Direction.WEST)
                        print("13º - SOUTH")
                        return self.dig_map(Direction.SOUTH)
                    print("14º - NORTH")
                    return self.dig_map(Direction.NORTH, [Direction.EAST, Direction.WEST, Direction.SOUTH])
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
                print("Timestamp after calculating tree:", time.time())
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
