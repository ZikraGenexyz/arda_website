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

# Import MoviePy for video processing
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, ColorClip, TextClip

# Global progress tracking dictionary
PROGRESS_DATA = {}

# Create your views here.
def home(request):
    return render(request, 'index.html')

def create_named_overlay(png_path, user_name, target_size):
    """Add name to PNG and resize it to match video size."""
    img = Image.open(png_path).convert("RGBA").resize(target_size)

    draw = ImageDraw.Draw(img)
    try:
        # Try to use Arial font, fall back to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 100)
        except IOError:
            try:
                # Try to find another system font if arial isn't available
                system_fonts = [
                    "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                    "C:/Windows/Fonts/Arial.ttf"  # Windows
                ]
                
                for font_path in system_fonts:
                    if os.path.exists(font_path):
                        font = ImageFont.truetype(font_path, 100)
                        break
                else:
                    # If no system fonts found, use default
                    font = ImageFont.load_default()
            except:
                # Use default as last resort
                font = ImageFont.load_default()
    except IOError:
        font = ImageFont.load_default()

    # Draw username in the center of the image
    try:
        # For newer Pillow versions
        text_width, text_height = font.getsize(user_name)
    except AttributeError:
        try:
            # For even newer Pillow versions (9.2.0+)
            bbox = font.getbbox(user_name)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback to a simple estimate if both methods are unavailable
            text_width = len(user_name) * 30  # rough estimate
            text_height = 50
    
    position = ((img.width - text_width) // 2, (img.height - text_height) * 3//4)
    draw.text(position, user_name, font=font, fill=(255, 255, 255, 255))
    
    return np.array(img)

def overlay_image(frame, overlay):
    """Overlay RGBA PNG over BGR frame using alpha blending."""
    # Check dimensions match
    h, w = frame.shape[:2]
    overlay = cv2.resize(overlay, (w, h))
    
    overlay_rgb = overlay[:, :, :3]
    alpha = overlay[:, :, 3:] / 255.0

    # Convert frame to float for blending
    frame = frame.astype(float)
    overlay_rgb = overlay_rgb.astype(float)

    # Blend with alpha
    blended = alpha * overlay_rgb + (1 - alpha) * frame
    return blended.astype(np.uint8)

def process_video_with_moviepy(input_video, output_video, overlay_path, username, progress_id, target_width=None, target_height=None):
    """Process video with MoviePy, reporting progress."""
    try:
        if not os.path.exists(input_video):
            PROGRESS_DATA[progress_id]['error'] = "Could not open video file"
            PROGRESS_DATA[progress_id]['status'] = "Error: Could not open video file"
            return False
            
        # Initialize progress
        PROGRESS_DATA[progress_id]['progress'] = 10
        PROGRESS_DATA[progress_id]['status'] = "Loading video file..."
        
        # Load the video file
        video = VideoFileClip(input_video)
        
        # Get original dimensions
        orig_width, orig_height = video.size
        
        # Use provided dimensions or original if not provided
        width = target_width if target_width is not None else orig_width
        height = target_height if target_height is not None else orig_height
        
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 30
        PROGRESS_DATA[progress_id]['status'] = "Preparing overlay..."
        
        # Resize video if needed
        if width != orig_width or height != orig_height:
            PROGRESS_DATA[progress_id]['status'] = f"Resizing video to {width}x{height}..."
            video = video.resize(newsize=(width, height))
        
        # Create a named overlay from the PNG
        # First add the username to the overlay
        img = Image.open(overlay_path).convert("RGBA")
        draw = ImageDraw.Draw(img)
        
        try:
            # Try to use system fonts
            system_fonts = [
                "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "C:/Windows/Fonts/Arial.ttf"  # Windows
            ]
                
            for font_path in system_fonts:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 50)  # Reduced font size
                    break
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
            
        # Draw username in the center bottom area
        try:
            # For newer Pillow versions
            bbox = font.getbbox(username)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except:
            # Fallback to a simple estimate
            text_width = len(username) * 20
            text_height = 30
        
        position = ((img.width - text_width) // 2, (img.height - text_height) * 3//4)
        draw.text(position, username, font=font, fill=(255, 255, 255, 255))
        
        # Save the modified overlay to a temporary file
        named_overlay_path = overlay_path.replace('.png', f'_{username}.png')
        img.save(named_overlay_path)
        
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 50
        PROGRESS_DATA[progress_id]['status'] = "Creating video overlay..."
        
        # Create the overlay clip
        overlay = (ImageClip(named_overlay_path)
                  .set_duration(video.duration)
                  .set_position(("center", "center")))
                  
        if width != orig_width or height != orig_height:
            overlay = overlay.resize((width, height))
                  
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 70
        PROGRESS_DATA[progress_id]['status'] = "Compositing video and overlay..."
            
        # Create the final composite
        final = CompositeVideoClip([video, overlay])
        
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 80
        PROGRESS_DATA[progress_id]['status'] = "Writing output video..."
        
        # Write the output file
        final.write_videofile(output_video, codec="libx264", audio_codec="aac", 
                            logger=None, verbose=False)  # Disable verbose output
        
        # Clean up
        video.close()
        final.close()
        
        # Remove temporary file
        if os.path.exists(named_overlay_path):
            os.remove(named_overlay_path)
            
        # Update progress
        if os.path.exists(output_video) and os.path.getsize(output_video) > 0:
            PROGRESS_DATA[progress_id]['progress'] = 100
            PROGRESS_DATA[progress_id]['status'] = "Complete"
            return True
        else:
            PROGRESS_DATA[progress_id]['error'] = "Failed to create output video"
            PROGRESS_DATA[progress_id]['status'] = "Error: Output file is empty or not created"
            return False
            
    except Exception as e:
        error_msg = f"MoviePy processing error: {str(e)}"
        print(error_msg)
        PROGRESS_DATA[progress_id]['error'] = error_msg
        PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
        
        # Create a static image fallback
        return generate_static_fallback_with_pil(input_video, output_video, username, progress_id)

def generate_static_fallback_with_pil(video_path, output_path, username, progress_id):
    """Generate a static image with the first frame and username as fallback using PIL"""
    try:
        PROGRESS_DATA[progress_id]['status'] = "Creating fallback image..."
        
        # Try to extract first frame from video using MoviePy
        try:
            video = VideoFileClip(video_path)
            frame = video.get_frame(0)  # Get the first frame
            width, height = video.size
            video.close()
        except:
            # Default dimensions if can't read frame
            width, height = 800, 600
            frame = None
        
        if frame is None:
            # Create a blank image
            img = Image.new('RGB', (width, height), (0, 0, 0))
        else:
            # Convert numpy array to PIL Image
            img = Image.fromarray(frame)
        
        # Add text
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        message = f"Hello {username}!\nVideo processing failed.\nHere's a static image instead."
        draw.text((img.width//2 - 150, img.height//2 - 50), message, fill=(255, 255, 255))
        
        # Save as JPEG
        output_image = output_path.replace('.mp4', '.jpg')
        img.save(output_image)
        
        # Update progress data
        PROGRESS_DATA[progress_id]['output_path'] = output_image
        PROGRESS_DATA[progress_id]['is_image'] = True
        PROGRESS_DATA[progress_id]['ready'] = True
        PROGRESS_DATA[progress_id]['progress'] = 100
        PROGRESS_DATA[progress_id]['status'] = "Complete (fallback image)"
        
        return True
    except Exception as e:
        error_msg = f"Fallback image creation error: {str(e)}"
        print(error_msg)
        PROGRESS_DATA[progress_id]['error'] = error_msg
        PROGRESS_DATA[progress_id]['status'] = "Error: All methods failed"
        return False

def process_video(username, video_path, frame_path, output_path, progress_id):
    """Process video in a separate thread"""
    try:
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 5
        PROGRESS_DATA[progress_id]['status'] = "Determining video dimensions..."
        
        # Get video dimensions using MoviePy
        try:
            video = VideoFileClip(video_path)
            original_width, original_height = video.size
            video.close()
        except Exception as e:
            print(f"Error reading video dimensions: {str(e)}")
            # Default dimensions if can't read
            original_width, original_height = 640, 480
        
        # Calculate reduced size dimensions (to about 1/3 of original)
        width = original_width // 3
        height = original_height // 3
        
        # Log the dimensions
        print(f"Original video dimensions: {original_width}x{original_height}")
        print(f"Resized video dimensions: {width}x{height}")
        
        # Update progress
        PROGRESS_DATA[progress_id]['progress'] = 20
        PROGRESS_DATA[progress_id]['status'] = "Processing video with MoviePy..."
        
        # Process video with reduced size dimensions
        success = process_video_with_moviepy(video_path, output_path, frame_path, username, progress_id, width, height)
        
        if success:
            PROGRESS_DATA[progress_id]['ready'] = True
        
    except Exception as e:
        error_msg = f"Error in video processing: {str(e)}"
        print(error_msg)
        PROGRESS_DATA[progress_id]['error'] = error_msg
        PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"

def get_progress(request):
    """Endpoint to check the progress of video processing"""
    progress_id = request.GET.get('id', '')
    if progress_id in PROGRESS_DATA:
        return JsonResponse(PROGRESS_DATA[progress_id])
    return JsonResponse({'error': 'Progress ID not found'}, status=404)

def start_process(request):
    """Start processing the video and return a progress ID"""
    username = request.GET.get('username', 'Guest')
    
    # Generate a unique progress ID
    progress_id = f"progress_{int(time.time())}_{username}"
    
    # Initialize progress tracking
    PROGRESS_DATA[progress_id] = {
        'progress': 0,
        'status': 'Initializing...',
        'ready': False,
        'username': username
    }
    
    try:
        # Get paths to static files
        base_dir = Path(__file__).resolve().parent
        static_dir = os.path.join(base_dir, 'static')
        video_dir = os.path.join(static_dir, 'video')
        image_dir = os.path.join(static_dir, 'image')
        
        # Ensure directories exist
        os.makedirs(static_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(image_dir, exist_ok=True)
        
        video_path = os.path.join(video_dir, 'liolio.mp4')
        frame_path = os.path.join(image_dir, 'frame.png')
        
        # Print out paths for debugging
        print(f"Starting process for {username}")
        print(f"Video path: {video_path}")
        print(f"Frame path: {frame_path}")
        
        # Create placeholder files if they don't exist
        if not os.path.exists(video_path):
            try:
                # Create a simple test video using MoviePy - use smaller dimensions
                width, height = 320, 240  # Half of the standard 640x480
                duration = 3  # seconds
                
                print(f"Creating test video at {video_path} with dimensions {width}x{height}")
                
                # Create a blank clip with blue background
                from moviepy.editor import ColorClip, TextClip, CompositeVideoClip
                
                # Create a blue background clip
                background = ColorClip(size=(width, height), color=(0, 0, 255), duration=duration)
                
                # Create a text clip
                text = (TextClip("Test Video", fontsize=30, color='white', font='Arial')
                       .set_position('center')
                       .set_duration(duration))
                
                # Combine the clips
                video_clip = CompositeVideoClip([background, text])
                
                # Write to file
                video_clip.write_videofile(video_path, codec='libx264', audio=False, 
                                          verbose=False, logger=None)
                
                # Clean up
                video_clip.close()
                background.close()
                text.close()
                
                print(f"Successfully created test video at {video_path}")
            except Exception as e:
                error_msg = f"Error creating test video: {str(e)}"
                print(error_msg)
                PROGRESS_DATA[progress_id]['error'] = error_msg
                PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
                return JsonResponse({'error': error_msg}, status=500)
        
        if not os.path.exists(frame_path):
            try:
                # Create a simple overlay PNG with transparency - smaller size
                overlay_width, overlay_height = 400, 300  # Half of 800x600
                
                print(f"Creating overlay image at {frame_path} with dimensions {overlay_width}x{overlay_height}")
                
                overlay = Image.new('RGBA', (overlay_width, overlay_height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                
                # Add a semi-transparent rectangle
                draw.rectangle([(50, 50), (350, 250)], fill=(255, 255, 255, 128))
                
                # Add text placeholder
                font = ImageFont.load_default()
                draw.text((overlay_width//2, overlay_height//2), "USERNAME", font=font, fill=(0, 0, 0, 255))
                
                # Save the overlay
                overlay.save(frame_path)
                print(f"Successfully created overlay image at {frame_path}")
            except Exception as e:
                error_msg = f"Error creating overlay image: {str(e)}"
                print(error_msg)
                PROGRESS_DATA[progress_id]['error'] = error_msg
                PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
                return JsonResponse({'error': error_msg}, status=500)
        
        # Verify files after creation
        if not os.path.exists(video_path):
            error_msg = f"Video file does not exist: {video_path}"
            print(error_msg)
            PROGRESS_DATA[progress_id]['error'] = error_msg
            PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
            return JsonResponse({'error': error_msg}, status=500)
            
        if not os.path.exists(frame_path):
            error_msg = f"Frame file does not exist: {frame_path}"
            print(error_msg)
            PROGRESS_DATA[progress_id]['error'] = error_msg
            PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
            return JsonResponse({'error': error_msg}, status=500)
        
        # Create temporary file for output
        temp_dir = tempfile.mkdtemp()
        output_path = os.path.join(temp_dir, f"output_{username}.mp4")
        
        print(f"Output path: {output_path}")
        
        # Store paths in progress data
        PROGRESS_DATA[progress_id]['output_path'] = output_path
        PROGRESS_DATA[progress_id]['temp_dir'] = temp_dir
        
        # Start processing in a thread
        thread = threading.Thread(
            target=process_video,
            args=(username, video_path, frame_path, output_path, progress_id)
        )
        thread.daemon = True
        thread.start()
        
        return JsonResponse({
            'progress_id': progress_id,
            'status': 'Processing started'
        })
    except Exception as e:
        error_msg = f"Error in start_process: {str(e)}"
        print(error_msg)
        PROGRESS_DATA[progress_id]['error'] = error_msg
        PROGRESS_DATA[progress_id]['status'] = f"Error: {error_msg}"
        return JsonResponse({'error': error_msg}, status=500)

def download(request):
    """Download the processed video or fallback image"""
    progress_id = request.GET.get('id', '')
    
    if not progress_id:
        print("No progress ID provided in download request")
        return JsonResponse({'error': 'No progress ID provided'}, status=400)
    
    print(f"Download requested for progress ID: {progress_id}")
    print(f"Available progress IDs: {list(PROGRESS_DATA.keys())}")
    
    if progress_id not in PROGRESS_DATA:
        print(f"Progress ID not found: {progress_id}")
        return JsonResponse({'error': 'Progress ID not found'}, status=404)
    
    progress_data = PROGRESS_DATA[progress_id]
    
    if not progress_data.get('ready', False):
        print(f"File not ready yet for progress ID: {progress_id}")
        print(f"Current progress: {progress_data.get('progress', 0)}%")
        return JsonResponse({'error': 'File not ready yet'}, status=400)
    
    try:
        output_path = progress_data.get('output_path', '')
        username = progress_data.get('username', 'unknown')
        
        print(f"Attempting to serve file: {output_path}")
        
        # Check if the file exists
        if not output_path or not os.path.exists(output_path):
            error_msg = f"Output file does not exist: {output_path}"
            print(error_msg)
            return JsonResponse({'error': error_msg}, status=500)
        
        # Get file size for logging
        file_size = os.path.getsize(output_path)
        print(f"File size: {file_size} bytes")
        
        if file_size == 0:
            print("WARNING: File size is zero bytes!")
        
        # Determine file type based on extension
        is_image = output_path.lower().endswith(('.jpg', '.jpeg', '.png'))
        
        # Copy the file to a new location to avoid cleanup issues
        temp_filename = f"output_{username}_{int(time.time())}"
        extension = ".jpg" if is_image else ".mp4"
        temp_file = os.path.join(tempfile.gettempdir(), temp_filename + extension)
        
        # Copy file
        import shutil
        shutil.copy2(output_path, temp_file)
        print(f"Copied file to {temp_file}")
        
        # Serve the copied file
        try:
            file_handle = open(temp_file, 'rb')
            response = FileResponse(file_handle)
            
            # Set appropriate content type and filename
            if is_image:
                filename = f"fallback_{username}.jpg"
                response['Content-Type'] = 'image/jpeg'
                print(f"Serving image file as {filename}")
            else:
                filename = f"overlay_{username}.mp4"
                response['Content-Type'] = 'video/mp4'
                print(f"Serving video file as {filename}")
                
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = file_size
            
            # Set a flag that this file was served
            progress_data['file_served'] = True
            
            # Schedule cleanup after response is sent
            def delayed_cleanup():
                time.sleep(60)  # Wait a minute before cleanup
                try:
                    # Clean up temp file
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        print(f"Cleaned up temporary file: {temp_file}")
                        
                    # Clean up original temp directory
                    temp_dir = progress_data.get('temp_dir')
                    if temp_dir and os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        print(f"Cleaned up temp directory: {temp_dir}")
                        
                    # Remove from progress tracking
                    if progress_id in PROGRESS_DATA:
                        del PROGRESS_DATA[progress_id]
                        print(f"Removed progress data for: {progress_id}")
                except Exception as e:
                    print(f"Cleanup error: {str(e)}")
                    
            cleanup_thread = threading.Thread(target=delayed_cleanup)
            cleanup_thread.daemon = True
            cleanup_thread.start()
            
            return response
        except Exception as e:
            error_msg = f"Error opening file: {str(e)}"
            print(error_msg)
            return JsonResponse({'error': error_msg}, status=500)
            
    except Exception as e:
        error_msg = f"Error serving file: {str(e)}"
        print(error_msg)
        return JsonResponse({'error': error_msg}, status=500)
