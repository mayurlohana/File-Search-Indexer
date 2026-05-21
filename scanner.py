import os
import hashlib
import time
from typing import Callable, Optional, List, Tuple
from database import DatabaseManager

class FileScanner:
    """
    Recursively scans directory structures, extracts metadata (name, size, dates),
    and manages efficient content hashing for duplicate detection using a 2-phase indexing strategy.
    """
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.is_cancelled = False

    def cancel(self):
        """Cancels any ongoing scan operation."""
        self.is_cancelled = True

    def calculate_md5(self, file_path: str, chunk_size: int = 65536) -> Optional[str]:
        """
        Computes the MD5 hash of a file's contents in a memory-safe, chunked manner.
        Returns None if the file cannot be read (e.g., due to permission errors).
        """
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (PermissionError, FileNotFoundError, OSError):
            return None

    def scan_directory(
        self,
        root_dir: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ) -> Tuple[int, int]:
        """
        Main scanner loop:
        1. Recursively scans the directory and retrieves file metadata.
        2. Batch inserts all metadata into the database.
        3. Identifies size duplicates and calculates MD5 hashes only for those files.
        """
        self.is_cancelled = False
        
        if not os.path.isdir(root_dir):
            if on_status:
                on_status(f"Error: {root_dir} is not a valid directory.")
            return 0, 0

        if on_status:
            on_status("Phase 1: Scanning directory and collecting metadata...")

        scanned_files = 0
        scanned_dirs = 0
        batch_size = 1000
        batch_data = []

        # Clear existing index before starting a new scan
        self.db.clear_index()

        for dirpath, dirnames, filenames in os.walk(root_dir):
            if self.is_cancelled:
                if on_status:
                    on_status("Scan cancelled by user.")
                return scanned_files, 0

            scanned_dirs += 1
            
            # Prune hidden or system directories to speed up (optional but highly recommended)
            # E.g., ignore .git, .gemini, Library (on Mac), etc.
            dirnames[:] = [d for d in dirnames if not d.startswith('.') and d not in ('Library', 'Library/Caches')]

            for filename in filenames:
                if self.is_cancelled:
                    if on_status:
                        on_status("Scan cancelled by user.")
                    return scanned_files, 0

                full_path = os.path.join(dirpath, filename)
                
                try:
                    # Retrieve stats, skipping broken symlinks
                    stat_result = os.stat(full_path, follow_symlinks=False)
                    # Check if it is a regular file
                    if not os.path.islink(full_path) and not os.path.isdir(full_path):
                        size = stat_result.st_size
                        modified_at = stat_result.st_mtime
                        
                        # Try macOS birthtime, fallback to st_ctime (change time)
                        try:
                            created_at = stat_result.st_birthtime
                        except AttributeError:
                            created_at = stat_result.st_ctime
                            
                        # Split extension
                        _, ext = os.path.splitext(filename)
                        ext = ext.lower()

                        # Collect row: (path, name, extension, size, created_at, modified_at, md5_hash)
                        batch_data.append((full_path, filename, ext, size, created_at, modified_at, None))
                        scanned_files += 1

                        if len(batch_data) >= batch_size:
                            self.db.insert_files_batch(batch_data)
                            batch_data.clear()

                        if on_progress and scanned_files % 100 == 0:
                            on_progress(scanned_files, scanned_dirs)

                except (PermissionError, FileNotFoundError, OSError):
                    # Gracefully skip files with permission errors, lockouts, or deleted mid-scan
                    continue

        # Insert remaining files
        if batch_data:
            self.db.insert_files_batch(batch_data)

        if on_progress:
            on_progress(scanned_files, scanned_dirs)

        if self.is_cancelled:
            return scanned_files, 0

        # Phase 2: Compute hashes for potential duplicates (same size)
        if on_status:
            on_status("Phase 2: Calculating content hashes for size-matching files...")

        # Fetch size matches (groups of files sharing the same non-zero size)
        size_matches = self.db.get_size_matches()
        total_hash_candidates = sum(len(group[1]) for group in size_matches)
        hashed_count = 0

        for size, files in size_matches:
            if self.is_cancelled:
                if on_status:
                    on_status("Hashing cancelled by user.")
                return scanned_files, 0

            # Calculate MD5 only for files that share identical sizes
            for f in files:
                if self.is_cancelled:
                    return scanned_files, 0

                file_id = f["id"]
                file_path = f["path"]
                
                md5_val = self.calculate_md5(file_path)
                if md5_val:
                    self.db.update_file_hash(file_id, md5_val)
                
                hashed_count += 1
                if on_status and hashed_count % 50 == 0:
                    on_status(f"Phase 2: Calculating content hashes ({hashed_count}/{total_hash_candidates})...")

        # Get final duplicate group count
        duplicate_groups = self.db.get_duplicate_groups()
        total_duplicate_files = sum(group["count"] for group in duplicate_groups)

        if on_status:
            if self.is_cancelled:
                on_status("Scan completed (cancelled before full hash completion).")
            else:
                on_status(f"Scan complete! Indexed {scanned_files} files across {scanned_dirs} directories. Found {total_duplicate_files} duplicate files.")

        return scanned_files, len(duplicate_groups)
