import sqlite3
import os
from typing import List, Dict, Any, Tuple, Optional

class DatabaseManager:
    """
    Manages SQLite database initialization, insertion of scanned file metadata,
    and structured querying (search, filtering, sorting, pagination, duplicates, recently added).
    """
    def __init__(self, db_path: str = "index.db"):
        self.db_path = db_path
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Returns a connection with Row factory enabled for dictionary-like access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self):
        """Initializes the database schema and indexes if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create files table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    extension TEXT,
                    size INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    modified_at REAL NOT NULL,
                    md5_hash TEXT
                )
            """)
            
            # Create indexes for optimal performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_name ON files(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_size ON files(size)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files(md5_hash)")
            conn.commit()

    def clear_index(self):
        """Clears all records in the files table."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM files")
            conn.commit()

    def insert_files_batch(self, files_data: List[Tuple[str, str, str, int, float, float, Optional[str]]]):
        """
        Batch inserts files into the database.
        Each item in files_data is a tuple: (path, name, extension, size, created_at, modified_at, md5_hash)
        """
        if not files_data:
            return
            
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT OR REPLACE INTO files (path, name, extension, size, created_at, modified_at, md5_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, files_data)
            conn.commit()

    def update_file_hash(self, file_id: int, md5_hash: str):
        """Updates the MD5 hash of a specific file by its ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE files SET md5_hash = ? WHERE id = ?", (md5_hash, file_id))
            conn.commit()

    def get_total_count(self) -> int:
        """Returns the total number of indexed files."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM files")
            row = cursor.fetchone()
            return row[0] if row else 0

    def search_files(
        self,
        query_str: Optional[str] = None,
        extension: Optional[str] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        min_date: Optional[float] = None,
        max_date: Optional[float] = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Searches files in the database based on multiple search and filter constraints,
        supporting sorting, pagination, and returning the total matched count alongside the page items.
        """
        # Validate sort inputs to avoid SQL injection
        allowed_sort_fields = {"name": "name", "size": "size", "modified_at": "modified_at", "created_at": "created_at"}
        sort_col = allowed_sort_fields.get(sort_by.lower(), "name")
        order = "DESC" if sort_order.lower() == "desc" else "ASC"

        # Build query constraints
        conditions = []
        params = []

        if query_str and query_str.strip():
            conditions.append("name LIKE ?")
            params.append(f"%{query_str.strip()}%")

        if extension and extension.strip():
            ext = extension.strip().lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            conditions.append("lower(extension) = ?")
            params.append(ext)

        if min_size is not None:
            conditions.append("size >= ?")
            params.append(min_size)

        if max_size is not None:
            conditions.append("size <= ?")
            params.append(max_size)

        if min_date is not None:
            conditions.append("modified_at >= ?")
            params.append(min_date)

        if max_date is not None:
            conditions.append("modified_at <= ?")
            params.append(max_date)

        # Assemble WHERE clause
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        # Fetch count query
        count_query = f"SELECT COUNT(*) FROM files{where_clause}"
        
        # Fetch page query
        page_query = f"""
            SELECT id, path, name, extension, size, created_at, modified_at, md5_hash
            FROM files
            {where_clause}
            ORDER BY {sort_col} {order}
            LIMIT ? OFFSET ?
        """

        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get total count first
            cursor.execute(count_query, params)
            total_count = cursor.fetchone()[0]

            # Get paginated data
            page_params = params + [limit, offset]
            cursor.execute(page_query, page_params)
            rows = cursor.fetchall()
            
            results = [dict(row) for row in rows]
            return results, total_count

    def get_recently_added(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves the top N most recently modified files."""
        query = """
            SELECT id, path, name, extension, size, created_at, modified_at, md5_hash
            FROM files
            ORDER BY modified_at DESC
            LIMIT ?
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_duplicate_groups(self) -> List[Dict[str, Any]]:
        """
        Identifies and groups files with identical content (based on MD5 hash and non-zero size).
        Returns a list of duplicate groups, where each entry contains metadata about the duplicates.
        """
        # Step 1: Find hashes that appear more than once with non-zero size
        find_duplicates_query = """
            SELECT md5_hash, size, COUNT(*) as file_count
            FROM files
            WHERE md5_hash IS NOT NULL AND md5_hash != '' AND size > 0
            GROUP BY md5_hash, size
            HAVING file_count > 1
            ORDER BY size DESC
        """
        
        # Step 2: Fetch all files that match those hashes
        get_files_for_hashes = """
            SELECT id, path, name, extension, size, created_at, modified_at, md5_hash
            FROM files
            WHERE md5_hash = ? AND size = ?
            ORDER BY path
        """
        
        groups = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(find_duplicates_query)
            dup_candidates = cursor.fetchall()
            
            for cand in dup_candidates:
                md5_hash = cand["md5_hash"]
                size = cand["size"]
                
                # Fetch all files with this hash and size
                cursor.execute(get_files_for_hashes, (md5_hash, size))
                file_rows = cursor.fetchall()
                
                groups.append({
                    "md5_hash": md5_hash,
                    "size": size,
                    "count": cand["file_count"],
                    "files": [dict(row) for row in file_rows]
                })
        
        return groups

    def get_size_matches(self) -> List[Tuple[int, List[Dict[str, Any]]]]:
        """
        Finds all files in the database that share the exact same size.
        This is a pre-filtering step used by the scanner to determine which files
        actually need MD5 calculation.
        """
        query_sizes = """
            SELECT size, COUNT(*) as file_count
            FROM files
            WHERE size > 0
            GROUP BY size
            HAVING file_count > 1
            ORDER BY size DESC
        """
        
        query_files = """
            SELECT id, path, name, size
            FROM files
            WHERE size = ?
        """
        
        matches = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query_sizes)
            size_rows = cursor.fetchall()
            
            for row in size_rows:
                size = row["size"]
                cursor.execute(query_files, (size,))
                files = [dict(r) for r in cursor.fetchall()]
                matches.append((size, files))
                
        return matches
