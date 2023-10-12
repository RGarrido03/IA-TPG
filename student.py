"""Example client."""
import asyncio
import getpass
import json
import os
import websockets
import pprint


class Agent:
    # Placeholder
    def __init__(self):
        self.state: dict[str, object] | None = None

    def get_key(self, state: dict[str, object]):
        self.state = state
        return ""


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
                # pprint.pprint(state)

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
