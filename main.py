import cv2
import easyocr
import pandas as pd
import os
import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
from threading import Thread
from queue import Queue

from utils.erkenner import detect_license_plate
from utils.helper import format_plate, validate_plate

# === Konfiguration ===
class Config:
    CSV_PATH = 'daten/kennzeichen.csv'
    LOG_PATH = 'daten/log.csv'
    SCREENSHOT_DIR = 'daten/screenshots'
    CAMERA_INDEX = 0
    REPEAT_DELAY = 120
    OCR_CONFIDENCE = 0.5

# === Hauptanwendung ===
class LicensePlateApp:
    def __init__(self, root):
        self.root = root
        self.setup_gui()
        self.setup_ocr()
        self.setup_data()
        self.setup_video()

    def setup_gui(self):
        self.root.title("🚗 Parkhaus Kennzeichen-Erkennung")
        self.root.geometry("1000x900")
        self.root.config(bg="#1e1e1e")

        self.video_label = tk.Label(self.root)
        self.video_label.pack(pady=10)

        self.plate_var = tk.StringVar()
        self.plate_label = tk.Label(
            self.root,
            textvariable=self.plate_var,
            font=("Courier New", 48, "bold"),
            fg="lime",
            bg="black"
        )
        self.plate_label.pack(pady=10)

        self.access_var = tk.StringVar()
        self.access_label = tk.Label(
            self.root,
            textvariable=self.access_var,
            font=("Courier New", 36, "bold"),
            width=30
        )
        self.access_label.pack(pady=10)

        self.cropped_preview_label = tk.Label(self.root)
        self.cropped_preview_label.pack(pady=10)

        self.listbox = tk.Listbox(self.root, height=6, width=30, font=("Courier New", 14))
        self.listbox.pack(pady=5)

        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Courier New", 12),
            fg="white",
            bg="#1e1e1e"
        )
        self.status_label.pack(pady=20)

        self.control_frame = tk.Frame(self.root, bg="#1e1e1e")
        self.control_frame.pack(pady=10)

        self.add_btn = tk.Button(
            self.control_frame,
            text="Manuell hinzufügen",
            command=self.add_plate_manually
        )
        self.add_btn.pack(side=tk.LEFT, padx=5)

        self.remove_btn = tk.Button(
            self.control_frame,
            text="Entfernen",
            command=self.remove_plate
        )
        self.remove_btn.pack(side=tk.LEFT, padx=5)

    def setup_ocr(self):
        self.reader = easyocr.Reader(['de'], gpu=False)

    def setup_data(self):
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        try:
            if os.path.exists(Config.CSV_PATH):
                df = pd.read_csv(Config.CSV_PATH, header=None)
                self.known_plates = df[0].tolist() if not df.empty else []
            else:
                self.known_plates = []
        except Exception as e:
            messagebox.showwarning("Datenfehler", f"Kennzeichenliste konnte nicht geladen werden: {e}")
            self.known_plates = []

        for plate in self.known_plates:
            self.listbox.insert(tk.END, plate)

        self.total_cars = 0
        self.access_granted = 0
        self.access_denied = 0
        self.detected_texts = []
        self.cooldown_frames = 0

    def setup_video(self):
        self.cap = cv2.VideoCapture(Config.CAMERA_INDEX)
        if not self.cap.isOpened():
            messagebox.showerror("Kamera Fehler", "Die Kamera konnte nicht geöffnet werden.")
            self.root.destroy()
            return

        self.video_queue = Queue(maxsize=1)
        self.running = True

        self.video_thread = Thread(target=self.video_capture_thread)
        self.video_thread.daemon = True
        self.video_thread.start()

        self.update_gui()

    def video_capture_thread(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret and self.video_queue.empty():
                self.video_queue.put(frame)

    def update_gui(self):
        try:
            if not self.video_queue.empty():
                frame = self.video_queue.get()
                result = detect_license_plate(frame, self.reader)

                if result:
                    frame, cropped, text = result
                    self.handle_plate_detection(text, cropped)

                self.display_frame(frame)

        except Exception as e:
            print(f"GUI Update Fehler: {e}")

        self.root.after(10, self.update_gui)

    def handle_plate_detection(self, plate, image):
        if plate in self.detected_texts:
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{Config.SCREENSHOT_DIR}/detection_{timestamp}.jpg"
        cv2.imwrite(filename, image)

        self.total_cars += 1
        self.plate_var.set(plate)
        self.detected_texts.append(plate)

        if plate in self.known_plates:
            self.access_granted += 1
            self.access_var.set("✅ ACCESS GRANTED")
            self.access_label.config(bg="green", fg="black")
            self.log_access(plate, "GRANTED", filename)
        else:
            self.access_denied += 1
            self.access_var.set("❌ ACCESS DENIED")
            self.access_label.config(bg="red", fg="white")
            self.known_plates.append(plate)
            self.listbox.insert(tk.END, plate)
            self.save_known_plates()
            self.log_access(plate, "DENIED", filename)

        self.update_cropped_preview(image, plate)
        self.update_status_display()

    def update_cropped_preview(self, image, text):
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb).resize((400, 100))

        draw = ImageDraw.Draw(img_pil)
        try:
            font = ImageFont.truetype("arial.ttf", 22)
        except:
            font = ImageFont.load_default()

        draw.text((10, 10), text, font=font, fill="lime")

        imgtk = ImageTk.PhotoImage(image=img_pil)
        self.cropped_preview_label.imgtk = imgtk
        self.cropped_preview_label.config(image=imgtk)

    def display_frame(self, frame):
        if frame is None:
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame).resize((800, 600))
        imgtk = ImageTk.PhotoImage(image=img)
        self.video_label.imgtk = imgtk
        self.video_label.config(image=imgtk)

    def update_status_display(self):
        status = f"Erkannt: {self.total_cars} | Zugriff: {self.access_granted} | Verweigert: {self.access_denied}"
        self.status_var.set(status)

    def log_access(self, plate, status, image_path):
        try:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(Config.LOG_PATH, 'a') as f:
                f.write(f"{now},{plate},{status},{image_path}\n")
        except Exception as e:
            print(f"Logging Fehler: {e}")

    def save_known_plates(self):
        try:
            pd.DataFrame(self.known_plates).to_csv(Config.CSV_PATH, header=False, index=False)
        except Exception as e:
            print(f"Speicherfehler: {e}")

    def add_plate_manually(self):
        plate = simpledialog.askstring("Kennzeichen hinzufügen", "Neues Kennzeichen:")
        if plate and plate not in self.known_plates:
            plate = format_plate(plate)
            if validate_plate(plate):
                self.known_plates.append(plate)
                self.listbox.insert(tk.END, plate)
                self.save_known_plates()
            else:
                messagebox.showwarning("Ungültiges Format", "Das eingegebene Kennzeichen entspricht keinem gültigen Format!")

    def remove_plate(self):
        selection = self.listbox.curselection()
        if selection:
            plate = self.listbox.get(selection[0])
            self.known_plates.remove(plate)
            self.listbox.delete(selection[0])
            self.save_known_plates()

    def on_closing(self):
        self.running = False
        self.video_thread.join()
        self.cap.release()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LicensePlateApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()