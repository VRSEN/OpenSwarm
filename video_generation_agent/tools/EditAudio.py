"""Tool for combining audio from one video with visuals from another video."""

import os
import subprocess
import asyncio
from typing import Optional
from pathlib import Path

from pydantic import Field, field_validator
from PIL import Image

from agency_swarm import BaseTool, ToolOutputText

from .utils.video_utils import (
    get_videos_dir,
    ensure_not_blank,
    generate_spritesheet,
    extract_last_frame,
    create_image_output,
    resolve_ffmpeg_executable,
)


class EditAudio(BaseTool):
    """
    Combine audio from one video with visuals from another video.
    
    Useful for adding b-roll footage over narration, or replacing visuals while keeping original audio.
    Supports padding to offset video timing relative to audio.
    
    Videos are saved to: mnt/{product_name}/generated_videos/
    """
    
    product_name: str = Field(
        ...,
        description="Name of the product this video is for (e.g., 'Acme_Widget_Pro', 'Green_Tea_Extract'). Used to organize files into product-specific folders.",
    )
    audio_source: str = Field(
        ...,
        description=(
            "The video to extract audio from. Can be: "
            "1) Video name without extension (searches generated_videos folder), "
            "2) Full local path to video file."
        ),
    )
    video_source: str = Field(
        ...,
        description=(
            "The video to use for visuals/b-roll. Can be: "
            "1) Video name without extension (searches generated_videos folder), "
            "2) Full local path to video file."
        ),
    )
    output_name: str = Field(
        ...,
        description="The name for the combined video file (without extension)",
    )
    pad_seconds: float = Field(
        default=0.0,
        description=(
            "Seconds to offset the video relative to audio. "
            "Negative = video starts before audio (e.g., -2.0 = video plays 2s before audio), "
            "Positive = video starts after audio (e.g., 2.0 = video plays 2s after audio starts), "
            "Zero = video and audio start together (default: 0.0)"
        ),
    )
    
    @field_validator("audio_source")
    @classmethod
    def _audio_not_blank(cls, value: str) -> str:
        return ensure_not_blank(value, "audio_source")
    
    @field_validator("video_source")
    @classmethod
    def _video_not_blank(cls, value: str) -> str:
        return ensure_not_blank(value, "video_source")
    
    @field_validator("output_name")
    @classmethod
    def _output_not_blank(cls, value: str) -> str:
        return ensure_not_blank(value, "output_name")
    
    async def run(self) -> list:
        """Mix audio and video from two different sources."""
        audio_path = self._resolve_video_path(self.audio_source)
        video_path = self._resolve_video_path(self.video_source)

        videos_dir = get_videos_dir(self.product_name)
        output_path = os.path.join(videos_dir, f"{self.output_name}.mp4")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._mix_audio_video_blocking, audio_path, video_path, output_path)

        output = []

        spritesheet_path = os.path.join(videos_dir, f"{self.output_name}_spritesheet.jpg")
        spritesheet = await loop.run_in_executor(None, generate_spritesheet, output_path, spritesheet_path)
        if spritesheet:
            output.extend(create_image_output(spritesheet_path, f"{self.output_name}_spritesheet.jpg"))

        thumbnail_path = os.path.join(videos_dir, f"{self.output_name}_thumbnail.jpg")
        thumbnail = await loop.run_in_executor(None, self._extract_first_frame, output_path, thumbnail_path)
        if thumbnail:
            output.extend(create_image_output(thumbnail_path, f"{self.output_name}_thumbnail.jpg"))

        last_frame_path = os.path.join(videos_dir, f"{self.output_name}_last_frame.jpg")
        last_frame = await loop.run_in_executor(None, extract_last_frame, output_path, last_frame_path)
        if last_frame:
            output.extend(create_image_output(last_frame_path, f"{self.output_name}_last_frame.jpg"))

        pad_info = ""
        if self.pad_seconds != 0.0:
            if self.pad_seconds < 0:
                pad_info = f"\nPadding: Video starts {abs(self.pad_seconds)}s before audio"
            else:
                pad_info = f"\nPadding: Video starts {self.pad_seconds}s after audio"
        
        output.append(ToolOutputText(
            type="text",
            text=f"Audio and video mixed successfully!\nSaved to: `{self.output_name}.mp4`\nPath: {output_path}{pad_info}"
        ))
        
        return output
    
    def _resolve_video_path(self, video_ref: str) -> str:
        """Resolve video reference to full path."""
        # Try as full path first
        path = Path(video_ref).expanduser().resolve()
        
        if path.exists():
            return str(path)
        
        # Try as video name without extension in generated_videos
        videos_dir = get_videos_dir(self.product_name)
        
        for ext in [".mp4", ".mov", ".avi", ".webm"]:
            potential_path = os.path.join(videos_dir, f"{video_ref}{ext}")
            if os.path.exists(potential_path):
                return potential_path
        
        raise FileNotFoundError(
            f"Video '{video_ref}' not found in {videos_dir}. "
            f"Tried extensions: .mp4, .mov, .avi, .webm"
        )
    
    def _mix_audio_video_blocking(self, audio_path: str, video_path: str, output_path: str) -> None:
        """Mix audio and video using ffmpeg (blocking operation)."""
        import cv2  # lazy: avoid SIGILL at import/agency-construction time (see #38)

        cap_audio = cv2.VideoCapture(audio_path)
        fps_audio = cap_audio.get(cv2.CAP_PROP_FPS)
        frames_audio = int(cap_audio.get(cv2.CAP_PROP_FRAME_COUNT))
        audio_duration = frames_audio / fps_audio if fps_audio > 0 else 0
        cap_audio.release()
        
        cap_video = cv2.VideoCapture(video_path)
        fps_video = cap_video.get(cv2.CAP_PROP_FPS)
        frames_video = int(cap_video.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frames_video / fps_video if fps_video > 0 else 0
        cap_video.release()

        ffmpeg_executable = resolve_ffmpeg_executable()
        
        if self.pad_seconds == 0.0:
            # Simple case: no padding, just combine audio and video
            ffmpeg_cmd = [
                ffmpeg_executable,
                "-y",  # Overwrite output file
                "-i", video_path,  # Input 0: video source
                "-i", audio_path,  # Input 1: audio source
                "-map", "0:v:0",  # Use video from input 0
                "-map", "1:a:0",  # Use audio from input 1
                "-c:v", "libx264",  # Video codec
                "-preset", "medium",
                "-crf", "23",
                "-c:a", "aac",  # Audio codec
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-pix_fmt", "yuv420p",
                "-t", str(video_duration),  # Use video duration as master timeline
                output_path
            ]
        else:
            # Complex case: apply padding offset
            # Negative pad = delay audio (video starts first)
            # Positive pad = delay video (audio starts first)
            
            if self.pad_seconds < 0:
                # Video starts before audio - delay audio track
                audio_delay = abs(self.pad_seconds)
                ffmpeg_cmd = [
                    ffmpeg_executable,
                    "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-filter_complex",
                    f"[1:a]adelay={int(audio_delay * 1000)}|{int(audio_delay * 1000)}[a]",  # Delay audio in milliseconds
                    "-map", "0:v:0",
                    "-map", "[a]",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-pix_fmt", "yuv420p",
                    "-t", str(video_duration),  # Use video duration as master timeline
                    output_path
                ]
            else:
                # Audio starts before video - delay video track
                video_delay = self.pad_seconds
                ffmpeg_cmd = [
                    ffmpeg_executable,
                    "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-filter_complex",
                    f"[0:v]setpts=PTS+{video_delay}/TB[v]",  # Delay video
                    "-map", "[v]",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-movflags", "+faststart",
                    "-pix_fmt", "yuv420p",
                    "-t", str(video_duration),  # Use video duration as master timeline
                    output_path
                ]
        
        try:
            subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"ffmpeg failed to mix audio and video. Error: {e.stderr}"
            )
        except FileNotFoundError:
            raise RuntimeError(
                "ffmpeg not found. Please install ffmpeg and ensure it's in your PATH. "
                "Download from: https://ffmpeg.org/download.html"
            )
    
    def _extract_first_frame(self, video_path: str, output_path: str) -> Optional[object]:
        """Extract the first frame from video as thumbnail."""
        import cv2  # lazy: avoid SIGILL at import/agency-construction time (see #38)

        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            return None
        
        # Convert BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        thumbnail_image = Image.fromarray(frame_rgb)
        thumbnail_image.save(output_path)
        
        return thumbnail_image


if __name__ == "__main__":
    # Check if test videos exist
    test_dir = Path(__file__).parent.parent.parent / "mnt" / "Test_Product" / "generated_videos"
    video1 = test_dir / "test_video.mp4"
    video2 = test_dir / "test_video_trimmed_last2s.mp4"
    
    if not video1.exists() or not video2.exists():
        print("Test videos not found. Skipping test.")
        print(f"Expected: {video1}")
        print(f"Expected: {video2}")
    else:
        # Example: Combine audio from one video with b-roll from another
        # Audio is 4s, b-roll is 26.8s - b-roll continues after audio ends
        # Video starts 5 seconds after audio (audio pre-roll)
        tool = EditAudio(
            product_name="Test_Product",
            audio_source="test_video",  # Audio from this video (4s)
            video_source="Ad2_3seg_AI_Employee_UGC_final",  # Visuals from this video (26.8s)
            output_name="mixed_video",
            pad_seconds=-3.0,  # Video starts 5 seconds after audio begins
        )
        
        try:
            result = asyncio.run(tool.run())
            print("\nMix complete!")
            for item in result:
                if hasattr(item, 'text'):
                    print(item.text)
        except Exception as exc:
            print(f"Audio/video mixing failed: {exc}")

