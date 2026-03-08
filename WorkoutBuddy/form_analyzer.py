class FormAnalyzer:
    def __init__(self):
        pass

    def check_calibration(self, landmarks, frame_width, frame_height, exercise="squat"):
        """
        Checks if the user is in frame for the selected exercise.
        Returns (is_calibrated, instruction_message)
        """
        exercise = (exercise or "squat").lower()

        # Exercise-specific required joints.
        # Pushups are often filmed lower and can crop feet, so don't hard-require ankles.
        if exercise == "pushup":
            required = ['left_shoulder', 'left_elbow', 'left_wrist', 'left_hip', 'left_knee']
            preferred_optional = ['left_ankle']
        elif exercise == "deadlift":
            required = ['left_shoulder', 'left_hip', 'left_knee', 'left_ankle']
            preferred_optional = []
        else:  # squat
            required = ['left_shoulder', 'left_hip', 'left_knee', 'left_ankle']
            preferred_optional = []
        
        missing = [j for j in required if j not in landmarks]
        if missing:
            if 'left_ankle' in missing:
                return False, "Tilt the camera down or step back to show your lower body."
            if 'left_wrist' in missing and exercise == "pushup":
                return False, "Move back so your hands and elbows are visible."
            elif 'left_shoulder' in missing:
                return False, "Step back to show your upper body."
            else:
                return False, "Step back so your full side profile is in frame."

        # Bounding box checks
        all_x = [landmarks[j][0] for j in required]
        all_y = [landmarks[j][1] for j in required]

        # Include optional joints in framing checks only when visible.
        for joint in preferred_optional:
            if joint in landmarks:
                all_x.append(landmarks[joint][0])
                all_y.append(landmarks[joint][1])
        
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        
        margin_x = frame_width * (0.12 if exercise == "pushup" else 0.15)
        margin_y = frame_height * (0.03 if exercise == "pushup" else 0.05)
        
        instructions = []
        if min_x < margin_x:
            instructions.append("Step to your right")
        elif max_x > frame_width - margin_x:
            instructions.append("Step to your left")
            
        if min_y < margin_y:
            instructions.append("Tilt camera up")
        elif max_y > frame_height - margin_y:
            instructions.append("Step farther back")
            
        if instructions:
            return False, " and ".join(instructions)
            
        return True, "Perfect. Hold still."

    def evaluate_squat_rep(self, min_knee_angle, max_back_angle):
        """
        Evaluates a complete squat rep using the lowest/worst angles recorded during the movement.
        Returns a tuple: (is_good_form, feedback_message, score)
        """
        is_good = True
        feedback = []
        score = 100

        # Check depth (knee angle) - ideally around 90 or below for a full squat
        if min_knee_angle > 100:
            is_good = False
            feedback.append("Go lower")
            score -= min(40, (min_knee_angle - 100) * 1.5)
            
        # Check back posture (leaning forward relative to vertical)
        if max_back_angle > 45:
             is_good = False
             feedback.append("Keep your torso upright")
             score -= min(40, (max_back_angle - 45) * 1.5)

        # Normalize score
        score = max(0, int(score))

        feedback_msg = " and ".join(feedback) if feedback else ""

        return is_good, feedback_msg, score

    def evaluate_pushup_rep(self, min_elbow_angle, max_body_deviation):
        """
        Evaluates a complete pushup rep.
        min_elbow_angle: lower = deeper rep
        max_body_deviation: degrees away from straight plank line
        """
        is_good = True
        feedback = []
        score = 100

        if min_elbow_angle > 95:
            is_good = False
            feedback.append("Go lower")
            score -= min(40, (min_elbow_angle - 95) * 1.5)

        if max_body_deviation > 20:
            is_good = False
            feedback.append("Keep your torso straight")
            score -= min(40, (max_body_deviation - 20) * 1.8)

        score = max(0, int(score))
        feedback_msg = " and ".join(feedback) if feedback else ""
        return is_good, feedback_msg, score

    def get_realtime_score(self, back_angle):
        """
        Provides a real-time tracking score mostly based on current back posture.
        """
        score = 100
        if back_angle > 40:
             score -= min(100, (back_angle - 40) * 2.5)
        return max(0, int(score))

    def get_pushup_realtime_score(self, body_line_angle):
        """
        Pushup posture score based on how close shoulder-hip-knee is to a straight line (180).
        """
        deviation = abs(180 - body_line_angle)
        score = 100 - min(100, deviation * 3.0)
        return max(0, int(score))
