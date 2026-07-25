"""
Dry-run integration test suite 'Run All'.

Responsibilities:
- Implements automated tests, mock execution environments, or workflow assertions to verify core features.

Coupling:
- Triggered by pytest or CI workflows to guarantee codebase stability without making active live API requests.
"""


from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dryrun.test_full_workflow import main as workflow_main
from dryrun.test_auto_mode import main as auto_main
from dryrun.test_jdocs import main as jdocs_main
from dryrun.test_e2e_simulation import main as e2e_main
from dryrun.test_gaps import main as gaps_main


async def run_all():
    print()
    await workflow_main()
    print()
    await auto_main()
    print()
    await jdocs_main()
    print()
    await e2e_main()
    print()
    await gaps_main()
    print()
    print("*" * 50)
    print("ALL DRY RUN SUITES PASSED")
    print("*" * 50)


if __name__ == "__main__":
    asyncio.run(run_all())
