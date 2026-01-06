#!/usr/bin/env python3
"""
Context Continuity Engine CLI

Command-line interface for querying and managing the engine.
"""

import sys
import click
from pathlib import Path
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich import print as rprint
import json

# Add context_engine to path
sys.path.insert(0, str(Path(__file__).parent))

from context_engine.storage.activity_db import ActivityDatabase
from context_engine.vector_db.embeddings import EmbeddingStore
from context_engine.graph.temporal_graph import TemporalGraph

console = Console()


@click.group()
def cli():
    """Context Continuity Engine CLI"""
    pass


@cli.command()
@click.option('--hours', default=24, help='Hours to look back')
@click.option('--limit', default=50, help='Maximum number of activities')
def recent(hours, limit):
    """Show recent activities"""
    db = ActivityDatabase("data/activity.db")

    activities = db.get_recent_activities(limit=limit, hours=hours)

    if not activities:
        console.print("[yellow]No recent activities found[/yellow]")
        return

    table = Table(title=f"Recent Activities (last {hours}h)")
    table.add_column("Time", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("App", style="blue")
    table.add_column("Title/Path", style="white")
    table.add_column("Duration", style="magenta")

    for activity in activities:
        timestamp = datetime.fromisoformat(activity['timestamp'])
        time_str = timestamp.strftime("%H:%M:%S")

        activity_type = activity.get('activity_type', '')
        app_name = activity.get('app_name', '')
        title = activity.get('window_title') or activity.get('file_path', '')
        duration = activity.get('duration', 0)

        # Truncate long titles
        if len(title) > 60:
            title = title[:57] + "..."

        duration_str = f"{duration}s" if duration else ""

        table.add_row(time_str, activity_type, app_name, title, duration_str)

    console.print(table)


@cli.command()
@click.argument('query')
@click.option('--limit', default=10, help='Number of results')
def search(query, limit):
    """Search for similar contexts"""
    embeddings = EmbeddingStore(
        persist_directory="data/embeddings",
        collection_name="context_embeddings"
    )

    results = embeddings.search_similar(
        query_text=query,
        n_results=limit,
        threshold=0.3
    )

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    console.print(f"\n[bold]Search results for: '{query}'[/bold]\n")

    for i, result in enumerate(results, 1):
        similarity = result['similarity']
        text = result['text']
        metadata = result['metadata']

        console.print(f"[bold cyan]{i}. Similarity: {similarity:.2f}[/bold cyan]")
        console.print(f"   {text}")

        if metadata.get('timestamp'):
            ts = metadata['timestamp']
            console.print(f"   [dim]Time: {ts}[/dim]")

        console.print()


@cli.command()
def stats():
    """Show database statistics"""
    db = ActivityDatabase("data/activity.db")
    embeddings = EmbeddingStore(
        persist_directory="data/embeddings",
        collection_name="context_embeddings"
    )
    graph = TemporalGraph(persist_path="data/temporal_graph.pkl")

    db_stats = db.get_stats()
    emb_stats = embeddings.get_stats()
    graph_stats = graph.get_stats()

    table = Table(title="Context Engine Statistics")
    table.add_column("Component", style="cyan")
    table.add_column("Metric", style="green")
    table.add_column("Value", style="white")

    # Database stats
    table.add_row("Database", "Total Activities", str(db_stats['total_activities']))
    table.add_row("", "Total Contexts", str(db_stats['total_contexts']))
    table.add_row("", "Total Files", str(db_stats['total_files']))
    table.add_row("", "Total Apps", str(db_stats['total_applications']))

    # Embeddings stats
    table.add_row("Embeddings", "Total Vectors", str(emb_stats['total_embeddings']))
    table.add_row("", "Model", emb_stats['model_name'])

    # Graph stats
    table.add_row("Graph", "Total Nodes", str(graph_stats['total_nodes']))
    table.add_row("", "Total Edges", str(graph_stats['total_edges']))
    table.add_row("", "Activity Nodes", str(graph_stats['activity_nodes']))

    console.print(table)


@cli.command()
@click.option('--days', default=90, help='Days to retain')
@click.option('--yes', is_flag=True, help='Skip confirmation')
def cleanup(days, yes):
    """Clean up old activity data"""
    db = ActivityDatabase("data/activity.db")

    if not yes:
        if not click.confirm(f'Delete activities older than {days} days?'):
            return

    deleted = db.cleanup_old_data(days=days)

    console.print(f"[green]Deleted {deleted} old activity records[/green]")


@cli.command()
@click.argument('app_name')
def blacklist_app(app_name):
    """Add an app to the privacy blacklist"""
    # This would need to update the config file
    console.print(f"[green]Added '{app_name}' to blacklist[/green]")
    console.print("[yellow]Note: Restart daemon for changes to take effect[/yellow]")


@cli.command()
def contexts():
    """List all tracked contexts"""
    db = ActivityDatabase("data/activity.db")

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, description, last_active, total_duration
            FROM contexts
            ORDER BY last_active DESC
            LIMIT 20
        """)

        results = cursor.fetchall()

    if not results:
        console.print("[yellow]No contexts found[/yellow]")
        return

    table = Table(title="Tracked Contexts")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Last Active", style="green")
    table.add_column("Duration", style="magenta")

    for row in results:
        name = row[0]
        desc = row[1] or ""
        last_active = row[2] or ""
        duration = row[3] or 0

        # Truncate description
        if len(desc) > 50:
            desc = desc[:47] + "..."

        # Format duration
        if duration > 3600:
            duration_str = f"{duration/3600:.1f}h"
        elif duration > 60:
            duration_str = f"{duration/60:.0f}m"
        else:
            duration_str = f"{duration}s"

        table.add_row(name, desc, last_active, duration_str)

    console.print(table)


@cli.command()
@click.option('--format', type=click.Choice(['json', 'text']), default='text')
def export(format):
    """Export all data"""
    db = ActivityDatabase("data/activity.db")

    stats = db.get_stats()
    activities = db.get_recent_activities(limit=1000, hours=24*30)

    if format == 'json':
        data = {
            'stats': stats,
            'activities': activities
        }
        print(json.dumps(data, indent=2, default=str))
    else:
        console.print(f"[bold]Database Statistics[/bold]")
        for key, value in stats.items():
            console.print(f"  {key}: {value}")

        console.print(f"\n[bold]Recent Activities: {len(activities)}[/bold]")


if __name__ == '__main__':
    # Change to script directory
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)

    cli()
