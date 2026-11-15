#!/usr/bin/env python3
"""Standalone ingestion of a timelapse into PostgreSQL.

Measure a local frame directory with the engine using the visualization's
profile, then persist the result as a track. The track must belong to an
existing playlist; create one first with `scripts/ingest_playlist.py`.

Usage:
    python scripts/ingest_playlist.py create --slug earth-timelapses \\
        --title "Earth Timelapses" --category timelapse

   python scripts/ingest_timelapse.py --dir frames/sea-temperature \\
        --profile sst-anomaly --slug sst-anomaly-2003-2026 \\
       --title "Sea Temperature 2003-2026" \\
        --playlist-slug earth-timelapses

   # Measure and save the JSON only, without touching the database:
   python scripts/ingest_timelapse.py --dir frames/sea-temperature \\
       --profile sst-anomaly --slug test --title "Test" \\
       --playlist-slug earth-timelapses --dry-run --out output/sst-anomaly.json

   # Remeasure an existing track, preserving its slug:
   python scripts/ingest_timelapse.py --dir frames/sea-temperature \\
        --profile sst-anomaly --slug sst-anomaly-2003-2026 \\
       --title "Sea Temperature 2003-2026" \\
        --playlist-slug earth-timelapses --replace
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.cv_engine import (  # noqa: E402
    PROFILES,
    DatasetProfile,
    MLEngineError,
    lossy,
    measure_timelapse,
)
from app.schemas.track import TrackIngestData  # noqa: E402


def validate_frames_directory(raw_path: str) -> Path:
    """Validate that the path exists and is a readable directory.

    Args:
        raw_path: Raw path received from the CLI.

    Returns:
        The resolved path as `Path`.

    Raises:
        SystemExit: With code 1 if the path does not exist or is not a directory.
    """
    directory = Path(raw_path).expanduser().resolve()
    if not directory.exists():
        print(f"Error: directory does not exist: {directory}", file=sys.stderr)
        raise SystemExit(1)
    if not directory.is_dir():
        print(f"Error: path is not a directory: {directory}", file=sys.stderr)
        raise SystemExit(1)
    return directory


def parse_args() -> argparse.Namespace:
    """Define and parse the CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Measure a local timelapse with the engine and save it to PostgreSQL.",
    )
    parser.add_argument(
        "-d",
        "--dir",
        type=str,
        required=True,
        help="Directory containing .png/.jpg frames (required).",
    )
    parser.add_argument(
        "-p",
        "--profile",
        type=str,
        required=True,
        choices=sorted(PROFILES),
        help="Engine profile matching the visualization (required).",
    )
    parser.add_argument("--title", type=str, required=True, help="Track title.")
    parser.add_argument("--slug", type=str, required=True, help="Unique track slug.")
    parser.add_argument(
        "--playlist-slug",
        type=str,
        required=True,
        help="Destination playlist slug (required; playlist must exist).",
    )
    parser.add_argument("--description", type=str, default=None, help="Description.")
    parser.add_argument("--sequence-order", type=int, default=0, help="Order in the playlist.")
    parser.add_argument(
        "--event-date",
        type=datetime.fromisoformat,
        default=None,
        help="Event date in ISO 8601 format (e.g. 2025-11-01).",
    )
    parser.add_argument(
        "--frames-url",
        type=str,
        default=None,
        help="Public URL of the image directory for the frontend (optional).",
    )
    parser.add_argument(
        "--frames-ext",
        type=str,
        default=None,
        help="Extension of the public images if different from the measured frames (e.g. webp).",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite the content if a track with that slug already exists.",
    )
    parser.add_argument(
        "--lossy",
        action="store_true",
        help="Tolerate color compression (video or JPEG frames).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Measure without connecting to the database or saving the track.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Save the track JSON as it would be ingested to this file.",
    )
    return parser.parse_args()


def build_track_data(
    args: argparse.Namespace,
    profile: DatasetProfile,
    frames_dir: Path,
    pipeline_result: dict[str, Any],
) -> TrackIngestData:
    """Build the track's editorial data from the CLI arguments and profile."""
    source_metadata: dict[str, Any] = {
        "source": profile.source,
        "profile_id": profile.id,
        "topic": profile.topic,
        # Store only the directory name; do not expose the full local path through the API.
        "frames_directory": frames_dir.name,
        "frame_count": len(pipeline_result.get("frames", [])),
    }
    if args.frames_url:
        source_metadata["frames_base_url"] = args.frames_url.rstrip("/")
    if args.frames_ext:
        source_metadata["frames_extension"] = args.frames_ext.lstrip(".").lower()
    return TrackIngestData(
        title=args.title,
        slug=args.slug,
        description=args.description,
        sequence_order=args.sequence_order,
        event_date=args.event_date,
        source_metadata=source_metadata,
    )


def main() -> None:
    """Complete workflow: measure with the engine and ingest into an existing playlist."""
    args = parse_args()
    frames_dir = validate_frames_directory(args.dir)
    profile = lossy(PROFILES[args.profile]) if args.lossy else PROFILES[args.profile]

    print(f"Measuring frames in {frames_dir} with profile {profile.id}...")
    try:
        pipeline_result = measure_timelapse(frames_dir, profile)
    except MLEngineError as exc:
        sys.exit(f"Engine error: {exc}")
    for warning in pipeline_result["dataset_info"]["warnings"]:
        print(f"Engine warning: {warning}")

    track_data = build_track_data(args, profile, frames_dir, pipeline_result)

    if args.out is not None:
        payload = {
            **track_data.model_dump(mode="json"),
            "engine_metadata": pipeline_result["dataset_info"],
            "frames": pipeline_result["frames"],
        }
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print(f"Track JSON saved to {args.out}")

    if args.dry_run:
        print(
            f"Measurement successful: {track_data.source_metadata['frame_count']} frames. "
            "The track was not saved to the database."
        )
        return

    from sqlalchemy.exc import SQLAlchemyError

    from app.core.database import SessionLocal, init_db
    from app.services.ingestion_service import (
        TrackAlreadyExistsError,
        ingest_timelapse_result,
    )
    from app.services.playlist_service import count_playlists, get_playlist_by_slug

    try:
        init_db()
        with SessionLocal() as session:
            if count_playlists(session) == 0:
                sys.exit(
                    "No playlists found. Create at least one with "
                    "python scripts/ingest_playlist.py create ..."
                )
            playlist = get_playlist_by_slug(session, args.playlist_slug)
            if playlist is None:
                sys.exit(
                    f"Playlist not found: {args.playlist_slug}. "
                    "Create the playlist with python scripts/ingest_playlist.py create ..."
                )

            track = ingest_timelapse_result(
                session,
                playlist_id=playlist.id,
                track_data=track_data,
                pipeline_result=pipeline_result,
                replace=args.replace,
            )
    except TrackAlreadyExistsError as exc:
        sys.exit(f"{exc} Use --replace to overwrite it.")
    except SQLAlchemyError as exc:
        sys.exit(f"Database error: {exc}")

    print(f"Track ingested: {track.slug} (id={track.id}, playlist_id={track.playlist_id})")


if __name__ == "__main__":
    main()
