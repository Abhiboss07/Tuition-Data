"""
Async Playwright-based scraper with proxy rotation, network interception, and async workers.
"""
import os
import asyncio
import json
import random
from typing import List, Dict, Optional, Tuple
from contextlib import asynccontextmanager

from utils.logger import logger
from utils.classifier import extract_location, extract_experience, extract_subjects, classify_role
from utils.storage import save_data
from scraper.google_api_scraper import GoogleAPISearcher

from playwright.async_api import async_playwright, Browser, BrowserContext, Page


def _get_user_agents() -> List[str]:
    # Minimal pool; users can extend via env USER_AGENTS (comma-separated)
    env_ua = os.getenv("USER_AGENTS", "").strip()
    pool = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    if env_ua:
        pool.extend([x.strip() for x in env_ua.split("|") if x.strip()])
    return pool


def _pick_proxy() -> Optional[Dict[str, str]]:
    """
    Load rotating proxies from env WEBSHARE_PROXIES comma-separated list, like:
    http://user:pass@host:port, http://user:pass@host:port
    """
    proxies = [p.strip() for p in os.getenv("WEBSHARE_PROXIES", "").split(",") if p.strip()]
    if not proxies:
        return None
    proxy = random.choice(proxies)
    # Parse basic formats
    try:
        if "@" in proxy:
            creds, server = proxy.split("@", 1)
            if creds.startswith("http://") or creds.startswith("https://"):
                scheme, rest = creds.split("://", 1)
                username, password = rest.split(":", 1)
            else:
                username, password = creds.split(":", 1)
            if not server.startswith("http"):
                server = f"http://{server}"
            return {"server": server, "username": username, "password": password}
        else:
            server = proxy if proxy.startswith("http") else f"http://{proxy}"
            return {"server": server}
    except Exception:
        return None


@asynccontextmanager
async def launch_browser() -> Browser:
    ua = random.choice(_get_user_agents())
    proxy = _pick_proxy()
    launch_args = {
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
        "proxy": proxy,
    }
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_args)
        try:
            yield browser
        finally:
            await browser.close()


async def new_context(browser: Browser, ua: str) -> BrowserContext:
    context = await browser.new_context(
        user_agent=ua,
        viewport={"width": 1366, "height": 768},
        java_script_enabled=True,
        locale="en-US",
        timezone_id="Asia/Kolkata",
    )
    # Basic stealth-like tweaks
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    return context


def build_urls(subject: str, city: str) -> List[Tuple[str, str]]:
    subject_clean = subject.lower().replace(" ", "-")
    city_clean = city.lower().replace(" ", "-")
    return [
        ("superprof", f"https://www.superprof.co.in/lessons/{subject_clean}/{city_clean}.html"),
        ("urbanpro", f"https://www.urbanpro.com/{subject_clean}/in-{city_clean}"),
    ]


async def extract_from_network(page: Page, domain: str) -> List[Dict]:
    """Collect JSON API payloads from network responses."""
    collected: List[Dict] = []

    async def handle_response(resp):
        try:
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if domain not in url:
                return
            if "application/json" in ct:
                data = await resp.json()
                # Heuristic flattening for common list payloads
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            collected.extend(v)
                elif isinstance(data, list):
                    if data and isinstance(data[0], dict):
                        collected.extend(data)
        except Exception:
            pass

    page.on("response", handle_response)
    return collected


def normalize_profile(raw: Dict, source: str) -> Optional[Dict]:
    try:
        text = json.dumps(raw, ensure_ascii=False)
        name = raw.get("name") or raw.get("title") or raw.get("teacherName") or ""
        desc = raw.get("description") or raw.get("bio") or raw.get("tagline") or ""
        link = raw.get("profileUrl") or raw.get("url") or raw.get("link") or ""
        loc = raw.get("location") or raw.get("city") or extract_location(text)
        exp = raw.get("experience") or extract_experience(text)
        role = classify_role(f"{name} {desc}")
        subjects = extract_subjects(text)
        if not name and not link:
            return None
        return {
            "name": name or "N/A",
            "title": f"{name} - Tutor" if name else "Tutor",
            "description": desc,
            "profile_link": link,
            "source": source,
            "location": loc,
            "experience": exp,
            "role": role,
            "subjects": ", ".join(subjects) if subjects else "N/A",
        }
    except Exception:
        return None


async def scrape_task(subject: str, city: str, api_fallback: GoogleAPISearcher, per_source_limit: int = 30) -> List[Dict]:
    ua = random.choice(_get_user_agents())
    results: List[Dict] = []
    async with launch_browser() as browser:
        context = await new_context(browser, ua)
        page = await context.new_page()
        try:
            for name, url in build_urls(subject, city):
                network_items = await extract_from_network(page, name)
                logger.info(f"[blue]Navigating {name}: {url}[/blue]")
                resp = await page.goto(url, wait_until="networkidle", timeout=30000)
                status = resp.status if resp else 0
                if status in (403, 429) or (status == 503):
                    logger.warning(f"[yellow]{name} blocked or rate-limited (HTTP {status}). Using API fallback...[/yellow]")
                    # Fallback to Google API for this query (no site restriction to maximize recall)
                    api_query = f"{subject} tutor for class 1 to 12 in {city}, India"
                    results.extend(api_fallback.scrape(api_query, per_source_limit))
                    continue
                # Give some time for XHRs
                await page.wait_for_timeout(2000)
                # Convert network payloads
                for item in list(network_items)[: per_source_limit]:
                    prof = normalize_profile(item, name.capitalize())
                    if prof:
                        results.append(prof)
        except Exception as e:
            logger.warning(f"[yellow]Playwright task error: {e}. Falling back to Google API...[/yellow]")
            api_query = f"{subject} tutor for class 1 to 12 in {city}, India"
            results.extend(api_fallback.scrape(api_query, per_source_limit))
        finally:
            await context.close()
    return results


async def run_async_scrape(subjects: List[str], cities: List[str], workers: int = 4, target: int = 1000, flush_every: int = 200, output_path: str = "data/tutors_async.csv") -> int:
    queue: asyncio.Queue[Tuple[str, str]] = asyncio.Queue()
    for s in subjects:
        for c in cities:
            await queue.put((s, c))

    api = GoogleAPISearcher()
    collected: List[Dict] = []
    seen: set = set()

    def key_fn(p: Dict) -> str:
        link = (p.get("profile_link") or "").strip().lower()
        return link or f"{p.get('name','').strip().lower()}|{p.get('source','').strip().lower()}"

    async def worker_fn(i: int):
        while not queue.empty() and len(collected) < target:
            subj, city = await queue.get()
            try:
                batch = await scrape_task(subj, city, api, per_source_limit=25)
                # dedup + store
                new_items: List[Dict] = []
                for p in batch:
                    k = key_fn(p)
                    if k and k not in seen:
                        seen.add(k)
                        new_items.append(p)
                if new_items:
                    collected.extend(new_items)
                    logger.info(f"[green]Worker {i}: +{len(new_items)} (total={len(collected)})[/green]")
                    if len(collected) % flush_every < len(new_items):
                        save_data(new_items, output_format="csv", output_path=output_path, separate_by_role=True, append_mode=True)
            except Exception as e:
                logger.error(f"[red]Worker {i} error: {e}[/red]")
            finally:
                queue.task_done()

    tasks = [asyncio.create_task(worker_fn(i)) for i in range(workers)]
    await queue.join()
    for t in tasks:
        t.cancel()
    # Final flush
    if collected:
        save_data(collected, output_format="csv", output_path=output_path, separate_by_role=True, append_mode=True)
    return len(collected)
