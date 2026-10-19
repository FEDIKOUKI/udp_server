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
    def __init__(self, parent, cols, col_widths=None, row_height=28, header_bg='#e6e6e6'):
        super().__init__(parent)
        self.cols = cols
        self.col_widths = col_widths or [120] * len(cols)
        self.row_height = row_height

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
        # create a row with black borders using an outer frame per cell
        row = tk.Frame(self.rows_container, bg='white')
        row.pack(fill='x')
        for i, v in enumerate(values):
            w = self.col_widths[i] if i < len(self.col_widths) else 120
            cell_outer = tk.Frame(row, bg='black', width=w, height=self.row_height)
            cell_outer.pack(side='left')
            cell_outer.pack_propagate(False)
            # inner white label
            lbl = tk.Label(cell_outer, text=str(v), bg='white', anchor='w' if i == 2 else 'center')
            lbl.pack(fill='both', expand=True, padx=2, pady=2)
        self.rows.append(row)
        # update scrollregion
        self.after(10, lambda: self.canvas.configure(scrollregion=self.canvas.bbox('all')))

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
        self.geometry("1002x630")
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
        self.start_btn.grid(row=5, column=0, padx=16, pady=(6,8))

        # indicator
        indicator_size = 64  # Size of the indicator in pixels
        
        # Get the background color from the parent frame
        bg_color = left.cget('fg_color')[1] if ctk.get_appearance_mode() == 'Dark' else left.cget('fg_color')[0]
        
        # Create a frame to hold the canvas with matching background
        indicator_frame = ctk.CTkFrame(left, fg_color='transparent')
        indicator_frame.grid(row=6, column=0, pady=(8,0))
        
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
        col_widths = [160, 80, 310, 147]
        self.table = TableCanvas(table_frame, cols=cols, col_widths=col_widths, row_height=28)
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
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        # schedule GUI update
        self.after(1, self._add_message, ip, str(port), message, ts)

    def _add_message(self, ip, port, message, ts):
        self.messages.append((ip, port, message, ts))
        self.table.insert_row((ip, port, message, ts))
        self._append_log(f"Message from {ip}:{port}: {message}")
        # Update message counter
        if hasattr(self, 'message_counter'):
            self.message_counter.configure(text=f'Messages: {len(self.messages)}')

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

    def clear_messages(self):
        if not self.messages:
            return
        if not messagebox.askyesno('Clear messages', 'Are you sure you want to clear all messages?'):
            return
        self.messages.clear()
        # clear custom table rows
        try:
            self.table.clear()
        except Exception:
            pass
        # Reset message counter to 0
        self.message_counter.configure(text='0')
        self._append_log('Messages cleared')
    def filter_messages(self):
            keyword = self.search_var.get().strip().lower()
            if not keyword:
                return

            self.table.clear()
            filtered = [msg for msg in self.messages if any(keyword in str(field).lower() for field in msg)]
            for msg in filtered:
                self.table.insert_row(msg)

            self._append_log(f'Filtered messages with keyword: \"{keyword}\"')
            self.message_counter.configure(text=f'{len(filtered)} / {len(self.messages)}')

    def reset_filter(self):
            self.search_var.set('')
            self.table.clear()
            for msg in self.messages:
                self.table.insert_row(msg)
            self.message_counter.configure(text=f'{len(self.messages)}')
            self._append_log('Filter reset')

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
