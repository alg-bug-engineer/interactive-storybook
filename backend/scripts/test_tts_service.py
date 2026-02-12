#!/usr/bin/env python3
"""
Standalone TTS smoke/regression test script.

Covers:
1) Official demo import path: apis/tts/binary.py
2) Volcano service wrapper: app.services.volcano_tts_service
3) Unified service + concurrent de-dup: app.services.tts_generation_service

Examples:
  python backend/scripts/test_tts_service.py --mode segment-concurrent --paid --concurrency 3 --clean
  python backend/scripts/test_tts_service.py --mode volcano --voice-id zh_male_beijingxiaoye_moon_bigtts
  python backend/scripts/test_tts_service.py --mode demo --output /tmp/demo.mp3
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
BACKEND_ROOT = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[2]


def _load_demo_binary_module():
    binary_path = PROJECT_ROOT / "apis" / "tts" / "binary.py"
    if not binary_path.exists():
        raise FileNotFoundError(f"Missing demo file: {binary_path}")
    spec = importlib.util.spec_from_file_location("tts_demo_binary", binary_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load demo file: {binary_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@dataclass
class WorkerResult:
    worker: int
    ok: bool
    elapsed: float
    value: str


def _build_user(is_paid: bool, email: str) -> dict[str, Any] | None:
    if not email and not is_paid:
        return None
    return {
        "email": email or "anonymous@example.com",
        "is_paid": bool(is_paid),
    }


async def run_demo_mode(args: argparse.Namespace) -> None:
    module = _load_demo_binary_module()
    appid = args.appid
    token = args.access_token
    if not appid or not token:
        raise ValueError("demo mode requires --appid and --access-token")

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.clean and output_path.exists():
        output_path.unlink()

    start = time.perf_counter()
    result = await module.synthesize_audio_to_file(
        appid=appid,
        access_token=token,
        voice_type=args.voice_id,
        text=args.text,
        output_path=str(output_path),
        cluster=args.cluster or "",
        encoding=args.encoding,
        endpoint=args.endpoint,
        proxy=None,
        open_timeout=args.open_timeout,
        recv_timeout=args.recv_timeout,
    )
    elapsed = time.perf_counter() - start
    size = output_path.stat().st_size if output_path.exists() else 0
    print(f"[demo] ok elapsed={elapsed:.2f}s size={size} bytes path={output_path}")
    print(f"[demo] chunk_count={result.get('chunk_count')} logid={result.get('logid')}")


async def run_volcano_mode(args: argparse.Namespace) -> None:
    import sys

    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    from app.services.volcano_tts_service import generate_tts_audio_volcano

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if args.clean and output_path.exists():
        output_path.unlink()

    start = time.perf_counter()
    await generate_tts_audio_volcano(
        text=args.text,
        output_path=str(output_path),
        voice_id=args.voice_id,
        max_retries=args.max_retries,
    )
    elapsed = time.perf_counter() - start
    size = output_path.stat().st_size if output_path.exists() else 0
    print(f"[volcano] ok elapsed={elapsed:.2f}s size={size} bytes path={output_path}")


async def run_segment_once_mode(args: argparse.Namespace) -> None:
    import sys

    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    from app.services.tts_generation_service import generate_segment_tts
    from app.services.volcano_tts_service import get_volcano_tts_audio_path
    from app.services.tts_service import get_tts_audio_path

    user = _build_user(args.paid, args.user_email)
    if args.paid:
        target = get_volcano_tts_audio_path(args.story_id, args.segment_index, args.voice_id)
    else:
        target = get_tts_audio_path(args.story_id, args.segment_index, args.voice_id)
    if args.clean and target.exists():
        target.unlink()

    start = time.perf_counter()
    relative_path = await generate_segment_tts(
        story_id=args.story_id,
        segment_index=args.segment_index,
        text=args.text,
        voice_id=args.voice_id,
        speed=args.speed,
        user=user,
    )
    elapsed = time.perf_counter() - start
    print(f"[segment] ok elapsed={elapsed:.2f}s relative_path={relative_path}")
    print(f"[segment] file={target} exists={target.exists()} size={(target.stat().st_size if target.exists() else 0)}")


async def run_segment_concurrent_mode(args: argparse.Namespace) -> None:
    import sys

    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))

    import app.services.tts_generation_service as tgs
    from app.services.volcano_tts_service import get_volcano_tts_audio_path
    from app.services.tts_service import get_tts_audio_path

    user = _build_user(args.paid, args.user_email)
    if args.paid:
        target = get_volcano_tts_audio_path(args.story_id, args.segment_index, args.voice_id)
    else:
        target = get_tts_audio_path(args.story_id, args.segment_index, args.voice_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    if args.clean and target.exists():
        target.unlink()

    # Count underlying generator calls to verify de-dup behavior.
    invoke_count = {"n": 0}
    if args.paid:
        original = tgs.generate_tts_audio_volcano

        async def wrapped(*a, **kw):
            invoke_count["n"] += 1
            return await original(*a, **kw)

        tgs.generate_tts_audio_volcano = wrapped
    else:
        original = tgs.generate_tts_edge

        async def wrapped(*a, **kw):
            invoke_count["n"] += 1
            return await original(*a, **kw)

        tgs.generate_tts_edge = wrapped

    gate = asyncio.Event()

    async def worker(i: int) -> WorkerResult:
        await gate.wait()
        t0 = time.perf_counter()
        try:
            rel = await tgs.generate_segment_tts(
                story_id=args.story_id,
                segment_index=args.segment_index,
                text=args.text,
                voice_id=args.voice_id,
                speed=args.speed,
                user=user,
            )
            return WorkerResult(worker=i, ok=True, elapsed=time.perf_counter() - t0, value=rel)
        except Exception as e:
            return WorkerResult(worker=i, ok=False, elapsed=time.perf_counter() - t0, value=f"{type(e).__name__}: {e}")

    tasks = [asyncio.create_task(worker(i)) for i in range(args.concurrency)]
    start = time.perf_counter()
    gate.set()
    results = await asyncio.gather(*tasks)
    total = time.perf_counter() - start

    # Restore monkey patch.
    if args.paid:
        tgs.generate_tts_audio_volcano = original
    else:
        tgs.generate_tts_edge = original

    ok_count = sum(1 for r in results if r.ok)
    err_count = len(results) - ok_count
    unique_values = sorted({r.value for r in results if r.ok})
    print(f"[segment-concurrent] workers={len(results)} ok={ok_count} err={err_count} total_elapsed={total:.2f}s")
    print(f"[segment-concurrent] underlying_invoke_count={invoke_count['n']}")
    print(f"[segment-concurrent] target={target} exists={target.exists()} size={(target.stat().st_size if target.exists() else 0)}")
    for r in sorted(results, key=lambda x: x.worker):
        print(f"  - worker={r.worker} ok={r.ok} elapsed={r.elapsed:.2f}s value={r.value}")
    if unique_values:
        print(f"[segment-concurrent] unique_relative_paths={unique_values}")
    if invoke_count["n"] > 1:
        print("[segment-concurrent] WARN: underlying generation invoked more than once.")
        print("  this usually means first generation failed, then later workers retried after lock release.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone TTS test script")
    parser.add_argument(
        "--mode",
        choices=["demo", "volcano", "segment", "segment-concurrent"],
        default="segment-concurrent",
        help="test mode",
    )
    parser.add_argument("--text", default="雨停了，山谷像被洗亮的宝石。", help="tts text")
    parser.add_argument("--voice-id", default="zh_male_beijingxiaoye_moon_bigtts", help="voice id")
    parser.add_argument("--speed", type=float, default=1.0, help="playback speed for segment mode")
    parser.add_argument("--story-id", default="tts_smoke_story", help="story id for segment mode")
    parser.add_argument("--segment-index", type=int, default=0, help="segment index for segment mode")
    parser.add_argument("--concurrency", type=int, default=3, help="worker count for segment-concurrent")
    parser.add_argument("--paid", action="store_true", help="use paid user tier")
    parser.add_argument("--user-email", default="test@example.com", help="user email")
    parser.add_argument("--clean", action="store_true", help="remove target cache file before run")
    parser.add_argument("--max-retries", type=int, default=3, help="retries for volcano mode")

    parser.add_argument(
        "--output",
        default=str((BACKEND_ROOT / "data" / "audio" / "volcano_tts" / "_tts_service_test.mp3").resolve()),
        help="output file path for demo/volcano mode",
    )
    parser.add_argument("--appid", default="", help="volcano appid (demo mode)")
    parser.add_argument("--access-token", default="", help="volcano access token (demo mode)")
    parser.add_argument("--cluster", default="", help="cluster override (demo mode)")
    parser.add_argument("--encoding", default="mp3", help="audio encoding for demo mode")
    parser.add_argument("--endpoint", default="wss://openspeech.bytedance.com/api/v1/tts/ws_binary", help="ws endpoint")
    parser.add_argument("--open-timeout", type=float, default=30.0, help="ws open timeout seconds")
    parser.add_argument("--recv-timeout", type=float, default=30.0, help="ws receive timeout seconds")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    print(f"[tts-test] mode={args.mode}")

    try:
        if args.mode == "demo":
            await run_demo_mode(args)
        elif args.mode == "volcano":
            await run_volcano_mode(args)
        elif args.mode == "segment":
            await run_segment_once_mode(args)
        else:
            await run_segment_concurrent_mode(args)
        print("[tts-test] done")
        return 0
    except Exception as e:
        print(f"[tts-test] failed: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
