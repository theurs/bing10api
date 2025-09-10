# monitor.py


import sqlite3
import time

from collections import deque
from typing import Any, Deque, Dict, List, Tuple

import cfg  # Import config file
import requests
from icmplib import ping
from icmplib.exceptions import ICMPLibError
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

# Take instance URLs from the config file
INSTANCES: List[Dict[str, Any]] = cfg.MONITOR_INSTANCES


def get_queue_size(db_path: str) -> int:
    """
    Safely gets the number of records from the log queue SQLite DB.
    Connects in read-only mode to prevent locking the database.
    Returns -1 if the database or table cannot be accessed.
    """
    # Build a URI for read-only connection
    db_uri = f"file:{db_path}?mode=ro"
    try:
        # Use the URI connection string
        with sqlite3.connect(db_uri, uri=True, timeout=1) as conn:
            cursor = conn.cursor()
            # The table 'unnamed' is the default name used by SqliteDict
            cursor.execute("SELECT count(*) FROM unnamed;")
            # fetchone() returns a tuple, e.g., (123,)
            count = cursor.fetchone()[0]
            return count
    except (sqlite3.OperationalError, FileNotFoundError):
        # Return -1 to indicate an error (e.g., DB not found, table missing)
        return -1


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
        # This MUST be True to work on your system, as proven by testing.
        result = ping(host, count=count, timeout=timeout, privileged=True)

        if result.is_alive:
            # result.avg_rtt is in milliseconds
            return {"status": "online", "latency": result.avg_rtt}
        else:
            return {"status": "offline", "error": "Host unreachable"}

    except (ICMPLibError, PermissionError) as e:
        # Catch permission errors if not run with sudo/setcap
        return {"status": "offline", "error": str(e)}


def generate_table() -> Tuple[Table, List[Dict[str, Any]]]:
    """
    Generates a Rich Table with instance data and a dynamic title with queue size.
    """
    title = "[bold cyan]Bing API Instances Status[/bold cyan]"

    # Check if queue monitoring is enabled in the config
    if hasattr(cfg, "QUEUE_DB_PATH") and cfg.QUEUE_DB_PATH:
        queue_size = get_queue_size(cfg.QUEUE_DB_PATH)
        if queue_size != -1:  # -1 indicates an error
            if queue_size > 1000:
                color = "bold red"
            elif queue_size > 300:
                color = "yellow"
            elif queue_size > 50:
                color = "cyan"
            else:
                color = "green"
            title += f" | Log Queue: [{color}]{queue_size}[/{color}]"
        else:
            # Display an error if the queue size could not be determined
            title += " | Log Queue: [bold red]ERROR[/bold red]"

    table = Table(title=title)
    table.add_column("Instance", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Cookie", style="yellow")
    table.add_column("Fails", style="magenta")
    table.add_column("Total Fails", style="red")
    table.add_column("Last 10 Attempts", style="green")

    all_failed_prompts: List[Dict[str, Any]] = []

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

        # Collect failed prompts, which are now dicts with timestamps
        failed_prompts = data.get("last_failed_prompts", [])
        for prompt_data in failed_prompts:
            # Add instance name to each prompt's data
            prompt_data['instance'] = instance['name']
            all_failed_prompts.append(prompt_data)

    # Sort all collected prompts by timestamp, newest first
    all_failed_prompts.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

    # Remove duplicates based on prompt text, keeping the newest entry
    unique_prompts = []
    seen_prompts = set()
    for item in all_failed_prompts:
        prompt_text = item.get("prompt")
        if prompt_text and prompt_text not in seen_prompts:
            unique_prompts.append(item)
            seen_prompts.add(prompt_text)

    return table, unique_prompts


def generate_ping_table(ping_target: str, history: Deque[Dict[str, Any]]) -> Table:
    """Generates a Rich Table for ping status with a latency sparkline."""
    # Characters from low to high latency
    SPARKLINE_CHARS = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
    # We'll scale latency up to this value. Anything higher gets the max block.
    MAX_LATENCY_FOR_SCALE = 500  # ms

    table = Table(title="[bold cyan]Ping Status[/bold cyan]")
    table.add_column("Target", style="cyan", no_wrap=True)
    table.add_column("Status", style="white")
    table.add_column("Latency (ms)", style="yellow")
    # The column must not wrap lines to keep the sparkline intact
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

    # --- Sparkline generation logic ---
    bars = []
    for attempt in history:
        if attempt.get("status") == "online":
            ping_ms = attempt.get("latency", 0)
            # Clamp latency to our max scale value
            clamped_ping = min(ping_ms, MAX_LATENCY_FOR_SCALE)
            # Calculate index for the character list
            index = int(
                (clamped_ping / MAX_LATENCY_FOR_SCALE) * (len(SPARKLINE_CHARS) - 1)
            )
            char = SPARKLINE_CHARS[index]
            bars.append(f"[green]{char}[/green]")
        else:
            # A full, red block for failures
            bars.append(f"[red]█[/red]")
    sparkline = "".join(bars)
    # --- End of sparkline logic ---

    table.add_row(ping_target, status_str, latency_str, sparkline)
    return table


def generate_failed_prompts_panel(prompts: List[Dict[str, str]], width: int) -> Panel:
    """Creates a Rich Panel to display the last failed prompts."""
    # Reserve some space for panel borders and padding
    # max_prompt_len = width - 15
    max_prompt_len = 400
    content = []
    # Ограничиваем количество промптов до 5
    for item in prompts[:5]:
        instance_name = f"([yellow]{item['instance']}[/yellow])"
        prompt_text = item['prompt'].replace('\n', ' ')
        if len(prompt_text) > max_prompt_len:
            prompt_text = prompt_text[:max_prompt_len] + "..."
        content.append(f"{instance_name}: {prompt_text}")

    return Panel(
        "\n".join(content),
        title="[bold red]Last Failed Prompts[/bold red]",
        border_style="red",
    )


if __name__ == "__main__":
    console = Console()

    # Check if ping target is configured
    ping_enabled = hasattr(cfg, "PING_TARGET") and cfg.PING_TARGET

    # --- Dynamic deque size based on terminal width ---
    # Reserve ~55 characters for other columns, borders, and padding
    sparkline_width = max(10, console.width - 55)
    ping_history: Deque[Dict[str, Any]] = deque(maxlen=sparkline_width)
    # --- End of dynamic deque logic ---

    def generate_layout() -> Group:
        """Generates the complete layout with all tables and panels."""
        api_table, failed_prompts = generate_table()

        elements = [api_table]

        if ping_enabled:
            ping_table = generate_ping_table(cfg.PING_TARGET, ping_history)
            elements.append(ping_table)

        if failed_prompts:
            # Pass console width to handle prompt truncation
            prompts_panel = generate_failed_prompts_panel(failed_prompts, console.width)
            elements.append(prompts_panel)

        return Group(*elements)

    with Live(generate_layout(), screen=True, auto_refresh=False) as live:
        while True:
            try:
                if ping_enabled:
                    result = ping_host(cfg.PING_TARGET)
                    ping_history.append(result)

                # Dynamically adjust sparkline width if terminal is resized
                new_sparkline_width = max(10, console.width - 55)
                if new_sparkline_width != ping_history.maxlen:
                    ping_history = deque(ping_history, maxlen=new_sparkline_width)

                live.update(generate_layout(), refresh=True)
                time.sleep(2)  # Refresh rate
            except KeyboardInterrupt:
                break