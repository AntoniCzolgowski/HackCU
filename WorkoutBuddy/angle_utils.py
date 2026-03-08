import numpy as np

def calculate_angle(a, b, c):
    """
    Calculate the angle between three points.
    Outputs angle in degrees.
    
    a: first point (x, y)
    b: mid point (x, y)
    c: last point (x, y)
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    
    # Calculate vectors
    ba = a - b
    bc = c - b
    
    # Calculate cosine of angle
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    
    # Handle floating point inaccuracies
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    
    # Calculate angle in radians then convert to degrees
    angle = np.arccos(cosine_angle)
    degrees = np.degrees(angle)
    
    return degrees
