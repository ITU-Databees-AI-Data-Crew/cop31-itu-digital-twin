"""Chat with the agent in the terminal, no frontend needed.

    cd backend
    OPENROUTER_API_KEY=... python -m app.agent

UI actions are printed and applied to a pretend screen state,
so follow-up questions like "and its water?" work.
"""

from datetime import datetime

from app.contract import UiState

from . import Agent


def main() -> None:
    agent = Agent()
    screen = UiState(sim_time=datetime(2026, 11, 14, 10, 0))

    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue

        out = agent.run("cli", message, screen)

        for action in out.ui_actions:
            print(f"  [screen] {action.type} {action.args}")
            if action.type == "SelectBuilding":
                screen.selected_building = action.args["building_id"]
            elif action.type == "OpenSystem":
                screen.system = action.args["system"]
            elif action.type == "ShowScenario":
                screen.scenario_id = action.args["scenario_id"]
        print(f"agent> {out.reply}\n")


if __name__ == "__main__":
    main()
