"""
Command-line interface for the Bharat Voice Assistant.

This module provides a simple CLI for testing and interacting with the
voice assistant system.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .core.orchestrator import BharatVoiceOrchestrator, InteractionRequest
from .core.logging import get_logger


logger = get_logger(__name__)
console = Console()


class BharatVoiceCLI:
    """Command-line interface for Bharat Voice Assistant."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.orchestrator = BharatVoiceOrchestrator()
        self.session_id = str(uuid.uuid4())
        self.user_id = "cli_user"
        self.language = "hindi"
    
    async def start_interactive_session(self):
        """Start an interactive CLI session."""
        console.print(Panel.fit(
            "[bold blue]Bharat Voice Assistant CLI[/bold blue]\n"
            "Type 'help' for commands, 'quit' to exit",
            title="Welcome"
        ))
        
        console.print(f"Session ID: {self.session_id}")
        console.print(f"Language: {self.language}")
        console.print()
        
        while True:
            try:
                # Get user input
                user_input = console.input("[bold green]You:[/bold green] ")
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                if user_input.lower().startswith('lang '):
                    new_lang = user_input.split(' ', 1)[1]
                    if new_lang in ['hindi', 'english']:
                        self.language = new_lang
                        console.print(f"[blue]Language changed to: {new_lang}[/blue]")
                    else:
                        console.print("[red]Supported languages: hindi, english[/red]")
                    continue
                
                if user_input.lower() == 'status':
                    await self._show_system_status()
                    continue
                
                if user_input.lower() == 'new':
                    self.session_id = str(uuid.uuid4())
                    console.print(f"[blue]New session started: {self.session_id}[/blue]")
                    continue
                
                # Process the interaction
                await self._process_interaction(user_input)
                
            except KeyboardInterrupt:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
    
    async def _process_interaction(self, user_input: str):
        """Process a user interaction."""
        try:
            # Show processing indicator
            with console.status("[bold blue]Processing...[/bold blue]"):
                # Create interaction request
                request = InteractionRequest(
                    session_id=self.session_id,
                    user_id=self.user_id,
                    text_input=user_input,
                    input_type="text",
                    language=self.language
                )
                
                # Process interaction
                response = await self.orchestrator.process_interaction(request)
            
            # Display response
            self._display_response(response)
            
        except Exception as e:
            console.print(f"[red]Failed to process interaction: {e}[/red]")
    
    def _display_response(self, response):
        """Display the assistant's response."""
        # Main response
        response_text = Text(response.response_text)
        console.print(Panel(
            response_text,
            title="[bold blue]Assistant[/bold blue]",
            border_style="blue"
        ))
        
        # Show suggestions if available
        if response.suggestions:
            suggestions_text = "\n".join(f"• {suggestion}" for suggestion in response.suggestions)
            console.print(Panel(
                suggestions_text,
                title="[bold yellow]Suggestions[/bold yellow]",
                border_style="yellow"
            ))
        
        # Show metadata
        metadata = (
            f"Processing time: {response.processing_time:.3f}s | "
            f"Confidence: {response.confidence:.2f} | "
            f"Next action: {response.next_action or 'None'}"
        )
        console.print(f"[dim]{metadata}[/dim]")
        console.print()
    
    async def _show_system_status(self):
        """Show system status."""
        try:
            status = self.orchestrator.get_system_status()
            
            status_text = f"""
Status: {status['status']}
Active Sessions: {status['active_sessions']}
Total Interactions: {status['total_interactions']}
Average Processing Time: {status['average_processing_time']:.3f}s
Error Rate: {status['error_rate']:.2%}

Components:
"""
            
            for component, component_status in status['components'].items():
                status_text += f"  • {component}: {component_status}\n"
            
            console.print(Panel(
                status_text.strip(),
                title="[bold green]System Status[/bold green]",
                border_style="green"
            ))
            
        except Exception as e:
            console.print(f"[red]Failed to get system status: {e}[/red]")
    
    def _show_help(self):
        """Show help information."""
        help_text = """
[bold]Available Commands:[/bold]

[blue]General:[/blue]
  help          - Show this help message
  quit/exit     - Exit the CLI
  new           - Start a new session
  status        - Show system status
  lang <lang>   - Change language (hindi/english)

[blue]Voice Assistant Commands:[/blue]
  योजना बताओ / show schemes     - Discover government schemes
  शिकायत करनी है / file complaint - File a grievance
  स्थिति जांचें / check status    - Check grievance status
  मदद चाहिए / help              - Get help

[blue]Examples:[/blue]
  "मैं किसान हूँ, कोई योजना है?"
  "I am a farmer, any schemes?"
  "बिजली नहीं आ रही है"
  "No electricity in my area"
  "REF123456 की स्थिति क्या है?"
  "What is the status of REF123456?"
"""
        
        console.print(Panel(
            help_text.strip(),
            title="[bold yellow]Help[/bold yellow]",
            border_style="yellow"
        ))


@click.group()
def cli():
    """Bharat Voice Assistant CLI."""
    pass


@cli.command()
@click.option('--language', '-l', default='hindi', help='Language (hindi/english)')
@click.option('--user-id', '-u', default='cli_user', help='User ID')
def interactive(language: str, user_id: str):
    """Start interactive CLI session."""
    cli_app = BharatVoiceCLI()
    cli_app.language = language
    cli_app.user_id = user_id
    
    asyncio.run(cli_app.start_interactive_session())


@cli.command()
@click.argument('text')
@click.option('--language', '-l', default='hindi', help='Language (hindi/english)')
@click.option('--user-id', '-u', default='cli_user', help='User ID')
def query(text: str, language: str, user_id: str):
    """Send a single query to the assistant."""
    async def run_query():
        orchestrator = BharatVoiceOrchestrator()
        
        request = InteractionRequest(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            text_input=text,
            input_type="text",
            language=language
        )
        
        response = await orchestrator.process_interaction(request)
        
        console.print(f"[bold blue]Query:[/bold blue] {text}")
        console.print(f"[bold green]Response:[/bold green] {response.response_text}")
        
        if response.suggestions:
            console.print(f"[bold yellow]Suggestions:[/bold yellow] {', '.join(response.suggestions)}")
        
        console.print(f"[dim]Processing time: {response.processing_time:.3f}s[/dim]")
    
    asyncio.run(run_query())


@cli.command()
def status():
    """Show system status."""
    async def show_status():
        orchestrator = BharatVoiceOrchestrator()
        status = orchestrator.get_system_status()
        
        console.print(Panel(
            f"""
Status: {status['status']}
Active Sessions: {status['active_sessions']}
Total Interactions: {status['total_interactions']}
Average Processing Time: {status['average_processing_time']:.3f}s
Error Rate: {status['error_rate']:.2%}
            """.strip(),
            title="[bold green]System Status[/bold green]"
        ))
    
    asyncio.run(show_status())


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def serve(host: str, port: int, debug: bool):
    """Start the API server."""
    from .app import run_server
    
    console.print(f"[bold blue]Starting Bharat Voice Assistant API server...[/bold blue]")
    console.print(f"Host: {host}")
    console.print(f"Port: {port}")
    console.print(f"Debug: {debug}")
    console.print()
    
    run_server(host=host, port=port, debug=debug)


if __name__ == "__main__":
    cli()