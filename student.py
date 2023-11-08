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
        self.rocks: list = []
        self.score: int = 0
        self.step: int = 0
        self.timeout: int = 0
        self.map: list = []
        self.map_size: list = []

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

    def get_key(self, state: dict) -> str:
        if "digdug" in state:
            self.last_pos = self.pos
            self.pos = state["digdug"]
            self.dir = self.get_digdug_direction()
            self.enemies = state["enemies"]
            self.rocks = state["rocks"]

            chosen_enemy = self.get_lower_cost_enemy()
            
            print("pos enemy: ", chosen_enemy["pos"])
            print("pos digdug: ", self.pos)

            #dist = math.hypot(chosen_enemy["pos"][0] - self.pos[0], chosen_enemy["pos"][1] - self.pos[1])
            dist = (chosen_enemy["pos"][0]  - self.pos[0]) + (chosen_enemy["pos"][1] - self.pos[1])
            x_dist = chosen_enemy["pos"][0] - self.pos[0]
            y_dist = chosen_enemy["pos"][1] - self.pos[1]

            # Run away from the enemy if it's spilling fire
            if "fire" in chosen_enemy and dist <= 3 and self.are_digdug_and_enemy_facing_each_other(chosen_enemy):
                return self.dig_map(chosen_enemy["dir"])

            # Change the direction when it bugs and just follows the enemy
            if "dir" in chosen_enemy and self.dir == chosen_enemy["dir"]:
                if chosen_enemy["pos"][0] - self.pos[0] == 1:
                    if self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                        print("1 - B")
                        return self.dig_map(Direction.NORTH) if self.pos[1] > 0 else self.dig_map(Direction.SOUTH)
                    elif self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                        print("1 - C")
                        return self.dig_map(Direction.NORTH) if self.pos[1] > 0 else self.dig_map(Direction.SOUTH)
                    elif self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                        print("1 - D")
                        return self.dig_map(Direction.NORTH) if self.pos[1] > 0 else self.dig_map(Direction.SOUTH)
                    elif self.pos[0] + 1 == chosen_enemy["pos"][0] - 1 and self.pos[1] == chosen_enemy["pos"][1]:
                        print("1 - E")
                        return self.dig_map(Direction.NORTH) if self.pos[1] > 0 else self.dig_map(Direction.SOUTH)
                    return self.dig_map(Direction.EAST)

                elif chosen_enemy["pos"][0] - self.pos[0] == -1:
                    if self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                        print("2 - B")
                        return self.dig_map(Direction.SOUTH) if self.pos[1] < self.map_size[1] - 1 else self.dig_map(Direction.NORTH)
                    elif self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                        print("2 - C")
                        return self.dig_map(Direction.SOUTH) if self.pos[1] < self.map_size[1] - 1 else self.dig_map(Direction.NORTH)
                    elif self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                        print("2 - D")
                        return self.dig_map(Direction.SOUTH) if self.pos[1] < self.map_size[1] - 1 else self.dig_map(Direction.NORTH)
                    elif self.pos[0] - 1 == chosen_enemy["pos"][0] + 1 and self.pos[1] == chosen_enemy["pos"][1]:
                        print("2 - E")
                        return self.dig_map(Direction.SOUTH) if self.pos[1] < self.map_size[1] - 1 else self.dig_map(Direction.NORTH)
                    return self.dig_map(Direction.WEST)

                elif chosen_enemy["pos"][1] - self.pos[1] == 1:
                    if self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                        print("3 - B")
                        return self.dig_map(Direction.EAST) if self.pos[0] < self.map_size[0] - 1 else self.dig_map(Direction.WEST)
                    elif self.pos[0] == chosen_enemy["pos"][0] + 1 and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                        print("3 - C")
                        return self.dig_map(Direction.EAST) if self.pos[0] < self.map_size[0] - 1 else self.dig_map(Direction.WEST)
                    elif self.pos[0] == chosen_enemy["pos"][0] -1 and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                        print("3 - D")
                        return self.dig_map(Direction.EAST) if self.pos[0] < self.map_size[0] - 1 else self.dig_map(Direction.WEST)
                    elif self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1] - 1:
                        print("3 - E")
                        return self.dig_map(Direction.EAST) if self.pos[0] < self.map_size[0] - 1 else self.dig_map(Direction.WEST)
                    return self.dig_map(Direction.SOUTH)

                elif chosen_enemy["pos"][1] - self.pos[1] == -1:
                    if self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                        print("4 - B")
                        return self.dig_map(Direction.WEST) if self.pos[0] > 0 else self.dig_map(Direction.EAST)
                    elif self.pos[0] == chosen_enemy["pos"][0] + 1 and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                        print("4 - C")
                        return self.dig_map(Direction.WEST) if self.pos[0] > 0 else self.dig_map(Direction.EAST)
                    elif self.pos[0] == chosen_enemy["pos"][0] - 1 and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                        print("4 - D")
                        return self.dig_map(Direction.WEST) if self.pos[0] > 0 else self.dig_map(Direction.EAST)
                    elif self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1] + 1:
                        print("4 - E")
                        return self.dig_map(Direction.WEST) if self.pos[0] > 0 else self.dig_map(Direction.EAST)
                    return self.dig_map(Direction.NORTH)
                
            
            # Move around the map
            if abs(x_dist) >= abs(y_dist):
                if x_dist > 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy)  and self.is_map_digged_to_direction(Direction.EAST):
                            print("1 - A")
                            return "A"
                        if self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                            print("1 - B")
                            if self.pos[1] > 0:
                                return self.dig_map(Direction.NORTH)
                            else:
                                return self.dig_map(Direction.SOUTH)
                        elif self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                            print("1 - C")
                            if self.pos[1] > 0:
                                return self.dig_map(Direction.NORTH)
                            else:
                                return self.dig_map(Direction.SOUTH)
                        elif self.pos[0] + 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                            print("1 - D")
                            if self.pos[1] > 0:
                                return self.dig_map(Direction.NORTH)
                            else:
                                return self.dig_map(Direction.SOUTH)
                        elif self.pos[0] + 1 == chosen_enemy["pos"][0] - 1 and self.pos[1] == chosen_enemy["pos"][1]:
                            print("1 - E")
                            if self.pos[1] > 0:
                                return self.dig_map(Direction.NORTH)
                            else:
                                return self.dig_map(Direction.SOUTH)
                    print("EAST")
                    return self.dig_map(Direction.EAST)
                elif x_dist < 0:
                    if dist <= 3 :
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) and self.is_map_digged_to_direction(Direction.WEST): 
                            print("2 - A")
                            return "A" 
                        if self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] == chosen_enemy["pos"][1]:
                            print("2 - B")
                            if self.pos[1] < self.map_size[1] - 1:
                                return self.dig_map(Direction.SOUTH)
                            else:
                                return self.dig_map(Direction.NORTH)
                        elif self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                            print("2 - C")
                            if self.pos[1] < self.map_size[1] - 1:
                                return self.dig_map(Direction.SOUTH)
                            else:
                                return self.dig_map(Direction.NORTH)
                        elif self.pos[0] - 1 == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                            print("2 - D")
                            if self.pos[1] < self.map_size[1] - 1:
                                return self.dig_map(Direction.SOUTH)
                            else:
                                return self.dig_map(Direction.NORTH)
                        elif self.pos[0] - 1 == chosen_enemy["pos"][0] + 1 and self.pos[1] == chosen_enemy["pos"][1]:
                            print("2 - E")
                            if self.pos[1] < self.map_size[1] - 1:
                                return self.dig_map(Direction.SOUTH)
                            else:
                                return self.dig_map(Direction.NORTH)    
                    print("WEST")
                    return self.dig_map(Direction.WEST)
            else:
                if y_dist > 0:
                    if dist <= 3 :
                        if self.is_digdug_in_front_of_enemy(chosen_enemy) and self.is_map_digged_to_direction(Direction.SOUTH):
                            print("3 - A")
                            return "A"
                        if self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                            print("3 - B")
                            if self.pos[0] < self.map_size[0] - 1:
                                return self.dig_map(Direction.EAST)
                            return self.dig_map(Direction.WEST)
                        elif self.pos[0] == chosen_enemy["pos"][0] + 1 and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                            print("3 - C")
                            if self.pos[0] < self.map_size[0] - 1:
                                return self.dig_map(Direction.EAST)
                            return self.dig_map(Direction.WEST)
                        elif self.pos[0] == chosen_enemy["pos"][0] -1 and self.pos[1] + 1 == chosen_enemy["pos"][1]:
                            print("3 - D")
                            if self.pos[0] < self.map_size[0] - 1:
                                return self.dig_map(Direction.EAST)
                            return self.dig_map(Direction.WEST)
                        elif self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] + 1 == chosen_enemy["pos"][1] - 1:
                            print("3 - E")
                            if self.pos[0] < self.map_size[0] - 1:
                                return self.dig_map(Direction.EAST)
                            return self.dig_map(Direction.WEST)
                    print("SOUTH")
                    return self.dig_map(Direction.SOUTH)
                elif y_dist < 0:
                    if dist <= 3:
                        if self.is_digdug_in_front_of_enemy(chosen_enemy)  and self.is_map_digged_to_direction(Direction.NORTH):
                            print("4 - A")
                            return "A"
                        if self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                            print("4 - B")
                            if self.pos[0] > 0:
                                return self.dig_map(Direction.WEST)
                            return self.dig_map(Direction.EAST)
                        elif self.pos[0] == chosen_enemy["pos"][0] + 1 and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                            print("4 - C")
                            if self.pos[0] > 0:
                                return self.dig_map(Direction.WEST)
                            return self.dig_map(Direction.EAST)
                        elif self.pos[0] == chosen_enemy["pos"][0] - 1 and self.pos[1] - 1 == chosen_enemy["pos"][1]:
                            print("4 - D")
                            if self.pos[0] > 0:
                                return self.dig_map(Direction.WEST)
                            return self.dig_map(Direction.EAST)
                        elif self.pos[0] == chosen_enemy["pos"][0] and self.pos[1] - 1 == chosen_enemy["pos"][1] + 1:
                            print("4 - E")
                            if self.pos[0] > 0:
                                return self.dig_map(Direction.WEST)
                            return self.dig_map(Direction.EAST)
                    print("NORTH")
                    return self.dig_map(Direction.NORTH)


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
