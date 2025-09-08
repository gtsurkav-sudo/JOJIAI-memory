
"""Command-line utility for JOJI Oi memory management."""

import json
import click
import time
from pathlib import Path
from typing import Optional
from .memory_agent import MemoryAgent
from .chat_memory import ChatMemory
from .backup import BackupManager
from .monitoring import StructuredLogger

logger = StructuredLogger('memoryctl')


@click.group()
@click.option('--memory-path', default='./memory', help='Path to memory storage')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, memory_path: str, verbose: bool):
    """JOJI Oi Memory Control Utility."""
    ctx.ensure_object(dict)
    ctx.obj['memory_path'] = memory_path
    ctx.obj['verbose'] = verbose
    
    if verbose:
        logger.logger.setLevel('DEBUG')


@cli.command()
@click.pass_context
def status(ctx):
    """Show memory system status."""
    memory_path = ctx.obj['memory_path']
    
    try:
        with MemoryAgent(memory_path) as agent:
            stats = agent.get_memory_stats()
            
            click.echo("JOJI Oi Memory System Status")
            click.echo("=" * 40)
            click.echo(f"Memory Path: {stats.get('memory_path', 'Unknown')}")
            click.echo(f"Dialogues: {stats.get('dialogues_count', 0)}")
            click.echo(f"Decisions: {stats.get('decisions_count', 0)}")
            click.echo(f"Profile Keys: {stats.get('profile_keys', 0)}")
            click.echo(f"WAL Entries: {stats.get('wal_entries', 0)}")
            click.echo(f"Snapshots: {stats.get('snapshots', 0)}")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Status command failed", error=str(e))


@cli.command()
@click.option('--name', help='Snapshot name')
@click.pass_context
def backup(ctx, name: Optional[str]):
    """Create memory backup snapshot."""
    memory_path = ctx.obj['memory_path']
    
    try:
        with MemoryAgent(memory_path) as agent:
            snapshot_id = agent.create_snapshot(name)
            click.echo(f"Backup created: {snapshot_id}")
            logger.info("Backup created", snapshot_id=snapshot_id)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Backup command failed", error=str(e))


@cli.command()
@click.argument('snapshot_name')
@click.option('--confirm', is_flag=True, help='Confirm restoration')
@click.pass_context
def restore(ctx, snapshot_name: str, confirm: bool):
    """Restore memory from snapshot."""
    memory_path = ctx.obj['memory_path']
    
    if not confirm:
        click.echo("This will overwrite current memory data.")
        if not click.confirm("Are you sure you want to continue?"):
            return
    
    try:
        with MemoryAgent(memory_path) as agent:
            agent.restore_snapshot(snapshot_name)
            click.echo(f"Restored from snapshot: {snapshot_name}")
            logger.info("Restore completed", snapshot_name=snapshot_name)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Restore command failed", error=str(e))


@cli.command()
@click.pass_context
def list_snapshots(ctx):
    """List available snapshots."""
    memory_path = ctx.obj['memory_path']
    
    try:
        backup_path = Path(memory_path) / 'backups'
        wal_path = Path(memory_path) / 'memory.wal'
        
        with BackupManager(memory_path, str(backup_path), str(wal_path)) as backup_mgr:
            snapshots = backup_mgr.list_snapshots()
            
            if not snapshots:
                click.echo("No snapshots found.")
                return
            
            click.echo("Available Snapshots:")
            click.echo("=" * 40)
            
            for snapshot in snapshots:
                name = snapshot.get('snapshot_name', 'Unknown')
                timestamp = snapshot.get('timestamp', 0)
                files_count = snapshot.get('files_count', 0)
                
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                click.echo(f"{name:<20} {time_str} ({files_count} files)")
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("List snapshots command failed", error=str(e))


@cli.command()
@click.option('--limit', default=10, help='Number of messages to show')
@click.option('--role', help='Filter by role (user, assistant, system)')
@click.pass_context
def chat_history(ctx, limit: int, role: Optional[str]):
    """Show chat history."""
    memory_path = ctx.obj['memory_path']
    
    try:
        with ChatMemory(memory_path) as chat:
            messages = chat.get_conversation_history(limit=limit, role_filter=role)
            
            if not messages:
                click.echo("No chat history found.")
                return
            
            click.echo(f"Chat History (last {len(messages)} messages):")
            click.echo("=" * 50)
            
            for message in messages:
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                timestamp = message.get('timestamp', 0)
                
                time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
                click.echo(f"[{time_str}] {role.upper()}: {content[:100]}")
                if len(content) > 100:
                    click.echo("    ...")
                click.echo()
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Chat history command failed", error=str(e))


@cli.command()
@click.option('--count', default=20, help='Number of recent messages to summarize')
@click.pass_context
def summarize(ctx, count: int):
    """Create conversation summary."""
    memory_path = ctx.obj['memory_path']
    
    try:
        with ChatMemory(memory_path) as chat:
            summary = chat.create_conversation_summary(count)
            click.echo(summary)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Summarize command failed", error=str(e))


@cli.command()
@click.argument('query')
@click.option('--limit', default=10, help='Maximum number of results')
@click.pass_context
def search(ctx, query: str, limit: int):
    """Search chat messages."""
    memory_path = ctx.obj['memory_path']
    
    try:
        with ChatMemory(memory_path) as chat:
            results = chat.search_messages(query, limit)
            
            if not results:
                click.echo(f"No messages found matching '{query}'.")
                return
            
            click.echo(f"Search Results for '{query}' ({len(results)} found):")
            click.echo("=" * 50)
            
            for message in results:
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                timestamp = message.get('timestamp', 0)
                
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                click.echo(f"[{time_str}] {role.upper()}:")
                click.echo(f"  {content}")
                click.echo()
                
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Search command failed", error=str(e))


@cli.command()
@click.option('--keep', default=5, help='Number of snapshots to keep')
@click.pass_context
def cleanup(ctx, keep: int):
    """Cleanup old snapshots and WAL entries."""
    memory_path = ctx.obj['memory_path']
    
    try:
        backup_path = Path(memory_path) / 'backups'
        wal_path = Path(memory_path) / 'memory.wal'
        
        with BackupManager(memory_path, str(backup_path), str(wal_path)) as backup_mgr:
            removed_snapshots = backup_mgr.cleanup_old_snapshots(keep)
            
            # Cleanup old WAL entries (older than 7 days)
            old_threshold = time.time() - (7 * 24 * 3600)
            removed_wal = backup_mgr.wal.truncate(old_threshold)
            
            click.echo(f"Cleanup completed:")
            click.echo(f"  Removed snapshots: {removed_snapshots}")
            click.echo(f"  Removed WAL entries: {removed_wal}")
            
            logger.info("Cleanup completed", 
                       removed_snapshots=removed_snapshots,
                       removed_wal=removed_wal)
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Cleanup command failed", error=str(e))


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate memory system integrity."""
    memory_path = ctx.obj['memory_path']
    
    try:
        issues = []
        
        # Check if memory files exist and are valid JSON
        memory_files = [
            'memory_dialogues_v2.json',
            'memory_decisions_v2.json',
            'memory_profile_v2.json',
            'memory_projects_v2.json'
        ]
        
        for filename in memory_files:
            file_path = Path(memory_path) / filename
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        json.load(f)
                    click.echo(f"✓ {filename} - Valid")
                except json.JSONDecodeError as e:
                    issues.append(f"{filename} - Invalid JSON: {e}")
                    click.echo(f"✗ {filename} - Invalid JSON")
            else:
                click.echo(f"? {filename} - Not found")
        
        # Check WAL integrity
        wal_path = Path(memory_path) / 'memory.wal'
        if wal_path.exists():
            try:
                with open(wal_path, 'r') as f:
                    json.load(f)
                click.echo("✓ WAL file - Valid")
            except json.JSONDecodeError:
                issues.append("WAL file - Invalid JSON")
                click.echo("✗ WAL file - Invalid JSON")
        
        if issues:
            click.echo("\nIssues found:")
            for issue in issues:
                click.echo(f"  - {issue}")
        else:
            click.echo("\n✓ Memory system validation passed")
            
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.error("Validate command failed", error=str(e))


if __name__ == '__main__':
    cli()
