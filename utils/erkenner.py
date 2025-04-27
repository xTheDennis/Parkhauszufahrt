from ultralytics import YOLO
import cv2
import easyocr

# YOLOv8 Modell laden (z. B. für Nummernschilder trainiert)
model = YOLO("models/plate_detection.pt")

# EasyOCR initialisieren (deutsch)
reader = easyocr.Reader(['de'], gpu=False)

def detect_license_plate(frame, reader):
    results = model.predict(source=frame, conf=0.5, verbose=False)[0]

    for box in results.boxes.data.tolist():
        x1, y1, x2, y2, _, class_id = box
        if int(class_id) == 0:
            # Bereich ausschneiden
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            cropped = frame[y1:y2, x1:x2]

            # Bild aufhellen & vergrößern
            cropped = cv2.convertScaleAbs(cropped, alpha=1.6, beta=30)
            cropped = cv2.resize(cropped, None, fx=2.0, fy=2.0)

            # Graustufen
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)

            # Invertieren
            inverted = cv2.bitwise_not(gray)

            # --------- NEU: Schwellenwert setzen, um nur "sehr helle" Stellen zu behalten ---------
            _, binary = cv2.threshold(inverted, 200, 255, cv2.THRESH_BINARY)
            # Jetzt sind nur noch die weißen Buchstaben übrig

            # OCR auf das bereinigte Bild
            ocr_results = reader.readtext(binary)

            if ocr_results:
                # Blöcke nach X-Position sortieren und zusammenfügen
                ocr_results = sorted(ocr_results, key=lambda r: r[0][0][0])
                full_text = "".join([r[1] for r in ocr_results if r[2] > 0.3])

                return frame, binary, full_text

    return frame, None, None
