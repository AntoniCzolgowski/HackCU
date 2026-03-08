import cv2
import mediapipe as mp

class PoseDetector:
    def __init__(self, min_detection_confidence=0.5, min_tracking_confidence=0.5):
        # MediaPipe package layout differs across builds/Python versions.
        # Prefer top-level solutions, then try known fallback modules.
        solutions = getattr(mp, "solutions", None)
        if solutions is None:
            try:
                from mediapipe.python import solutions as mp_solutions
                solutions = mp_solutions
            except Exception:
                solutions = None

        if solutions is None:
            raise RuntimeError(
                "MediaPipe Pose is unavailable in this Python environment. "
                "Use Python 3.11 on Streamlit Cloud and redeploy."
            )

        self.mp_pose = solutions.pose
        self.mp_drawing = solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def find_pose(self, frame, draw=True):
        """Process frame and return landmarks. Optionally draw landmarks on frame."""
        # Convert BGR to RGB
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.results = self.pose.process(img_rgb)
        
        if self.results.pose_landmarks and draw:
            self.mp_drawing.draw_landmarks(
                frame, 
                self.results.pose_landmarks, 
                self.mp_pose.POSE_CONNECTIONS
            )
            
        return frame, self.results.pose_landmarks

    def extract_landmarks(self, frame_width, frame_height):
        """Extracts significant landmarks into a dictionary of (x, y) coordinates."""
        landmarks_dict = {}
        
        if self.results.pose_landmarks:
            landmarks = self.results.pose_landmarks.landmark
            
            # Map MediaPipe landmarks to a dictionary with pixel coordinates
            keypoints = {
                'nose': self.mp_pose.PoseLandmark.NOSE,
                'left_shoulder': self.mp_pose.PoseLandmark.LEFT_SHOULDER,
                'right_shoulder': self.mp_pose.PoseLandmark.RIGHT_SHOULDER,
                'left_elbow': self.mp_pose.PoseLandmark.LEFT_ELBOW,
                'right_elbow': self.mp_pose.PoseLandmark.RIGHT_ELBOW,
                'left_wrist': self.mp_pose.PoseLandmark.LEFT_WRIST,
                'right_wrist': self.mp_pose.PoseLandmark.RIGHT_WRIST,
                'left_hip': self.mp_pose.PoseLandmark.LEFT_HIP,
                'right_hip': self.mp_pose.PoseLandmark.RIGHT_HIP,
                'left_knee': self.mp_pose.PoseLandmark.LEFT_KNEE,
                'right_knee': self.mp_pose.PoseLandmark.RIGHT_KNEE,
                'left_ankle': self.mp_pose.PoseLandmark.LEFT_ANKLE,
                'right_ankle': self.mp_pose.PoseLandmark.RIGHT_ANKLE
            }
            
            for name, kp in keypoints.items():
                lm = landmarks[kp.value]
                # Check visibility
                if lm.visibility > 0.5:
                    x, y = int(lm.x * frame_width), int(lm.y * frame_height)
                    landmarks_dict[name] = (x, y)
                    
        return landmarks_dict
