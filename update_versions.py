#!/usr/bin/env python3
"""
Script to automatically update app versions from Docker Hub.

This script:
1. Scans all apps in the /apps directory
2. Extracts Docker image names from docker-compose.yml files
3. Queries Docker Hub (or other registries) for available tags
4. Updates app.json files with the latest version information
5. Supports parallel processing for faster updates
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import urllib.request
import urllib.error
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import sys


class DockerImageVersionFetcher:
    """Fetches available versions for Docker images from various registries."""

    def __init__(self, debug: bool = False, max_tags: int = 100, max_concurrent: int = 10):
        self.debug = debug
        self.max_tags = max_tags
        self.cache: Dict[str, List[str]] = {}
        # Use semaphore for concurrency limit
        self.semaphore = threading.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        # Rate limiting to prevent 429 errors
        self.request_lock = threading.Lock()
        self.last_request_time = 0
        self.min_request_interval = 0.15  # Minimum 150ms between requests

    def log(self, msg: str):
        if self.debug:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def extract_image_info(self, image_string: str) -> Optional[Tuple[str, str]]:
        """
        Extract registry and image name from image string.
        Returns (registry, image_name) or None if cannot parse.

        Examples:
        - "mysql:${VERSION}" -> ("docker.io", "mysql")
        - "ghcr.io/owner/repo:tag" -> ("ghcr.io", "owner/repo")
        - "registry.cn-hangzhou.aliyuncs.com/darry/bind_mysql" -> ("registry.cn-hangzhou.aliyuncs.com", "darry/bind_mysql")
        """
        # Remove quotes and version variables
        image_string = image_string.strip('\'"')
        image_string = re.sub(r'\$\{[^}]+\}', '', image_string)

        # Remove tag/version suffix
        image_string = image_string.split(':')[0]

        # Skip if contains unresolved variables
        if '${' in image_string:
            return None

        # Detect registry
        parts = image_string.split('/')

        if len(parts) >= 3 or '.' in parts[0]:
            # Has explicit registry (e.g., ghcr.io/owner/repo or registry.com/image)
            registry = parts[0]
            image_name = '/'.join(parts[1:])
        elif len(parts) == 2:
            # Docker Hub with owner (e.g., owner/repo)
            registry = "docker.io"
            image_name = image_string
        elif len(parts) == 1:
            # Official Docker image (e.g., mysql, redis)
            registry = "docker.io"
            image_name = f"library/{image_string}"
        else:
            return None

        return (registry, image_name)

    def fetch_dockerhub_tags(self, image_name: str, max_retries: int = 3) -> List[Tuple[str, str]]:
        """Fetch available tags from Docker Hub with their last_updated timestamps.
        Returns list of (tag_name, last_updated) tuples.
        Uses semaphore for concurrency control and rate limiting to prevent 429 errors."""
        cache_key = f"docker.io:{image_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        self.log(f"Fetching Docker Hub tags for {image_name}...")

        tags = []
        url = f"https://registry.hub.docker.com/v2/repositories/{image_name}/tags?page_size={self.max_tags}"

        for attempt in range(max_retries):
            try:
                # Acquire semaphore to limit concurrent requests
                with self.semaphore:
                    # Rate limiting: ensure minimum interval between requests
                    with self.request_lock:
                        current_time = time.time()
                        time_since_last = current_time - self.last_request_time
                        if time_since_last < self.min_request_interval:
                            sleep_time = self.min_request_interval - time_since_last
                            # Add jitter to prevent thundering herd
                            import random
                            jitter = random.uniform(0, 0.05)  # 0-50ms jitter
                            time.sleep(sleep_time + jitter)
                        self.last_request_time = time.time()
                    
                    # Make the request
                    with urllib.request.urlopen(url, timeout=15) as response:
                        data = json.loads(response.read().decode())

                        if 'results' in data:
                            for tag_info in data['results']:
                                tag_name = tag_info.get('name', '')
                                last_updated = tag_info.get('last_updated', '')
                                if tag_name:
                                    tags.append((tag_name, last_updated))

                        self.log(f"Found {len(tags)} tags for {image_name}")
                        break  # Success, exit retry loop

            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.log(f"Image not found on Docker Hub: {image_name}")
                    break  # Don't retry 404s
                elif e.code == 429:
                    # Rate limited - aggressive exponential backoff
                    wait_time = (2 ** attempt) * 3  # 3, 6, 12 seconds
                    if attempt < max_retries - 1:
                        self.log(f"Rate limited (429) for {image_name}, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(wait_time)
                    else:
                        self.log(f"Rate limit exceeded for {image_name} after {max_retries} attempts")
                else:
                    self.log(f"HTTP error {e.code} fetching tags for {image_name}")
                    if attempt < max_retries - 1:
                        time.sleep(1 * (attempt + 1))  # Simple backoff
                    else:
                        break
            except Exception as e:
                self.log(f"Error fetching tags for {image_name}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))

        self.cache[cache_key] = tags
        return tags

    def parse_version_string(self, version: str) -> Optional[Tuple]:
        """
        Parse version string into sortable tuple.
        Returns tuple of (major, minor, patch, extra) or None if cannot parse.
        """
        # Remove common prefixes
        version = re.sub(r'^[vV]', '', version)

        # Try to match semantic versioning
        match = re.match(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(.*)$', version)
        if match:
            major = int(match.group(1))
            minor = int(match.group(2)) if match.group(2) else 0
            patch = int(match.group(3)) if match.group(3) else 0
            extra = match.group(4) if match.group(4) else ""
            return (major, minor, patch, extra)

        return None

    def organize_versions(self, tags: List[Tuple[str, str]]) -> Dict[str, List[str]]:
        """
        Organize tags into major versions with their minor versions.
        Tags are sorted by last_updated date (newest first).
        Returns dict like: {"8": ["7.4.2", "7.4.2-bookworm"], "bookworm": [], "alpine": []}
        Non-numeric tags get empty lists as they are standalone tags.
        """
        version_map: Dict[str, List[Tuple[str, str]]] = {}
        non_numeric_tags: List[Tuple[str, str]] = []

        for tag_name, last_updated in tags:
            parsed = self.parse_version_string(tag_name)
            if parsed:
                major, minor, patch, extra = parsed

                # Skip pre-release versions (alpha, beta, rc, dev)
                if extra and any(pre in extra.lower() for pre in ['-alpha', '-beta', '-rc', '-dev', 'alpha', 'beta']):
                    continue

                major_key = str(major)

                if major_key not in version_map:
                    version_map[major_key] = []

                # Store full tag with timestamp
                version_map[major_key].append((tag_name, last_updated))
            else:
                # Tag doesn't start with a number (e.g., bookworm, alpine)
                # Skip pre-release tags
                if any(pre in tag_name.lower() for pre in ['alpha', 'beta', 'rc', 'dev']):
                    continue
                non_numeric_tags.append((tag_name, last_updated))

        # Sort by last_updated date (newest first) and convert to tag names only
        result = {}
        
        # Add non-numeric tags first as individual entries with empty lists
        # Sort them by last_updated (newest first)
        sorted_non_numeric = sorted(non_numeric_tags, key=lambda v: v[1], reverse=True)
        for tag_name, _ in sorted_non_numeric:
            result[tag_name] = []
        
        # Then add numeric versions
        for major, versions in version_map.items():
            sorted_versions = sorted(
                versions,
                key=lambda v: v[1],  # Sort by last_updated timestamp
                reverse=True
            )
            result[major] = [tag for tag, _ in sorted_versions]

        return result

    def get_versions_for_image(self, image_string: str) -> Optional[Dict[str, List[str]]]:
        """Get organized versions for a Docker image."""
        image_info = self.extract_image_info(image_string)
        if not image_info:
            return None

        registry, image_name = image_info

        # Currently only support Docker Hub
        if registry != "docker.io":
            self.log(f"Skipping non-Docker Hub image: {registry}/{image_name}")
            return None

        tags = self.fetch_dockerhub_tags(image_name)
        if not tags:
            return None

        return self.organize_versions(tags)


class AppVersionUpdater:
    """Updates app.json files with latest version information."""

    def __init__(self, apps_dir: str = "apps", debug: bool = False, dry_run: bool = False, 
                 max_tags: int = 100, max_versions_per_major: int = None, max_major_versions: int = None,
                 workers: int = 1):
        self.apps_dir = Path(apps_dir)
        self.debug = debug
        self.dry_run = dry_run
        self.max_versions_per_major = max_versions_per_major  # None = unlimited
        self.max_major_versions = max_major_versions  # None = unlimited
        self.workers = workers  # Number of parallel workers
        
        # Calculate optimal concurrency based on workers to prevent 429
        # Conservative: fewer concurrent requests = less 429 errors
        if workers == 1:
            max_concurrent = 3  # Sequential mode, very conservative
        elif workers <= 5:
            max_concurrent = 5  # Small batch
        elif workers <= 10:
            max_concurrent = 8  # Medium batch
        else:
            max_concurrent = 10  # Large batch, cap at 10
        
        self.fetcher = DockerImageVersionFetcher(debug=debug, max_tags=max_tags, max_concurrent=max_concurrent)
        
        if debug:
            print(f"Max concurrent API calls: {max_concurrent}")
            print(f"Min interval between requests: {self.fetcher.min_request_interval}s")
        
        self.stats = {
            'total': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        self.stats_lock = threading.Lock()  # Thread-safe stats updates
        self.print_lock = threading.Lock()  # Thread-safe printing
        
        # Check if output is a TTY for progress bar
        self.is_tty = sys.stdout.isatty() and not debug
        self.last_progress_line = ""

    def log(self, msg: str):
        with self.print_lock:
            print(msg)
    
    def progress(self, msg: str, final: bool = False):
        """Print progress message, in-place if TTY, otherwise normal."""
        with self.print_lock:
            if self.is_tty and not final:
                # Clear previous line and print new progress
                sys.stdout.write('\r' + ' ' * len(self.last_progress_line) + '\r')
                sys.stdout.write(msg)
                sys.stdout.flush()
                self.last_progress_line = msg
            else:
                # Clear progress line if switching to normal print
                if self.is_tty and self.last_progress_line:
                    sys.stdout.write('\r' + ' ' * len(self.last_progress_line) + '\r')
                    self.last_progress_line = ""
                print(msg)

    def find_docker_compose(self, app_path: Path) -> Optional[Path]:
        """Find docker-compose.yml in app directory."""
        # Look for docker-compose.yml in subdirectory matching app name
        app_name = app_path.name
        compose_path = app_path / app_name / "docker-compose.yml"

        if compose_path.exists():
            return compose_path

        # Also check for compose files in any subdirectory
        for compose_file in app_path.rglob("docker-compose.yml"):
            return compose_file

        return None

    def extract_image_from_compose(self, compose_path: Path) -> Optional[str]:
        """Extract the main image name from docker-compose.yml."""
        try:
            with open(compose_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all image: lines
            image_matches = re.findall(r'^\s*image:\s*(.+?)(?:\s|$)', content, re.MULTILINE)

            if image_matches:
                # Return the first non-postgres/non-redis image
                # (assuming those are dependencies, not the main app)
                for img in image_matches:
                    img_lower = img.lower()
                    if 'postgres' not in img_lower and 'redis' not in img_lower and 'mysql' not in img_lower:
                        return img.strip()

                # If all are postgres/redis/mysql, return the first one
                return image_matches[0].strip()

        except Exception as e:
            if self.debug:
                self.log(f"Error reading {compose_path}: {e}")

        return None

    def format_json_compact(self, data: dict) -> str:
        """
        Format JSON with compact style for arrays.
        This mimics the original formatting style in the repository.
        """
        lines = ['{']
        items = []

        for key, value in data.items():
            key_str = json.dumps(key, ensure_ascii=False)

            if key == 'appversion' and isinstance(value, list):
                # Format appversion compactly
                version_lines = []
                for item in value:
                    compact = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
                    version_lines.append(f"        {compact}")
                value_str = '[\n' + ',\n'.join(version_lines) + '\n    ]'
            elif isinstance(value, list):
                # Format other arrays compactly
                array_lines = []
                for item in value:
                    if isinstance(item, dict):
                        compact = json.dumps(item, ensure_ascii=False, separators=(',', ':'))
                    else:
                        compact = json.dumps(item, ensure_ascii=False)
                    array_lines.append(f"        {compact}")
                value_str = '[\n' + ',\n'.join(array_lines) + '\n    ]'
            elif isinstance(value, dict):
                value_str = json.dumps(value, ensure_ascii=False, separators=(', ', ': '))
            elif value is None:
                value_str = 'null'
            else:
                value_str = json.dumps(value, ensure_ascii=False)

            items.append(f'    {key_str}: {value_str}')

        lines.append(',\n'.join(items))
        lines.append('}')
        return '\n'.join(lines)

    def update_app_json(self, app_path: Path, versions: Dict[str, List[str]]) -> bool:
        """Update app.json with new version information."""
        app_json_path = app_path / "app.json"

        if not app_json_path.exists():
            return False

        try:
            with open(app_json_path, 'r', encoding='utf-8') as f:
                app_data = json.load(f)

            # Check if versions are different
            old_versions = app_data.get('appversion', [])

            # Build new version list
            new_versions = []
            
            # Separate numeric and non-numeric versions
            numeric_versions = {}
            non_numeric_versions = []
            
            for major, minors in versions.items():
                if major.isdigit():
                    numeric_versions[major] = minors
                else:
                    # Keep track of non-numeric tags (already sorted by date)
                    non_numeric_versions.append(major)
            
            # Add non-numeric tags first (sorted by date in organize_versions)
            for tag in non_numeric_versions:
                new_versions.append({
                    "m_version": tag,
                    "s_version": []
                })
            
            # Add numeric versions (sorted by major version, descending)
            major_versions = sorted(numeric_versions.keys(), key=int, reverse=True)
            
            # Limit number of major versions if specified
            if self.max_major_versions:
                major_versions = major_versions[:self.max_major_versions]
            
            for major in major_versions:
                minors = numeric_versions[major]
                
                # Limit minor versions per major if specified
                if self.max_versions_per_major:
                    minors = minors[:self.max_versions_per_major]
                
                new_versions.append({
                    "m_version": major,
                    "s_version": minors
                })

            # Check if there are actual changes
            if json.dumps(old_versions, sort_keys=True) == json.dumps(new_versions, sort_keys=True):
                return False

            # Update the version
            app_data['appversion'] = new_versions
            app_data['updateat'] = int(datetime.now().timestamp())

            if not self.dry_run:
                # Write back with compact formatting
                formatted_json = self.format_json_compact(app_data)
                with open(app_json_path, 'w', encoding='utf-8') as f:
                    f.write(formatted_json)

            return True

        except Exception as e:
            self.log(f"Error updating {app_json_path}: {e}")
            return False

    def process_app(self, app_path: Path) -> bool:
        """Process a single app directory."""
        app_name = app_path.name

        # Skip if it's a GPU variant (they typically share versions with base app)
        if 'gpu' in app_name.lower():
            if self.debug:
                self.log(f"Skipping GPU variant: {app_name}")
            return False

        # In debug mode, show full details
        if self.debug:
            self.log(f"\n{'='*60}")
            self.log(f"Processing: {app_name}")
            self.log(f"{'='*60}")

        # Find docker-compose.yml
        compose_path = self.find_docker_compose(app_path)
        if not compose_path:
            if self.debug:
                self.log(f"  ⚠️  No docker-compose.yml found")
            return False

        if self.debug:
            self.log(f"  📄 Found compose: {compose_path.relative_to(self.apps_dir.parent)}")

        # Extract image name
        image_string = self.extract_image_from_compose(compose_path)
        if not image_string:
            if self.debug:
                self.log(f"  ⚠️  Could not extract image name")
            return False

        if self.debug:
            self.log(f"  🐳 Image: {image_string}")

        # Fetch versions
        versions = self.fetcher.get_versions_for_image(image_string)
        if not versions:
            if self.debug:
                self.log(f"  ⚠️  Could not fetch versions")
            return False

        # Show version summary
        if self.debug:
            version_summary = ", ".join([f"{k}: {len(v)} versions" for k, v in sorted(versions.items(), reverse=True)])
            self.log(f"  📦 Versions found: {version_summary}")

        # Update app.json
        updated = self.update_app_json(app_path, versions)

        if updated:
            if self.debug:
                self.log(f"  ✅ Updated app.json")
            return True
        else:
            if self.debug:
                self.log(f"  ℹ️  No changes needed")
            return False

    def process_app_safe(self, app_path: Path) -> Tuple[str, bool, Optional[str]]:
        """Process a single app with exception handling (thread-safe wrapper)."""
        try:
            updated = self.process_app(app_path)
            return (app_path.name, updated, None)
        except Exception as e:
            return (app_path.name, False, str(e))

    def process_all_apps(self, specific_apps: Optional[List[str]] = None):
        """Process all apps or specific apps with parallel processing."""
        if not self.apps_dir.exists():
            self.log(f"Error: Apps directory not found: {self.apps_dir}")
            return

        # Get list of apps to process
        if specific_apps:
            app_dirs = [self.apps_dir / app for app in specific_apps if (self.apps_dir / app).is_dir()]
        else:
            app_dirs = [p for p in self.apps_dir.iterdir() if p.is_dir()]

        app_dirs = sorted(app_dirs, key=lambda p: p.name.lower())
        
        self.log(f"\n{'#'*60}")
        self.log(f"Starting version update for {len(app_dirs)} apps")
        self.log(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        self.log(f"Workers: {self.workers} parallel thread(s)")
        self.log(f"{'#'*60}")
        
        # Start timer
        start_time = time.time()

        if self.workers == 1:
            # Sequential processing (original behavior)
            for i, app_path in enumerate(app_dirs, 1):
                with self.stats_lock:
                    self.stats['total'] += 1

                # Show progress counter in non-debug mode
                if not self.debug and self.is_tty:
                    progress_msg = f"[{i}/{len(app_dirs)}] Processing: {app_path.name}..."
                    self.progress(progress_msg)

                try:
                    updated = self.process_app(app_path)
                    with self.stats_lock:
                        if updated:
                            self.stats['updated'] += 1
                            # Show update notification
                            if not self.debug and self.is_tty:
                                self.progress(f"[{i}/{len(app_dirs)}] ✅ {app_path.name} - Updated")
                        else:
                            self.stats['skipped'] += 1
                            # Just continue to next without showing "no changes"
                except Exception as e:
                    if not self.debug:
                        self.progress(f"[{i}/{len(app_dirs)}] ❌ {app_path.name} - Error: {e}", final=True)
                    else:
                        self.log(f"\n❌ Error processing {app_path.name}: {e}")
                    with self.stats_lock:
                        self.stats['errors'] += 1
            
            # Clear final progress line
            if not self.debug and self.is_tty:
                self.progress("", final=True)
        else:
            # Parallel processing
            with self.stats_lock:
                self.stats['total'] = len(app_dirs)
            
            completed = 0

            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                # Submit all tasks
                future_to_app = {executor.submit(self.process_app_safe, app_path): app_path 
                                for app_path in app_dirs}

                # Process results as they complete
                for future in as_completed(future_to_app):
                    app_name, updated, error = future.result()
                    completed += 1
                    
                    # Show progress in non-debug mode
                    if not self.debug and self.is_tty:
                        with self.stats_lock:
                            progress_msg = f"[{completed}/{len(app_dirs)}] Completed: {self.stats['updated']} updated, {self.stats['skipped']} skipped, {self.stats['errors']} errors"
                        self.progress(progress_msg)
                    
                    with self.stats_lock:
                        if error:
                            if not self.is_tty:
                                self.progress(f"❌ Error processing {app_name}: {error}", final=True)
                            self.stats['errors'] += 1
                        elif updated:
                            self.stats['updated'] += 1
                        else:
                            self.stats['skipped'] += 1
            
            # Clear progress line after parallel completion
            if not self.debug and self.is_tty:
                self.progress("", final=True)

        # End timer
        end_time = time.time()
        duration = end_time - start_time
        
        # Print summary
        self.log(f"\n{'#'*60}")
        self.log(f"SUMMARY")
        self.log(f"{'#'*60}")
        self.log(f"Total apps processed: {self.stats['total']}")
        self.log(f"Updated: {self.stats['updated']}")
        self.log(f"Skipped (no changes): {self.stats['skipped']}")
        self.log(f"Errors: {self.stats['errors']}")
        self.log(f"Time elapsed: {duration:.2f} seconds")
        
        # Performance info
        if duration > 0 and self.stats['total'] > 0:
            avg_time = duration / self.stats['total']
            self.log(f"Average time per app: {avg_time:.2f} seconds")
        
        self.log(f"{'#'*60}")



def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Automatically update Docker app versions from Docker Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all apps (dry run)
  python3 update_versions.py --dry-run
  
  # Update all apps (live)
  python3 update_versions.py
  
  # Update specific apps
  python3 update_versions.py mysql redis nginx_proxy_manager
  
  # Update with debug output
  python3 update_versions.py --debug mysql
  
  # Get more tags from Docker Hub
  python3 update_versions.py --max-tags 200 redis
  
  # Limit versions per major version
  python3 update_versions.py --max-versions-per-major 15 redis
  
  # Limit number of major versions
  python3 update_versions.py --max-major-versions 5 redis
  
  # Use parallel processing (faster for many apps)
  python3 update_versions.py --workers 5
  
  # Update all apps with optimal parallel configuration
  python3 update_versions.py --workers 10 --max-versions-per-major 20 --max-major-versions 5
"""
    )

    parser.add_argument(
        'apps',
        nargs='*',
        help='Specific app names to update (leave empty for all apps)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )

    parser.add_argument(
        '--apps-dir',
        default='apps',
        help='Path to apps directory (default: apps)'
    )
    
    parser.add_argument(
        '--max-tags',
        type=int,
        default=100,
        help='Maximum number of tags to fetch from Docker Hub (default: 100, max: 100)'
    )
    
    parser.add_argument(
        '--max-versions-per-major',
        type=int,
        default=None,
        help='Maximum number of versions to keep per major version (default: unlimited)'
    )
    
    parser.add_argument(
        '--max-major-versions',
        type=int,
        default=None,
        help='Maximum number of major versions to keep (default: unlimited)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        default=32,
        help='Number of parallel workers for processing apps (default: 1 = sequential)'
    )

    args = parser.parse_args()

    updater = AppVersionUpdater(
        apps_dir=args.apps_dir,
        debug=args.debug,
        dry_run=args.dry_run,
        max_tags=args.max_tags,
        max_versions_per_major=args.max_versions_per_major,
        max_major_versions=args.max_major_versions,
        workers=args.workers
    )

    updater.process_all_apps(specific_apps=args.apps if args.apps else None)


if __name__ == '__main__':
    main()