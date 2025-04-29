import cv2
import easyocr
import pandas as pd
import os
import datetime
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
from threading import Thread
from queue import Queue
import paho.mqtt.client as mqtt

from utils.erkenner import detect_license_plate
from utils.helper import format_plate, validate_plate

# === Konfiguration ===
class Config:
    CSV_PATH = 'daten/kennzeichen.csv'
    ILLEGAL_PLATES_PATH = 'daten/illegale_kennzeichen.csv'
    LOG_PATH = 'daten/log.csv'
    SCREENSHOT_DIR = 'daten/screenshots'
    CAMERA_INDEX = 0
    REPEAT_DELAY = 120
    OCR_CONFIDENCE = 0.5
    MQTT_BROKER = "ec9fcfef37fe4148b6b61bb13f3f1259.s1.eu.hivemq.cloud"
    MQTT_PORT = 8883
    MQTT_USERNAME = "esp32"
    MQTT_PASSWORD = "!Dennis99"
    MQTT_TOPIC_ACCESS = "parkhaus/tor/öffnen"

# === Hauptanwendung ===
class LicensePlateApp:
    def __init__(self, root):
        self.root = root
        self.setup_gui()
        self.setup_ocr()
        self.setup_data()
        self.setup_mqtt()
        self.setup_video()

    def setup_gui(self):
        self.root.title("🚗 Parkhaus Kennzeichen-Erkennung")
        self.root.geometry("1400x800")
        self.root.config(bg="#1e1e1e")
        
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Linke Spalte für Listbox
        left_frame = tk.Frame(main_frame, bg="#2e2e2e", width=300)
        left_frame.grid(row=0, column=0, rowspan=4, padx=10, pady=10, sticky="ns")

        # Whitelist-Kennzeichen Anzeige
        self.listbox_label = tk.Label(left_frame, text="Whitelist-Kennzeichen:", 
                                    bg="#2e2e2e", fg="white", font=("Arial", 12))
        self.listbox_label.pack(pady=(10,5))

        self.listbox = tk.Listbox(left_frame, bg="white", fg="black", 
                                font=("Courier New", 12), height=20)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Buttons
        button_frame = tk.Frame(left_frame, bg="#2e2e2e")
        button_frame.pack(fill=tk.X, pady=10)

        self.add_button = tk.Button(button_frame, text="Hinzufügen", command=self.add_plate_manually,
                                  bg="#4CAF50", fg="white")
        self.add_button.pack(side="left", padx=5, expand=True)

        self.remove_button = tk.Button(button_frame, text="Entfernen", command=self.remove_plate,
                                     bg="#f44336", fg="white")
        self.remove_button.pack(side="left", padx=5, expand=True)

        # Rechte Spalte für Kamera
        right_frame = tk.Frame(main_frame, bg="#1e1e1e")
        right_frame.grid(row=0, column=1, sticky="nsew")

        # Kamera-Anzeige
        self.video_label = tk.Label(right_frame, bg="black")
        self.video_label.pack(pady=20)

        # Zugriffsstatus
        self.access_var = tk.StringVar()
        self.access_label = tk.Label(
            right_frame,
            textvariable=self.access_var,
            font=("Courier New", 24, "bold"),
            width=25,
            height=2
        )
        self.access_label.pack(pady=10)

        # Vorschau des erkannten Kennzeichens
        self.cropped_preview_label = tk.Label(right_frame, bg="black")
        self.cropped_preview_label.pack(pady=10)

        # Erkanntes Kennzeichen
        self.plate_var = tk.StringVar()
        self.plate_label = tk.Label(
            right_frame,
            textvariable=self.plate_var,
            font=("Courier New", 18),
            fg="lime",
            bg="#1e1e1e",
            width=25,
            height=2
        )
        self.plate_label.pack(pady=10)

        # Uhrzeit-Anzeige
        self.time_var = tk.StringVar()
        self.time_label = tk.Label(
            right_frame,
            textvariable=self.time_var,
            font=("Courier New", 16),
            fg="white",
            bg="#1e1e1e"
        )
        self.time_label.pack(pady=10)
        self.update_time()

        # Status-Anzeige
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(
            right_frame,
            textvariable=self.status_var,
            font=("Courier New", 14),
            fg="white",
            bg="#1e1e1e"
        )
        self.status_label.pack(pady=10)

    def update_time(self):
        now = datetime.datetime.now()
        formatted_time = now.strftime("%d.%m.%Y %H:%M:%S")
        self.time_var.set(formatted_time)
        self.root.after(1000, self.update_time)

    def setup_ocr(self):
        self.reader = easyocr.Reader(['de'], gpu=False)

    def setup_data(self):
        os.makedirs(Config.SCREENSHOT_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(Config.ILLEGAL_PLATES_PATH), exist_ok=True)
        
        # Whitelist laden
        try:
            if os.path.exists(Config.CSV_PATH):
                df = pd.read_csv(Config.CSV_PATH, header=None)
                self.known_plates = df[0].tolist() if not df.empty else []
                self.update_listbox()
            else:
                self.known_plates = []
        except Exception as e:
            messagebox.showwarning("Datenfehler", f"Kennzeichenliste konnte nicht geladen werden: {e}")
            self.known_plates = []

        # Blacklist initialisieren
        self.illegal_plates = []
        self.load_illegal_plates()

        self.total_cars = 0
        self.access_granted = 0
        self.access_denied = 0
        self.detected_texts = []
        self.cooldown_frames = 0

    def update_listbox(self):
        """Aktualisiert die Listbox mit den bekannten Kennzeichen"""
        self.listbox.delete(0, tk.END)
        for plate in sorted(self.known_plates):
            self.listbox.insert(tk.END, plate)

    def load_illegal_plates(self):
        """Lädt vorhandene illegale Kennzeichen"""
        try:
            if os.path.exists(Config.ILLEGAL_PLATES_PATH):
                df = pd.read_csv(Config.ILLEGAL_PLATES_PATH, header=None)
                self.illegal_plates = df[0].tolist() if not df.empty else []
        except Exception as e:
            print(f"Warnung: Illegaleliste konnte nicht geladen werden: {e}")

    def save_illegal_plate(self, plate: str):
        """Speichert nur gültige, nicht-whitelistete Kennzeichen"""
        if (plate and 
            plate not in self.known_plates and 
            plate not in self.illegal_plates and
            validate_plate(plate)):
            
            self.illegal_plates.append(plate)
            try:
                with open(Config.ILLEGAL_PLATES_PATH, 'a', encoding='utf-8') as f:
                    f.write(f"{plate}\n")
            except Exception as e:
                print(f"Fehler beim Speichern: {e}")

    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(Config.MQTT_USERNAME, Config.MQTT_PASSWORD)
        self.mqtt_client.tls_set()

        try:
            self.mqtt_client.connect(Config.MQTT_BROKER, Config.MQTT_PORT)
            self.mqtt_client.loop_start()
            print("✅ MQTT-Verbindung hergestellt!")
        except Exception as e:
            print(f"❌ MQTT-Verbindung fehlgeschlagen: {e}")

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
                    if text:  # Nur verarbeiten wenn Text erkannt wurde
                        self.handle_plate_detection(text, cropped)

                self.display_frame(frame)

        except Exception as e:
            print(f"GUI Update Fehler: {e}")

        self.root.after(10, self.update_gui)

    def handle_plate_detection(self, plate, image):
        # Formatierung und Validierung
        plate = format_plate(plate)
        if not validate_plate(plate):
            return

        # Prüfe auf Doppelerkennung
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

            try:
                plate_payload = '{"command": "open", "plate": "' + plate + '"}'
                self.mqtt_client.publish(Config.MQTT_TOPIC_ACCESS, plate_payload)
            except Exception as e:
                print(f"MQTT-Fehler: {e}")
        else:
            self.access_denied += 1
            self.access_var.set("❌ ACCESS DENIED")
            self.access_label.config(bg="red", fg="white")
            self.save_illegal_plate(plate)
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
        img = Image.fromarray(frame).resize((400, 300))
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

    def add_plate_manually(self):
        plate = simpledialog.askstring("Kennzeichen hinzufügen", "Neues Kennzeichen:")
        if plate:
            plate = format_plate(plate)
            if validate_plate(plate):
                if plate not in self.known_plates:
                    self.known_plates.append(plate)
                    pd.DataFrame(self.known_plates).to_csv(Config.CSV_PATH, header=False, index=False)
                    self.update_listbox()
                else:
                    messagebox.showinfo("Info", "Kennzeichen existiert bereits!")
            else:
                messagebox.showwarning("Ungültiges Format", "Das eingegebene Kennzeichen entspricht keinem gültigen Format!")

    def remove_plate(self):
        selection = self.listbox.curselection()
        if selection:
            plate = self.listbox.get(selection[0])
            self.known_plates.remove(plate)
            pd.DataFrame(self.known_plates).to_csv(Config.CSV_PATH, header=False, index=False)
            self.update_listbox()

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