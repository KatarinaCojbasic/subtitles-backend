import os
import speech_recognition as sr
import pysrt
from moviepy.video.io.VideoFileClip import VideoFileClip
from pydub import AudioSegment
import tempfile
import time
from django.core.files.base import ContentFile
from django.conf import settings

def generate_subtitles(video_upload):
    """
    Generate SRT subtitles from an uploaded video file.
    
    This function extracts audio from the video, converts speech to text,
    and creates SRT subtitle file.
    
    Args:
        video_upload: VideoUpload model instance
    """
    try:
        # Extract audio from video
        video_path = video_upload.video_file.path
        print(f"Starting subtitle generation for video: {video_path}")
        
        if not os.path.exists(video_path):
            raise Exception(f"Video file not found: {video_path}")
        
        temp_dir = tempfile.mkdtemp()
        temp_audio_path = os.path.join(temp_dir, 'audio.wav')
        
        # Update the model status
        video_upload.status = 'processing'
        video_upload.save()
        
        # Extract audio using moviepy
        print(f"Extracting audio from video: {video_path}")
        try:
            video_clip = VideoFileClip(video_path)
        except Exception as e:
            raise Exception(f"Failed to open video file: {str(e)}")
        
        try:
            # Check if video has audio
            if video_clip.audio is None:
                video_clip.close()
                raise Exception("Video file has no audio track. Please upload a video with audio.")
            
            print(f"Video duration: {video_clip.duration} seconds")
            print(f"Video FPS: {video_clip.fps}")
            print(f"Video size: {video_clip.size}")
            
            try:
                # Extract audio with optimal settings for speech recognition
                # Use mono channel, 16kHz sample rate (optimal for Google Speech Recognition)
                video_clip.audio.write_audiofile(
                    temp_audio_path,
                    codec='pcm_s16le',
                    ffmpeg_params=['-ac', '1', '-ar', '16000']  # Mono, 16kHz
                )
            except TypeError:
                # Fallback for older MoviePy versions
                try:
                    video_clip.audio.write_audiofile(temp_audio_path, codec='pcm_s16le')
                except Exception as e2:
                    video_clip.close()
                    raise Exception(f"Failed to extract audio from video: {str(e2)}")
            except Exception as e:
                video_clip.close()
                raise Exception(f"Failed to extract audio from video: {str(e)}")
            
            video_clip.close()
            
            # Verify audio file was created
            if not os.path.exists(temp_audio_path):
                raise Exception("Audio extraction failed - output file not created")
            
            audio_file_size = os.path.getsize(temp_audio_path)
            if audio_file_size == 0:
                raise Exception("Audio extraction failed - output file is empty")
            
            print(f"Audio file created: {temp_audio_path} ({audio_file_size} bytes)")
            
        except Exception as e:
            if 'video_clip' in locals():
                try:
                    video_clip.close()
                except:
                    pass
            raise
        
        # Process audio in chunks for better recognition
        print(f"Loading audio file: {temp_audio_path}")
        audio = AudioSegment.from_wav(temp_audio_path)
        print(f"Audio duration: {len(audio)} ms ({len(audio)/1000} seconds)")
        print(f"Audio frame rate: {audio.frame_rate} Hz")
        print(f"Audio channels: {audio.channels}")
        
        # Convert to mono if stereo (speech recognition works better with mono)
        if audio.channels > 1:
            print("Converting stereo to mono for better recognition")
            audio = audio.set_channels(1)
        
        # Set sample rate to 16kHz if different (optimal for Google Speech Recognition)
        if audio.frame_rate != 16000:
            print(f"Resampling from {audio.frame_rate}Hz to 16000Hz")
            audio = audio.set_frame_rate(16000)
        
        # Normalize audio (increase volume if too quiet)
        # Normalize to -20dBFS which is a good level for speech recognition
        print(f"Original audio dBFS: {audio.dBFS}")
        normalized_audio = audio.normalize()
        print(f"Normalized audio dBFS: {normalized_audio.dBFS}")
        
        # Apply additional processing to improve recognition
        # Increase volume if too quiet (but don't over-amplify)
        if normalized_audio.dBFS < -30:
            print("Audio is very quiet, applying gain")
            normalized_audio = normalized_audio + 10  # Add 10dB gain
            print(f"After gain audio dBFS: {normalized_audio.dBFS}")
        
        # Apply high-pass filter to remove low-frequency noise (below 80Hz)
        # This helps remove background rumble and improves speech clarity
        print("Applying high-pass filter to remove low-frequency noise")
        normalized_audio = normalized_audio.high_pass_filter(80)
        
        # Apply compression to even out volume levels
        # This helps with inconsistent volume in speech
        print("Applying compression to even out volume levels")
        normalized_audio = normalized_audio.compress_dynamic_range(threshold=-20.0, ratio=4.0, attack=5.0, release=50.0)
        
        # Export normalized audio
        normalized_audio_path = os.path.join(temp_dir, 'audio_normalized.wav')
        normalized_audio.export(normalized_audio_path, format="wav")
        
        # Use optimal chunk size for speech recognition
        # 10-12 seconds is optimal - long enough for context, short enough for accuracy
        chunk_length_ms = 12000  # 12 seconds - optimal for Google Speech Recognition
        # Use overlapping chunks (50% overlap) for better accuracy at boundaries
        overlap_ms = chunk_length_ms // 2  # 50% overlap
        chunks = []
        chunk_starts = []
        for i in range(0, len(normalized_audio), chunk_length_ms - overlap_ms):
            chunk = normalized_audio[i:i+chunk_length_ms]
            if len(chunk) > 1000:  # Only process chunks longer than 1 second
                chunks.append(chunk)
                chunk_starts.append(i)
        print(f"Split audio into {len(chunks)} overlapping chunks of ~{chunk_length_ms/1000} seconds each")
        
        # Log audio properties
        print(f"Audio max possible amplitude: {normalized_audio.max_possible_amplitude}")
        print(f"Audio max amplitude: {normalized_audio.max}")
        print(f"Audio dBFS: {normalized_audio.dBFS}")
        
        # Recognize speech in chunks
        recognizer = sr.Recognizer()
        # Optimize recognizer settings for better accuracy
        recognizer.energy_threshold = 400  # Balanced threshold
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 1.0  # Optimal pause detection
        recognizer.phrase_threshold = 0.3  # Lower threshold for phrase detection
        recognizer.non_speaking_duration = 0.8  # Shorter non-speaking duration
        
        subtitles = pysrt.SubRipFile()
        successful_chunks = 0
        failed_chunks = 0
        
        for i, chunk in enumerate(chunks):
            # Save chunk to temporary file
            chunk_file = os.path.join(temp_dir, f'chunk_{i}.wav')
            # Export with optimal settings for speech recognition
            # Mono, 16kHz, 16-bit PCM
            chunk.export(
                chunk_file, 
                format="wav",
                parameters=["-ac", "1", "-ar", "16000", "-sample_fmt", "s16"]
            )
            
            chunk_start_time = chunk_starts[i] / 1000.0  # in seconds
            chunk_end_time = chunk_start_time + (len(chunk) / 1000)
            print(f"Processing chunk {i+1}/{len(chunks)} (time: {chunk_start_time:.2f}s - {chunk_end_time:.2f}s, duration: {len(chunk)/1000:.2f}s)")
            
            # Recognize speech with retry logic
            max_retries = 2
            text = None
            
            for retry in range(max_retries):
                try:
                    with sr.AudioFile(chunk_file) as source:
                        # Adjust for ambient noise in this chunk (longer duration for better accuracy)
                        recognizer.adjust_for_ambient_noise(source, duration=1.0)
                        # Record with better settings
                        audio_data = recognizer.record(source)
                
                    # Try Google Speech Recognition with optimized settings
                    # Use English language
                    try:
                        text = recognizer.recognize_google(
                            audio_data, 
                            language="en-US",  # English (US)
                            show_all=False
                        )
                        
                        if text and len(text.strip()) >= 3:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): SUCCESS - Recognized text: '{text}'")
                            break  # Success, exit retry loop
                        else:
                            if retry < max_retries - 1:
                                print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s) retry {retry+1}: Got empty/short text, retrying...")
                                continue
                            else:
                                print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): NOT DETECTED - Text too short or empty after {max_retries} attempts")
                                failed_chunks += 1
                                text = None
                                break  # Exit retry loop
                            
                    except sr.UnknownValueError:
                        if retry < max_retries - 1:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s) retry {retry+1}: Could not understand, retrying...")
                            continue
                        else:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): NOT DETECTED - Could not understand audio after {max_retries} attempts (no speech detected or unclear)")
                            failed_chunks += 1
                            text = None
                            break  # Exit retry loop
                    except sr.RequestError as e:
                        if retry < max_retries - 1:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s) retry {retry+1}: Service error, retrying...")
                            time.sleep(1)  # Wait before retry
                            continue
                        else:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): ERROR - Google Speech Recognition service error: {str(e)}")
                            failed_chunks += 1
                            text = None
                            break  # Exit retry loop
                    except Exception as e:
                        if retry < max_retries - 1:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s) retry {retry+1}: Error, retrying...")
                            continue
                        else:
                            print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): ERROR - Unexpected error during recognition: {str(e)}")
                            failed_chunks += 1
                            text = None
                            break  # Exit retry loop
                    
                except Exception as e:
                    if retry < max_retries - 1:
                        print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s) retry {retry+1}: Processing error, retrying...")
                        continue
                    else:
                        print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): ERROR - Error processing chunk: {str(e)}")
                        failed_chunks += 1
                        text = None
                        break  # Exit retry loop on final failure
            
            # After retry loop, check if we got text and add it to subtitles
            if text and len(text.strip()) >= 3:
                # Calculate timing based on actual chunk start
                start_time = chunk_start_time
                end_time = min(chunk_start_time + (len(chunk) / 1000), len(normalized_audio) / 1000)
                
                subtitle = pysrt.SubRipItem(
                    index=len(subtitles) + 1,
                    start=pysrt.SubRipTime(seconds=start_time),
                    end=pysrt.SubRipTime(seconds=end_time),
                    text=text
                )
                subtitles.append(subtitle)
                successful_chunks += 1
                print(f"Chunk {i+1} (time {start_time:.2f}s - {end_time:.2f}s): ADDED TO SUBTITLES - '{text}'")
            elif text is None:
                # Text is None means it failed
                print(f"Chunk {i+1} (time {chunk_start_time:.2f}s - {chunk_end_time:.2f}s): NOT ADDED - No text recognized")
            
            # Clean up the chunk file
            try:
                os.remove(chunk_file)
            except:
                pass
        
        print(f"Recognition complete: {successful_chunks} successful, {failed_chunks} failed chunks")
        print(f"Total segments processed: {len(chunks)}")
        print(f"Success rate: {(successful_chunks/len(chunks)*100):.1f}%")
        
        # Clean up normalized audio
        try:
            os.remove(normalized_audio_path)
        except:
            pass
        
        # Save the subtitles to a file
        srt_content = '\n'.join([str(sub) for sub in subtitles])
        
        # Check if we have any subtitles
        if not srt_content or len(srt_content.strip()) == 0:
            print("WARNING: No subtitles were generated - srt_content is empty!")
            print(f"Total chunks processed: {len(chunks)}, Successful: {successful_chunks}, Failed: {failed_chunks}")
            
            # Don't create a subtitle file with error message
            # Instead, mark as failed with detailed error message
            if failed_chunks == len(chunks):
                error_msg = (
                    "No speech detected in video. Please check: "
                    "Video has audio track, Audio is clear and audible, "
                    "Internet connection is available for speech recognition"
                )
            else:
                error_msg = "Partial recognition failed. Some audio chunks could not be processed."
            
            # Set status to failed instead of creating fake subtitle file
            video_upload.status = 'failed'
            video_upload.error_message = error_msg
            video_upload.save()
            raise Exception(error_msg)
        
        print(f"Generated subtitle content length: {len(srt_content)} characters")
        print(f"Number of subtitle entries: {len(subtitles)}")
        
        # Create a temporary SRT file
        temp_srt_path = os.path.join(temp_dir, 'subtitles.srt')
        with open(temp_srt_path, 'w', encoding='utf-8') as srt_file:
            srt_file.write(srt_content)
        
        # Verify the file was written correctly
        if os.path.getsize(temp_srt_path) == 0:
            raise Exception("Failed to write subtitle file - file is empty after writing")
        
        # Save the SRT file to the model
        with open(temp_srt_path, 'rb') as srt_file:
            # Get the original video filename without extension
            video_filename = os.path.basename(video_upload.video_file.name)
            base_filename = os.path.splitext(video_filename)[0]
            
            # Save the subtitle file
            subtitle_filename = f"{base_filename}.srt"
            video_upload.subtitle_file.save(subtitle_filename, ContentFile(srt_file.read()))
        
        # Update the model status
        video_upload.status = 'completed'
        video_upload.save()
        
        # Clean up temporary files
        os.remove(temp_audio_path)
        os.remove(temp_srt_path)
        os.rmdir(temp_dir)
        
    except Exception as e:
        # Handle errors
        import traceback
        error_traceback = traceback.format_exc()
        error_message = str(e)
        
        print(f"ERROR in generate_subtitles:")
        print(f"Error message: {error_message}")
        print(f"Traceback:\n{error_traceback}")
        
        video_upload.status = 'failed'
        video_upload.error_message = error_message
        video_upload.save()
        
        # Clean up any temporary files that might have been created
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            try:
                for file in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, file))
                    except:
                        pass
                try:
                    os.rmdir(temp_dir)
                except:
                    pass
            except Exception as cleanup_error:
                print(f"Error during cleanup: {str(cleanup_error)}")
        
        # Re-raise the exception for handling at the view level
        raise