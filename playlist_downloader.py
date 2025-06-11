import os
import subprocess

# Replace with your playlist URL
playlist_url = input("Playlist URL: ")

downloads_dir = "downloads"
output_file = "combined_output.mp4"

# Create downloads directory if it doesn't exist
os.makedirs(downloads_dir, exist_ok=True)

# Download playlist videos using yt-dlp
download_cmd = [
    "yt-dlp",
    "--yes-playlist",
    "-f", "bv*+ba/b",
    "-o", f"{downloads_dir}/video_%(playlist_index)03d.%(ext)s",  # Zero-padded numeric filenames
    playlist_url
]

try:
    subprocess.run(download_cmd, check=True)
except subprocess.CalledProcessError as e:
    print(f"❌ Error downloading videos: {e}")
    exit(1)

# Detect video extension by finding a real file
video_files = sorted([
    f for f in os.listdir(downloads_dir)
    if f.startswith("video_") and f.endswith(".mp4")
])


# Create list.txt for ffmpeg concat (must use absolute paths, properly escaped)
list_path = os.path.join(downloads_dir, "list.txt")
with open(list_path, "w", encoding="utf-8") as f:
    for video in video_files:
        abs_path = os.path.abspath(os.path.join(downloads_dir, video))
        escaped_path = abs_path.replace("'", "'\\''")
        f.write(f"file '{escaped_path}'\n")

# Combine videos using ffmpeg
concat_cmd = [
    "ffmpeg",
    "-f", "concat",
    "-safe", "0",
    "-i", list_path,
    "-c", "copy",
    output_file
]

try:
    subprocess.run(concat_cmd, check=True)
    print(f"✅✅✅ Combined all videos into: {output_file}")
except subprocess.CalledProcessError as e:
    print(f"❌ Error combining videos: {e}")

# Extract combined audio from the merged video
audio_output = "combined_audio.mp3"
extract_audio_cmd = [
    "ffmpeg",
    "-i", "combined_output.mp4",
    "-vn",  # no video
    "-acodec", "libmp3lame",
    "-q:a", "2",  # high-quality VBR MP3
    audio_output
]

try:
    subprocess.run(extract_audio_cmd, check=True)
    print(f"🎧✅ Extracted audio to: {audio_output}")
except subprocess.CalledProcessError as e:
    print(f"❌ Error extracting audio: {e}")
