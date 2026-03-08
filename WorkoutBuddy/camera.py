import cv2
from streamlit_webrtc import webrtc_streamer

class Camera:
    def __init__(self, camera_id=0, zoom_factor=1.0):
        self.camera_id = camera_id
        self.zoom_factor = zoom_factor
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
        except:
            self.cap = webrtc_streamer(key="camera")
        if not self.cap.isOpened():
            raise ValueError(f"Unable to open camera with ID {self.camera_id}")
            
    def set_zoom(self, zoom_factor):
        self.zoom_factor = float(zoom_factor)

    def read_frame(self):
        """Reads a frame from the camera, applying digital zoom if specified."""
        success, frame = self.cap.read()
        
        if success and self.zoom_factor > 1.0:
            h, w = frame.shape[:2]
            
            # Calculate new dimensions for the crop based on zoom
            new_h, new_w = int(h / self.zoom_factor), int(w / self.zoom_factor)
            
            # Get bounding box for center crop
            y1 = (h - new_h) // 2
            y2 = y1 + new_h
            x1 = (w - new_w) // 2
            x2 = x1 + new_w
            
            # Crop the frame and resize it back to the original dimensions
            cropped = frame[y1:y2, x1:x2]
            frame = cv2.resize(cropped, (w, h))
            
        return success, frame

    def release(self):
        """Releases the camera resource"""
        if self.cap.isOpened():
            self.cap.release()

    def __del__(self):
        self.release()
