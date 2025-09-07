# monitor.py
import os
import time
from typing import Any, Dict, List

import requests
from rich.console import Console
from rich.live import Live
from rich.table import Table

import cfg  # Import config file

# Take instance URLs from the config file
INSTANCES: List[Dict[str, Any]] = cfg.MONITOR_INSTANCES


def get_status(url: str) -> Dict[str, Any]:
    """Fetches status from a service instance."""
    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def generate_table() -> Table:
    """Generates a Rich Table with data from all instances."""
    table = Table(title="[bold cyan]Bing API Instances Status[/bold cyan]")
    table.add_column("Instance", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Cookie", style="yellow")
    table.add_column("Fails", style="magenta")
    table.add_column("Total Fails", style="red")
    table.add_column("Last 10 Attempts", style="green")

    for instance in INSTANCES:
        data = get_status(instance["url"])
        if "error" in data:
            table.add_row(
                instance["name"],
                "[bold red]OFFLINE[/bold red]",
                "N/A",
                "N/A",
                "N/A",
                data.get("error"),
            )
            continue

        # Status color coding
        status = data.get("service_status", "UNKNOWN")
        if status == "OK":
            status_str = f"[bold green]{status}[/bold green]"
        elif status == "SUSPENDED":
            status_str = f"[bold red]{status}[/bold red]\nRestart in {data.get('time_to_restart', 'N/A')}"
        else:
            status_str = f"[yellow]{status}[/yellow]"

        # Attempts visualization
        attempts = "".join(
            "[green]■[/green]" if attempt["status"] == "OK" else "[red]■[/red]"
            for attempt in reversed(data.get("last_attempts", []))
        )

        table.add_row(
            instance["name"],
            status_str,
            data.get("current_cookie", "N/A"),
            f"{data.get('cookie_fail_count', 'N/A')}/{data.get('max_fail_for_rotate', 'N/A')}",
            f"{data.get('total_fail_count', 'N/A')}/{data.get('max_fail_for_suspend', 'N/A')}",
            attempts,
        )
    return table


if __name__ == "__main__":
    console = Console()
    with Live(generate_table(), screen=True, auto_refresh=False) as live:
        while True:
            try:
                live.update(generate_table(), refresh=True)
                time.sleep(10)  # Refresh rate
            except KeyboardInterrupt:
                break