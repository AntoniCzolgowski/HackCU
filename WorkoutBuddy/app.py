import cv2
import time
import random
import pandas as pd
import streamlit as st
import glob
import plotly.graph_objects as go
import numpy as np
from collections import Counter
from dotenv import load_dotenv

# Load environment variables (API Keys) securely from .env
load_dotenv()

from camera import Camera
from pose_detector import PoseDetector
from angle_utils import calculate_angle
from form_analyzer import FormAnalyzer
from rep_counter import RepCounter
from fatigue_analyzer import FatigueAnalyzer
from voice_feedback import VoiceFeedback
from voice_assistant import VoiceAssistant
from database import DatabaseManager

st.set_page_config(page_title="Workout Assistant", layout="wide")

if 'db' not in st.session_state:
    st.session_state.db = DatabaseManager()
# We wait to initialize TTS/Assistant until after we know the Goggins mode state.


def form_band(score):
    if score >= 90:
        return "GREEN", "#16a34a"
    if score >= 70:
        return "YELLOW", "#eab308"
    return "RED", "#dc2626"


def dominant_fatigue_trigger(signals):
    if not signals:
        return "general fatigue"
    label_map = {
        "rep_slowdown": "rep speed dropping",
        "depth_loss": "squat depth getting shallow",
        "form_breakdown": "form breaking down",
        "pause_time": "resting too long between reps",
    }
    key = max(signals, key=signals.get)
    return label_map.get(key, "general fatigue")


def build_adaptive_line(assistant, exercise, rep_count, fatigue_info):
    score = fatigue_info["score"]
    level = fatigue_info["level"]
    trigger = dominant_fatigue_trigger(fatigue_info.get("signals", {}))

    low_lines = [
        f"Good rep. Keep going. That's {rep_count}.",
        f"Nice depth. Rep {rep_count}.",
        f"Strong pace. Keep it smooth.",
    ]
    medium_lines = [
        f"Stay tight. Two more clean reps.",
        f"You're slowing a bit. Lock your brace and keep driving.",
        f"Good fight. Keep your depth honest.",
    ]

    if level == "high":
        return assistant.generate_trash_talk(
            exercise=f"{exercise}s",
            fatigue_score=score,
            trigger=trigger,
        )
    if level == "medium":
        return random.choice(medium_lines)
    return random.choice(low_lines)

def render_home_screen():
    st.title("💪 AI Workout Assistant")
    st.markdown("---")

    if 'last_workout_summary' in st.session_state:
        s = st.session_state.last_workout_summary
        st.success(
            f"Workout Summary | {s['exercise']}: {s['reps']} reps | "
            f"Average Depth: {s['avg_depth']}° | Form Score: {s['avg_form_score']}% | "
            f"Most Common Error: {s['most_common_error']}"
        )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Your Workout History")
        workouts = st.session_state.db.get_all_workouts()
        
        if workouts:
            df = pd.DataFrame(workouts)
            for col in ["avg_depth", "avg_form_score", "most_common_error"]:
                if col not in df.columns:
                    df[col] = None
            df = df[
                [
                    'date', 'exercise_name', 'weight', 'reps_completed', 'duration_seconds',
                    'avg_depth', 'avg_form_score', 'most_common_error'
                ]
            ]
            df.columns = [
                "Date", "Exercise", "Weight (lbs)", "Reps", "Duration (s)",
                "Avg Depth (deg)", "Form Score (%)", "Most Common Error"
            ]
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.info("No workouts logged yet. Time to get moving!")
            
    with col2:
        st.subheader("Quick Actions")
        
        with st.form("setup_form"):
            st.write("Start a new session")
            exercise = st.selectbox("Exercise", ["Squat", "Pushup", "Deadlift"])
            weight = st.number_input("Added Weight (lbs)", min_value=0.0, value=0.0, step=5.0)
            
            camera_id = st.selectbox("Camera Device ID", [0, 1, 2, 3], index=0)
            camera_zoom = st.slider("Digital Zoom", min_value=1.0, max_value=3.0, value=1.0, step=0.1)
            save_log = st.checkbox("Save to Log after completion", value=True)
            goggins_mode = st.toggle("🔥 David Goggins Mode (Intense Motivation)")
            
            submitted = st.form_submit_button("Start Camera Session", type="primary", width="stretch")
            
            if submitted:
                st.session_state.current_exercise = exercise.lower()
                st.session_state.current_weight = weight
                st.session_state.camera_id = int(camera_id)
                st.session_state.camera_zoom = float(camera_zoom)
                st.session_state.save_log = save_log
                
                # Initialize Voice drivers with intended mode
                st.session_state.tts = VoiceFeedback(cooldown=4.0, goggins_mode=goggins_mode)
                st.session_state.assistant = VoiceAssistant(st.session_state.tts, goggins_mode=goggins_mode)
                
                st.session_state.app_mode = "tracker"
                st.rerun()

def get_guide_image(exercise):
    mapping = {
        "squat": "assets/squat_guide*.png",
        "pushup": "assets/pushup_guide*.png",
        "deadlift": "assets/deadlift_guide*.png"
    }
    pattern = mapping.get(exercise)
    if not pattern: return None
    files = glob.glob(pattern)
    if files:
        # Return the most recently modified matching image to ensure we use the updated overlays
        import os
        return max(files, key=os.path.getmtime)
    return None


def _lerp(p1, p2, t):
    return (int(p1[0] + (p2[0] - p1[0]) * t), int(p1[1] + (p2[1] - p1[1]) * t))


def build_stickman_guide(exercise, phase=0.0):
    """
    Draw an animated side-profile stickman showing ideal form.
    phase should be in [0, 1], where 0=top/start, 1=bottom/end range.
    """
    canvas = np.full((420, 320, 3), 255, dtype=np.uint8)
    color = (30, 30, 30)
    accent = (0, 140, 255)
    thick = 4

    # Floor line
    cv2.line(canvas, (20, 360), (300, 360), (180, 180, 180), 2)

    if exercise == "squat":
        top = {
            "head": (120, 80),
            "shoulder": (120, 122),
            "hip": (130, 190),
            "knee": (138, 270),
            "ankle": (140, 340),
            "toe": (178, 340),
            "elbow": (150, 145),
            "wrist": (175, 150),
        }
        bottom = {
            "head": (120, 95),
            "shoulder": (120, 140),
            "hip": (140, 200),
            "knee": (160, 275),
            "ankle": (145, 340),
            "toe": (180, 340),
            "elbow": (160, 170),
            "wrist": (185, 180),
        }
        pts = {k: _lerp(top[k], bottom[k], phase) for k in top}
        label = "Perfect Squat: neutral torso, knee tracks toes, full depth"
    elif exercise == "pushup":
        top = {
            "head": (90, 160),
            "shoulder": (118, 178),
            "hip": (185, 184),
            "knee": (235, 188),
            "ankle": (280, 192),
            "toe": (295, 192),
            "elbow": (138, 198),
            "wrist": (118, 230),
        }
        bottom = {
            "head": (90, 180),
            "shoulder": (120, 195),
            "hip": (185, 205),
            "knee": (235, 210),
            "ankle": (280, 215),
            "toe": (295, 215),
            "elbow": (145, 230),
            "wrist": (125, 255),
        }
        pts = {k: _lerp(top[k], bottom[k], phase) for k in top}
        label = "Perfect Pushup: straight body line, chest lowered, tight core"
    else:  # deadlift
        top = {
            "head": (95, 82),
            "shoulder": (100, 124),
            "hip": (122, 198),
            "knee": (152, 262),
            "ankle": (160, 340),
            "toe": (196, 340),
            "elbow": (130, 145),
            "wrist": (135, 225),
        }
        bottom = {
            "head": (105, 100),
            "shoulder": (110, 145),
            "hip": (145, 205),
            "knee": (172, 268),
            "ankle": (168, 340),
            "toe": (198, 340),
            "elbow": (145, 180),
            "wrist": (148, 260),
        }
        pts = {k: _lerp(top[k], bottom[k], phase) for k in top}
        label = "Perfect Deadlift: flat back, bar close, hips and chest rise together"

    # Head
    cv2.circle(canvas, pts["head"], 20, color, thick)
    # Torso + legs
    cv2.line(canvas, pts["shoulder"], pts["hip"], color, thick)
    cv2.line(canvas, pts["hip"], pts["knee"], color, thick)
    cv2.line(canvas, pts["knee"], pts["ankle"], color, thick)
    cv2.line(canvas, pts["ankle"], pts["toe"], color, thick)
    # Arm
    cv2.line(canvas, pts["shoulder"], pts["elbow"], color, thick)
    cv2.line(canvas, pts["elbow"], pts["wrist"], color, thick)

    # Joint markers
    for key in ["shoulder", "hip", "knee", "ankle"]:
        cv2.circle(canvas, pts[key], 7, accent, -1)

    # Angle cues
    cv2.putText(canvas, "Back neutral", (175, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.45, accent, 1)
    cv2.putText(canvas, "Depth target", (185, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.45, accent, 1)

    # Wrap-ish label (two lines max for readability)
    label1 = label[:52]
    label2 = label[52:]
    cv2.putText(canvas, label1, (12, 390), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 80, 80), 1)
    if label2:
        cv2.putText(canvas, label2, (12, 408), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (80, 80, 80), 1)

    return cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)


def animated_guide_html(exercise):
    """
    Inline SVG animation avoids Streamlit media-file churn from per-frame st.image updates.
    """
    ex = (exercise or "squat").lower()
    if ex == "pushup":
        note = "Perfect Pushup: straight body line, chest lowered, tight core"
        body_y = ("145;155;145")
    elif ex == "deadlift":
        note = "Perfect Deadlift: flat back, bar close, hips and chest rise together"
        body_y = ("120;145;120")
    else:
        note = "Perfect Squat: neutral torso, knee tracks toes, full depth"
        body_y = ("122;140;122")

    return f"""
    <div style="border:1px dashed #cbd5e1;border-radius:10px;padding:8px;background:#fff;">
      <svg viewBox="0 0 320 320" width="100%" role="img" aria-label="animated form guide">
        <line x1="10" y1="300" x2="310" y2="300" stroke="#cbd5e1" stroke-width="2"/>
        <g>
          <circle cx="120" cy="80" r="18" stroke="#1f2937" stroke-width="4" fill="none">
            <animate attributeName="cy" dur="1.5s" repeatCount="indefinite" values="80;95;80" />
          </circle>
          <line x1="120" y1="{body_y.split(';')[0]}" x2="140" y2="200" stroke="#1f2937" stroke-width="5">
            <animate attributeName="y1" dur="1.5s" repeatCount="indefinite" values="{body_y}" />
          </line>
          <line x1="140" y1="200" x2="160" y2="275" stroke="#1f2937" stroke-width="5"/>
          <line x1="160" y1="275" x2="145" y2="340" stroke="#1f2937" stroke-width="5"/>
          <line x1="145" y1="340" x2="180" y2="340" stroke="#1f2937" stroke-width="5"/>
          <line x1="120" y1="140" x2="160" y2="170" stroke="#1f2937" stroke-width="5">
            <animate attributeName="y1" dur="1.5s" repeatCount="indefinite" values="140;160;140" />
            <animate attributeName="y2" dur="1.5s" repeatCount="indefinite" values="170;190;170" />
          </line>
          <line x1="160" y1="170" x2="185" y2="180" stroke="#1f2937" stroke-width="5">
            <animate attributeName="y1" dur="1.5s" repeatCount="indefinite" values="170;190;170" />
            <animate attributeName="y2" dur="1.5s" repeatCount="indefinite" values="180;200;180" />
          </line>
        </g>
        <text x="180" y="130" fill="#0284c7" font-size="12">Back neutral</text>
        <text x="182" y="285" fill="#0284c7" font-size="12">Depth target</text>
      </svg>
      <div style="font-size:0.85rem;color:#475569;">{note}</div>
    </div>
    """

def render_tracker_screen():
    col_main, col_guide = st.columns([2, 1])
    
    with col_main:
        st.title(f"Active Workout: {st.session_state.current_exercise.capitalize()}")
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        rep_metric = m_col1.empty()
        form_metric = m_col2.empty()
        fatigue_metric = m_col3.empty()
        last_rep_metric = m_col4.empty()
        
        rep_metric.metric("Reps Completed", 0)
        form_metric.metric("FORM SCORE", "100%")
        fatigue_metric.metric("Fatigue Level", "LOW", "0%")
        last_rep_metric.metric("Last Rep Rating", "N/A")
        
        if st.button("🛑 End Workout & Save", type="primary"):
             st.session_state.tracking_active = False
             time.sleep(0.5)
             st.rerun()
             
        frame_placeholder = st.empty()
        st.caption("Please ensure your full side profile (Shoulder, Hip, Knee, Ankle) is visible.")

    with col_guide:
        st.subheader("Target Form Guidelines")
        st.write("Expected camera pose (ideal form):")
        guide_placeholder = st.empty()
        guide_placeholder.markdown(animated_guide_html(st.session_state.current_exercise), unsafe_allow_html=True)
            
        st.subheader("Live Form Rating 📈")
        gauge_placeholder = st.empty()

    if getattr(st.session_state, 'tracking_initialized', False) is False:
        try:
            st.session_state.pose = PoseDetector(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        except Exception as e:
            st.error(f"Pose engine failed to initialize: {e}")
            st.info("Fix: deploy with Python 3.11 (add `.python-version` with `3.11`) and redeploy.")
            if st.button("Return Home"):
                st.session_state.app_mode = "home"
                st.rerun()
            return
        st.session_state.analyzer = FormAnalyzer()
        st.session_state.counter = RepCounter(exercise=st.session_state.current_exercise)
        st.session_state.fatigue = FatigueAnalyzer()
        st.session_state.rep_scores = []
        st.session_state.error_counter = Counter()
        st.session_state.last_fatigue_info = {
            "score": 0.0,
            "level": "low",
            "signals": {},
        }
        
        try:
             st.session_state.camera = Camera(st.session_state.camera_id, zoom_factor=st.session_state.camera_zoom)
        except Exception as e:
             st.error(f"Cannot access Camera Unit {st.session_state.camera_id}.")
             if st.button("Return Home"):
                 st.session_state.app_mode = "home"
                 st.rerun()
             return

        # We already initialized the VoiceAssistant inside the Setup UI form based on the Goggins toggle
             
        # Start background STT listening
        st.session_state.assistant.start_listening()

        st.session_state.tts.speak("Step into the frame to calibrate.", force=True)
        st.session_state.tracking_initialized = True
        st.session_state.tracking_active = True
        st.session_state.start_time = time.time()
        
        # New Calibration State
        st.session_state.calibrated = False
        st.session_state.calibration_hold_start = 0.0
        st.session_state.last_calib_msg = 0.0
        
    camera = st.session_state.camera
    pose = st.session_state.pose
    analyzer = st.session_state.analyzer
    counter = st.session_state.counter
    fatigue = st.session_state.fatigue
    tts = st.session_state.tts
    assistant = st.session_state.assistant
    
    while getattr(st.session_state, 'tracking_active', False):
        try:
             success, frame = camera.read_frame()
        except:
             success = False
             
        if not success:
            st.error("Lost connection to webcam.")
            break
            
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        
        frame, landmarks_raw = pose.find_pose(frame, draw=True)
        landmarks = pose.extract_landmarks(w, h)
        
        # --- Calibration Phase ---
        if not getattr(st.session_state, 'calibrated', False):
            is_valid, calib_msg = analyzer.check_calibration(
                landmarks,
                w,
                h,
                st.session_state.current_exercise,
            )
            
            cv2.putText(frame, "CALIBRATING: " + calib_msg, (30, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        
            current_time = time.time()
            if not is_valid:
                st.session_state.calibration_hold_start = 0.0
                if current_time - getattr(st.session_state, 'last_calib_msg', 0.0) > 4.0:
                    tts.speak(calib_msg, feedback_type="correction", force=True)
                    st.session_state.last_calib_msg = current_time
            else:
                if st.session_state.calibration_hold_start == 0.0:
                     st.session_state.calibration_hold_start = current_time
                elif current_time - st.session_state.calibration_hold_start > 2.0:
                     st.session_state.calibrated = True
                     tts.speak("Perfect position. Let's begin!", force=True)
                     
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB", width="stretch")
            continue
        # --- End Calibration Phase ---
        
        if st.session_state.current_exercise == "squat" and all(k in landmarks for k in ['left_hip', 'left_knee', 'left_ankle', 'left_shoulder']):
            knee_angle = calculate_angle(landmarks['left_hip'], landmarks['left_knee'], landmarks['left_ankle'])
            
            # Proper back angle: angle between (Shoulder-Hip) and an absolute Vertical line
            vertical_pt = [landmarks['left_hip'][0], landmarks['left_hip'][1] - 100]
            back_angle = calculate_angle(landmarks['left_shoulder'], landmarks['left_hip'], vertical_pt)
            
            cv2.putText(frame, f"Knee: {int(knee_angle)}", (landmarks['left_knee'][0] + 10, landmarks['left_knee'][1]), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
            # Real-time visual tracking (only based on posture)
            realtime_score = analyzer.get_realtime_score(back_angle)
            band_text, band_color = form_band(realtime_score)
            
            # Live Voice Feedback: Torso Posture
            if back_angle > 45:
                tts.speak("Keep your torso upright", feedback_type="correction")
                
            # Core logic: evaluate dynamically over the whole rep
            is_new_rep, is_bottom = counter.update_squat(knee_angle, back_angle)

            # Continuously raise fatigue score if inter-rep pauses get long.
            current_pause = 0.0
            if counter.rep_end_time > 0:
                current_pause = time.time() - counter.rep_end_time
            st.session_state.last_fatigue_info = fatigue.update_live_pause(current_pause)
            
            # Live Voice Feedback: Squat Depth Check
            if is_bottom:
                if counter._current_min_knee > 100:
                    tts.speak("Go lower", feedback_type="correction")
            
            if is_new_rep:
                # The rep just finished. Evaluate exactly what went wrong for the final scorecard.
                is_good, feedback_msg, rep_score = analyzer.evaluate_squat_rep(counter.last_rep_min_knee, counter.last_rep_max_back)
                st.session_state.last_rep_score = rep_score
                st.session_state.last_rep_msg = feedback_msg if feedback_msg else "Perfect!"
                st.session_state.rep_scores.append(rep_score)
                if feedback_msg:
                    for err in feedback_msg.split(" and "):
                        st.session_state.error_counter[err.strip()] += 1

                st.session_state.last_fatigue_info = fatigue.update_rep(
                    rep_duration=counter.rep_durations[-1],
                    rep_depth=counter.last_rep_min_knee,
                    max_back_angle=counter.last_rep_max_back,
                    pause_duration=counter.last_pause_duration,
                )
                adaptive_line = build_adaptive_line(
                    assistant=assistant,
                    exercise=st.session_state.current_exercise,
                    rep_count=counter.count,
                    fatigue_info=st.session_state.last_fatigue_info,
                )
                tts.speak(adaptive_line, feedback_type="motivation")
                    
            # Pull metrics
            rep_metric.metric("Reps Completed", counter.count)
            form_metric.metric("FORM SCORE", f"{realtime_score}%", band_text)
            fatigue_pct = int(st.session_state.last_fatigue_info["score"] * 100)
            fatigue_level = st.session_state.last_fatigue_info["level"].upper()
            fatigue_metric.metric("Fatigue Level", fatigue_level, f"{fatigue_pct}%")
            
            last_score = getattr(st.session_state, 'last_rep_score', 0)
            last_msg = getattr(st.session_state, 'last_rep_msg', "Pending...")
            if last_score > 0:
                last_rep_metric.metric(f"Last Rep Rating: {counter.count}", f"{last_score}/100", delta=last_msg, delta_color="off")
            
            # Plotly Gauge UI update based on real-time posture
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = realtime_score,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "FORM SCORE"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': band_color},
                    'steps' : [
                        {'range': [0, 70], 'color': "#fee2e2"},
                        {'range': [70, 90], 'color': "#fef9c3"},
                        {'range': [90, 100], 'color': "#dcfce7"},
                    ]
                }
            ))
            fig.update_layout(height=180, margin=dict(l=10, r=10, t=30, b=10))
            gauge_placeholder.plotly_chart(fig, width="stretch", key=f"gauge_{time.time()}")

        elif st.session_state.current_exercise == "pushup" and all(
            k in landmarks for k in ['left_shoulder', 'left_elbow', 'left_wrist', 'left_hip', 'left_knee']
        ):
            elbow_angle = calculate_angle(
                landmarks['left_shoulder'],
                landmarks['left_elbow'],
                landmarks['left_wrist']
            )
            body_line_angle = calculate_angle(
                landmarks['left_shoulder'],
                landmarks['left_hip'],
                landmarks['left_knee']
            )

            cv2.putText(frame, f"Elbow: {int(elbow_angle)}", (landmarks['left_elbow'][0] + 10, landmarks['left_elbow'][1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Horizontal pushup posture is correct when shoulder-hip-knee is near a straight line (180).
            realtime_score = analyzer.get_pushup_realtime_score(body_line_angle)
            band_text, band_color = form_band(realtime_score)

            if abs(180 - body_line_angle) > 20:
                tts.speak("Keep your torso straight", feedback_type="correction")

            is_new_rep, is_bottom = counter.update_pushup(elbow_angle, body_line_angle)

            current_pause = 0.0
            if counter.rep_end_time > 0:
                current_pause = time.time() - counter.rep_end_time
            st.session_state.last_fatigue_info = fatigue.update_live_pause(current_pause)

            if is_bottom and counter._current_min_elbow > 95:
                tts.speak("Go lower", feedback_type="correction")

            if is_new_rep:
                is_good, feedback_msg, rep_score = analyzer.evaluate_pushup_rep(
                    counter.last_rep_min_elbow,
                    counter.last_rep_max_back
                )
                st.session_state.last_rep_score = rep_score
                st.session_state.last_rep_msg = feedback_msg if feedback_msg else "Perfect!"
                st.session_state.rep_scores.append(rep_score)
                if feedback_msg:
                    for err in feedback_msg.split(" and "):
                        st.session_state.error_counter[err.strip()] += 1

                st.session_state.last_fatigue_info = fatigue.update_rep(
                    rep_duration=counter.rep_durations[-1],
                    rep_depth=counter.last_rep_min_elbow,
                    max_back_angle=counter.last_rep_max_back,
                    pause_duration=counter.last_pause_duration,
                )
                adaptive_line = build_adaptive_line(
                    assistant=assistant,
                    exercise=st.session_state.current_exercise,
                    rep_count=counter.count,
                    fatigue_info=st.session_state.last_fatigue_info,
                )
                tts.speak(adaptive_line, feedback_type="motivation")

            rep_metric.metric("Reps Completed", counter.count)
            form_metric.metric("FORM SCORE", f"{realtime_score}%", band_text)
            fatigue_pct = int(st.session_state.last_fatigue_info["score"] * 100)
            fatigue_level = st.session_state.last_fatigue_info["level"].upper()
            fatigue_metric.metric("Fatigue Level", fatigue_level, f"{fatigue_pct}%")

            last_score = getattr(st.session_state, 'last_rep_score', 0)
            last_msg = getattr(st.session_state, 'last_rep_msg', "Pending...")
            if last_score > 0:
                last_rep_metric.metric(f"Last Rep Rating: {counter.count}", f"{last_score}/100", delta=last_msg, delta_color="off")

            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=realtime_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "FORM SCORE"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': band_color},
                    'steps': [
                        {'range': [0, 70], 'color': "#fee2e2"},
                        {'range': [70, 90], 'color': "#fef9c3"},
                        {'range': [90, 100], 'color': "#dcfce7"},
                    ]
                }
            ))
            fig.update_layout(height=180, margin=dict(l=10, r=10, t=30, b=10))
            gauge_placeholder.plotly_chart(fig, width="stretch", key=f"gauge_{time.time()}")
            
        else:
            cv2.putText(frame, "Please step into frame fully", (w//2 - 150, h//2), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                        
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb, channels="RGB", width="stretch")
        
    if not getattr(st.session_state, 'tracking_active', False) and getattr(st.session_state, 'tracking_initialized', False):
        camera.release()
        if 'assistant' in st.session_state:
             st.session_state.assistant.stop_listening()

        avg_depth = int(sum(counter.rep_depths) / len(counter.rep_depths)) if counter.rep_depths else 0
        avg_form = int(sum(st.session_state.rep_scores) / len(st.session_state.rep_scores)) if st.session_state.rep_scores else 0
        common_error = "None"
        if st.session_state.error_counter:
            common_error = st.session_state.error_counter.most_common(1)[0][0]

        if st.session_state.save_log:
             duration = int(time.time() - st.session_state.start_time)
             st.session_state.db.add_workout(
                 st.session_state.current_exercise.capitalize(),
                 st.session_state.current_weight,
                 counter.count,
                 duration,
                 avg_depth=avg_depth,
                 avg_form_score=avg_form,
                 most_common_error=common_error,
             )

        st.session_state.last_workout_summary = {
            "exercise": st.session_state.current_exercise.capitalize(),
            "reps": counter.count,
            "avg_depth": avg_depth,
            "avg_form_score": avg_form,
            "most_common_error": common_error,
        }
             
        st.session_state.tracking_initialized = False
        st.session_state.app_mode = "home"
        st.rerun()

if 'app_mode' not in st.session_state:
    st.session_state.app_mode = "home"

if st.session_state.app_mode == "home":
    render_home_screen()
elif st.session_state.app_mode == "tracker":
    render_tracker_screen()
