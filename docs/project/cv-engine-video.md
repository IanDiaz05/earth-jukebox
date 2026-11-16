# CV engine video extraction

**Source:** `app/cv_engine/video.py`

Some source visualizations are published as video rather than as a folder of
images. This module extracts still frames that the measurement pipeline can
process.

## `extract_frames(video, destination, every=1.0, limit=0)`

- Opens the video with OpenCV.
- Computes a frame step from the video's FPS and the requested interval in
  seconds.
- Saves every selected frame as `frame_0000.png`, `frame_0001.png`, and so on in
  the destination directory, creating it if needed.
- Returns the number of frames saved.

| Argument | Meaning |
|---|---|
| `video` | Video file readable by OpenCV |
| `destination` | Output directory |
| `every` | Seconds between saved frames |
| `limit` | Maximum number of frames; `0` means no limit |

It raises `MLEngineError` when the interval is not positive or the video cannot
be opened.

## Important note

Video frames are compressed. When measuring extracted frames, use the tolerant
profile variant `lossy(profile)` so color matching allows for compression
artifacts.
