"""
CustomTkinter GUI for UDP server control and message display.

Requirements:
  pip install customtkinter

Features:
- Left panel: logo placeholder, Host, Port, Start/Stop button, indicator
- Right panel: server status label, "MESSAGES" table (IP, Port, Message), Download Messages button
- Starts/stops `udp_server.py` as subprocess and reads stdout to populate table
"""
import os
import sys
import subprocess
import threading
import csv
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import PhotoImage
from tkinter import messagebox, filedialog, ttk
from PIL import Image
from customtkinter import CTkImage
try:
    import customtkinter as ctk
except Exception:
    ctk = None


# Simple table implemented with frames on a canvas to allow black borders per cell
class TableCanvas(tk.Frame):
    def __init__(self, parent, cols, col_widths=None, row_height=200, header_bg='#e6e6e6'):
        super().__init__(parent)
        self.cols = cols
        self.col_widths = col_widths or [120] * len(cols)
        self.row_height = row_height
        self.main_window = None
        
        # Trouver la fenêtre principale
        widget = parent
        while widget and not hasattr(widget, '_download_file'):
            widget = widget.master
        self.main_window = widget

        self.canvas = tk.Canvas(self, bg='white', highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.hsb = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.vsb.grid(row=0, column=1, sticky='ns')
        self.hsb.grid(row=1, column=0, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # inner frame inside canvas
        self.inner = tk.Frame(self.canvas, bg='white')
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', self._on_inner_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)

        # Header
        header = tk.Frame(self.inner, bg='white')
        header.pack(fill='x')
        for i, col in enumerate(cols):
            cell_outer = tk.Frame(header, bg='black', width=self.col_widths[i], height=self.row_height)
            cell_outer.pack(side='left')
            cell_outer.pack_propagate(False)
            lbl = tk.Label(cell_outer, text=col.upper(), bg=header_bg, anchor='center')
            lbl.pack(fill='both', expand=True, padx=2, pady=2)

        self.rows_container = tk.Frame(self.inner, bg='white')
        self.rows_container.pack(fill='both', expand=True)
        self.rows = []

    def _on_inner_configure(self, _ev):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_configure(self, ev):
        # keep inner width >= canvas width so horizontal scrollbar works
        self.canvas.itemconfigure(self.window, width=max(self.inner.winfo_reqwidth(), ev.width))

    def insert_row(self, values):
        try:
            # create a row with black borders using an outer frame per cell
            row = tk.Frame(self.rows_container, bg='white')
            row.pack(fill='x')
            
            # Vérifier que nous avons assez de colonnes
            num_cols = min(len(self.cols), len(values))
            
            for i in range(num_cols):
                w = self.col_widths[i] if i < len(self.col_widths) else 120
                v = values[i] if i < len(values) else ""
                
                # Créer le cadre extérieur noir (bordure)
                cell_outer = tk.Frame(row, bg='black', width=w, height=self.row_height)
                cell_outer.pack(side='left')
                cell_outer.pack_propagate(False)
                
                # Créer un frame intérieur pour le contenu
                inner_frame = tk.Frame(cell_outer, bg='white')
                inner_frame.pack(fill='both', expand=True, padx=1, pady=1)
                
                # Si c'est la colonne Message (index 2) et que c'est un fichier CSV
                if i == 2 and isinstance(v, str) and '|' in v and v.startswith('CSV_START|'):
                    try:
                        # Extraire le nom du fichier et le contenu
                        parts = v.split('|', 2)
                        if len(parts) >= 3:
                            filename = parts[1]
                            file_content = parts[2]
                            
                            # Afficher le nom du fichier à gauche
                            file_label = tk.Label(
                                inner_frame, 
                                text=filename,
                                bg='white',
                                anchor='w',
                                padx=5
                            )
                            file_label.pack(side='left', fill='x', expand=True)
                            
                            # Ajouter le bouton de téléchargement à droite
                            btn = tk.Button(
                                inner_frame,
                                text="📥",  # Add back the download icon
                                command=lambda c=file_content, n=filename: self.main_window._download_file(c, n) if self.main_window else None,
                                bd=0,
                                bg='white',
                                activebackground='#f0f0f0',
                                font=('Arial', 12),
                                relief='flat'
                            )
                            btn.pack(side='right', padx=5)
                            
                            # Forcer l'affichage du bouton
                            btn.update()
                            continue  # Skip the default label creation
                        
                    except Exception as e:
                        print(f"Erreur création bouton téléchargement: {e}")
                        tk.Label(inner_frame, text=str(v), bg='white', anchor='w').pack(fill='both', expand=True)
                else:
                    # Pour les autres cellules, afficher le texte normalement
                    tk.Label(
                        inner_frame, 
                        text=str(v)[:100],  # Limiter la longueur du texte
                        bg='white', 
                        anchor='w' if i == 2 else 'center',
                        wraplength=w-10,  # Ajuster pour le padding
                        justify='left' if i == 2 else 'center'
                    ).pack(fill='both', expand=True)
            
            # Ajouter la rangée à la liste
            self.rows.append(row)
            
            # Mettre à jour la zone de défilement
            self.after(10, self._update_scrollregion)
            
        except Exception as e:
            print(f"Erreur dans insert_row: {e}")
    
    def _update_scrollregion(self):
        """Met à jour la zone de défilement du canvas"""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def clear(self):
        for r in self.rows:
            r.destroy()
        self.rows.clear()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))



class UDPServerCTK(ctk.CTk if ctk else tk.Tk):
    def _update_status_indicator(self, connected):
        """Update the status indicator based on server connection state"""
        color = '#4CAF50' if connected else '#F44336'  # Green when connected, red when disconnected
        self.status_indicator.itemconfig(self.status_indicator_circle, fill=color)
        
        if connected:
            host = self.host_var.get().strip()
            port = self.port_var.get().strip()
            self.status_label.configure(text=f"Server running on {host}:{port} (Public IP: 193.95.82.45)")
        else:
            self.status_label.configure(text='Server Disconnected')
            
    def import_csv(self):
        """Import messages from a CSV file"""
        file_path = filedialog.askopenfilename(
            title="Sélectionner un fichier CSV",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
        )
        
        if not file_path:
            return  # User cancelled the dialog
            
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                header = next(reader, None)  # Skip header if exists
                
                for row in reader:
                    if len(row) >= 3:  # Ensure we have at least IP, Port, Message
                        ip = row[0].strip()
                        port = row[1].strip()
                        message = row[2].strip()
                        timestamp = row[3] if len(row) > 3 else time.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Add to messages list and update UI
                        msg_data = (ip, port, message, timestamp)
                        self.messages.append(msg_data)
                        self.table.insert_row(msg_data)
                
                # Update message counter
                self.message_counter.configure(text=str(len(self.messages)))
                self._append_log(f'Fichier CSV importé : {os.path.basename(file_path)}')
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de lire le fichier CSV : {str(e)}")
            self._append_log(f'Erreur lors de l\'import du CSV : {str(e)}')
            
    def _handle_message(self, data, addr):
        """Gère les messages entrants et les fichiers CSV"""
        ip, port = addr
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # Décoder les données
            data_str = data.decode('utf-8')
            self._append_log(f'Données brutes reçues: {data_str[:100]}...')  # Afficher les 100 premiers caractères
            
            # Vérifier si c'est un fichier CSV
            if data_str.startswith('CSV_START|'):
                try:
                    # Séparer l'en-tête du contenu
                    parts = data_str.split('|', 2)  # Sépare en 3 parties : 'CSV_START', 'nom_du_fichier', 'contenu...'
                    if len(parts) < 3:
                        raise ValueError("Format de fichier invalide")
                        
                    filename = parts[1].strip()
                    content = parts[2]
                    
                    # Nettoyer le nom du fichier
                    if not filename.endswith('.csv'):
                        filename += '.csv'
                    
                    self._append_log(f'Fichier détecté: {filename}, Taille: {len(content)} caractères')
                    
                    if not content.strip():
                        raise ValueError("Fichier vide reçu")
                    
                    # Créer le dossier de sauvegarde
                    save_dir = os.path.join(os.path.dirname(__file__), 'received_csv')
                    os.makedirs(save_dir, exist_ok=True)
                    
                    # Sauvegarder le fichier
                    filepath = os.path.join(save_dir, filename)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    # Créer le contenu à afficher dans la colonne message
                    # On crée un frame pour contenir le nom du fichier et le bouton
                    message_frame = tk.Frame()
                    
                    # Ajouter le nom du fichier
                    file_label = tk.Label(message_frame, text=filename, anchor='w', bg='white')
                    file_label.pack(side='left', fill='x', expand=True, padx=5)
                    
                    # Ajouter le bouton de téléchargement
                    btn = tk.Button(
                        message_frame,
                        text="📥",
                        command=lambda c=content, n=filename: self._download_file(c, n),
                        bd=0,
                        bg='white',
                        activebackground='#f0f0f0',
                        font=('Arial', 12)
                    )
                    btn.pack(side='right', padx=5)
                    
                    # Ajouter la ligne au tableau avec le contenu réel
                    self._add_message(ip, str(port), content, timestamp)
                    
                    # Ajouter aux logs
                    self._append_log(f'Fichier reçu: {filename} ({len(content)} octets)')
                    
                    # Mettre à jour le compteur de messages
                    if hasattr(self, 'message_counter'):
                        self.message_counter.configure(text=f'Messages: {len(self.messages) + 1}')
                    
                except Exception as e:
                    error_msg = f'Erreur traitement fichier: {str(e)}'
                    self._append_log(error_msg)
                    self._add_message(ip, port, error_msg, timestamp)
            else:
                # Traitement des messages normaux
                self._add_message(ip, str(port), data_str.strip(), timestamp)
                self._append_log(f'Message de {ip}:{port}: {data_str.strip()}')
        
        except Exception as e:
            error_msg = f'Erreur: {str(e)}'
            self._append_log(error_msg)
            self._add_message(ip, port, error_msg, timestamp)
    
    def _download_file(self, content, filename):
        """Ouvre une boîte de dialogue pour enregistrer le fichier
        
        Args:
            content: Le contenu du fichier à enregistrer
            filename: Nom du fichier à suggérer dans la boîte de dialogue
        """
        try:
            # Demander où sauvegarder le fichier
            save_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                initialfile=filename,
                filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")]
            )
            
            if not save_path:  # Si l'utilisateur a annulé
                return False
                
            # Toujours écrire le contenu directement dans le fichier
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(str(content))
                    
            self._append_log(f'Fichier enregistré : {save_path}')
            return True
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'enregistrer le fichier: {str(e)}")
            self._append_log(f'Erreur lors de la sauvegarde: {str(e)}')
    
    def _add_message(self, ip, port, message, ts):
        """Ajoute un message à l'interface"""
        try:
            # S'assurer que les données sont au bon format
            ip = str(ip)
            port = str(port)
            message = str(message)
            ts = str(ts)
            
            # Créer le tuple de données
            msg_data = (ip, port, message, ts)
            
            # Ajouter aux messages et au tableau
            self.messages.append(msg_data)
            self.table.insert_row(msg_data)
            
            # Mettre à jour le compteur
            if hasattr(self, 'message_counter'):
                self.message_counter.configure(text=f'Messages: {len(self.messages)}')
                
            # Forcer la mise à jour de l'interface
            self.update_idletasks()
            
        except Exception as e:
            self._append_log(f'Erreur dans _add_message: {str(e)}')
        
    def __init__(self):
        if not ctk:
            # fallback: show message and exit after user sees instructions
            root = tk.Tk()
            root.withdraw()
            message = (
                "customtkinter is required.\nInstall with:\n\n"
                "pip install customtkinter\n\n"
                "Then re-run this script.")
            messagebox.showerror("Missing dependency", message)
            root.destroy()
            raise SystemExit(1)

        super().__init__()
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("UDP Server — Dashboard")
        self.geometry("1200x630")
        self.resizable(False, False)

        # Load the application icon
        try:
            # For .ico files on Windows
            self.iconbitmap('assets/icon.ico')
        except Exception as e:
            print(f"Could not load icon: {e}")
            print("Please ensure 'icon.ico' exists in the 'assets' folder")

        # server thread (in-process)
        self.server_thread = None
        self.server_stop = None

        # messages: list of (ip, port, message, timestamp)
        self.messages = []

        # layout: left control frame, right content frame
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(self, width=240)
        left.grid(row=0, column=0, sticky='nsw')
        left.grid_rowconfigure(8, weight=1)

        # Add ACTIA logo
        try:
            from PIL import Image
            from customtkinter import CTkImage
            img = Image.open("assets/logo_AES.png")
            img = img.resize((200, 50), Image.Resampling.LANCZOS)  # Resize to fit
            self.logo_img = CTkImage(light_image=img, dark_image=img, size=(200, 50))
            logo_label = ctk.CTkLabel(left, image=self.logo_img, text="")
            logo_label.grid(row=0, column=0, pady=(20, 10), padx=20)
        except Exception as e:
            print(f"Error loading logo: {e}")
            # Fallback to text if image loading fails
            logo_label = ctk.CTkLabel(left, text="ACTIA", font=('Arial', 20, 'bold'))
            logo_label.grid(row=0, column=0, pady=(20, 10), padx=20)

        # Update the Host label to maintain consistent spacing
        ctk.CTkLabel(left, text="Host", anchor='w').grid(row=1, column=0, sticky='w', padx=20, pady=(10, 0))

        self.host_var = ctk.StringVar(value='0.0.0.0')
        ctk.CTkEntry(left, textvariable=self.host_var, width=200).grid(row=2, column=0, padx=16, pady=(4,10))

        ctk.CTkLabel(left, text="Port", anchor='w').grid(row=3, column=0, sticky='w', padx=16)
        self.port_var = ctk.StringVar(value='1030')
        ctk.CTkEntry(left, textvariable=self.port_var, width=200).grid(row=4, column=0, padx=16, pady=(4,10))

        self.start_btn = ctk.CTkButton(left, text="Start Server", command=self.toggle_server, width=160)
        self.start_btn.grid(row=5, column=0, padx=16, pady=(6, 8))
        
        # Bouton pour importer un fichier CSV
        self.import_btn = ctk.CTkButton(left, text="Importer CSV", command=self.import_csv, width=160)
        self.import_btn.grid(row=6, column=0, padx=16, pady=(8, 4))
        
        # indicator
        indicator_size = 64  # Size of the indicator in pixels
        
        # Get the background color from the parent frame
        bg_color = left.cget('fg_color')[1] if ctk.get_appearance_mode() == 'Dark' else left.cget('fg_color')[0]
        
        # Create a frame to hold the canvas with matching background
        indicator_frame = ctk.CTkFrame(left, fg_color='transparent')
        indicator_frame.grid(row=7, column=0, pady=(20,0))  # Déplacé plus bas avec plus d'espace
        
        # Create canvas with matching background
        self.ind_canvas = tk.Canvas(indicator_frame, width=indicator_size, height=indicator_size,
                                  highlightthickness=0, bg=bg_color)
        self.ind_canvas.pack()
        
        # Function to load and process image
        def load_image(path, size):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                img = img.resize((size, size), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception as e:
                print(f"Error loading image {path}: {e}")
                # Create a colored square as fallback
                img = Image.new('RGBA', (size, size), (255, 0, 0, 255))
                return ImageTk.PhotoImage(img)

        # Load indicator images
        self.off_img = load_image("assets/udp_off.png", indicator_size)
        self.on_img = load_image("assets/udp_on.png", indicator_size)
        
        if not self.off_img or not self.on_img:
            # Fallback to colored circles if images not found
            self.off_img = None
            self.on_img = None
            self.ind = self.ind_canvas.create_oval(6, 6, indicator_size-6, indicator_size-6, 
                                                 fill='red', outline='')
        else:
            # Create image items centered in the canvas
            center = indicator_size // 2
            self.off_ind = self.ind_canvas.create_image(center, center, image=self.off_img)
            self.on_ind = self.ind_canvas.create_image(center, center, image=self.on_img, state='hidden')

        # copyright_label
        copyright_text = "© 2025 Actia Engineering Services. All rights reserved."
        copyright_lbl = ctk.CTkLabel(left, text=copyright_text, text_color='black', font=('Arial', 9))
        copyright_lbl.grid(row=9, column=0, sticky='s', pady=(0, 12))

        # right frame
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky='nsew', padx=12, pady=12)
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Top bar frame for status and counter
        top_bar = ctk.CTkFrame(right, fg_color='transparent')
        top_bar.grid(row=0, column=0, sticky='ew', padx=12, pady=(12,6))
        top_bar.columnconfigure(1, weight=1)  # Allow the middle space to expand
        
        # Status indicator and label frame
        status_frame = ctk.CTkFrame(top_bar, fg_color='transparent')
        status_frame.grid(row=0, column=0, sticky='w')

        # Status indicator (red circle for disconnected)
        self.status_indicator = tk.Canvas(status_frame, width=12, height=12, bg='gray', highlightthickness=0)
        self.status_indicator_circle = self.status_indicator.create_oval(2, 2, 10, 10, fill='red', outline='')
        self.status_indicator.pack(side='left', padx=(0, 8))

        # Status label
        self.status_label = ctk.CTkLabel(status_frame, text='Server Disconnected', anchor='w')
        self.status_label.pack(side='left')
        
        # Message counter on the right with icon
        try:
            from PIL import Image
            from customtkinter import CTkImage
            # Load and resize the message icon (using the same size as the ACTIA logo for consistency)
            msg_img = Image.open("assets/message.png")  # Using ACTIA logo as message icon for now
            msg_img = msg_img.resize((20, 20), Image.Resampling.LANCZOS)
            self.msg_icon = CTkImage(light_image=msg_img, dark_image=msg_img, size=(20, 20))
            
            # Create a frame to hold both icon and counter
            counter_frame = ctk.CTkFrame(top_bar, fg_color='transparent')
            counter_frame.grid(row=0, column=2, sticky='e')
            
            # Add icon and counter label side by side
            ctk.CTkLabel(counter_frame, image=self.msg_icon, text="").pack(side='left', padx=(0, 5))
            self.message_counter = ctk.CTkLabel(counter_frame, text='0', anchor='e')
            self.message_counter.pack(side='left')
        except Exception as e:
            print(f"Error loading message icon: {e}")
            # Fallback to text only if image loading fails
            self.message_counter = ctk.CTkLabel(top_bar, text='Messages: 0', anchor='e')
            self.message_counter.grid(row=0, column=2, sticky='e')

        header = ctk.CTkLabel(right, text='MESSAGES', font=ctk.CTkFont(size=18, weight='bold'))
        header.grid(row=1, column=0, sticky='w', padx=12, pady=(6,8))
        # Search/filter bar
        search_frame = ctk.CTkFrame(right, fg_color='transparent')
        search_frame.grid(row=1, column=0, sticky='e', padx=12, pady=(6, 0))

        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=self.search_var, placeholder_text='Search IP, Port, Message...')
        search_entry.grid(row=0, column=0, padx=(0, 8))

        search_btn = ctk.CTkButton(search_frame, text='Filter', command=self.filter_messages, width=100)
        search_btn.grid(row=0, column=1)

        reset_btn = ctk.CTkButton(search_frame, text='Reset', command=self.reset_filter, width=80)
        reset_btn.grid(row=0, column=2, padx=(8, 0))

        # messages table using ttk.Treeview for columns: IP, Port, Message
        table_frame = tk.Frame(right)
        table_frame.grid(row=2, column=0, sticky='nsew', padx=12, pady=(0,12))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        cols = ('IP', 'Port', 'Message', 'Time')
        # create custom table with black borders per cell
        col_widths = [160, 80, 508, 147]
        self.table = TableCanvas(table_frame, cols=cols, col_widths=col_widths, row_height=40)
        self.table.grid(row=0, column=0, sticky='nsew')

        # buttons: Download and Clear
        btn_frame = ctk.CTkFrame(right, fg_color='transparent')
        btn_frame.grid(row=3, column=0, sticky='e', padx=12, pady=(0,12))
        self.download_btn = ctk.CTkButton(btn_frame, text='Download Messages', command=self.download_messages, width=160)
        self.download_btn.grid(row=0, column=0, padx=(0,8))
        # Replace the clear button with a trash icon
        try:
            trash_img = Image.open("assets/trash.png")
            trash_img = trash_img.resize((20, 20), Image.Resampling.LANCZOS)
            self.trash_icon = CTkImage(light_image=trash_img, dark_image=trash_img, size=(20, 20))
            self.clear_btn = ctk.CTkButton(
                btn_frame, 
                text='', 
                image=self.trash_icon, 
                command=self.clear_messages, 
                width=40,
                fg_color='transparent',
                hover_color='#f0f0f0' if ctk.get_appearance_mode() == 'Light' else '#2b2b2b'
            )
        except Exception as e:
            print(f"Error loading trash icon: {e}")
            # Fallback to text button if image loading fails
            self.clear_btn = ctk.CTkButton(
                btn_frame, 
                text='Clear', 
                command=self.clear_messages, 
                width=60,
                fg_color='#d9534f'
            )
        self.clear_btn.grid(row=0, column=1, padx=(8, 0))

        # log area (small) at top-right
        self.log_text = tk.Text(right, height=2, state='disabled')
        self.log_text.grid(row=4, column=0, sticky='ew', padx=12, pady=(0,8))

        # periodic UI update
        self.after(500, self._periodic)

    # Helper methods
    def _set_indicator(self, color):
        if hasattr(self, 'on_ind'):
            # Image-based indicator
            if color == 'green':
                self.ind_canvas.itemconfig(self.off_ind, state='hidden')
                self.ind_canvas.itemconfig(self.on_ind, state='normal')
                self._update_status_indicator(True)  # Update status text and indicator
            else:
                self.ind_canvas.itemconfig(self.on_ind, state='hidden')
                self.ind_canvas.itemconfig(self.off_ind, state='normal')
                self._update_status_indicator(False)  # Update status text and indicator
        else:
            # Fallback to colored circle
            self.ind_canvas.itemconfigure(self.ind, fill=color)

    def _append_log(self, text: str):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', text + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def toggle_server(self):
        if self.server_thread and self.server_thread.is_alive():
            self.stop_server()
        else:
            self.start_server()

    def start_server(self):
       
        host = self.host_var.get().strip()
        port = self.port_var.get().strip()
        try:
            port_i = int(port)
        except Exception:
            messagebox.showerror('Invalid port', 'Port must be an integer')
            return
        # start server in-process using udp_server.run_server
        try:
            from udp_server import run_server
        except Exception as e:
            messagebox.showerror('Import error', f'Could not import udp_server: {e}')
            return

        self.server_stop = threading.Event()

        def target():
            try:
                run_server(host, port_i, stop_event=self.server_stop, on_message=self._on_message)
            except Exception as e:
                # show error in log
                self.after(1, self._append_log, f"Server thread error: {e}")

        self.server_thread = threading.Thread(target=target, daemon=True)
        self.server_thread.start()

        self.after(100, lambda: self._update_status_indicator(True))
        self._set_indicator('green')
        self.status_label.configure(text=f"Server running on {host}:{port_i} (Public IP: 193.95.82.45)")
        self.start_btn.configure(text='Stop Server')
        self._append_log('Server started (in-process)')

    def stop_server(self):
       
        if not self.server_thread:
            return
        self._append_log('Stopping server...')
        try:
            self.server_stop.set()
            self.server_thread.join(timeout=3)
        except Exception:
            pass
        self.server_thread = None
        self.server_stop = None
        self._set_indicator('red')
        self.status_label.configure(text='Server Disconnected')  # Update status text
        self.start_btn.configure(text='Start Server')  # Update button text
        self._update_status_indicator(False)  # Update status indicator
        self._append_log('Server stopped')

    # removed subprocess stdout reader; server now calls _on_message directly
    def _on_message(self, ip, port, message):
        try:
            print(f"DEBUG: _on_message received - IP: {ip}, Port: {port}, Message: {message[:100]}...")  # Log first 100 chars
            # Get current time with milliseconds in YYYY-MM-DD HH:MM:SS:MS format
            ms = int(time.time() * 1000) % 1000
            ts = time.strftime('%Y-%m-%d %H:%M:%S:') + f"{ms:03d}"
            # schedule GUI update
            print(f"DEBUG: Scheduling _add_message with timestamp: {ts}")
            self.after(1, self._add_message, ip, str(port), message, ts)
        except Exception as e:
            print(f"ERROR in _on_message: {str(e)}")
            import traceback
            traceback.print_exc()

    def _add_message(self, ip, port, message, ts):
        try:
            # Ensure all values are strings
            ip = str(ip)
            port = str(port)
            message = str(message)
            ts = str(ts)
            
            # Create the data tuple for the table
            msg_data = (ip, port, message, ts)
            
            # Add to messages and table
            self.messages.append(msg_data)
            self.table.insert_row(msg_data)
            
            # Update the log and counter
            self._append_log(f"Message from {ip}:{port}: {message}")
            if hasattr(self, 'message_counter'):
                self.message_counter.configure(text=f'Messages: {len(self.messages)}')
                
            # Force UI update
            self.update_idletasks()
            
        except Exception as e:
            self._append_log(f'Error in _add_message: {str(e)}')

    def _handle_server_line(self, line: str):
        # append to small log
        pass

    def download_messages(self):
        if not self.messages:
            messagebox.showinfo('No messages', 'No messages to download')
            return
        f = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV files','*.csv')])
        if not f:
            return
        try:
            with open(f, 'w', newline='', encoding='utf-8') as fh:
                writer = csv.writer(fh)
                writer.writerow(['ip','port','message','time'])
                writer.writerows(self.messages)
            messagebox.showinfo('Saved', f'Saved {len(self.messages)} messages to {f}')
        except Exception as e:
            messagebox.showerror('Save error', str(e))

    def export_csv(self):
        """Export messages to a CSV file"""
        if not self.messages:
            messagebox.showinfo("Aucun message", "Il n'y a aucun message à exporter.")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Fichiers CSV", "*.csv"), ("Tous les fichiers", "*.*")],
            title="Enregistrer sous"
        )
        
        if not file_path:
            return  # User cancelled the dialog
            
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                # Écrire l'en-tête avec des tabulations comme séparateurs
                file.write("Adresse IP\tPort\tMessage\tHorodatage\n")
                
                # Écrire les données
                for msg in self.messages:
                    # Nettoyer chaque champ
                    ip = str(msg[0]).strip() if len(msg) > 0 else ""
                    port = str(msg[1]).strip() if len(msg) > 1 else ""
                    message = str(msg[2]).strip() if len(msg) > 2 else ""
                    timestamp = str(msg[3]).strip() if len(msg) > 3 else ""
                    
                    # Écrire la ligne avec des tabulations comme séparateurs
                    file.write(f"{ip}\t{port}\t{message}\t{timestamp}\n")
                    
            messagebox.showinfo("Export réussi", f"Les messages ont été exportés avec succès vers :\n{file_path}")
            self._append_log(f'Export CSV réussi : {os.path.basename(file_path)}')
            
        except Exception as e:
            messagebox.showerror("Erreur d'export", f"Une erreur est survenue lors de l'export :\n{str(e)}")
            self._append_log(f'Erreur lors de l\'export CSV : {str(e)}')

    def clear_messages(self):
        """Vider tous les messages du tableau et réinitialiser le compteur"""
        if not self.messages:
            return
        if not messagebox.askyesno('Vider les messages', 'Êtes-vous sûr de vouloir effacer tous les messages ?'):
            return
        self.messages.clear()
        self.table.clear()
        # Réinitialiser le compteur de messages à 0
        self.message_counter.configure(text='0')
        self._append_log('Messages effacés')

    def filter_messages(self):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self.reset_filter()
            return

        # Clear the current table
        self.table.clear()
        
        # Filter messages based on keyword
        filtered = []
        for msg in self.messages:
            # Check if any field contains the keyword
            if any(keyword in str(field).lower() for field in msg):
                filtered.append(msg)
        
        # Rebuild the table with filtered messages
        for msg in filtered:
            self.table.insert_row(msg)

        self._append_log(f'Filtrage avec le mot-clé : "{keyword}"')
        self.message_counter.configure(text=f'{len(filtered)} / {len(self.messages)}')

    def reset_filter(self):
        self.search_var.set('')
        self.table.clear()
        # Rebuild the full table
        for msg in self.messages:
            self.table.insert_row(msg)
        self.message_counter.configure(text=f'Messages: {len(self.messages)}')
        self._append_log('Filtre réinitialisé')

    def _periodic(self):
        # update indicator according to process
        if self.server_thread and self.server_thread.is_alive():
            self._set_indicator('green')
            self.start_btn.configure(text='Stop Server')
        else:
            self._set_indicator('red')
            self.start_btn.configure(text='Start Server')
        self.after(500, self._periodic)


def main():
    app = UDPServerCTK()
    app.mainloop()


if __name__ == '__main__':
    main()
