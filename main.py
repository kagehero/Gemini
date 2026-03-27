"""
SharePoint × Gemini AI Search — main entry point.

Commands:
  setup     Print Azure AD setup guide
  test      Test all connections
  index     Initial indexing (--site NAME | --all)
  sync      Run delta sync (--now | --daemon)
  query     Query CLI (--ask Q | --hybrid | --compare Q)
  stats     Show index statistics
  api       FastAPI server for Next.js UI (uvicorn)
"""

import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)


def cmd_setup(_args):
    from scripts.setup_azure_app import main
    main()


def cmd_test(_args):
    from scripts.test_connection import main
    main()


def cmd_index(args):
    from scripts.initial_index import main
    # Simulate sys.argv for the sub-script
    sub_args = []
    if getattr(args, "all", False):
        sub_args = ["--all"]
    elif getattr(args, "site", None):
        sub_args = ["--site", args.site]
    sys.argv = ["initial_index"] + sub_args
    main()


def cmd_sync(args):
    from scripts.daily_sync import main
    sub_args = ["--now"] if getattr(args, "now", False) else ["--daemon"]
    sys.argv = ["daily_sync"] + sub_args
    main()


def cmd_query(args):
    from scripts.query import main
    sub_args = []
    if getattr(args, "ask", None):
        sub_args += ["--ask", args.ask]
    if getattr(args, "compare", None):
        sub_args += ["--compare", args.compare]
    if getattr(args, "site", None):
        sub_args += ["--site", args.site]
    if getattr(args, "hybrid", False):
        sub_args += ["--hybrid"]
    if getattr(args, "hybrid_top", None) is not None:
        sub_args += ["--hybrid-top", str(args.hybrid_top)]
    sys.argv = ["query"] + sub_args
    main()


def cmd_api(_args):
    import uvicorn

    from config import settings

    uvicorn.run(
        "api.app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )


def cmd_stats(_args):
    from storage.metadata_store import init_db, get_stats
    from vector_db.vectordb import get_collection_stats

    init_db()
    meta = get_stats()
    vec = get_collection_stats()

    print("\n── Index Statistics ──────────────────────────────────────")
    print(f"  Files indexed : {meta['total_files']}")
    print(f"  Total chunks  : {meta['total_chunks']}")
    print("\n  By site:")
    for site, count in meta["by_site"].items():
        print(f"    {site}: {count} files")
    print("\n  Vector collections:")
    for col, count in vec.items():
        print(f"    {col}: {count} chunks")
    print("──────────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(
        description="SharePoint × Gemini AI Search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("setup", help="Azure AD setup guide")
    sub.add_parser("test", help="Test all connections")

    p_index = sub.add_parser("index", help="Initial indexing")
    grp = p_index.add_mutually_exclusive_group()
    grp.add_argument("--site", type=str)
    grp.add_argument("--all", action="store_true")

    p_sync = sub.add_parser("sync", help="Delta sync")
    sg = p_sync.add_mutually_exclusive_group(required=True)
    sg.add_argument("--now", action="store_true")
    sg.add_argument("--daemon", action="store_true")

    p_query = sub.add_parser("query", help="Query (RAG or hybrid Search→fetch→Gemini)")
    p_query.add_argument("--ask", type=str)
    p_query.add_argument("--compare", type=str)
    p_query.add_argument("--site", type=str)
    p_query.add_argument(
        "--hybrid",
        action="store_true",
        help="Use SharePoint search + download top files only (no vector DB)",
    )
    p_query.add_argument("--hybrid-top", type=int, default=None, help="Hybrid: max files per question")

    sub.add_parser("stats", help="Show index statistics")

    sub.add_parser("api", help="Start FastAPI server for the Next.js UI (uvicorn)")

    args = parser.parse_args()

    dispatch = {
        "setup": cmd_setup,
        "test": cmd_test,
        "index": cmd_index,
        "sync": cmd_sync,
        "query": cmd_query,
        "stats": cmd_stats,
        "api": cmd_api,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
