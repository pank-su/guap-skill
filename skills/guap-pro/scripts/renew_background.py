#!/usr/bin/env python3
"""No-agent GUAP renewal tick; successes and repeated failures stay silent."""
import os
import sys
from pathlib import Path

home = Path(os.environ.get('HERMES_HOME', str(Path.home() / '.hermes'))).expanduser()
sys.path.insert(0, str(home / 'skills' / 'guap-pro' / 'scripts'))
from session_client import background_tick

if __name__ == '__main__':
    notice = background_tick()
    if notice:
        print(notice)
