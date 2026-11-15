#!/usr/bin/env python3
"""Administrative CLI for PostgreSQL playlists.

Playlists are not created when ingesting tracks: create at least one here,
then pass its slug to `scripts/ingest_timelapse.py`.

Usage:
    python scripts/ingest_playlist.py create --slug earth-timelapses \\
        --title "Earth Timelapses" --category timelapse

    python scripts/ingest_playlist.py list
    python scripts/ingest_playlist.py show --slug earth-timelapses
    python scripts/ingest_playlist.py update --slug earth-timelapses --featured
    python scripts/ingest_playlist.py delete --slug earth-timelapses --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.database import SessionLocal, init_db  # noqa: E402
from app.models.playlist import Playlist  # noqa: E402
from app.schemas.playlist import PlaylistCreate, PlaylistUpdate  # noqa: E402
from app.services.playlist_service import (  # noqa: E402
    create_playlist,
    delete_playlist,
    get_playlist_by_slug,
    list_playlists,
    update_playlist,
)


def parse_args() -> argparse.Namespace:
    """Define and parse the CLI subcommands."""
    parser = argparse.ArgumentParser(
        description="Create, list, update, or delete playlists in PostgreSQL.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a playlist.")
    create_parser.add_argument("--slug", type=str, required=True, help="Unique slug.")
    create_parser.add_argument("--title", type=str, required=True, help="Title.")
    create_parser.add_argument(
        "--category",
        type=str,
        required=True,
        help="Editorial category (e.g. timelapse).",
    )
    create_parser.add_argument("--description", type=str, default=None, help="Description.")
    create_parser.add_argument(
        "--cover-url",
        type=str,
        default=None,
        help="Cover image URL (optional).",
    )
    create_parser.add_argument(
        "--featured",
        action="store_true",
        help="Mark the playlist as featured.",
    )

    list_parser = subparsers.add_parser("list", help="List playlists.")
    list_parser.add_argument("--category", type=str, default=None, help="Filter by category.")
    list_parser.add_argument(
        "--featured",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Filter by featured status.",
    )
    list_parser.add_argument("--limit", type=int, default=50, help="Maximum number of results.")
    list_parser.add_argument("--offset", type=int, default=0, help="Offset.")

    show_parser = subparsers.add_parser("show", help="Show a playlist by slug.")
    show_parser.add_argument("--slug", type=str, required=True, help="Playlist slug.")

    update_parser = subparsers.add_parser("update", help="Update editorial fields.")
    update_parser.add_argument("--slug", type=str, required=True, help="Playlist slug.")
    update_parser.add_argument("--title", type=str, default=None, help="New title.")
    update_parser.add_argument("--description", type=str, default=None, help="New description.")
    update_parser.add_argument("--category", type=str, default=None, help="New category.")
    update_parser.add_argument("--cover-url", type=str, default=None, help="New cover image URL.")
    update_parser.add_argument(
        "--featured",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Change the featured status.",
    )

    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete a playlist and its tracks through cascading.",
    )
    delete_parser.add_argument("--slug", type=str, required=True, help="Playlist slug.")
    delete_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion (required).",
    )

    return parser.parse_args()


def _require_playlist(session: Session, slug: str) -> Playlist:
    """Return the playlist or exit if it does not exist."""
    playlist = get_playlist_by_slug(session, slug)
    if playlist is None:
        sys.exit(f"Playlist not found: {slug}")
    return playlist


def _cmd_create(session: Session, args: argparse.Namespace) -> None:
    playlist = create_playlist(
        session,
        PlaylistCreate(
            slug=args.slug,
            title=args.title,
            description=args.description,
            category=args.category,
            cover_url=args.cover_url,
            is_featured=args.featured,
        ),
    )
    print(f"Playlist created: {playlist.slug} (id={playlist.id})")


def _cmd_list(session: Session, args: argparse.Namespace) -> None:
    playlists = list_playlists(
        session,
        category=args.category,
        is_featured=args.featured,
        limit=args.limit,
        offset=args.offset,
    )
    if not playlists:
        print("No playlists found.")
        return
    for playlist in playlists:
        featured = " featured" if playlist.is_featured else ""
        track_count = len(playlist.tracks)
        print(
            f"{playlist.slug}\tid={playlist.id}\t{playlist.title}\t"
            f"{playlist.category}{featured}\t{track_count} tracks"
        )


def _cmd_show(session: Session, args: argparse.Namespace) -> None:
    playlist = _require_playlist(session, args.slug)
    print(f"id: {playlist.id}")
    print(f"slug: {playlist.slug}")
    print(f"title: {playlist.title}")
    print(f"category: {playlist.category}")
    print(f"featured: {playlist.is_featured}")
    print(f"cover_url: {playlist.cover_url or ''}")
    print(f"description: {playlist.description or ''}")
    print(f"tracks: {len(playlist.tracks)}")
    for track in playlist.tracks:
        print(f"  - {track.slug} (id={track.id}, order={track.sequence_order})")


def _cmd_update(session: Session, args: argparse.Namespace) -> None:
    playlist = _require_playlist(session, args.slug)
    updates: dict[str, object] = {}
    if args.title is not None:
        updates["title"] = args.title
    if args.description is not None:
        updates["description"] = args.description
    if args.category is not None:
        updates["category"] = args.category
    if args.cover_url is not None:
        updates["cover_url"] = args.cover_url
    if args.featured is not None:
        updates["is_featured"] = args.featured
    if not updates:
        sys.exit("No fields to update.")
    updated = update_playlist(session, playlist, PlaylistUpdate.model_validate(updates))
    print(f"Playlist updated: {updated.slug} (id={updated.id})")


def _cmd_delete(session: Session, args: argparse.Namespace) -> None:
    if not args.yes:
        sys.exit("Deletion requires --yes.")
    playlist = _require_playlist(session, args.slug)
    slug = playlist.slug
    playlist_id = playlist.id
    delete_playlist(session, playlist)
    print(f"Playlist deleted: {slug} (id={playlist_id})")


def main() -> None:
    """Route the subcommand to the playlist service."""
    args = parse_args()
    handlers = {
        "create": _cmd_create,
        "list": _cmd_list,
        "show": _cmd_show,
        "update": _cmd_update,
        "delete": _cmd_delete,
    }

    try:
        init_db()
        with SessionLocal() as session:
            handlers[args.command](session, args)
    except IntegrityError:
        sys.exit(f"A playlist with slug '{getattr(args, 'slug', '')}' already exists.")
    except SQLAlchemyError as exc:
        sys.exit(f"Database error: {exc}")


if __name__ == "__main__":
    main()
