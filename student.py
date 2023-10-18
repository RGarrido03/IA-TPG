"""Example client."""
import asyncio
import getpass
import json
import os
import websockets
import pprint

import math


class Agent:
    def __init__(self):
        self.pos = None
        self.state: dict[str, object] | None = None

    def get_key(self, state: dict[str, object]):
        self.state = state
        if "digdug" in self.state:
            self.pos = self.state["digdug"]
            for enemy in self.state["enemies"]:
                dist = math.hypot(enemy["pos"][0] - self.pos[0], enemy["pos"][1] - self.pos[1])

                if dist <= 3:
                    return "A"
                else:
                    # persegue o inimigo
                    if enemy["pos"][0] > self.pos[0]:
                        return "d"
                    elif enemy["pos"][0] < self.pos[0]:
                        return "a"
                    elif enemy["pos"][1] > self.pos[1]:
                        return "s"
                    elif enemy["pos"][1] < self.pos[1]:
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
