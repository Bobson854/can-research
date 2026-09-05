To Restrt Server.
In Terminal Window #1

cd C:\dev\Can_Research\Can-Research_V1\can-research
uv run canresearch mcp serve --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp

In Terminal Window #2

K:\Downloads\tunnel-client-v0.0.14-windows-amd64\tunnel-client.exe run --profile can-research-office --health.listen-addr 127.0.0.1:8081

