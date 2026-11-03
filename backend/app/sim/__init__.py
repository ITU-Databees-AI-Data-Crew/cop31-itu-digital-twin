"""Simulation engine: owns "now" (clock.py) and what-ifs (scenarios.py, whatif.py, presets.py).

engine.py has the questions: the Data API's questions with the clock and what-ifs applied.
Anyone who wants "now" or what-if numbers asks here; plain history can go to the Data API directly.

The current campus = baseline + every APPLIED what-if. A DRAFT is only shown when asked for
(scenario_id=...), on top of the current campus. Nothing here ever changes the stored numbers.
"""
