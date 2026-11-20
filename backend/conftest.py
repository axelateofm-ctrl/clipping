"""Rend le paquet ``app`` importable quand on lance pytest depuis backend/."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
