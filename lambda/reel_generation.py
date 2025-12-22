from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image
import numpy as np
import os
from pathlib import Path
import subprocess


def test():
    try:
        out = subprocess.check_output(
            ["ffmpeg", "-version"],
            stderr=subprocess.STDOUT
        ).decode()
        print("FFMPEG OK:", out.splitlines()[0])
    except Exception as e:
        print("FFMPEG FAILED:", e)


def transform_image(image_path, scale=1.0, rotation=0, opacity=1.0):
    """
    Load and transform an image with scaling, rotation, and opacity.
    
    Args:
        image_path: Path to the image file
        scale: Scaling factor (1.0 = original size)
        rotation: Rotation angle in degrees
        opacity: Opacity from 0.0 to 1.0
    
    Returns:
        PIL Image object with transformations applied
    """
    # Load image
    img = Image.open(image_path).convert("RGBA")
    
    # Apply scaling
    if scale != 1.0:
        new_size = (int(img.width * scale), int(img.height * scale))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Apply rotation
    if rotation != 0:
        img = img.rotate(-rotation, expand=True, fillcolor=(0, 0, 0, 0))
    
    # Apply opacity
    if opacity < 1.0:
        alpha = img.split()[3]
        alpha = alpha.point(lambda p: int(p * opacity))
        img.putalpha(alpha)
    
    return img


def get_position(position, video_size, image_size):
    """
    Calculate the actual position coordinates.
    
    Args:
        position: Can be 'center', (x, y) tuple, or a function
        video_size: (width, height) of the video
        image_size: (width, height) of the image
    
    Returns:
        (x, y) tuple for the position
    """
    if position == "center":
        return ("center", "center")
    elif callable(position):
        return position(video_size, image_size)
    else:
        return position
\
def save_output():
    pass
# overlay: {[\"start_time\": 1, \"duration\": 1], [\"start_time\": 3, \"duration\": 1]}
def overlay_images_on_video(video_path, overlays, output_path):

    test()
    """
    Overlay multiple images on a video at specific timestamps with transformations.
    
    Args:
        video_path: Path to input video
        overlays: List of overlay configurations
        output_path: Path to save output video
    """
    # Load the video
    print(f"Loading video: {video_path}")
    video = VideoFileClip(video_path)
    video_duration = video.duration
    video_size = (video.w, video.h)
    
    print(f"Video loaded: {video_size[0]}x{video_size[1]}, duration: {video_duration:.2f}s")
    
    # Prepare overlay clips
    overlay_clips = []
    
    for i, overlay_config in enumerate(overlays):
        image_path = overlay_config["image_path"]
        
        start_time = overlay_config["start_time"]
        duration = overlay_config["duration"]
        end_time = start_time + duration
        scale = overlay_config.get("scale", 1.0)
        rotation = overlay_config.get("rotation", 0)
        opacity = overlay_config.get("opacity", 1.0)
        position = overlay_config.get("position", "center")
        width = overlay_config.get("width", None)
        height = overlay_config.get("height", None)
        
        # Check if overlay is within video duration
        if start_time >= video_duration:
            print(f"Warning: Overlay {i+1} starts after video ends, skipping...")
            continue
        
        # Handle special "WHITE_FRAME" case
        if image_path == "WHITE_FRAME":
            print(f"\nProcessing overlay {i+1}:")
            print(f"  Image: WHITE_FRAME (generating white image)")
            print(f"  Time: {start_time:.2f}s - {end_time:.2f}s ({duration:.2f}s)")
            
            # Calculate dimensions
            if width is not None:
                if width <= 1.0:
                    img_width = int(video_size[0] * width)
                else:
                    img_width = int(width)
            else:
                img_width = video_size[0]
                
            if height is not None:
                if height <= 1.0:
                    img_height = int(video_size[1] * height)
                else:
                    img_height = int(height)
            else:
                img_height = video_size[1]
            
            # Create white image with RGBA (white with full opacity)
            white_img = Image.new("RGBA", (img_width, img_height), (255, 255, 255, int(255 * opacity)))
            
            # Apply rotation if needed
            if rotation != 0:
                white_img = white_img.rotate(-rotation, expand=True, fillcolor=(0, 0, 0, 0))
            
            # Convert PIL image to numpy array
            img_array = np.array(white_img)
            
        else:
            # Check if image exists
            if not os.path.exists(image_path):
                print(f"Warning: Image {i+1} not found at {image_path}, skipping...")
                continue
            
            print(f"\nProcessing overlay {i+1}:")
            print(f"  Image: {image_path}")
            print(f"  Time: {start_time:.2f}s - {end_time:.2f}s ({duration:.2f}s)")
            print(f"  Scale: {scale}, Rotation: {rotation}°, Opacity: {opacity}")
            
            # Transform the image
            transformed_img = transform_image(image_path, scale=scale, rotation=rotation, opacity=opacity)
            
            # Apply width/height if specified (override scale)
            if width is not None or height is not None:
                current_w, current_h = transformed_img.size
                
                if width is not None:
                    if width <= 1.0:
                        new_width = int(video_size[0] * width)
                    else:
                        new_width = int(width)
                else:
                    new_width = current_w
                    
                if height is not None:
                    if height <= 1.0:
                        new_height = int(video_size[1] * height)
                    else:
                        new_height = int(height)
                else:
                    new_height = current_h
                
                transformed_img = transformed_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert PIL image to numpy array
            img_array = np.array(transformed_img)
        
        # Create ImageClip from the transformed image
        # In moviepy 2.x, duration is set in constructor, and use with_* methods instead of set_*
        img_clip = ImageClip(img_array, duration=duration)
        img_clip = img_clip.with_start(start_time)
        
        # Set position
        pos = get_position(position, video_size, (img_array.shape[1], img_array.shape[0]))
        img_clip = img_clip.with_position(pos)
        
        overlay_clips.append(img_clip)
        print(f"  ✓ Overlay {i+1} prepared")
    
    # Composite all clips
    print(f"\nCompositing {len(overlay_clips)} overlays on video...")
    final_video = CompositeVideoClip([video] + overlay_clips)
    
    # Write the output video
    print(f"\nWriting output video to: {output_path}")
    # save_output()
    final_video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=video.fps,
        preset='medium',
        threads=4,
    )
    
    # Clean up
    video.close()
    final_video.close()
    print(f"\n✓ Video processing complete! Output saved to: {output_path}")

    # return final_video
    


# import tempfile
# import requests
# import json
# import os

# def generate_reel(template_url, overlay_config):
#     """
#     Downloads the video from template_url, saves to temp storage,
#     parses overlay_config (stringified JSON), and passes these to
#     overlay_images_on_video.
#     """
#     # Download video to a temporary file
#     print(f"Downloading video from template URL: {template_url}")
#     with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
#         response = requests.get(template_url, stream=True)
#         if response.status_code != 200:
#             raise Exception(f"Failed to download video file. Status: {response.status_code}")
#         for chunk in response.iter_content(chunk_size=8192):
#             if chunk:
#                 tmp_file.write(chunk)
#         video_path = tmp_file.name
#     print(f"Video downloaded to: {video_path}")

#     # overlays :{"overlays":[\"start_time\": 1, \"duration\": 1], [\"start_time\": 3, \"duration\": 1]}
#     overlays = json.loads(overlay_config).get("overlays")

#     # Output path: temp file
#     output_path = video_path.replace('.mp4', '_output.mp4')
#     # Pass to overlay_images_on_video
#     overlay_images_on_video(video_path, overlays, output_path)

#     print(f"Generated reel saved to {output_path}")

#     # Optionally cleanup original file (comment this out if you need source video later)
#     try:
#         os.remove(video_path)
#     except Exception:
#         pass

#     return output_path
