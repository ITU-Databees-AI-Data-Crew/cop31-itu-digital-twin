"""Chat with the agent in the terminal, no frontend needed.

    cd backend
    python -m app.agent          (OPENROUTER_API_KEY from the environment or backend/.env)

The answer streams in as it's written. UI actions are printed and applied to a pretend screen state (and SetTime to the real app clock),
so follow-up questions like "and its water?" work.
"""

from app.contract import UiState
from app.sim.clock import CLOCK

from . import Agent


def main() -> None:
    agent = Agent()
    screen = UiState(sim_time=CLOCK.now().to_pydatetime())
    print(f"App time: {screen.sim_time:%Y-%m-%d %H:%M}. Ctrl-D to quit.\n")

    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue

        screen.sim_time = CLOCK.now().to_pydatetime()
        print("agent> ", end="", flush=True)
        for event in agent.stream("cli", message, screen):
            if event["type"] == "text":
                print(event["delta"], end="", flush=True)
            elif event["type"] == "tool":
                print(f"\n  [checking] {event['name']} {event['args']}", flush=True)
            elif event["type"] == "error":
                print(f"\n  [error] {event['detail']}")
            elif event["type"] == "ui_action":
                action = event["action"]
                print(f"\n  [screen] {action['type']} {action['args']}", flush=True)
                if action["type"] == "SelectBuilding":
                    screen.selected_building = action["args"]["building_id"]
                elif action["type"] == "OpenSystem":
                    screen.system = action["args"]["system"]
                elif action["type"] == "ShowScenario":
                    screen.scenario_id = action["args"]["scenario_id"]
                elif action["type"] == "SetTime":
                    CLOCK.set_time(action["args"]["time"])
        print("\n")


if __name__ == "__main__":
    main()
