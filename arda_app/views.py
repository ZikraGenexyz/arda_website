from django.shortcuts import render
from django.http import FileResponse, JsonResponse
import os
import tempfile
import threading
import time
import numpy as np
from pathlib import Path
from arda_app import models
import subprocess
import re
import io
# Import Pillow for image manipulation
from PIL import Image, ImageDraw, ImageFont

# Import FFmpeg for video processing
import ffmpeg

# Add compatibility for newer PIL versions (PIL.Image.ANTIALIAS is deprecated)
# In newer Pillow versions, ANTIALIAS was removed and replaced with LANCZOS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# Global progress tracking dictionary
PROGRESS_DATA = {}
DOWNLOAD_DATA = {}
# Store output video paths for quick access on reconnection
VIDEO_PATHS = {}

def get_progress(request):
    """API endpoint to get the current progress for a specific user"""
    user_id = request.GET.get('id', None)
    
    if not user_id:
        return JsonResponse({'error': 'No user ID provided'}, status=400)
        
    progress = PROGRESS_DATA.get(user_id, 0)
    is_ready = user_id in VIDEO_PATHS and os.path.exists(VIDEO_PATHS[user_id]) and PROGRESS_DATA[user_id] == 100
    return JsonResponse({'progress': progress, 'is_ready': is_ready})

def monitor_ffmpeg_progress(process, user_id, duration):
    """
    Monitors progress from FFmpeg by reading its stderr output
    and updates the progress value in PROGRESS_DATA
    
    How it works:
    1. FFmpeg outputs progress information to stderr with "-progress pipe:2"
    2. We parse this output to extract the current timestamp being processed
    3. We convert this timestamp to seconds and calculate progress percentage
    4. The percentage is stored in PROGRESS_DATA[user_id] for the client to access
    """
    # Regular expression to extract time information from FFmpeg output
    time_regex = re.compile(r"time=(\d+:\d+:\d+\.\d+)")
    
    # Track progress updates for debugging
    last_progress = 0
    update_count = 0
    
    try:
        # Read output line by line
        for line in io.TextIOWrapper(process.stderr, encoding="utf-8", errors="replace"):
            # Print occasional lines for debugging
            if update_count % 50 == 0:
                print(f"FFmpeg output line: {line.strip()}")
            
            # Extract time information
            match = time_regex.search(line)
            if match:
                time_str = match.group(1)
                
                try:
                    # Convert time_str (HH:MM:SS.ms) to seconds
                    h, m, s = time_str.split(':')
                    seconds = float(h) * 3600 + float(m) * 60 + float(s)
                    
                    # Calculate and update progress percentage
                    percentage = min((seconds / duration) * 100, 100)
                    current_progress = round(percentage, 2)
                    
                    # Only update if progress has changed significantly (reduces log spam)
                    if current_progress - last_progress >= 1.0 or current_progress >= 100:
                        PROGRESS_DATA[user_id] = current_progress
                        print(f"FFmpeg progress: {current_progress:.2f}% (time: {time_str})")
                        last_progress = current_progress
                    
                    update_count += 1
                except (ValueError, ZeroDivisionError) as e:
                    # Handle parsing errors
                    print(f"Error parsing time from FFmpeg output: {e}")
    except Exception as e:
        print(f"Error monitoring FFmpeg progress: {e}")
        # Don't let monitoring errors crash the whole process
        # If monitoring fails, we'll still have the final video if FFmpeg completes successfully

def home(request):
    """
    Directly overlay the frame.png with username on video and return for download
    """
    user_id = request.GET.get('id', 'None')

    if user_id == 'None':
        return JsonResponse({'error': 'No user ID provided'}, status=400)
    
    username = models.UserList.objects.get(id=user_id).name
    download = request.GET.get('download', False)
    
    # Check if processing is already in progress for this user
    processing_in_progress = user_id in DOWNLOAD_DATA and DOWNLOAD_DATA[user_id] == "Running"
    
    # If no download parameter is specified, show the loading UI with the username
    if not download:
        # Initialize progress for this user if not already processing
        if user_id not in PROGRESS_DATA:
            PROGRESS_DATA[user_id] = 0
        
        # Pass processing status to template
        return render(request, 'index.html', {
            'id': user_id, 
            'username': username
        })
    
    try:
        # Check if the video has already been generated and still exists
        if user_id in VIDEO_PATHS and os.path.exists(VIDEO_PATHS[user_id]) and PROGRESS_DATA[user_id] == 100:
            # Video already exists, serve it immediately
            output_video_path = VIDEO_PATHS[user_id]
            PROGRESS_DATA[user_id] = 100  # Ensure progress shows as complete
            
            # Serve the existing file
            f = open(output_video_path, 'rb')
            response = FileResponse(f)
            response['Content-Type'] = 'video/mp4'
            response['Content-Disposition'] = f'attachment; filename="overlay_{username}.mp4"'
            print(f"Serving existing video for user {user_id} from: {output_video_path}")
            return response
        
        # Check multiple possible static file locations
        base_dir = Path(__file__).resolve().parent
        static_dirs = [
            os.path.join(base_dir, 'static'),  # App static dir
            os.path.join(base_dir, '../static'),  # Project static dir
            os.path.join(base_dir, '../staticfiles'),  # Collected static dir
            os.path.join(base_dir, '../arda_website/staticfiles'),  # Django project staticfiles
            '/var/task/arda_app/static',  # Vercel path
            '/var/task/static',  # Vercel alternative path
            '/var/task/public',  # Vercel public dir
            '/public',  # Vercel public dir (root)
            '/tmp/static'  # Temp dir as fallback
        ]
        
        # Try to find video and frame in various locations
        video_path = None
        frame_path = None
        
        for static_dir in static_dirs:
            print(f"Checking static dir: {static_dir}")
            potential_video_path = os.path.join(static_dir, 'video', 'liolio.mp4')
            if os.path.exists(potential_video_path):
                video_path = potential_video_path
                print(f"Found video at: {video_path}")
            potential_frame_path = os.path.join(static_dir, 'image', 'frame.png')
            if os.path.exists(potential_frame_path):
                frame_path = potential_frame_path
                print(f"Found frame at: {frame_path}")
            if video_path and frame_path:
                break
        
        if not video_path or not frame_path:
            raise FileNotFoundError("Video or frame not found in any of the checked locations.")
        
        # Create temp directories
        temp_dir = tempfile.mkdtemp()
        # Create a user-specific subdirectory
        user_temp_dir = os.path.join(temp_dir, f"user_{user_id}")
        try:
            os.makedirs(user_temp_dir, exist_ok=True)
            print(f"Created user directory: {user_temp_dir}")
        except Exception as e:
            print(f"Error creating user directory: {str(e)}")
            # Fall back to main temp directory if user directory creation fails
            user_temp_dir = temp_dir
            print(f"Falling back to main temp directory: {temp_dir}")
        
        # Process the overlay frame with username
        img = Image.open(frame_path).convert("RGBA")
        
        # Get video info using ffprobe
        probe = ffmpeg.probe(video_path)
        video_info = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        
        if video_info:
            # Get original video dimensions
            video_width = int(video_info['width'])
            video_height = int(video_info['height'])
            duration = float(video_info.get('duration', 0))
            fps = eval(video_info.get('r_frame_rate', '24/1'))
            if isinstance(fps, tuple):
                fps = fps[0] / fps[1]
            
            print(f"Video dimensions: {video_width}x{video_height}")
            
            # Resize the overlay to match video dimensions
            img = img.resize((video_width, video_height))
            print(f"Overlay dimensions: {img.width}x{img.height}")
        else:
            # Fallback values
            print("Warning: Could not get video info from ffprobe, using defaults")
            video_width, video_height = 1280, 720
            duration = 10
            fps = 24
            
            # Resize overlay to match fallback dimensions
            img = img.resize((video_width, video_height))
            print(f"Overlay dimensions (fallback): {img.width}x{img.height}")
        
        # Add the username to the overlay image
        draw = ImageDraw.Draw(img)
        
        # Calculate font size based on image dimensions
        font_size = max(20, min(img.width, img.height) // 15)  # Responsive font size
        print(f"Font size for {username}: {font_size}px")
        
        # Try to use a better font if available, otherwise fallback
        try:
            # Try common font locations across different OSes
            possible_font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "C:\\Windows\\Fonts\\arialbd.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
            ]
            
            font = None
            for font_path in possible_font_paths:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, font_size)
                    print(f"Using font: {font_path}")
                    break
            
            if font is None:
                font = ImageFont.load_default()
                print("Using default font (no specific font found)")
        except Exception as e:
            # Fallback to default font
            print(f"Error loading font: {str(e)}")
            font = ImageFont.load_default()
            print("Falling back to default font due to error")
        
        # Calculate text size to position it centrally
        # PIL has different APIs in different versions
        if hasattr(draw, 'textsize'):
            # Older PIL versions
            text_width, text_height = draw.textsize(username, font=font)
        elif hasattr(font, 'getbbox'):
            # Newer PIL versions
            bbox = font.getbbox(username)
            text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        else:
            # Fallback estimation
            text_width = font_size * len(username) * 0.6
            text_height = font_size * 1.2
        
        print(f"Text dimensions for '{username}': {text_width}x{text_height}")
        
        # Center text position
        position = ((img.width - text_width) // 2, (img.height - text_height) // 2)
        print(f"Text position: {position}")
        
        # Create text with better visibility
        # Add a semi-transparent background for the text
        bg_padding = font_size // 2
        bg_box = [
            position[0] - bg_padding, 
            position[1] - bg_padding,
            position[0] + text_width + bg_padding,
            position[1] + text_height + bg_padding
        ]
        
        # Draw semi-transparent background
        bg_color = (0, 0, 0, 128)  # Semi-transparent black
        draw.rectangle(bg_box, fill=bg_color)
        
        # Add outline/shadow for better visibility
        shadow_color = (0, 0, 0, 180)  # Semi-transparent black
        outline_size = max(1, font_size // 20)
        
        # Draw multiple offset shadows for an outline effect
        for dx in range(-outline_size, outline_size + 1):
            for dy in range(-outline_size, outline_size + 1):
                if dx != 0 or dy != 0:  # Skip the center position
                    shadow_pos = (position[0] + dx, position[1] + dy)
                    draw.text(shadow_pos, username, font=font, fill=shadow_color)
        
        # Draw the main text
        text_color = (255, 255, 255, 255)  # Solid white
        draw.text(position, username, font=font, fill=text_color)
        
        # Save the frame image with username
        named_frame_path = os.path.join(user_temp_dir, f"frame_{username}.png")
        img.save(named_frame_path)
        print(f"Saved frame at: {named_frame_path}")
        
        # Set output video path
        output_video_path = os.path.join(user_temp_dir, f"output_{username}.mp4")
        print(f"Will save output video at: {output_video_path}")
        
        # Store the output path in the global dictionary for future requests
        VIDEO_PATHS[user_id] = output_video_path

        # Schedule cleanup of temporary files with longer timeout
        def delayed_cleanup():
            try:
                time.sleep(900)  # Wait 15 minutes before cleaning up
                print(f"Starting cleanup for user {user_id}")
                
                # Clean up user's files only
                if os.path.exists(named_frame_path):
                    try:
                        os.remove(named_frame_path)
                        print(f"Removed frame: {named_frame_path}")
                    except Exception as e:
                        print(f"Error removing frame: {str(e)}")
                
                if os.path.exists(output_video_path):
                    try:
                        os.remove(output_video_path)
                        print(f"Removed video: {output_video_path}")
                        # Remove from paths dictionary
                        if user_id in VIDEO_PATHS:
                            del VIDEO_PATHS[user_id]
                    except Exception as e:
                        print(f"Error removing video: {str(e)}")
                
                # Remove user's directory first
                try:
                    if os.path.exists(user_temp_dir):
                        os.rmdir(user_temp_dir)
                        print(f"Removed user temp directory: {user_temp_dir}")
                except Exception as e:
                    print(f"Error removing user temp directory: {str(e)}")
                
                # Then try to remove the parent temp directory if it's empty
                try:
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                        print(f"Removed parent temp directory: {temp_dir}")
                except Exception as e:
                    print(f"Error removing parent temp directory: {str(e)}")
                
                # Clean up progress data
                if user_id in PROGRESS_DATA:
                    del PROGRESS_DATA[user_id]
                print(f"Cleanup completed for user {user_id}")
                DOWNLOAD_DATA[user_id] = "Not Running"
            except Exception as e:
                print(f"Error in delayed cleanup for user {user_id}: {str(e)}")
                DOWNLOAD_DATA[user_id] = "Not Running"
        
        if user_id not in DOWNLOAD_DATA or DOWNLOAD_DATA[user_id] == "Not Running":
            DOWNLOAD_DATA[user_id] = "Running"
            try:
                print(f"Starting video processing for user {user_id}")
                
                # Start with base progress
                PROGRESS_DATA[user_id] = 0
                
                # Generate command for running FFmpeg
                ffmpeg_cmd = [
                    'ffmpeg', 
                    '-y',  # Overwrite output files without asking
                    '-i', video_path,  # Input video
                    '-i', named_frame_path,  # Input overlay image
                    '-filter_complex', 
                    # Ensure overlay is properly positioned and scaled
                    # The format=auto ensures proper alpha handling
                    # The format=yuv420p ensures compatibility with most players
                    '[0:v][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:format=auto,format=yuv420p',
                    '-c:v', 'libx264',  # Video codec
                    '-c:a', 'copy',  # Copy audio stream without re-encoding
                    '-b:v', '2M',  # Video bitrate
                    '-movflags', '+faststart',  # Optimize for web playback
                    '-loglevel', 'info',  # Set log level to get progress info
                    '-progress', 'pipe:2',  # Output progress to stderr
                    output_video_path
                ]
                
                print(f"Running FFmpeg command for user {user_id}")
                print(f"Input video: {video_path}")
                print(f"Overlay image: {named_frame_path}")
                print(f"Output video: {output_video_path}")
                
                try:
                    # Start FFmpeg process
                    process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=False
                    )
                    
                    # Start monitoring progress in a separate thread
                    monitor_thread = threading.Thread(
                        target=monitor_ffmpeg_progress,
                        args=(process, user_id, duration)
                    )
                    monitor_thread.daemon = True
                    monitor_thread.start()
                    
                    # Wait for FFmpeg to finish
                    process.wait()
                    
                    # Check if FFmpeg was successful
                    if process.returncode != 0:
                        raise Exception(f"FFmpeg exited with error code {process.returncode}")
                except Exception as e:
                    print(f"Error with subprocess FFmpeg: {str(e)}")
                    print("Falling back to ffmpeg-python library")
                    
                    # Fallback to ffmpeg-python library
                    PROGRESS_DATA[user_id] = 10  # Start at 10%
                    
                    # Set up the ffmpeg inputs
                    input_video = ffmpeg.input(video_path)
                    input_overlay = ffmpeg.input(named_frame_path)
                    
                    # Overlay the image with centered position
                    # Position calculation: (main_w-overlay_w)/2 centers horizontally
                    # (main_h-overlay_h)/2 centers vertically
                    stream = input_video.overlay(
                        input_overlay, 
                        x='(main_w-overlay_w)/2',  # Center horizontally
                        y='(main_h-overlay_h)/2',  # Center vertically
                        format='auto'  # Proper alpha handling
                    ).filter('format', 'yuv420p')  # Ensure compatibility
                    
                    # Set up the output
                    stream = ffmpeg.output(
                        stream, 
                        output_video_path, 
                        vcodec='libx264',
                        acodec='copy',
                        video_bitrate='2M',
                        movflags='+faststart'
                    )
                    
                    # Run the FFmpeg command via the library
                    print("Running FFmpeg via Python library...")
                    ffmpeg.run(stream, overwrite_output=True, quiet=True)
                    
                    # Since we can't track progress with the library easily, simulate progress jumps
                    progress_points = [25, 50, 75, 90]
                    total_time = duration * 0.02  # Estimate processing time based on duration
                    sleep_interval = total_time / len(progress_points)
                    
                    for progress in progress_points:
                        time.sleep(sleep_interval)
                        PROGRESS_DATA[user_id] = progress
                        print(f"FFmpeg progress (simulated): {progress}%")
                
                # Ensure progress is set to 100% when complete
                PROGRESS_DATA[user_id] = 100
                
                print(f"Video processing completed for user {user_id}")
                
                # Start cleanup thread after successful generation
                cleanup_thread = threading.Thread(target=delayed_cleanup)
                cleanup_thread.daemon = True
                cleanup_thread.start()
                print(f"Cleanup thread started for user {user_id}")
            except Exception as e:
                print(f"Error during video processing for user {user_id}: {str(e)}")
                # Remove the path from VIDEO_PATHS if processing failed
                if user_id in VIDEO_PATHS:
                    del VIDEO_PATHS[user_id]
                raise  # Re-raise to be caught by outer exception handler

        # Serve file for download
        f = open(output_video_path, 'rb')
        response = FileResponse(f)
        response['Content-Type'] = 'video/mp4'
        response['Content-Disposition'] = f'attachment; filename="overlay_{username}.mp4"'
        print(f"Serving newly generated video for user {user_id} from: {output_video_path}")
        
        return response

    except Exception as e:
        error_msg = f"Error in processing video: {str(e)}"
        # Clean up any temporary files created in case of error
        try:
            # Try to delete the temporary files
            if 'named_frame_path' in locals() and os.path.exists(named_frame_path):
                os.remove(named_frame_path)
            
            if 'output_video_path' in locals() and os.path.exists(output_video_path):
                os.remove(output_video_path)
            
            if 'user_temp_dir' in locals() and os.path.exists(user_temp_dir):
                os.rmdir(user_temp_dir)
            
            if 'temp_dir' in locals() and os.path.exists(temp_dir) and not os.listdir(temp_dir):
                os.rmdir(temp_dir)
            
            # Clean up dictionaries
            if user_id in VIDEO_PATHS:
                del VIDEO_PATHS[user_id]
            
            if user_id in DOWNLOAD_DATA:
                DOWNLOAD_DATA[user_id] = "Not Running"
                
            print(f"Cleaned up temporary files after error for user {user_id}")
        except Exception as cleanup_e:
            print(f"Error during cleanup after processing failure: {str(cleanup_e)}")
            
        print(f"Error for user {user_id}: {error_msg}")
        return JsonResponse({'error': error_msg}, status=500)