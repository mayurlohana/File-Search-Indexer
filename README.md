# File Search Indexer

A high-performance local file indexing, searching, and cleanup tool built in Python. It recursively scans directories, indexes file metadata into an SQLite database, and offers a premium, modern dark-themed Tkinter GUI. It features advanced search filtering, sorting, pagination, a recently modified dashboard, and a duplicate file finder.

## Features

- **Object-Oriented Design**: Pure Python codebase structured cleanly around modular components (`scanner.py`, `database.py`, `gui.py`, `main.py`).
- **Recursive Metadata Harvesting**: Walks directories to gather names, paths, extensions, sizes, and modification/creation timestamps safely, handling permission errors, broken symlinks, and files deleted mid-scan.
- **SQLite Performance Core**: Utilizes an SQLite backend with carefully placed indices to support instant querying, complex range filtering (size, date ranges), and pagination without loading files into memory.
- **Two-Phase Hashing**: Optimizes disk I/O by calculating MD5 content hashes *only* for files with matching non-zero sizes, avoiding redundant hashing of unique files.
- **Custom-Themed Dark GUI**: Styled modern Tkinter interface incorporating custom CSS-like theme rules for a dark aesthetic, complete with:
  - Sidebar filters (extension combobox, min/max size with unit selection, date presets, and custom range selection).
  - Paged search results table (custom vertical/horizontal scrollbars, header click-to-sort, and row-count selection).
  - Background thread processing with dynamic progress updates to keep the GUI fluid and responsive.
  - Interactive context menu (Right-click or two-finger tap) to Open File, Open Containing Folder, or Copy Full Path.
  - **Recently Modified Tab**: A real-time log of the latest 50 files edited.
  - **Duplicate Finder Tab**: Lists groupings of exact content duplicates, showing detail paths with standard interactions, plus **direct file deletion from disk and index**.

---

## Getting Started

### Prerequisites

The project relies entirely on Python standard library modules (`sqlite3`, `tkinter`, `hashlib`, `threading`, etc.). No external dependencies are strictly necessary, making it lightweight and cross-platform.

Ensure you have **Python 3.7+** installed.

### Run the Application

Execute the entry point module:

```bash
python3 main.py
```

To use a custom database path, specify the `--db` argument:

```bash
python3 main.py --db /path/to/custom_index.db
```

---

## Directory Structure

```text
├── database.py       # SQLite index database interactions (schemas, queries)
├── scanner.py        # Recursive directory walking and chunked MD5 hashing
├── gui.py            # Custom-themed Tkinter multi-tab GUI, event queues, and OS utilities
├── main.py           # Application entry point
├── test_indexer.py   # Complete integration and unit test suite
└── README.md         # Documentation
```

---

## Running Tests

Verify the entire application logic using Python's built-in unit-testing framework:

```bash
python3 -m unittest test_indexer.py
```

The test suite validates:
- Recursive scanner walker counts and metadata harvesting.
- Advanced keyword and extension filters.
- Accurate file size range filtering.
- Pagination limits, offsets, and ascending/descending sort ordering.
- Content hash comparison and duplicate file grouping logic.
