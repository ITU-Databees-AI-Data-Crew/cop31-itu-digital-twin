"""Generator: makes a believable year of synthetic campus data.

Real inputs (data/inputs/, from data/fetch_inputs.py): building sizes and shapes,
hourly weather, and the academic calendar. Everything else is synthetic, driven by
the knobs in params.yaml and a fixed seed (same seed = same data).

Run:  python -m app.generator [--plot]
"""
