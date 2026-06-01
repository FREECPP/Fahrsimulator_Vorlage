def print_mediapipe_result(results):
    if not results.multi_face_landmarks:
        print("x Kein Gesicht erkannt")
        return

    print("✓ Gesicht erkannt!")

    landmarks = results.multi_face_landmarks[0]

    print(f"  Landmarks erkannt: {len(landmarks.landmark)}")
    nose_tip = landmarks.landmark[1]
    left_eye = landmarks.landmark[33]
    right_eye = landmarks.landmark[263]

    print(f"  Nasenspitze Position: x={nose_tip.x:.3f}, y={nose_tip.y:.3f}, z={nose_tip.z:.3f}")
    print(f"  Linkes Auge: x={left_eye.x:.3f}, y={left_eye.y:.3f}")
    print(f"  Rechtes Auge: x={right_eye.x:.3f}, y={right_eye.y:.3f}")

def calculate_bounding_box(landmarks):
    x_coords = [lm.x for lm in landmarks.landmark]
    y_coords = [lm.y for lm in landmarks.landmark]

    print(f"  Gesicht Breite: {(max(x_coords) - min(x_coords)):.3f}")
    print(f"  Gesicht Höhe: {(max(y_coords) - min(y_coords)):.3f}")