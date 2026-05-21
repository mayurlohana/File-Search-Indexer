import os
import argparse
from gui import FileIndexerApp

def main():
    parser = argparse.ArgumentParser(description="File Search Indexer - OOP Local File Indexer with SQLite & Tkinter")
    parser.add_argument("--db", type=str, default="index.db", help="Path to SQLite index database file")
    args = parser.parse_args()

    # Determine absolute database path in workspace
    db_path = os.path.abspath(args.db)

    # Initialize and run Tkinter Application
    app = FileIndexerApp(db_path=db_path)
    app.mainloop()

if __name__ == "__main__":
    main()
