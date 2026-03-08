import time
class RepCounter:
    def __init__(self, exercise="squat"):
        self.exercise = exercise.lower()
        self.count = 0
        self.state = "up"
        
        # Track angles during the repetition for holistic post-rep analysis
        self.last_rep_min_knee = 180
        self.last_rep_max_back = 0
        
        self._current_min_knee = 180
        self._current_max_back = 0
        
        self.last_knee = 180
        self.direction = "stationary"
        self.last_direction = "stationary"
        
        # Tracking for Fatigue Analyzer
        self.rep_start_time = 0.0
        self.rep_end_time = 0.0
        self.last_pause_duration = 0.0
        
        self.rep_durations = []
        self.rep_depths = []
        self.last_rep_min_elbow = 180
        self._current_min_elbow = 180

    def update_squat(self, knee_angle, back_angle):
        """
        State machine that completes a rep when returning to standing.
        Also detects the 'bottom' of the squat turnaround for live feedback.
        Returns a tuple: (rep_completed, bottom_turnpoint)
        """
        rep_completed = False
        bottom_turnpoint = False
        
        # Determine instantaneous direction
        if knee_angle > self.last_knee + 1.5:
            self.direction = "up"
        elif knee_angle < self.last_knee - 1.5:
            self.direction = "down"

        if self.state == "up":
            if knee_angle < 140:
                self.state = "down"
                
                # Calculate pause time since previous rep finished
                if self.rep_end_time > 0:
                     self.last_pause_duration = time.time() - self.rep_end_time
                self.rep_start_time = time.time()
                
                # Reset trackers for a new rep
                self._current_min_knee = knee_angle
                self._current_max_back = back_angle
                
        elif self.state == "down":
            # Update trackers while in the hole
            if knee_angle < self._current_min_knee:
                self._current_min_knee = knee_angle
            if back_angle > self._current_max_back:
                self._current_max_back = back_angle
                
            # Detect turnaround (bottom of squat)
            if self.direction == "up" and self.last_direction == "down":
                bottom_turnpoint = True
                
            # Ascending back up to completion
            if knee_angle > 150:
                self.state = "up"
                self.count += 1
                
                self.rep_end_time = time.time()
                duration = self.rep_end_time - self.rep_start_time
                self.rep_durations.append(duration)
                self.rep_depths.append(self._current_min_knee)
                
                # Save trackers for Form Analyzer
                self.last_rep_min_knee = self._current_min_knee
                self.last_rep_max_back = self._current_max_back
                rep_completed = True

        self.last_direction = self.direction
        self.last_knee = knee_angle

        return rep_completed, bottom_turnpoint

    def update_pushup(self, elbow_angle, body_line_angle):
        """
        Pushup state machine.
        Returns a tuple: (rep_completed, bottom_turnpoint)
        """
        rep_completed = False
        bottom_turnpoint = False

        if elbow_angle > self.last_knee + 1.5:
            self.direction = "up"
        elif elbow_angle < self.last_knee - 1.5:
            self.direction = "down"

        if self.state == "up":
            if elbow_angle < 130:
                self.state = "down"
                if self.rep_end_time > 0:
                    self.last_pause_duration = time.time() - self.rep_end_time
                self.rep_start_time = time.time()
                self._current_min_elbow = elbow_angle
                self._current_max_back = max(0, 180 - body_line_angle)

        elif self.state == "down":
            if elbow_angle < self._current_min_elbow:
                self._current_min_elbow = elbow_angle

            body_deviation = max(0, 180 - body_line_angle)
            if body_deviation > self._current_max_back:
                self._current_max_back = body_deviation

            if self.direction == "up" and self.last_direction == "down":
                bottom_turnpoint = True

            if elbow_angle > 155:
                self.state = "up"
                self.count += 1
                self.rep_end_time = time.time()
                duration = self.rep_end_time - self.rep_start_time
                self.rep_durations.append(duration)
                self.rep_depths.append(self._current_min_elbow)
                self.last_rep_min_elbow = self._current_min_elbow
                self.last_rep_max_back = self._current_max_back
                rep_completed = True

        self.last_direction = self.direction
        self.last_knee = elbow_angle

        return rep_completed, bottom_turnpoint
