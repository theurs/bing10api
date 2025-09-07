# monitor.py
import time
from collections import deque
from typing import Any, Dict, Deque, List

import cfg  # Import config file
import requests
from icmplib import ping
from icmplib.exceptions import ICMPLibError
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table

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


def ping_host(host: str, timeout: int = 2, count: int = 1) -> Dict[str, Any]:
    """
    Pings a host using ICMP packets via the icmplib library.
    This requires privileged access (run with sudo or use setcap).
    """
    try:
        result = ping(host, count=count, timeout=timeout, privileged=True)
        if result.is_alive:
            return {"status": "online", "latency": result.avg_rtt}
        else:
            return {"status": "offline", "error": "Host unreachable"}
    except (ICMPLibError, PermissionError) as e:
        return {"status": "offline", "error": str(e)}


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
                instance["name"], "[bold red]OFFLINE[/bold red]", "N/A", "N/A", "N/A", data.get("error")
            )
            continue
        status = data.get("service_status", "UNKNOWN")
        if status == "OK":
            status_str = f"[bold green]{status}[/bold green]"
        elif status == "SUSPENDED":
            status_str = f"[bold red]{status}[/bold red]\nRestart in {data.get('time_to_restart', 'N/A')}"
        else:
            status_str = f"[yellow]{status}[/yellow]"
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


def generate_ping_table(ping_target: str, history: Deque[Dict[str, Any]]) -> Table:
    """Generates a Rich Table for ping status with a multi-line sparkline."""
    SPARKLINE_HEIGHT = 4  # Height of the graph in characters
    MAX_LATENCY_FOR_SCALE = 500  # ms, anything higher gets the max bar height

    table = Table(title="[bold cyan]Ping Status[/bold cyan]")
    table.add_column("Target", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Latency (ms)", style="yellow")
    table.add_column("Latency History", style="green", no_wrap=True)

    if not history:
        table.add_row(ping_target, "[yellow]INITIALIZING...[/yellow]", "N/A", "")
        return table

    last_result = history[-1]
    status = last_result.get("status", "unknown")
    status_str = (
        f"[bold green]ONLINE[/bold green]"
        if status == "online"
        else f"[bold red]OFFLINE[/bold red]"
    )
    latency = last_result.get("latency")
    latency_str = f"{latency:.2f}" if latency is not None else "N/A"

    # --- Multi-line Sparkline Generation ---
    graph_rows = [""] * SPARKLINE_HEIGHT
    for attempt in history:
        if attempt.get("status") == "online":
            ping_ms = attempt.get("latency", 0)
            clamped_ping = min(ping_ms, MAX_LATENCY_FOR_SCALE)
            # Calculate how many blocks to fill, from 0 to SPARKLINE_HEIGHT
            fill_height = int(
                (clamped_ping / MAX_LATENCY_FOR_SCALE) * SPARKLINE_HEIGHT
            )

            # Build the column of characters from bottom to top
            for i in range(SPARKLINE_HEIGHT):
                # i=0 is the bottom row, i=3 is the top row
                char = '█' if i < fill_height else ' '
                # Add character to the correct row string
                graph_rows[SPARKLINE_HEIGHT - 1 - i] += f"[green]{char}[/green]"
        else:
            # For offline pings, draw a full red bar
            for i in range(SPARKLINE_HEIGHT):
                graph_rows[i] += f"[red]█[/red]"

    sparkline = "\n".join(graph_rows)
    # --- End of Sparkline Logic ---

    table.add_row(ping_target, status_str, latency_str, sparkline)
    return table


if __name__ == "__main__":
    console = Console()

    ping_enabled = hasattr(cfg, "PING_TARGET") and cfg.PING_TARGET

    # Reserve ~55 characters for other columns, borders, and padding
    sparkline_width = max(10, console.width - 55)
    ping_history: Deque[Dict[str, Any]] = deque(maxlen=sparkline_width)

    def generate_layout() -> Group:
        """Generates the complete layout with all tables."""
        api_table = generate_table()
        if ping_enabled:
            ping_table = generate_ping_table(cfg.PING_TARGET, ping_history)
            return Group(api_table, ping_table)
        return Group(api_table)

    with Live(generate_layout(), screen=True, auto_refresh=False) as live:
        while True:
            try:
                if ping_enabled:
                    result = ping_host(cfg.PING_TARGET)
                    ping_history.append(result)

                live.update(generate_layout(), refresh=True)
                time.sleep(2)  # Refresh rate
            except KeyboardInterrupt:
                break