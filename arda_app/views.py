from django.shortcuts import render
from django.http import FileResponse, JsonResponse
import os
import tempfile
import threading
import time
import numpy as np
from pathlib import Path

# Import Pillow for image manipulation
from PIL import Image, ImageDraw, ImageFont

# Add compatibility for newer PIL versions (PIL.Image.ANTIALIAS is deprecated)
# In newer Pillow versions, ANTIALIAS was removed and replaced with LANCZOS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# Import MoviePy for video processing
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, TextClip
# Import proglog directly - don't import logger from moviepy.config
import proglog

# Global progress tracking dictionary
PROGRESS_DATA = {}

def home(request):
    """
    Directly overlay the frame.png with username on video and return for download
    """
    username = request.GET.get('username', 'Guest')
    download = request.GET.get('download', False)
    
    # If no download parameter is specified, show the loading UI with the username
    if not download:
        return render(request, 'index.html', {'username': username})
    
    try:
        # Check multiple possible static file locations
        # Get paths to static files - check multiple possible locations
        base_dir = Path(__file__).resolve().parent
        
        # List of possible static directories
        static_dirs = [
            os.path.join(base_dir, 'static'),                           # App static dir
            os.path.join(base_dir, '../static'),                        # Project static dir
            os.path.join(base_dir, '../staticfiles'),                   # Collected static dir
            os.path.join(base_dir, '../arda_website/staticfiles'),      # Django project staticfiles
            '/var/task/arda_app/static',                                # Vercel path
            '/var/task/static',                                         # Vercel alternative path
            '/tmp/static'                                               # Temp dir as fallback
        ]
        
        # Try to find video and frame in various locations
        video_path = None
        frame_path = None
        
        for static_dir in static_dirs:
            print(f"Checking static dir: {static_dir}")
            
            # Check for video file
            potential_video_path = os.path.join(static_dir, 'video', 'liolio.mp4')
            if os.path.exists(potential_video_path):
                video_path = potential_video_path
                print(f"Found video at: {video_path}")
            
            # Check for frame file
            potential_frame_path = os.path.join(static_dir, 'image', 'frame.png')
            if os.path.exists(potential_frame_path):
                frame_path = potential_frame_path
                print(f"Found frame at: {frame_path}")
            
            # If both found, break
            if video_path and frame_path:
                break
        
        # Create temporary directory for all output files
        temp_dir = tempfile.mkdtemp()
        named_frame_path = os.path.join(temp_dir, f"frame_{username}.png")
        output_video_path = os.path.join(temp_dir, f"output_{username}.mp4")
        
        print(f"Processing direct overlay for {username}")
        print(f"Temp dir: {temp_dir}")
        print(f"Output path: {output_video_path}")
        
        # Check if files exist before processing
        if not video_path:
            # List directories to help debug
            debug_info = "\nChecked directories:\n"
            for static_dir in static_dirs:
                debug_info += f"- {static_dir}/video/liolio.mp4 exists: {os.path.exists(os.path.join(static_dir, 'video', 'liolio.mp4'))}\n"
            
            raise FileNotFoundError(f"Video file not found in any of the checked locations.{debug_info}")
        
        if not frame_path:
            # List directories to help debug
            debug_info = "\nChecked directories:\n"
            for static_dir in static_dirs:
                debug_info += f"- {static_dir}/image/frame.png exists: {os.path.exists(os.path.join(static_dir, 'image', 'frame.png'))}\n"
            
            raise FileNotFoundError(f"Frame image not found in any of the checked locations.{debug_info}")
        
        # Open video and get properties - do not close until after composite creation
        original_video = VideoFileClip(video_path)
        original_size = original_video.size
        duration = original_video.duration
        fps = getattr(original_video, 'fps', 24)
        
        # Calculate new size (50% of original size for faster processing)
        # Make sure to maintain aspect ratio
        new_width = int(original_size[0] * 0.5)
        new_height = int(original_size[1] * 0.5)
        new_size = (new_width, new_height)
        
        # Resize video for faster processing
        video = original_video.resize(width=new_width, height=new_height)
        
        # Create named frame optimized for simplicity based on reference
        img = Image.open(frame_path).convert("RGBA")
        img = img.resize(new_size)  # Match the new video size
        draw = ImageDraw.Draw(img)
        
        # Find a usable font
        try:
            # Check multiple static directories for fonts
            font_paths = []
            for static_dir in static_dirs:
                font_paths.append(os.path.join(static_dir, 'fonts', 'DejaVuSans.ttf'))
                font_paths.append(os.path.join(static_dir, 'fonts', 'Arial.ttf'))
            
            # Add system font paths
            font_paths.extend([
                "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "C:/Windows/Fonts/Arial.ttf",  # Windows
                "/var/task/arda_app/static/fonts/DejaVuSans.ttf"  # Vercel path
            ])
            
            font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    # Adjust font size proportionally to the video resize
                    font_size = int(40 * 0.5)  # 50% of original font size
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"Using font: {font_path}")
                    break
            
            if font is None:
                print("Using default font as no system fonts were found")
                font = ImageFont.load_default()
        except Exception as e:
            print(f"Font error: {str(e)}")
            font = ImageFont.load_default()
        
        # Center text in bottom half of the image
        try:
            bbox = font.getbbox(username)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except Exception as e:
            print(f"Text sizing error: {str(e)}")
            text_width = len(username) * 10  # Adjusted for smaller font
            text_height = 15  # Adjusted for smaller font
        
        position = ((img.width - text_width) // 2, (img.height - text_height) * 3//4)
        draw.text(position, username, font=font, fill=(255, 255, 255, 255))
        img.save(named_frame_path)
        
        # Process video directly with no progress tracking
        print(f"Creating video overlay with username: {username}")
        
        # Create overlay clip and ensure it's valid
        overlay = ImageClip(named_frame_path)
        overlay = overlay.set_duration(duration).set_position(("center", "center"))
        
        # Create composite
        clips = [video, overlay]
        final = CompositeVideoClip(clips)
        
        # Use lower bitrate and resolution for faster processing
        try:
            final.write_videofile(
                output_video_path, 
                codec="libx264", 
                audio_codec="aac",
                bitrate="1000k",  # Lower bitrate
                logger=None, 
                verbose=False, 
                fps=fps
            )
            print(f"Video created successfully at {output_video_path}")
        except Exception as e:
            print(f"Video creation error: {str(e)}")
            raise
        
        # Clean up - Only close the clips after writing the video file
        overlay.close()
        video.close()
        original_video.close()
        final.close()
        
        # Serve file directly for download
        try:
            with open(output_video_path, 'rb') as f:
                response = FileResponse(f)
                response['Content-Type'] = 'video/mp4'
                response['Content-Disposition'] = f'attachment; filename="overlay_{username}.mp4"'
                # Add cache control headers to prevent caching
                response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response['Pragma'] = 'no-cache'
                response['Expires'] = '0'
                
                print(f"Serving download for {username}, file size: {os.path.getsize(output_video_path)} bytes")
                
                # Schedule cleanup of temporary files
                def delayed_cleanup():
                    time.sleep(60)  # Wait before cleaning up
                    try:
                        if os.path.exists(named_frame_path):
                            os.remove(named_frame_path)
                        if os.path.exists(output_video_path):
                            os.remove(output_video_path)
                        if os.path.exists(temp_dir):
                            os.rmdir(temp_dir)
                        print(f"Cleanup completed for {username}")
                    except Exception as e:
                        print(f"Cleanup error: {str(e)}")
                
                cleanup_thread = threading.Thread(target=delayed_cleanup)
                cleanup_thread.daemon = True
                cleanup_thread.start()
                
                return response
        except Exception as e:
            print(f"File response error: {str(e)}")
            raise
        
    except Exception as e:
        error_msg = f"Error in direct_overlay: {str(e)}"
        print(error_msg)
        return JsonResponse({'error': error_msg}, status=500)