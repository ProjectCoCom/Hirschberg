"""
Summary: Python logic module 'Test Jdocs'.

What it does: Provides backend utility operations and core logical helper interfaces for 'Test Jdocs'.

How it fits in: Imported and utilized by surrounding backend structures.
"""



from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_context_template():
    from core.jdocs import CONTEXT_TEMPLATE
    assert "<context>" in CONTEXT_TEMPLATE
    assert "<agents>" in CONTEXT_TEMPLATE
    print("[PASS] context_template: valid XML structure")


async def test_rules_template():
    from core.jdocs import RULES_TEMPLATE
    assert "<rules>" in RULES_TEMPLATE
    assert "40 lines" in RULES_TEMPLATE
    assert "Atomic commits" in RULES_TEMPLATE
    print("[PASS] rules_template: contains coding standards")


async def test_session_history_template():
    from core.jdocs import SESSION_HISTORY_TEMPLATE
    assert "<session_history>" in SESSION_HISTORY_TEMPLATE
    print("[PASS] session_history_template: valid XML structure")


async def test_context_update_xml():
    from core.jdocs import CONTEXT_TEMPLATE
    existing = CONTEXT_TEMPLATE
    agent_entry = '  <agent id="agent-1"><task>Add auth</task><status>completed</status></agent>\n'
    updated = existing.replace("</agents>", f"{agent_entry}</agents>")
    assert '<agent id="agent-1">' in updated
    assert "<task>Add auth</task>" in updated
    assert "</agents>" in updated
    print("[PASS] context_update: agent entry injected correctly")


async def test_history_append_xml():
    from core.jdocs import SESSION_HISTORY_TEMPLATE
    existing = SESSION_HISTORY_TEMPLATE
    entry = '  <session agent="agent-1" id="sess-001" status="completed" timestamp="2026-05-03T12:00:00Z">\n    <prompt>Add auth</prompt>\n  </session>\n'
    updated = existing.replace("</session_history>", f"{entry}</session_history>")
    assert 'agent="agent-1"' in updated
    assert 'id="sess-001"' in updated
    assert "</session_history>" in updated
    print("[PASS] history_append: session entry appended correctly")


async def main():
    print("=" * 50)
    print("JAT-AI JDOCS DRY RUN")
    print("=" * 50)
    print()

    await test_context_template()
    await test_rules_template()
    await test_session_history_template()
    await test_context_update_xml()
    await test_history_append_xml()

    print()
    print("=" * 50)
    print("ALL JDOCS TESTS PASSED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
