import unittest
import os
import tempfile
import time
from database import DatabaseManager
from scanner import FileScanner

class TestFileIndexer(unittest.TestCase):
    """
    Unit and integration tests for the DatabaseManager and FileScanner.
    Uses tempfile to create isolated directory structures and db instances.
    """
    def setUp(self):
        # Create temp DB in memory or a temp file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.db = DatabaseManager(self.db_path)
        self.scanner = FileScanner(self.db)

        # Create temporary directory structure for scanning
        self.test_dir = tempfile.TemporaryDirectory()
        self.root_path = self.test_dir.name

        # Construct dummy files
        # Duplicates Group 1: 11 bytes each
        self.write_file("dup1.txt", "Hello World")
        self.write_file("dup2.txt", "Hello World")
        
        # Subdirectory
        os.makedirs(os.path.join(self.root_path, "subdir"), exist_ok=True)
        self.write_file("subdir/dup3.txt", "Hello World") # Third duplicate
        
        # Unique files
        self.write_file("unique.log", "This is a unique log file with distinct size.") # 46 bytes
        self.write_file("subdir/image.png", "BinaryDataHere!!!") # 17 bytes
        self.write_file("empty.txt", "") # 0 bytes

    def tearDown(self):
        # Close database connection and clean up files
        self.test_dir.cleanup()
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def write_file(self, relative_path: str, content: str):
        full_path = os.path.join(self.root_path, relative_path)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        # Add a tiny sleep to ensure stat times have minuscule ordering if needed
        time.sleep(0.01)

    def test_scanning_and_counts(self):
        """Verify the scanner detects all files and populates database metadata."""
        files_indexed, dup_groups = self.scanner.scan_directory(self.root_path)
        
        # Should scan 6 files: dup1.txt, dup2.txt, dup3.txt, unique.log, image.png, empty.txt
        self.assertEqual(files_indexed, 6)
        
        # Total files in DB should be 6
        self.assertEqual(self.db.get_total_count(), 6)

    def test_search_by_name_and_extension(self):
        """Test name searching and extension filtering."""
        self.scanner.scan_directory(self.root_path)

        # Search keyword "dup" -> Should return dup1.txt, dup2.txt, dup3.txt
        results, count = self.db.search_files(query_str="dup")
        self.assertEqual(count, 3)
        self.assertEqual(len(results), 3)
        names = [f["name"] for f in results]
        self.assertIn("dup1.txt", names)
        self.assertIn("dup2.txt", names)
        self.assertIn("dup3.txt", names)

        # Search extension ".log"
        results, count = self.db.search_files(extension="log")
        self.assertEqual(count, 1)
        self.assertEqual(results[0]["name"], "unique.log")

        # Search extension without leading dot "txt" (db should handle auto-adding dot)
        results, count = self.db.search_files(extension="txt")
        self.assertEqual(count, 4) # dup1, dup2, dup3, empty

    def test_search_size_filtering(self):
        """Test search filtering by min and max size range."""
        self.scanner.scan_directory(self.root_path)

        # Min size 15 bytes -> image.png (17) and unique.log (46)
        results, count = self.db.search_files(min_size=15)
        self.assertEqual(count, 2)
        
        # Max size 12 bytes -> dup1, dup2, dup3 (11 bytes each) and empty.txt (0 bytes)
        results, count = self.db.search_files(max_size=12)
        self.assertEqual(count, 4)

        # Size between 5 and 15 bytes -> dup1, dup2, dup3 (11 bytes)
        results, count = self.db.search_files(min_size=5, max_size=15)
        self.assertEqual(count, 3)

    def test_sorting_and_pagination(self):
        """Test result order sorting and limit/offset paging."""
        self.scanner.scan_directory(self.root_path)

        # Sort by size Descending
        results, count = self.db.search_files(sort_by="size", sort_order="desc")
        self.assertEqual(results[0]["name"], "unique.log") # 46 bytes (largest)
        self.assertEqual(results[-1]["name"], "empty.txt") # 0 bytes (smallest)

        # Pagination: Limit 2, Offset 0
        results_page1, count = self.db.search_files(sort_by="name", sort_order="asc", limit=2, offset=0)
        self.assertEqual(count, 6)
        self.assertEqual(len(results_page1), 2)
        
        # Pagination: Limit 2, Offset 2 (Page 2)
        results_page2, count = self.db.search_files(sort_by="name", sort_order="asc", limit=2, offset=2)
        self.assertEqual(len(results_page2), 2)
        
        # Ensure pages are contiguous and non-overlapping
        page1_names = [f["name"] for f in results_page1]
        page2_names = [f["name"] for f in results_page2]
        for name in page1_names:
            self.assertNotIn(name, page2_names)

    def test_duplicate_detection(self):
        """Verify files with identical content hashes are correctly grouped."""
        files_indexed, dup_groups = self.scanner.scan_directory(self.root_path)
        
        # Should detect exactly 1 duplicate content group (the "Hello World" files)
        self.assertEqual(dup_groups, 1)

        groups = self.db.get_duplicate_groups()
        self.assertEqual(len(groups), 1)
        
        dup_group = groups[0]
        self.assertEqual(dup_group["size"], 11)
        self.assertEqual(dup_group["count"], 3)
        
        paths = [f["path"] for f in dup_group["files"]]
        self.assertTrue(any(p.endswith("dup1.txt") for p in paths))
        self.assertTrue(any(p.endswith("dup2.txt") for p in paths))
        self.assertTrue(any(p.endswith("dup3.txt") for p in paths))

        # The unique log and image have different sizes, so they should NOT be grouped
        # The empty.txt has size 0, so it's ignored for duplicates per requirements
        self.assertFalse(any(g["size"] == 0 for g in groups))

    def test_recently_added(self):
        """Test retrieving recently modified files."""
        self.scanner.scan_directory(self.root_path)
        recent = self.db.get_recently_added(3)
        self.assertEqual(len(recent), 3)

if __name__ == "__main__":
    unittest.main()
