CAN Research - First Run
========================

You do not need Git, Cursor, or a developer IDE.

1. If needed, install uv
   uv is a small tool that installs Python and CAN Research dependencies for you.
   https://docs.astral.sh/uv/getting-started/installation/
   Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex

2. Run setup.cmd

   When upgrading, copy your existing data\ folder into the new release folder
   before running setup.cmd.

3. Connect CANsub.2 — docs\CANSUB_SETUP.md

4. First-time OpenAI tunnel on current customer runtimes:
   uv run python scripts\connection_windows.py configure

5. Run .\start-can-research.cmd  (leave that window open)

6. Open docs\AI_INTEGRATION.md — connect your AI frontend

7. Install bundled Skills from skills\dist\
   - can-onboarding.skill.zip  (install first)
   - can-reference-builder.skill.zip
   - can-signal-research.skill.zip
   Details: docs\SKILL_INSTALLATION.md

8. Start can-onboarding in ChatGPT

Health check: .\status.cmd
Overview: README.md
Developers: docs\INSTALLATION.md
