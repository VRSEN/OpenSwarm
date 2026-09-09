"""Tool for adding animated subtitles to videos using OpenAI Whisper API for timing."""

import logging
import os
from typing import Optional, Literal

from pydantic import Field, field_validator

from agency_swarm import BaseTool
from shared_tools.openai_client_utils import get_openai_client
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

from .utils.video_utils import get_videos_dir

logger = logging.getLogger(__name__)


class AddSubtitles(BaseTool):
    """
    Add animated subtitles to a video.
    Uses OpenAI Whisper API to automatically transcribe audio and extract word-level timestamps.
    Subtitles appear word-by-word or phrase-by-phrase with highlighting effect.
    
    Videos are saved to: mnt/{product_name}/generated_videos/
    """

    product_name: str = Field(
        ...,
        description="Name of the product this video is for (e.g., 'Acme_Widget_Pro', 'Green_Tea_Extract'). Used to organize files into product-specific folders.",
    )
    video_name: str = Field(
        ...,
        description="Name of the video file (without extension) to add subtitles to",
    )
    original_script: str = Field(
        ...,
        description="Original script of the video to provide guidance for the subtitles. Should be provided in a single text block, without any formatting.",
    )
    output_name: Optional[str] = Field(
        None,
        description="Output video name (without extension). If not provided, adds '_subtitled' to original name",
    )
    font_size: int = Field(
        default=60,
        description="Font size for subtitles (default: 60, recommended range: 40-80 for vertical videos)",
    )
    position: Literal["center", "bottom", "top"] = Field(
        default="bottom", description="Vertical position of subtitles on screen"
    )
    words_per_clip: int = Field(
        default=6,
        description="Number of words to show per subtitle clip (default: 6, usually 2-6)",
    )
    highlight_color: str = Field(
        default="white",
        description="Color for highlighting text (default: 'yellow', options: 'yellow', 'white', 'cyan', 'green')",
    )

    @field_validator("video_name")
    @classmethod
    def _validate_video_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("video_name must not be empty")
        return value

    @field_validator("font_size")
    @classmethod
    def _validate_font_size(cls, value: int) -> int:
        if value < 20 or value > 120:
            raise ValueError("font_size must be between 20 and 120")
        return value

    @field_validator("words_per_clip")
    @classmethod
    def _validate_words_per_clip(cls, value: int) -> int:
        if value < 1 or value > 10:
            raise ValueError("words_per_clip must be between 1 and 10")
        return value

    def run(self) -> str:
        """Add animated subtitles to the video using Whisper for timing."""
        from moviepy.editor import (  # lazy: avoid SIGILL at import time (see #38)
            CompositeVideoClip,
            ImageClip,
            VideoFileClip,
        )
        import numpy as np  # lazy: avoid native import at agency-construction time

        videos_dir = get_videos_dir(self.product_name)
        video_path = os.path.join(videos_dir, f"{self.video_name}.mp4")

        if not os.path.exists(video_path):
            raise FileNotFoundError(
                f"Video file not found: {video_path}. "
                f"Make sure the video exists in the {videos_dir} directory."
            )

        video = VideoFileClip(video_path)
        video_width, video_height = video.size

        client = get_openai_client(tool=self)

        prompt = (
            "Transcribe the audio of the video into text, make sure to include correct periods and capitalization. "
            "Do not use em dashes, use hyphens instead. "
            f"The original script, use it as a reference to ensure correct spelling: {self.original_script}."
        )

        # Transcribe with word-level timestamps using OpenAI API
        with open(video_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                prompt=prompt,
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["word"],
                temperature=0.0,
            )


        # Extract words with timestamps from API response and add punctuation
        words_with_timing = []

        if hasattr(transcript, "words") and transcript.words:
            # Character replacements for Unicode normalization
            char_replacements = {
                '\u2014': '-',  # Em dash
                '\u2013': '-',  # En dash
                '\u2212': '-',  # Minus sign
                '\u2010': '-',  # Hyphen
                '\u2011': '-',  # Non-breaking hyphen
                '\ufe63': '-',  # Small hyphen-minus
                '\uff0d': '-',  # Fullwidth hyphen-minus
                '\u2019': "'",  # Right single quote
                '\u2018': "'",  # Left single quote
                '\u2032': "'",  # Prime
                '\u2035': "'"   # Reversed prime
            }
            
            # Split full text into words (preserves punctuation)
            full_text_words = transcript.text.split()
            
            # Match API words with full text words to get punctuation
            full_text_idx = 0
            
            for word_info in transcript.words:
                word = word_info.word.strip()
                
                # Try to find matching word in full text (with punctuation)
                final_word = word
                if full_text_idx < len(full_text_words):
                    full_word = full_text_words[full_text_idx]
                    # Check if the word matches (case-insensitive, ignoring punctuation)
                    if word.lower() == full_word.strip('.,!?;:').lower():
                        final_word = full_word  # Use the version with punctuation
                        full_text_idx += 1
                    else:
                        # Try to find it in the next few words
                        for i in range(full_text_idx, min(full_text_idx + 3, len(full_text_words))):
                            if word.lower() == full_text_words[i].strip('.,!?;:').lower():
                                final_word = full_text_words[i]
                                full_text_idx = i + 1
                                break
                
                # Normalize Unicode characters to ASCII equivalents
                for old_char, new_char in char_replacements.items():
                    final_word = final_word.replace(old_char, new_char)
                
                words_with_timing.append(
                    {
                        "word": final_word,
                        "start": word_info.start,
                        "end": word_info.end,
                    }
                )

        if not words_with_timing:
            raise RuntimeError(
                "No words detected in audio. Video may not have speech or audio track."
            )


        chunks = []
        i = 0

        while i < len(words_with_timing):
            chunk_words = []
            words_added = 0

            # Add words until we reach max words_per_clip or hit a sentence ending
            while (
                i + words_added < len(words_with_timing)
                and words_added < self.words_per_clip
            ):
                word_data = words_with_timing[i + words_added]
                chunk_words.append(word_data)
                words_added += 1

                # Check if this word ends a sentence (period, exclamation, question mark)
                word_text = word_data["word"].strip()
                if (
                    word_text.endswith(".")
                    or word_text.endswith("!")
                    or word_text.endswith("?")
                ):
                    # End chunk here
                    break

            # Create chunk with combined text and timing
            if chunk_words:
                chunk = {
                    "text": " ".join([w["word"] for w in chunk_words]),
                    "start": chunk_words[0]["start"],
                    "end": chunk_words[-1]["end"],
                }
                chunks.append(chunk)
                i += words_added
            else:
                # Safety: should never happen, but just in case
                i += 1


        if self.position == "center":
            y_position = "center"
        elif self.position == "bottom":
            y_position = video_height - 400  # 400px from bottom
        else:  # top
            y_position = 150  # 150px from top

        # Color mapping (RGB format for PIL)
        color_map = {
            "yellow": (255, 255, 0),
            "white": (255, 255, 255),
            "cyan": (0, 255, 255),
            "green": (144, 238, 144),
        }
        text_color = color_map.get(self.highlight_color, (255, 255, 0))

        # Helper function to create text image using PIL
        def create_text_image(text, font_size, width, color):
            """Create an image with text using PIL, with automatic line wrapping."""
            # Get the fonts directory relative to this tool file
            tools_dir = os.path.dirname(os.path.abspath(__file__))
            fonts_dir = os.path.join(tools_dir, "utils", "fonts")

            # Montserrat font paths - try multiple variations
            font_paths = [
                os.path.join(fonts_dir, "Montserrat-Bold.ttf"),
                os.path.join(fonts_dir, "Montserrat-SemiBold.ttf"),
                os.path.join(fonts_dir, "Montserrat-Regular.ttf"),
                "C:/Windows/Fonts/Montserrat-Bold.ttf",
                "Montserrat-Bold.ttf",
            ]

            # Try to load Montserrat font
            font = None
            for font_path in font_paths:
                try:
                    font = ImageFont.truetype(font_path, font_size)
                    break
                except Exception:
                    continue

            # Fall back to default if no font loaded
            if font is None:
                font = ImageFont.load_default()

            # Create temporary image to measure text
            temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            # Word wrapping logic
            words = text.split(" ")
            lines = []
            current_line = []

            max_width = width  # Maximum width available for text

            for word in words:
                # Try adding this word to current line
                test_line = " ".join(current_line + [word])
                bbox = temp_draw.textbbox((0, 0), test_line, font=font)
                line_width = bbox[2] - bbox[0]

                if line_width <= max_width:
                    # Word fits, add it to current line
                    current_line.append(word)
                else:
                    # Word doesn't fit, start new line
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                    else:
                        # Single word is too long, add it anyway
                        lines.append(word)

            # Add remaining words
            if current_line:
                lines.append(" ".join(current_line))

            # Calculate dimensions for multi-line text
            padding = 20
            line_height = font_size + 10  # Add some spacing between lines

            # Get max line width
            max_line_width = 0
            for line in lines:
                bbox = temp_draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                max_line_width = max(max_line_width, line_width)

            img_width = max_line_width + padding * 2
            img_height = len(lines) * line_height + padding * 2

            # Create actual image with transparent background
            img = Image.new("RGBA", (img_width, img_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Draw each line of text
            stroke_width = 6
            y_offset = padding

            for line in lines:
                # Get line width for centering
                bbox = draw.textbbox((0, 0), line, font=font)
                line_width = bbox[2] - bbox[0]
                x = (img_width - line_width) // 2

                # Draw stroke (outline)
                for offset_x in range(-stroke_width, stroke_width + 1):
                    for offset_y in range(-stroke_width, stroke_width + 1):
                        draw.text(
                            (x + offset_x, y_offset + offset_y),
                            line,
                            font=font,
                            fill=(0, 0, 0, 255),
                        )

                # Draw main text
                draw.text((x, y_offset), line, font=font, fill=(*color, 255))

                # Move to next line
                y_offset += line_height

            return np.array(img)

        subtitle_clips = []

        for i, chunk in enumerate(chunks):
            # Bold, uppercase for visibility
            text = chunk["text"].upper()
            start_time = chunk["start"]
            duration = chunk["end"] - chunk["start"]

            try:
                # Create text image using PIL
                text_img = create_text_image(
                    text, self.font_size, video_width - 100, text_color
                )

                # Create ImageClip from the text image
                txt_clip = ImageClip(text_img)

                # Position and time the clip
                txt_clip = txt_clip.set_position(("center", y_position))
                txt_clip = txt_clip.set_start(start_time)
                txt_clip = txt_clip.set_duration(duration)

                subtitle_clips.append(txt_clip)

            except Exception:
                continue
        final_video = CompositeVideoClip([video] + subtitle_clips)
        final_video = final_video.set_duration(video.duration)
        final_video = final_video.set_audio(video.audio)

        if self.output_name:
            output_name = self.output_name
        else:
            output_name = f"{self.video_name}_subtitled"

        output_path = os.path.join(videos_dir, f"{output_name}.mp4")

        try:
            final_video.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile="temp-audio.m4a",
                remove_temp=True,
                logger=None,
                fps=video.fps,
            )
        finally:
            # Clean up
            video.close()
            final_video.close()
            for clip in subtitle_clips:
                try:
                    clip.close()
                except Exception:
                    pass

        return (
            f"Successfully added animated subtitles to {self.video_name}.mp4\n\n"
            f"Output: {output_name}.mp4\n"
            f"Path: {output_path}\n\n"
            f"Details:\n"
            f"  - Duration: {video.duration:.1f} seconds\n"
            f"  - Subtitle chunks: {len(subtitle_clips)}\n"
            f"  - Style: {self.highlight_color.upper()} text, {self.words_per_clip} words per clip\n"
            f"  - Transcribed: {transcript.text[:200]}..."
        )

if __name__ == "__main__":
    # Test case
    tool = AddSubtitles(
        product_name="Test_Product",
        video_name="herbaluxe_ad_v3",
        original_script="Does your moisturizer still smell like perfume? Mine did, and my skin hated it. So I switched to HerbaLuxe—an aloe‑first daily moisturizer made with organic ingredients. It's fragrance‑free, with no essential oils and a minimal formula. First swipe feels cool and soothing. Sinks in fast—no stickiness. Layers clean under sunscreen. Skin feels calm, not coated. herbaluxe-cosmetics.com",
        words_per_clip=4,
        position="bottom",
        highlight_color="white",
        font_size=60,
    )
    result = tool.run()
    print(result)
