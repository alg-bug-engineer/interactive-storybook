#!/usr/bin/env python3
"""
Merge and diagnose existing story resources from fixed project directories.

Usage:
  python backend/scripts/merge_existing_story_resources.py --story-id 6b4f3299
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {shlex.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def ffprobe_duration(path: Path) -> Optional[float]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        str(path),
    ]
    proc = run_cmd(cmd, check=False)
    if proc.returncode != 0:
        return None
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def ffmpeg_decode_errors(path: Path) -> list[str]:
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "null",
        "-",
    ]
    proc = run_cmd(cmd, check=False)
    lines = [line.strip() for line in (proc.stderr or "").splitlines() if line.strip()]
    return lines


@dataclass
class SegmentDiagnosis:
    index: int
    clip_path: str
    audio_path: Optional[str]
    clip_duration: Optional[float]
    audio_duration: Optional[float]
    decode_error_count: int
    decode_errors: list[str]
    issues: list[str]
    merged_segment_path: Optional[str]


def normalize_video(input_clip: Path, output_clip: Path) -> None:
    output_clip.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-fflags",
        "+discardcorrupt",
        "-err_detect",
        "ignore_err",
        "-i",
        str(input_clip),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        "scale=1024:1024:force_original_aspect_ratio=decrease,pad=1024:1024:(ow-iw)/2:(oh-ih)/2:black,fps=24",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_clip),
    ]
    run_cmd(cmd, check=True)


def merge_one_segment(
    normalized_clip: Path,
    audio_path: Optional[Path],
    output_segment: Path,
    clip_duration: Optional[float],
    audio_duration: Optional[float],
) -> None:
    output_segment.parent.mkdir(parents=True, exist_ok=True)

    if audio_path and audio_path.exists() and audio_duration:
        if clip_duration is None:
            clip_duration = ffprobe_duration(normalized_clip) or 0.0
        if audio_duration > clip_duration + 0.03:
            pad = max(audio_duration - clip_duration, 0.0)
            filter_complex = f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f},setpts=PTS-STARTPTS[v]"
        elif clip_duration > audio_duration + 0.03:
            filter_complex = f"[0:v]trim=0:{audio_duration:.3f},setpts=PTS-STARTPTS[v]"
        else:
            filter_complex = "[0:v]setpts=PTS-STARTPTS[v]"

        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(normalized_clip),
            "-i",
            str(audio_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "24",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_segment),
        ]
        run_cmd(cmd, check=True)
        return

    # No audio: generate silence track so all segments have uniform streams for concat.
    dur = clip_duration or ffprobe_duration(normalized_clip) or 5.0
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(normalized_clip),
        "-f",
        "lavfi",
        "-t",
        f"{dur:.3f}",
        "-i",
        "anullsrc=channel_layout=mono:sample_rate=24000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_segment),
    ]
    run_cmd(cmd, check=True)


def concat_segments(segments: list[Path], output_path: Path, work_dir: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_list = work_dir / "concat_segments.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in segments) + "\n",
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_cmd(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge existing story clips with diagnosis report.")
    parser.add_argument("--story-id", required=True, help="story id, e.g. 6b4f3299")
    parser.add_argument("--segments-dir", default="", help="override segments dir")
    parser.add_argument("--output", default="", help="final output video path")
    parser.add_argument("--analyze-only", action="store_true", help="only analyze, do not merge")
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ERROR: ffmpeg/ffprobe not found in PATH", file=sys.stderr)
        return 2

    backend_root = Path(__file__).resolve().parents[1]
    if args.segments_dir:
        segments_dir = Path(args.segments_dir).resolve()
    else:
        segments_dir = (backend_root / "storybook_videos" / "segments" / args.story_id).resolve()
    if not segments_dir.exists():
        print(f"ERROR: segments directory not found: {segments_dir}", file=sys.stderr)
        return 2

    output_path = (
        Path(args.output).resolve()
        if args.output
        else (backend_root / "storybook_videos" / f"{args.story_id}_remerged.mp4").resolve()
    )
    work_dir = segments_dir / "_remerge_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    clip_pattern = re.compile(r"^clip_(\d{3})\.mp4$")
    clip_entries: list[tuple[int, Path]] = []
    for p in segments_dir.iterdir():
        m = clip_pattern.match(p.name)
        if not m:
            continue
        clip_entries.append((int(m.group(1)), p))
    clip_entries.sort(key=lambda x: x[0])

    if not clip_entries:
        print(f"ERROR: no clip_XXX.mp4 found in {segments_dir}", file=sys.stderr)
        return 2

    report: list[SegmentDiagnosis] = []
    merged_segments: list[Path] = []

    for idx, clip_path in clip_entries:
        audio_path = segments_dir / f"audio_{idx:03d}.mp3"
        audio_ref = audio_path if audio_path.exists() else None

        clip_duration = ffprobe_duration(clip_path)
        audio_duration = ffprobe_duration(audio_ref) if audio_ref else None
        decode_errors = ffmpeg_decode_errors(clip_path)
        issues: list[str] = []

        if clip_duration is None:
            issues.append("clip_duration_unavailable")
        if decode_errors:
            issues.append("clip_decode_errors")
        if audio_ref is None:
            issues.append("audio_missing")
        elif audio_duration is None:
            issues.append("audio_duration_unavailable")
        elif clip_duration and audio_duration > clip_duration + 0.03:
            issues.append("audio_longer_than_video")
        elif clip_duration and clip_duration > audio_duration + 0.03:
            issues.append("video_longer_than_audio")

        merged_segment_path: Optional[Path] = None
        if not args.analyze_only:
            normalized = work_dir / "normalized" / f"clip_{idx:03d}.mp4"
            merged_segment_path = work_dir / "segments" / f"segment_{idx:03d}.mp4"
            normalize_video(clip_path, normalized)
            merge_one_segment(
                normalized_clip=normalized,
                audio_path=audio_ref,
                output_segment=merged_segment_path,
                clip_duration=clip_duration,
                audio_duration=audio_duration,
            )
            merged_segments.append(merged_segment_path)

        report.append(
            SegmentDiagnosis(
                index=idx,
                clip_path=str(clip_path),
                audio_path=str(audio_ref) if audio_ref else None,
                clip_duration=clip_duration,
                audio_duration=audio_duration,
                decode_error_count=len(decode_errors),
                decode_errors=decode_errors,
                issues=issues,
                merged_segment_path=str(merged_segment_path) if merged_segment_path else None,
            )
        )

    if not args.analyze_only:
        concat_segments(merged_segments, output_path, work_dir)

    report_path = work_dir / "merge_report.json"
    report_path.write_text(
        json.dumps(
            {
                "story_id": args.story_id,
                "segments_dir": str(segments_dir),
                "output_path": str(output_path) if not args.analyze_only else None,
                "segment_count": len(report),
                "segments": [asdict(item) for item in report],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    issue_count = sum(1 for r in report if r.issues)
    print(f"story_id={args.story_id}")
    print(f"segments={len(report)}, segments_with_issues={issue_count}")
    print(f"report={report_path}")
    if not args.analyze_only:
        print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
