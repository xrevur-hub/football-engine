"""
football_engine.api — HTTP/web adapter layer.

This package is a *boundary*, not a model. It contains no football
mathematics: it loads the dataset through the existing Layer 1 loader, walks
the existing Layer 2-6 call order, and projects the resulting engine objects
into JSON. See `adapter.py` for the call order and `pitch_formation.py` for the
free-placement grid -> Formation template mapping.
"""
