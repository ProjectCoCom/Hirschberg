"""
Summary: Interactive AI-assisted CLI command runner.

What it does: Implements command-line AI-assistant interactions, streaming completions, and workspace context parsing.

How it fits in: Relies on 'src/core/ai_interface.py' to chat and stream responses to the CLI.
"""



from __future__ import annotations

import json
import sys

from db import db


async def run_providers(settings, args) -> None:
    from clients.ai_providers import AIProviderPool
    from core.ai_interface import AIInterface, KeyVault

    vault = KeyVault(settings.encryption_key)
    pool = AIProviderPool()
    ai = AIInterface(db, pool, vault)

    if args.prov_action == "add":
        row = await ai.add_provider(
            provider_type=args.type,
            name=args.name,
            api_key=args.key,
            model=args.model,
            base_url=args.base_url,
            daily_limit=args.daily_limit,
        )
        print(json.dumps(row, indent=2, default=str))
    elif args.prov_action == "list":
        providers = await ai.list_providers()
        for p in providers:
            status = "enabled" if p["enabled"] else "disabled"
            key_status = "key set" if p["has_key"] else "no key"
            print(f"{p['id'][:8]} | {p['name']} | {p['provider_type']} | {p['model']} | {status} | {key_status}")
    elif args.prov_action == "remove":
        await ai.remove_provider(args.id)
        print(f"Removed provider {args.id}")
    else:
        print("Usage: jat providers [add|list|remove]")


async def run_chat(settings, args) -> None:
    from clients.ai_providers import AIProviderPool
    from core.ai_interface import AIInterface, KeyVault
    from core.conversation import ConversationManager
    from core.templates import get_template

    vault = KeyVault(settings.encryption_key)
    pool = AIProviderPool()
    ai = AIInterface(db, pool, vault)
    await ai.load_providers_into_pool()

    conv_mgr = ConversationManager(db, pool)

    if args.conversation_id:
        conv_id = args.conversation_id
    else:
        template = get_template(args.template)
        conv = await conv_mgr.create(
            provider_name=args.provider,
            model=args.model,
            mode=args.mode,
            repo_owner=args.owner or settings.default_repo_owner,
            repo_name=args.repo or settings.default_repo_name,
            template=args.template,
            title=f"{template['name']} - {args.provider}",
        )
        conv_id = conv["id"]
        print(f"Conversation created: {conv_id}")

        if template.get("system"):
            await db.insert("conversation_messages", {
                "conversation_id": conv_id,
                "role": "system",
                "content": template["system"],
            })

    if not args.message:
        print("No message provided. Use: jat chat --provider X 'your message'")
        return

    response = await conv_mgr.send_message(conv_id, args.message)
    print(f"\n{response['content']}")


async def run_templates() -> None:
    from core.templates import list_templates
    templates = list_templates()
    for t in templates:
        repo_tag = "[requires repo]" if t["requires_repo"] else "[no repo needed]"
        print(f"  {t['key']:15} | {t['name']:15} | {t['description']} {repo_tag}")


async def run_decompose(settings, args) -> None:
    from clients.ai_providers import AIProviderPool
    from core.ai_interface import AIInterface, KeyVault
    from core.decomposer import decompose_task

    vault = KeyVault(settings.encryption_key)
    pool = AIProviderPool()
    ai = AIInterface(db, pool, vault)
    await ai.load_providers_into_pool()

    repo_context = ""
    if args.context:
        with open(args.context) as f:
            repo_context = f.read()

    result = await decompose_task(pool, args.provider, args.task, repo_context)

    if not result.valid:
        print("Decomposition FAILED:")
        for w in result.warnings:
            print(f"  {w}")
        sys.exit(1)

    print(f"Decomposed into {len(result.specs)} agents:")
    for spec in result.specs:
        deps = f" (depends on: {spec.depends_on})" if spec.depends_on else ""
        print(f"\n  Agent {spec.index}: {spec.title}{deps}")
        print(f"    Branch: {spec.branch_name}")
        print(f"    Scope: {spec.files_scope}")
        for c in spec.acceptance_criteria:
            print(f"    - {c}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  {w}")
