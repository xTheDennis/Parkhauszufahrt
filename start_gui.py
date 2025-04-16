import tkinter as tk
from tkinter import messagebox, filedialog
import os
import subprocess
import pandas as pd
from PIL import Image, ImageTk

class StartApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚦 Parkhaus Startmenü")
        self.root.geometry("600x400")
        self.root.config(bg="#1e1e1e")

        tk.Label(
            root, text="Willkommen im Parkhaus-System", font=("Courier New", 20, "bold"), fg="white", bg="#1e1e1e"
        ).pack(pady=30)

        tk.Button(
            root, text="🚗 Parkhaus starten", font=("Courier New", 14), width=25, command=self.start_main
        ).pack(pady=10)

        tk.Button(
            root, text="📸 Screenshots anzeigen", font=("Courier New", 14), width=25, command=self.show_screenshots
        ).pack(pady=10)

        tk.Button(
            root, text="📋 Kennzeichen anzeigen", font=("Courier New", 14), width=25, command=self.show_plates
        ).pack(pady=10)

    def start_main(self):
        try:
            subprocess.Popen(["python", "main.py"])
        except Exception as e:
            messagebox.showerror("Fehler", f"main.py konnte nicht gestartet werden: {e}")

    def show_screenshots(self):
        screenshot_dir = "daten/screenshots"
        if not os.path.exists(screenshot_dir):
            messagebox.showinfo("Info", "Keine Screenshots gefunden.")
            return

        top = tk.Toplevel(self.root)
        top.title("Screenshots")
        top.geometry("900x600")
        canvas = tk.Canvas(top, bg="#1e1e1e")
        scrollbar = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#1e1e1e")

        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for file in os.listdir(screenshot_dir):
            if file.endswith(".jpg") or file.endswith(".png"):
                img_path = os.path.join(screenshot_dir, file)
                try:
                    img = Image.open(img_path)
                    img.thumbnail((300, 150))
                    imgtk = ImageTk.PhotoImage(img)

                    panel = tk.Label(scroll_frame, image=imgtk, bg="#1e1e1e")
                    panel.image = imgtk
                    panel.pack(pady=10)
                except:
                    continue

    def show_plates(self):
        csv_path = "daten/kennzeichen.csv"
        if not os.path.exists(csv_path):
            messagebox.showinfo("Info", "Keine CSV-Datei gefunden.")
            return

        try:
            df = pd.read_csv(csv_path, header=None)
        except Exception as e:
            messagebox.showerror("Fehler", f"CSV konnte nicht geladen werden: {e}")
            return

        top = tk.Toplevel(self.root)
        top.title("Bekannte Kennzeichen")
        top.geometry("400x400")

        listbox = tk.Listbox(top, font=("Courier New", 14))
        listbox.pack(fill="both", expand=True, padx=10, pady=10)

        for plate in df[0].tolist():
            listbox.insert(tk.END, plate)

if __name__ == "__main__":
    root = tk.Tk()
    app = StartApp(root)
    root.mainloop()