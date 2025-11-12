"""
TuitionDataCollector - CLI tool for scraping tutor/student data
"""
import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from scraper.google_scraper import GoogleScraper
from scraper.urbanpro_scraper import UrbanProScraper
from scraper.superprof_scraper import SuperprofScraper
from scraper.google_api_scraper import GoogleAPISearcher
from scraper.direct_scraper import UniversalTutorScraper
from utils.storage import save_data
from utils.logger import logger
from utils.classifier import filter_tutors_by_experience, is_indian_profile

# Load environment variables
load_dotenv()

# Create Typer app
app = typer.Typer(
    name="TuitionDataCollector",
    help="🎓 Ethical tutor/student data scraper CLI tool",
    add_completion=False
)

console = Console()


def display_results_table(data: list, top_n: int = 5):
    """
    Display results in a formatted table
    
    Args:
        data: List of profile dictionaries
        top_n: Number of top results to display
    """
    if not data:
        console.print("[yellow]No data to display[/yellow]")
        return
    
    table = Table(title=f"📊 Top {min(top_n, len(data))} Results", show_header=True, header_style="bold magenta")
    
    table.add_column("Name", style="cyan", width=25)
    table.add_column("Role", style="green", width=10)
    table.add_column("Subjects", style="yellow", width=20)
    table.add_column("Location", style="blue", width=15)
    table.add_column("Source", style="magenta", width=20)
    
    for item in data[:top_n]:
        table.add_row(
            item.get('name', 'N/A')[:25],
            item.get('role', 'N/A'),
            item.get('subjects', 'N/A')[:20],
            item.get('location', 'N/A') or 'N/A',
            item.get('source', 'N/A')[:20]
        )
    
    console.print("\n")
    console.print(table)
    console.print("\n")


def create_env_if_missing():
    """Create .env file from .env.example if it doesn't exist"""
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    if not env_path.exists() and env_example_path.exists():
        import shutil
        shutil.copy(env_example_path, env_path)
        logger.info("[green]✓ Created .env file from template[/green]")


@app.command()
def fetch(
    source: str = typer.Option(
        "google",
        "--source",
        "-s",
        help="Data source: google, api, urbanpro, superprof, direct, or all"
    ),
    query: str = typer.Option(
        ...,
        "--query",
        "-q",
        help="Search query (e.g., 'math tutor Delhi')"
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-l",
        help="Maximum number of results to fetch"
    ),
    output: str = typer.Option(
        "csv",
        "--output",
        "-o",
        help="Output format: csv, mongo, or both"
    ),
    output_path: Optional[str] = typer.Option(
        None,
        "--output-path",
        "-p",
        help="Custom CSV output path"
    ),
    max_experience: Optional[int] = typer.Option(
        None,
        "--max-experience",
        "-e",
        help="Filter tutors with experience less than specified years (e.g., 5 for < 5 years)"
    ),
    exclude_students: bool = typer.Option(
        False,
        "--exclude-students",
        help="Exclude student profiles from results (focus only on tutors)"
    ),
    india_only: bool = typer.Option(
        False,
        "--india-only",
        help="Keep only profiles likely from India (based on location/text)"
    ),
    max_save: int = typer.Option(
        100,
        "--max-save",
        help="Maximum number of profiles to save after filtering"
    ),
    append: bool = typer.Option(
        False,
        "--append",
        help="Append to CSV instead of overwriting"
    )
):
    """
    🔍 Fetch tutor/student data from specified source
    
    Example:
        python main.py fetch --source google --query "math tutor Delhi" --limit 20 --output csv
        python main.py fetch --source api --query "tutor" --max-experience 5 --exclude-students
    """
    create_env_if_missing()
    
    console.print(f"\n[bold cyan]🎓 TuitionDataCollector[/bold cyan]\n")
    console.print(f"[bold]Query:[/bold] {query}")
    console.print(f"[bold]Source:[/bold] {source}")
    console.print(f"[bold]Limit:[/bold] {limit}")
    console.print(f"[bold]Output:[/bold] {output}")
    
    if max_experience:
        console.print(f"[bold]Max Experience:[/bold] < {max_experience} years")
    if exclude_students:
        console.print(f"[bold]Student Filtering:[/bold] Excluded")
    if india_only:
        console.print(f"[bold]Region Filter:[/bold] India-only")
    if max_save:
        console.print(f"[bold]Max Save:[/bold] {max_save}")
    console.print()
    
    all_results = []
    
    # Select scraper(s) based on source
    scrapers = []
    
    if source.lower() == "google":
        # Use Google API if configured, otherwise fallback to HTML scraper
        api_scraper = GoogleAPISearcher()
        if api_scraper.is_configured():
            scrapers = [("Google Custom Search API", api_scraper)]
            console.print("[green]✓ Using Google Custom Search API (recommended)[/green]\n")
        else:
            scrapers = [("Google HTML", GoogleScraper())]
            console.print("[yellow]⚠ Google API not configured, using HTML scraping (may be blocked)[/yellow]")
            console.print("[yellow]For better results, configure Google API in .env file[/yellow]\n")
    
    elif source.lower() == "api":
        scrapers = [("Google Custom Search API", GoogleAPISearcher())]
    
    elif source.lower() == "urbanpro":
        scrapers = [("UrbanPro", UrbanProScraper())]
    
    elif source.lower() == "superprof":
        scrapers = [("Superprof", SuperprofScraper())]
    
    elif source.lower() == "direct":
        scrapers = [("Direct Platform Scraper", UniversalTutorScraper())]
    
    elif source.lower() == "all":
        # Prioritize API if available
        api_scraper = GoogleAPISearcher()
        if api_scraper.is_configured():
            scrapers = [
                ("Google Custom Search API", api_scraper),
                ("Direct Platform Scraper", UniversalTutorScraper()),
                ("UrbanPro", UrbanProScraper()),
                ("Superprof", SuperprofScraper())
            ]
        else:
            scrapers = [
                ("Direct Platform Scraper", UniversalTutorScraper()),
                ("UrbanPro", UrbanProScraper()),
                ("Superprof", SuperprofScraper()),
                ("Google HTML", GoogleScraper())
            ]
    
    else:
        console.print(f"[red]✗ Invalid source: {source}[/red]")
        console.print("[yellow]Valid sources: google, api, urbanpro, superprof, direct, all[/yellow]")
        raise typer.Exit(1)
    
    # Scrape from each source
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for source_name, scraper in scrapers:
            task = progress.add_task(f"Scraping {source_name}...", total=None)
            
            try:
                results = scraper.scrape(query, limit)
                all_results.extend(results)
                progress.update(task, completed=True)
            
            except Exception as e:
                logger.error(f"[red]✗ Error scraping {source_name}: {e}[/red]")
                progress.update(task, completed=True)
    
    # Display summary
    console.print(f"\n[bold green]✓ Total results fetched: {len(all_results)}[/bold green]\n")
    
    if not all_results:
        console.print("[yellow]No data collected. Try a different query or source.[/yellow]")
        raise typer.Exit(0)
    
    # Apply filters
    original_count = len(all_results)
    
    # Exclude students if requested
    if exclude_students:
        all_results = [profile for profile in all_results if profile.get('role') != 'Student']
        console.print(f"[yellow]📊 Excluded students: {original_count - len(all_results)} profiles[/yellow]")

    # Filter by experience if requested
    if max_experience:
        filtered_tutors = filter_tutors_by_experience(all_results, max_experience)
        # Keep non-tutor profiles that weren't filtered by experience
        non_tutors = [profile for profile in all_results if profile.get('role') != 'Tutor']
        all_results = filtered_tutors + non_tutors
        console.print(f"[yellow]📊 Applied experience filter (< {max_experience} years): {original_count - len(all_results)} profiles excluded[/yellow]")

    # India-only filter
    if india_only:
        before = len(all_results)
        all_results = [p for p in all_results if is_indian_profile(p)]
        console.print(f"[yellow]📊 India-only filter: {before - len(all_results)} profiles excluded[/yellow]")

    # Cap results to max_save
    if max_save and len(all_results) > max_save:
        all_results = all_results[:max_save]
        console.print(f"[yellow]📊 Capped results to max-save: {max_save}[/yellow]")
    
    console.print(f"[bold green]✓ Final results after filtering: {len(all_results)}[/bold green]\n")
    
    if not all_results:
        console.print("[yellow]No data remaining after filtering. Try adjusting your filters.[/yellow]")
        raise typer.Exit(0)
    
    # Display top results
    display_results_table(all_results, top_n=5)
    
    # Save data
    console.print("[cyan]💾 Saving data...[/cyan]\n")
    
    csv_path = output_path or "data/tutors.csv"
    success = save_data(all_results, output_format=output, output_path=csv_path, separate_by_role=True, append_mode=append)
    
    if success:
        console.print(f"[bold green]✓ Data collection complete![/bold green]")
        if output in ['csv', 'both']:
            console.print(f"[green]📁 CSV saved to: {csv_path}[/green]")
    else:
        console.print("[red]✗ Failed to save data[/red]")
        raise typer.Exit(1)


@app.command()
def init():
    """
    ⚙️ Initialize project configuration
    
    Creates .env file and data directory
    """
    console.print("\n[bold cyan]🔧 Initializing TuitionDataCollector...[/bold cyan]\n")
    
    # Create .env file
    create_env_if_missing()
    
    # Create data directory
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    console.print("[green]✓ Created data directory[/green]")
    
    console.print("\n[bold green]✓ Initialization complete![/bold green]")
    console.print("\n[yellow]Next steps:[/yellow]")
    console.print("1. Edit .env file with your MongoDB credentials (if using MongoDB)")
    console.print("2. Run: python main.py fetch --query 'your search query'\n")


# Demo command removed - use 'fetch' for real data collection


@app.command()
def version():
    """
    📌 Show version information
    """
    console.print("\n[bold cyan]TuitionDataCollector v1.0.0[/bold cyan]")
    console.print("[dim]Python-based CLI for ethical tutor/student data collection[/dim]\n")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    🎓 TuitionDataCollector - Ethical tutor/student data scraper
    
    Run 'python main.py --help' to see available commands
    """
    if ctx.invoked_subcommand is None:
        console.print("\n[bold cyan]🎓 TuitionDataCollector[/bold cyan]\n")
        console.print("[yellow]Usage:[/yellow] python main.py [COMMAND] [OPTIONS]\n")
        console.print("[yellow]Commands:[/yellow]")
        console.print("  fetch    - Fetch tutor/student data from real sources")
        console.print("  demo     - Run demo with sample data")
        console.print("  init     - Initialize project configuration")
        console.print("  version  - Show version information\n")
        console.print("[dim]Run 'python main.py --help' for more information[/dim]\n")


if __name__ == "__main__":
    app()
