"""
Package execution entrypoint for app module.
Allows running via `python -m app`.
"""
import sys
from app.process import main

if __name__ == "__main__":
    sys.exit(main())
