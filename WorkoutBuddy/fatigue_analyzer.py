from collections import deque


def _clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


class FatigueAnalyzer:
    def __init__(self):
        self.rep_durations = []
        self.rep_depths = []
        self.rep_back_angles = []
        self.current_score = 0.0
        self.recent_scores = deque(maxlen=6)

        self._latest_slowdown = 0.0
        self._latest_depth_loss = 0.0
        self._latest_form_breakdown = 0.0

    def _baseline(self, values, window=3):
        if not values:
            return None
        size = min(window, len(values))
        return sum(values[:size]) / size

    def _compute_score(self, pause_signal):
        # Weighted sum of all fatigue contributors.
        score = (
            0.40 * self._latest_slowdown
            + 0.25 * self._latest_depth_loss
            + 0.20 * self._latest_form_breakdown
            + 0.15 * pause_signal
        )
        # Smooth score to avoid mode-flapping.
        if self.recent_scores:
            score = 0.65 * self.recent_scores[-1] + 0.35 * score
        score = _clamp(score)
        self.recent_scores.append(score)
        self.current_score = score
        return score

    def level_from_score(self, score):
        if score < 0.3:
            return "low"
        if score < 0.7:
            return "medium"
        return "high"

    def update_rep(self, rep_duration, rep_depth, max_back_angle, pause_duration):
        self.rep_durations.append(float(rep_duration))
        self.rep_depths.append(float(rep_depth))
        self.rep_back_angles.append(float(max_back_angle))

        duration_baseline = self._baseline(self.rep_durations[:-1]) if len(self.rep_durations) > 1 else self.rep_durations[0]
        depth_baseline = self._baseline(self.rep_depths[:-1]) if len(self.rep_depths) > 1 else self.rep_depths[0]

        rep_slowdown = 0.0
        if duration_baseline and duration_baseline > 0:
            rep_slowdown = _clamp((rep_duration - duration_baseline) / (duration_baseline * 1.5))

        # For squats, larger minimum knee angle means shallower depth.
        depth_loss = 0.0
        if depth_baseline is not None:
            depth_loss = _clamp((rep_depth - depth_baseline) / 30.0)

        # Back angle above 45 is treated as increasing form collapse.
        form_breakdown = _clamp((max_back_angle - 45.0) / 25.0)
        pause_signal = _clamp((pause_duration - 3.0) / 4.0)

        self._latest_slowdown = rep_slowdown
        self._latest_depth_loss = depth_loss
        self._latest_form_breakdown = form_breakdown

        score = self._compute_score(pause_signal)
        level = self.level_from_score(score)

        signals = {
            "rep_slowdown": rep_slowdown,
            "depth_loss": depth_loss,
            "form_breakdown": form_breakdown,
            "pause_time": pause_signal,
        }
        return {"score": score, "level": level, "signals": signals}

    def update_live_pause(self, pause_duration):
        pause_signal = _clamp((pause_duration - 3.0) / 4.0)
        score = self._compute_score(pause_signal)
        level = self.level_from_score(score)
        signals = {
            "rep_slowdown": self._latest_slowdown,
            "depth_loss": self._latest_depth_loss,
            "form_breakdown": self._latest_form_breakdown,
            "pause_time": pause_signal,
        }
        return {"score": score, "level": level, "signals": signals}
