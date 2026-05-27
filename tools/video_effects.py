import os
import sys
import time
import shutil
import logging
import subprocess
from pathlib import Path

# Add project root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Configure logger
logger = logging.getLogger(__name__)


def format_srt_time(seconds: float) -> str:
    """Format seconds into SRT timestamp format: HH:MM:SS,mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1
        ms = 0
    if s >= 60:
        m += 1
        s = 0
    if m >= 60:
        h += 1
        m = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def get_obj_val(obj, key, default=0.0):
    """Safely get value from object attribute or dictionary key"""
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def generate_srt(segments: list, srt_path: Path, start_sec: float, end_sec: float) -> bool:
    """
    Generate an SRT file matching only the segments within start_sec and end_sec.
    Timestamps are offset so they start at 0 relative to the clip start.
    """
    try:
        lines = []
        idx = 1
        for seg in segments:
            seg_start = get_obj_val(seg, "start", get_obj_val(seg, "start_sec", 0.0))
            seg_end = get_obj_val(seg, "end", get_obj_val(seg, "end_sec", 0.0))
            text = str(get_obj_val(seg, "text", "")).strip()

            # Filter segments overlapping with our clip segment
            overlap_start = max(seg_start, start_sec)
            overlap_end = min(seg_end, end_sec)

            if overlap_start < overlap_end:
                # Calculate relative timestamps for the clip
                rel_start = overlap_start - start_sec
                rel_end = overlap_end - start_sec

                lines.append(str(idx))
                lines.append(f"{format_srt_time(rel_start)} --> {format_srt_time(rel_end)}")
                lines.append(text)
                lines.append("")
                idx += 1

        if not lines:
            # Fallback if no specific overlapping segments found
            lines.append("1")
            lines.append("00:00:00,000 --> 00:00:05,000")
            lines.append("Klip Video Pilihan")
            lines.append("")

        srt_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Berhasil menghasilkan file subtitle SRT: {srt_path}")
        return True
    except Exception as e:
        logger.error(f"Gagal menghasilkan file SRT: {e}", exc_info=True)
        return False


def track_face_and_reframe(
    video_path: Path,
    output_path: Path,
    start_sec: float,
    end_sec: float,
    srt_path: Path | None = None
) -> bool:
    """
    Perform facial detection & dynamic 9:16 cropping on the source video.
    Aligns speaker's face to the center smoothly, burns subtitles, and merges audio IN A SINGLE FFmpeg pass!
    Optimized detection speed using N=10 and 30% downscaling.
    """
    import cv2
    import numpy as np
    from app.config import settings

    try:
        logger.info(f"Mulai mendeteksi wajah & memotong video dinamis untuk: {video_path}")
        
        # 1. Open source video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Gagal membuka file video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0
            
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Output sizes
        export_w = settings.export_width  # 1080
        export_h = settings.export_height # 1920
        
        # Crop parameters
        target_h = orig_h
        target_w = int(round(target_h * 9 / 16))
        if target_w % 2 != 0:
            target_w += 1
            
        # Ensure target_w is not larger than original width
        if target_w > orig_w:
            target_w = orig_w

        # 2. Determine frame range
        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)

        # 3. Load Haar Cascade detector
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            raise RuntimeError("Gagal memuat Haar Cascade Face Detector.")

        # 4. First pass: Detect faces every N=10 frames (3x faster than N=5)
        N = 10
        detected_xs = {}
        last_known_x = orig_w / 2  # Default to absolute center

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame

        while current_frame <= end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            if (current_frame - start_frame) % N == 0:
                # Downscale heavily (30% scale) for ultra-speedy CPU scanning
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (0, 0), fx=0.3, fy=0.3)
                
                faces = face_cascade.detectMultiScale(
                    small,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(20, 20)
                )

                if len(faces) > 0:
                    # Choose the largest face (closest to camera)
                    largest = max(faces, key=lambda rect: rect[2] * rect[3])
                    fx, fy, fw, fh = largest
                    # Scale coordinates back up (1 / 0.3 = 3.333)
                    face_center_x = (fx + fw / 2) * 3.333
                    last_known_x = face_center_x

                detected_xs[current_frame] = last_known_x

            current_frame += 1

        # Fill in and interpolate X coordinates for every frame
        full_xs = []
        current_frame = start_frame
        while current_frame <= end_frame:
            if current_frame in detected_xs:
                last_known_x = detected_xs[current_frame]
            full_xs.append(last_known_x)
            current_frame += 1

        # Smooth coordinates using moving average (sliding window) to look like smooth camera pan
        window_size = int(1.5 * fps)
        if window_size % 2 == 0:
            window_size += 1
        if window_size < 3:
            window_size = 3

        smoothed_xs = np.convolve(full_xs, np.ones(window_size) / window_size, mode='same')

        # Fix borders padding
        half = window_size // 2
        for i in range(half):
            smoothed_xs[i] = full_xs[i]
            if len(smoothed_xs) > i:
                smoothed_xs[-i-1] = full_xs[-i-1]

        # 5. Crop, resize, and write silent video
        temp_silent = output_path.parent / f"silent_{output_path.name}"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(temp_silent), fourcc, fps, (export_w, export_h))

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame
        idx = 0

        while current_frame <= end_frame and idx < len(smoothed_xs):
            ret, frame = cap.read()
            if not ret:
                break

            center_x = smoothed_xs[idx]
            x_start = int(center_x - target_w / 2)
            x_end = x_start + target_w

            # Clamp boundaries
            if x_start < 0:
                x_start = 0
                x_end = target_w
            elif x_end > orig_w:
                x_end = orig_w
                x_start = orig_w - target_w

            # Perform Crop & Resize
            cropped = frame[0:orig_h, x_start:x_end]
            resized = cv2.resize(cropped, (export_w, export_h), interpolation=cv2.INTER_LANCZOS4)
            writer.write(resized)

            current_frame += 1
            idx += 1

        cap.release()
        writer.release()

        # 6. SINGLE PASS FFmpeg: Merge original audio + dynamic crop video + burn subtitles!
        logger.info("Menggabungkan audio dan membakar subtitle dalam SATU perintah FFmpeg tunggal...")
        
        duration = end_sec - start_sec
        local_srt = None
        
        # Prepare filters
        filters = []
        if srt_path and srt_path.exists():
            # Copy to local directory to solve Windows path escaping bugs in FFmpeg
            local_srt = Path.cwd() / f"local_single_sub_{output_path.name}.srt"
            shutil.copy2(srt_path, local_srt)
            
            style = (
                "Alignment=2,FontName=Impact,FontSize=20,"
                "PrimaryColour=&H00FFFF,Outline=3,Shadow=0,"
                "MarginV=120"
            )
            filters.append(f"subtitles={local_srt.name}:force_style='{style}'")
            
        # Build command
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_sec),
            "-t", str(duration),
            "-i", str(video_path),           # Input 0: original audio
            "-i", str(temp_silent),          # Input 1: vertical cropped video
        ]
        
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
            
        cmd.extend([
            "-map", "1:v:0",                  # Map video from dynamic cropped source
            "-map", "0:a:0?",                 # Map audio from original source (optional)
            "-c:v", "libx264",
            "-preset", settings.export_video_preset,
            "-crf", str(settings.export_video_crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", settings.export_audio_bitrate,
            "-movflags", "+faststart",
            str(output_path)
        ])
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg single pass failed: {res.stderr[-500:]}")
        finally:
            # Clean up temporary files
            if temp_silent.exists():
                temp_silent.unlink()
            if local_srt and local_srt.exists():
                local_srt.unlink()
            
        logger.info(f"Smart Face Tracking & Subtitle (Single Pass) berhasil diselesaikan! Output: {output_path}")
        return True

    except Exception as e:
        logger.exception("Error di track_face_and_reframe")
        return False
