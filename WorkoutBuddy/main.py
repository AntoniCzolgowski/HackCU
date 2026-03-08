import cv2
import time
from camera import Camera
from pose_detector import PoseDetector
from angle_utils import calculate_angle
from form_analyzer import FormAnalyzer
from rep_counter import RepCounter
from voice_feedback import VoiceFeedback

def main():
    # Initialize Core Components
    print("Initializing components...")
    cam = Camera(0)
    
    # Fast setup for MediaPipe to prioritize speed
    pose = PoseDetector(min_detection_confidence=0.5, min_tracking_confidence=0.5)
    
    analyzer = FormAnalyzer()
    counter = RepCounter(exercise="squat")
    tts = VoiceFeedback(cooldown=3.0) # Wait 3s between voice prompts
    
    print("Ready. Press 'q' to quit.")
    
    # Processing Loop
    while True:
        success, frame = cam.read_frame()
        if not success:
            print("Failed to read from camera. Exiting.")
            break
            
        # Optional: flip horizontally for a mirror effect
        frame = cv2.flip(frame, 1)
        h, w, c = frame.shape
        
        # 1. Pose Estimation & Landmark Extraction
        frame, landmarks_raw = pose.find_pose(frame, draw=True)
        landmarks = pose.extract_landmarks(w, h)
        
        # 2. Application Logic (If person is visible)
        cv2.putText(frame, "AI Workout Assistant - Squats", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
        if all(k in landmarks for k in ['left_hip', 'left_knee', 'left_ankle', 'left_shoulder']):
            # We use the left side for demonstration; in a real app you might use the side mostly facing the camera
            
            # 3. Feature Computation
            knee_angle = calculate_angle(
                landmarks['left_hip'], 
                landmarks['left_knee'], 
                landmarks['left_ankle']
            )
            
            hip_angle = calculate_angle(
                landmarks['left_shoulder'], 
                landmarks['left_hip'], 
                landmarks['left_knee']
            )
            
            # Back angle approximating using shoulder to hip vs straight vertical line
            # This is a simple heuristic: shoulder x vs hip x. Alternatively standard angle:
            # Here we just use hip angle as a proxy for back angle for simplicity in this MVP
            back_angle = hip_angle 
            
            # Real-time visual debugging
            cv2.putText(frame, f"Knee: {int(knee_angle)}", (landmarks['left_knee'][0] + 10, landmarks['left_knee'][1]), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
            # 4. Form Analysis
            is_good, feedback_msg = analyzer.check_squat_form(knee_angle, hip_angle, back_angle)
            
            # 5. Rep Counter
            is_new_rep = counter.update(knee_angle)
            
            # 6. Feedback Engine
            form_text = "Form: GOOD" if is_good else f"Form: {feedback_msg}"
            form_color = (0, 255, 0) if is_good else (0, 0, 255)
            
            cv2.putText(frame, form_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, form_color, 2)
            cv2.putText(frame, f"Reps: {counter.count}", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
            cv2.putText(frame, f"State: {counter.state.upper()}", (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            if is_new_rep:
                # Force feedback on rep complete over bad form warnings
                tts.speak(f"Good rep. That's {counter.count}.", force=True)
            elif not is_good and feedback_msg:
                # Speak correction if bad form & off cooldown
                tts.speak(feedback_msg)
        else:
            cv2.putText(frame, "Please step into frame", (w//2 - 100, h//2), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # 7. Render Overlay Display
        cv2.imshow("Workout Assistant", frame)
        
        # Exit condition
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cam.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
