"""Allow `python -m agentxray`."""

import sys

from .cli import main

sys.exit(main())
