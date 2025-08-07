#!/usr/bin/env python3
import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import re
import shutil
import threading

bitlocker_password_cache = None
montajes = []

def centrar_ventana(ventana, ancho=400, alto=200):
    ventana.update_idletasks()
    screen_width = ventana.winfo_screenwidth()
    screen_height = ventana.winfo_screenheight()
    x = int((screen_width / 2) - (ancho / 2))
    y = int((screen_height / 2) - (alto / 2))
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

def relanzar_con_pkexec():
    exe = os.path.abspath(sys.argv[0])
    args = sys.argv[1:]
    display = os.environ.get("DISPLAY")
    xauthority = os.environ.get("XAUTHORITY", os.path.expanduser("~/.Xauthority"))

    if not display:
        print("DISPLAY no está definido. ¿Estás en entorno gráfico?")
        sys.exit(1)

    if os.getenv("PKEXEC_UID"):
        print("Ya se ejecuta con pkexec pero no se logró elevar permisos.")
        sys.exit(1)

    print("Reintentando con pkexec (gráfico)...")
    try:
        os.execvp("pkexec", ["pkexec", "env", f"DISPLAY={display}", f"XAUTHORITY={xauthority}",
                             "python3", exe] + args)
    except Exception as e:
        print(f"Error al relanzar con pkexec: {e}")
        sys.exit(1)

if os.geteuid() != 0:
    print("Requiere privilegios de superusuario. Reintentando con pkexec...")
    relanzar_con_pkexec()

def ejecutar(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except subprocess.CalledProcessError:
        return ""

def desmontar_todo():
    for mnt in montajes:
        print(f"Desmontando: {mnt}")
        subprocess.run(["umount", "-f", mnt])
        try:
            shutil.rmtree(mnt)
        except Exception as e:
            print(f"No se pudo eliminar {mnt}: {e}")
    montajes.clear()

    # Desmontar BitLocker si se usó, reintenta hasta 3 veces si está montado
    if os.path.ismount("/mnt/dislocker"):
        for _ in range(3):
            result = subprocess.run(["umount", "/mnt/dislocker"])
            if not os.path.ismount("/mnt/dislocker"):
                break
    # Elimina la carpeta aunque no esté montada (robustez extra)
    if os.path.exists("/mnt/dislocker"):
        try:
            shutil.rmtree("/mnt/dislocker")
        except Exception as e:
            print(f"No se pudo eliminar /mnt/dislocker: {e}")

    # Eliminar loop devices creados por el script
    losetups = ejecutar(["losetup", "-a"]).splitlines()
    for linea in losetups:
        if "/imagen_" in linea or any(ext in linea for ext in [".img", ".dd", ".iso", ".raw", ".bin"]):
            loopdev = linea.split(":")[0]
            print(f"Liberando loop: {loopdev}")
            subprocess.run(["losetup", "-d", loopdev])

    messagebox.showinfo("Listo", "Todos los montajes fueron desmontados.")

def montar_particion(loop, partnum, es_bitlocker, bitlocker_password=None, root=None):
    device = f"/dev/mapper/{loop}p{partnum}" if partnum else f"/dev/{loop}"
    if not os.path.exists(device):
        device = f"/dev/{loop}p{partnum}"
    if not os.path.exists(device):
        messagebox.showerror("Error", f"No se encontró la partición: {device}", parent=root)
        return

    if es_bitlocker:
        cmd = ["dislocker", "-V", device, "-u", bitlocker_password,
               "--", "/mnt/dislocker"]
        os.makedirs("/mnt/dislocker", exist_ok=True)
        resultado = subprocess.run(cmd, capture_output=True)
        if resultado.returncode != 0:
            messagebox.showerror("Error", f"No se pudo desbloquear BitLocker:\n{resultado.stderr.decode()}", parent=root)
            try:
                shutil.rmtree("/mnt/dislocker")
            except Exception as e:
                print(f"No se pudo eliminar /mnt/dislocker: {e}")
            return
        device = "/mnt/dislocker/dislocker-file"

    punto_montaje = f"/mnt/imagen_{loop}_{partnum}"
    os.makedirs(punto_montaje, exist_ok=True)
    resultado = subprocess.run(["mount", device, punto_montaje])
    if resultado.returncode == 0:
        montajes.append(punto_montaje)
        messagebox.showinfo("Montado", f"Montado en: {punto_montaje}", parent=root)
    else:
        messagebox.showerror("Error", f"No se pudo montar {device}", parent=root)
        try:
            shutil.rmtree(punto_montaje)
        except Exception as e:
            print(f"No se pudo eliminar {punto_montaje}: {e}")

def mostrar_particiones(loop, root):
    output = ejecutar(["fdisk", "-l", f"/dev/{loop}"])
    particiones = re.findall(rf"/dev/{loop}p?(\d+).*", output)
    ventana = tk.Toplevel(root)
    ventana.title("Elegir partición a montar")
    centrar_ventana(ventana, 350, 150)

    for part in particiones:
        ruta = f"/dev/{loop}p{part}"
        bitlocker = ejecutar(["blkid", ruta])
        es_bit = "BitLocker" in bitlocker or "FVE" in bitlocker
        etiqueta = f"{ruta} {'(BitLocker)' if es_bit else ''}"

        def on_click(p=part, b=es_bit):
            ventana.destroy()
            password = None
            if b:
                password = simpledialog.askstring("Contraseña BitLocker",
                                                  f"Ingresá la contraseña para {ruta}:", show='*', parent=root)
                if not password:
                    return
            threading.Thread(target=montar_particion, args=(loop, p, b, password, root), daemon=True).start()

        btn = tk.Button(ventana, text=etiqueta, command=on_click)
        btn.pack(padx=10, pady=5)

def montar_imagen(root):
    archivo = filedialog.askopenfilename(filetypes=[("Imágenes de disco", "*.dd *.img *.iso *.raw *.bin"), ("Todos los archivos", "*.*")], parent=root)
    if not archivo:
        return

    loop = ejecutar(["losetup", "-f", "--show", "-P", archivo])
    if not loop:
        messagebox.showerror("Error", "No se pudo asociar el archivo con loop.", parent=root)
        return

    loop = os.path.basename(loop)
    mostrar_particiones(loop, root)

def crear_gui():
    root = tk.Tk()
    root.title("Montador de Imágenes de Disco")
    centrar_ventana(root, 400, 180)

    btn_montar = tk.Button(root, text="Montar imagen", command=lambda: montar_imagen(root), height=2, width=30)
    btn_montar.pack(pady=20)

    btn_desmontar = tk.Button(root, text="Desmontar todo",
                              command=lambda: threading.Thread(target=desmontar_todo, daemon=True).start(),
                              height=2, width=30)
    btn_desmontar.pack()

    root.mainloop()

if __name__ == "__main__":
    crear_gui()