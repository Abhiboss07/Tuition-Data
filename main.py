"""
TuitionDataCollector - CLI tool for scraping tutor/student data
"""
import os
import sys
import time
import random
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from scraper.async_playwright_scraper import run_async_scrape
from utils.storage import save_data
from utils.logger import logger
from utils.classifier import filter_tutors_by_experience, is_indian_profile, parse_experience_years

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
    only_api: bool = typer.Option(
        False,
        "--only-api/--all-sources",
        help="Use only Google Custom Search API (recommended for scale)"
    ),
    api_sites: Optional[str] = typer.Option(
        None,
        "--api-sites",
        help="Optional site filter for API queries, e.g. 'site:superprof.co.in OR site:urbanpro.com OR site:teacheron.com'"
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


@app.command()
def bulk(
    target_count: int = typer.Option(
        3000,
        "--target",
        "-t",
        help="Target number of tutor profiles to collect"
    ),
    output: str = typer.Option(
        "csv",
        "--output",
        "-o",
        help="Output format: csv, mongo, or both"
    ),
    output_path: Optional[str] = typer.Option(
        "data/tutors.csv",
        "--output-path",
        "-p",
        help="CSV path to save (append mode)"
    ),
    max_workers: int = typer.Option(
        8,
        "--workers",
        "-w",
        help="Max concurrent scraping workers"
    ),
    flush_every: int = typer.Option(
        250,
        "--flush-every",
        help="Append to CSV every N new profiles"
    ),
    max_experience: int = typer.Option(
        5,
        "--max-experience",
        help="Keep tutors with strictly less than this many years of experience"
    ),
    india_only: bool = typer.Option(
        True,
        "--india-only/--no-india-only",
        help="Keep only profiles likely from India"
    ),
    exclude_students: bool = typer.Option(
        True,
        "--exclude-students/--include-students",
        help="Exclude student profiles"
    ),
    only_api: bool = typer.Option(
        False,
        "--only-api/--all-sources",
        help="Use only Google Custom Search API (recommended for scale)"
    ),
    api_sites: Optional[str] = typer.Option(
        None,
        "--api-sites",
        help="Optional site filter for API queries, e.g. 'site:superprof.co.in OR site:urbanpro.com OR site:teacheron.com'"
    ),
):
    """
    🚀 Bulk-collect Indian tutor profiles (classes 1–12) across subjects and cities with concurrency.

    Strategy:
    - Iterate a grid of subjects × cities with multiple scrapers.
    - Small per-task limits, high coverage, dedup by profile link.
    - Periodic CSV appends to avoid memory and enable progress.
    """
    create_env_if_missing()

    console.print(f"\n[bold cyan]🎓 TuitionDataCollector (Bulk Mode)[/bold cyan]\n")
    console.print(f"[bold]Target:[/bold] {target_count}")
    console.print(f"[bold]Workers:[/bold] {max_workers}")
    console.print(f"[bold]Output:[/bold] {output} -> {output_path}")
    console.print(f"[bold]India-only:[/bold] {india_only}")
    console.print(f"[bold]Max Experience:[/bold] < {max_experience} years")
    console.print(f"[bold]Exclude students:[/bold] {exclude_students}")
    console.print(f"[bold]Only API:[/bold] {only_api}")
    if api_sites:
        console.print(f"[bold]API site filter:[/bold] {api_sites}")
    console.print()

    # Define coverage
    subjects = [
        "math", "science", "english", "physics", "chemistry", "biology",
        "computer", "hindi", "social science", "accounting", "economics",
        "history", "geography", "civics", "environmental science"
    ]
    cities = [
        # Tier-1/2
        "delhi", "mumbai", "bangalore", "chennai", "kolkata", "pune", "hyderabad",
        "ahmedabad", "jaipur", "lucknow", "kanpur", "nagpur", "indore", "thane",
        "bhopal", "visakhapatnam", "patna", "vadodara", "ghaziabad", "ludhiana",
        "agra", "nashik", "faridabad", "meerut", "rajkot", "varanasi",
        # A few more large cities
        "surat", "noida", "gurgaon", "coimbatore", "trichy"
    ]

    # Scrapers: prefer API if configured
    api_scraper = GoogleAPISearcher()
    scrapers: List[Tuple[str, object]] = []
    if api_scraper.is_configured():
        scrapers.append(("Google API", api_scraper))
    else:
        scrapers.append(("Google HTML", GoogleScraper()))
    if not only_api:
        scrapers.extend([
            ("Superprof", SuperprofScraper()),
            ("UrbanPro", UrbanProScraper()),
            ("Direct", UniversalTutorScraper()),
        ])

    # Build queries (class 1-12 emphasis)
    def build_query(subj: str, city: str) -> str:
        # Vary phrasing to broaden recall
        variants = [
            f"{subj} tutor for class 1 to 12 in {city}, India",
            f"{subj} teacher near {city} India for school students",
            f"home tutor {subj} {city} India class 1-12",
        ]
        return random.choice(variants)

    # Task generator
    tasks: List[Tuple[str, object, str, int]] = []  # (source_name, scraper, query, limit)
    per_task_limit_api = int(os.getenv("BULK_API_PER_TASK_LIMIT", "50"))  # fetch more pages per API query
    per_task_limit_html = int(os.getenv("BULK_HTML_PER_TASK_LIMIT", "20"))  # keep small for HTML scrapers
    for subj in subjects:
        for city in cities:
            q = build_query(subj, city)
            for source_name, scraper in scrapers:
                is_api = isinstance(scraper, GoogleAPISearcher)
                # If using API and site filters provided, append them to query
                final_q = f"{q} {api_sites}" if (is_api and api_sites) else q
                limit = per_task_limit_api if is_api else per_task_limit_html
                tasks.append((source_name, scraper, final_q, limit))

    collected: List[Dict] = []
    seen_keys: Set[str] = set()
    saved_total = 0

    def profile_key(p: Dict) -> str:
        link = (p.get("profile_link") or "").strip().lower()
        if link:
            return link
        # Fallback key
        return f"{p.get('name','').strip().lower()}|{p.get('source','').strip().lower()}"

    # Limit in-flight API tasks to avoid 429 bursts
    import threading
    api_max = max(1, int(os.getenv("BULK_MAX_CONCURRENT_API", "2")))
    html_max = max(1, int(os.getenv("BULK_MAX_CONCURRENT_HTML", "4")))
    api_sem = threading.Semaphore(api_max)
    html_sem = threading.Semaphore(html_max)

    def submit_task(executor, source_name, scraper, query, limit):
        # Wrap to return with metadata
        try:
            is_api = isinstance(scraper, GoogleAPISearcher)
            sem = api_sem if is_api else html_sem
            with sem:
                results = scraper.scrape(query, limit)
            return source_name, query, results
        except Exception as e:
            logger.error(f"[red]Error in {source_name} for '{query}': {e}[/red]")
            return source_name, query, []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(submit_task, executor, src, scr, q, l)
            for (src, scr, q, l) in tasks
        ]

        for fut in as_completed(futures):
            src_name, q, results = fut.result()

            # Post-filters and dedup
            for p in results:
                # Only tutors
                if exclude_students and p.get("role", "").lower() == "student":
                    continue
                # India-only heuristic
                if india_only and not is_indian_profile(p):
                    continue
                # Experience strictly less than max_experience and known
                years = parse_experience_years(str(p.get("experience") or ""))
                if years is None or years >= max_experience:
                    continue
                k = profile_key(p)
                if not k or k in seen_keys:
                    continue
                seen_keys.add(k)
                collected.append(p)

            # Periodic flush
            if len(collected) - saved_total >= flush_every:
                console.print(f"[cyan]💾 Flushing {len(collected) - saved_total} new profiles...[/cyan]")
                save_data(collected[saved_total:], output_format=output, output_path=output_path, separate_by_role=True, append_mode=True)
                saved_total = len(collected)

            # Stop early when target reached (remaining futures will still complete, but we won't append more)
            if len(collected) >= target_count:
                break

        # Final flush
        if len(collected) > saved_total:
            console.print(f"[cyan]💾 Final flush {len(collected) - saved_total} profiles...[/cyan]")
            save_data(collected[saved_total:], output_format=output, output_path=output_path, separate_by_role=True, append_mode=True)

    console.print(f"\n[bold green]✓ Bulk collection complete: {len(collected)} profiles (deduped)[/bold green]")
    console.print(f"[green]📁 Data saved to: {output_path}[/green]")


# Demo command removed - use 'fetch' for real data collection


@app.command()
def version():
    """
    📌 Show version information
    """
    console.print("\n[bold cyan]TuitionDataCollector v1.0.0[/bold cyan]")
    console.print("[dim]Python-based CLI for ethical tutor/student data collection[/dim]\n")


@app.command()
def playwright_scrape(
    target: int = typer.Option(500, "--target", "-t", help="Target number of profiles"),
    workers: int = typer.Option(4, "--workers", "-w", help="Concurrent async workers"),
    output_path: str = typer.Option("data/tutors_play.csv", "--output-path", "-p", help="CSV output path"),
):
    """
    ⚙️ Run Playwright-based async scraper with proxy rotation and API fallback.

    Configure proxies via WEBSHARE_PROXIES env (comma-separated). Optionally set USER_AGENTS.
    """
    create_env_if_missing()
    console.print("\n[bold cyan]🎭 Playwright Async Scraper[/bold cyan]\n")
    console.print(f"[bold]Target:[/bold] {target}")
    console.print(f"[bold]Workers:[/bold] {workers}")
    console.print(f"[bold]Output:[/bold] {output_path}\n")

    subjects = [
        "math", "science", "english", "physics", "chemistry", "biology",
        "computer", "hindi", "social science"
    ]
    cities = [
        "delhi", "mumbai", "bangalore", "chennai", "kolkata", "pune", "hyderabad"
    ]

    try:
        import asyncio
        total = asyncio.run(run_async_scrape(subjects, cities, workers=workers, target=target, flush_every=100, output_path=output_path))
        console.print(f"\n[bold green]✓ Playwright run complete: {total} profiles collected[/bold green]")
        console.print(f"[green]📁 CSV saved to: {output_path}[/green]")
    except Exception as e:
        logger.error(f"[red]Playwright scraping failed: {e}[/red]")
        raise typer.Exit(1)


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
