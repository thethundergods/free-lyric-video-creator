"""Cross-platform dialog system - uses native dialogs on Mac, tkinter on Windows/Linux."""
import sys
import subprocess
import platform

IS_MAC = platform.system() == 'Darwin'
IS_WINDOWS = platform.system() == 'Windows'


# === macOS Implementation (AppleScript) ===

def _run_osascript(script):
    """Run AppleScript and return output."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _mac_askopenfilename(title="Open File", filetypes=None):
    type_list = ""
    if filetypes:
        extensions = []
        for name, pattern in filetypes:
            for p in pattern.split():
                ext = p.replace("*.", "").replace("*", "")
                if ext:
                    extensions.append(f'"{ext}"')
        if extensions:
            type_list = "{" + ", ".join(extensions) + "}"

    if type_list:
        script = f'''
        set theFile to choose file with prompt "{title}" of type {type_list}
        return POSIX path of theFile
        '''
    else:
        script = f'''
        set theFile to choose file with prompt "{title}"
        return POSIX path of theFile
        '''
    return _run_osascript(script)


def _mac_asksaveasfilename(title="Save File", defaultextension="", initialfile=""):
    default_name = initialfile if initialfile else f"untitled{defaultextension}"
    script = f'''
    set theFile to choose file name with prompt "{title}" default name "{default_name}"
    return POSIX path of theFile
    '''
    path = _run_osascript(script)
    if path and defaultextension and not path.endswith(defaultextension):
        path = path + defaultextension
    return path


def _mac_askstring(title, prompt):
    script = f'''
    set theResponse to display dialog "{prompt}" with title "{title}" default answer ""
    return text returned of theResponse
    '''
    result = _run_osascript(script)
    return result if result else None


def _mac_askyesno(title, message):
    script = f'''
    set theResponse to display dialog "{message}" with title "{title}" buttons {{"No", "Yes"}} default button "Yes"
    return button returned of theResponse
    '''
    result = _run_osascript(script)
    return result == "Yes"


def _mac_showinfo(title, message):
    script = f'''
    display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK"
    '''
    _run_osascript(script)


def _mac_showerror(title, message):
    script = f'''
    display dialog "{message}" with title "{title}" buttons {{"OK"}} default button "OK" with icon stop
    '''
    _run_osascript(script)


def _mac_get_clipboard():
    try:
        result = subprocess.run(['pbpaste'], capture_output=True, text=True)
        return result.stdout
    except Exception:
        return ""


def _mac_askchoice(title, prompt, options):
    option_list = "{" + ", ".join(f'"{opt}"' for opt in options) + "}"
    script = f'''
    set theChoice to choose from list {option_list} with prompt "{prompt}" with title "{title}" default items {{"{options[0]}"}}
    if theChoice is false then
        return ""
    else
        return item 1 of theChoice
    end if
    '''
    result = _run_osascript(script)
    return result if result else None


def _mac_asktextarea(title, prompt, default=""):
    import tempfile
    import os

    script = '''
import tkinter as tk
from tkinter import scrolledtext
import sys

def on_ok():
    text = text_area.get("1.0", tk.END).strip()
    print(text)
    root.destroy()

def on_cancel():
    root.destroy()
    sys.exit(1)

root = tk.Tk()
root.title("{title}")
root.geometry("600x400")

label = tk.Label(root, text="{prompt}")
label.pack(pady=(10, 5))

text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=70, height=20)
text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
text_area.insert("1.0", """{default}""")
text_area.focus()

button_frame = tk.Frame(root)
button_frame.pack(pady=10)

ok_btn = tk.Button(button_frame, text="OK", command=on_ok, width=10)
ok_btn.pack(side=tk.LEFT, padx=5)

cancel_btn = tk.Button(button_frame, text="Cancel", command=on_cancel, width=10)
cancel_btn.pack(side=tk.LEFT, padx=5)

root.bind('<Command-Return>', lambda e: on_ok())
root.bind('<Escape>', lambda e: on_cancel())

root.mainloop()
'''.format(title=title.replace('"', '\\"'),
           prompt=prompt.replace('"', '\\"'),
           default=default.replace('\\', '\\\\').replace('"', '\\"'))

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(script)
        script_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout
        return None
    finally:
        os.unlink(script_path)


# === Windows/Linux Implementation (tkinter) ===

def _tk_askopenfilename(title="Open File", filetypes=None):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    tk_filetypes = []
    if filetypes:
        for name, pattern in filetypes:
            exts = tuple(p.replace("*", "") for p in pattern.split())
            tk_filetypes.append((name, exts))
    tk_filetypes.append(("All files", "*.*"))

    path = filedialog.askopenfilename(title=title, filetypes=tk_filetypes)
    root.destroy()
    return path if path else ""


def _tk_asksaveasfilename(title="Save File", defaultextension="", initialfile=""):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    path = filedialog.asksaveasfilename(
        title=title,
        defaultextension=defaultextension,
        initialfile=initialfile
    )
    root.destroy()
    return path if path else ""


def _tk_askstring(title, prompt):
    import tkinter as tk
    from tkinter import simpledialog
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    result = simpledialog.askstring(title, prompt, parent=root)
    root.destroy()
    return result


def _tk_askyesno(title, message):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    result = messagebox.askyesno(title, message, parent=root)
    root.destroy()
    return result


def _tk_showinfo(title, message):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def _tk_showerror(title, message):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)

    messagebox.showerror(title, message, parent=root)
    root.destroy()


def _tk_get_clipboard():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        text = root.clipboard_get()
    except tk.TclError:
        text = ""
    root.destroy()
    return text


def _tk_askchoice(title, prompt, options):
    import tkinter as tk

    result = [None]

    def on_select():
        selection = listbox.curselection()
        if selection:
            result[0] = options[selection[0]]
        root.destroy()

    def on_cancel():
        root.destroy()

    root = tk.Tk()
    root.title(title)
    root.attributes('-topmost', True)
    root.geometry("300x250")

    label = tk.Label(root, text=prompt)
    label.pack(pady=(10, 5))

    listbox = tk.Listbox(root, selectmode=tk.SINGLE, height=len(options))
    for opt in options:
        listbox.insert(tk.END, opt)
    listbox.selection_set(0)
    listbox.pack(padx=20, pady=5, fill=tk.BOTH, expand=True)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)

    ok_btn = tk.Button(btn_frame, text="OK", command=on_select, width=10)
    ok_btn.pack(side=tk.LEFT, padx=5)

    cancel_btn = tk.Button(btn_frame, text="Cancel", command=on_cancel, width=10)
    cancel_btn.pack(side=tk.LEFT, padx=5)

    listbox.bind('<Double-1>', lambda e: on_select())
    root.bind('<Return>', lambda e: on_select())
    root.bind('<Escape>', lambda e: on_cancel())

    root.mainloop()
    return result[0]


def _tk_asktextarea(title, prompt, default=""):
    import tkinter as tk
    from tkinter import scrolledtext

    result = [None]

    def on_ok():
        result[0] = text_area.get("1.0", tk.END).strip()
        root.destroy()

    def on_cancel():
        root.destroy()

    root = tk.Tk()
    root.title(title)
    root.attributes('-topmost', True)
    root.geometry("600x400")

    label = tk.Label(root, text=prompt)
    label.pack(pady=(10, 5))

    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=70, height=20)
    text_area.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    text_area.insert("1.0", default)
    text_area.focus()

    button_frame = tk.Frame(root)
    button_frame.pack(pady=10)

    ok_btn = tk.Button(button_frame, text="OK", command=on_ok, width=10)
    ok_btn.pack(side=tk.LEFT, padx=5)

    cancel_btn = tk.Button(button_frame, text="Cancel", command=on_cancel, width=10)
    cancel_btn.pack(side=tk.LEFT, padx=5)

    root.bind('<Control-Return>', lambda e: on_ok())
    root.bind('<Escape>', lambda e: on_cancel())

    root.mainloop()
    return result[0]


# === Public API (auto-selects implementation) ===

if IS_MAC:
    askopenfilename = _mac_askopenfilename
    asksaveasfilename = _mac_asksaveasfilename
    askstring = _mac_askstring
    askyesno = _mac_askyesno
    showinfo = _mac_showinfo
    showerror = _mac_showerror
    get_clipboard = _mac_get_clipboard
    askchoice = _mac_askchoice
    asktextarea = _mac_asktextarea
else:
    askopenfilename = _tk_askopenfilename
    asksaveasfilename = _tk_asksaveasfilename
    askstring = _tk_askstring
    askyesno = _tk_askyesno
    showinfo = _tk_showinfo
    showerror = _tk_showerror
    get_clipboard = _tk_get_clipboard
    askchoice = _tk_askchoice
    asktextarea = _tk_asktextarea
