import sys
import os
from pathlib import Path

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from moviepy import VideoFileClip

def convert_video_to_gif(input_path, output_path):
    print(f"Converting {input_path} to {output_path}...")
    try:
        clip = VideoFileClip(str(input_path))
        # Resize to width 320 to keep file size reasonable for GIF
        clip = clip.resized(width=320)
        # Write GIF (10fps is usually enough for previews)
        clip.write_gif(str(output_path), fps=10)
        print("Conversion successful!")
        return True
    except Exception as e:
        print(f"Conversion failed: {e}")
        return False

if __name__ == "__main__":
    input_file = Path("/home/code/trai/backend/4S.mp4")
    output_file = Path("/home/code/trai/backend/4S.gif")
    
    if not input_file.exists():
        print(f"Error: Input file {input_file} does not exist.")
    else:
        convert_video_to_gif(input_file, output_file)
