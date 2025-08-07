#!/usr/bin/env python3
import os
import sys
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import re

bitlocker_password_cache = None
montajes = []

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
            os.rm("-rf ",mnt)
        except:
            pass
    montajes.clear()

    # Desmontar BitLocker si se usó
    if os.path.ismount("/mnt/dislocker"):
        subprocess.run(["umount", "/mnt/dislocker"])
        try:
            os.rm("-rf /mnt/dislocker")
        except:
            pass

    # Eliminar loop devices creados por el script
    losetups = ejecutar(["losetup", "-a"]).splitlines()
    for linea in losetups:
        if "/imagen_" in linea or any(ext in linea for ext in [".img", ".dd", ".iso", ".raw", ".bin"]):
            loopdev = linea.split(":")[0]
            print(f"Liberando loop: {loopdev}")
            subprocess.run(["losetup", "-d", loopdev])

    messagebox.showinfo("Listo", "Todos los montajes fueron desmontados.")

def montar_particion(loop, partnum, es_bitlocker):
    global bitlocker_password_cache
    device = f"/dev/mapper/{loop}p{partnum}" if partnum else f"/dev/{loop}"
    if not os.path.exists(device):
        device = f"/dev/{loop}p{partnum}"
    if not os.path.exists(device):
        messagebox.showerror("Error", f"No se encontró la partición: {device}")
        return

    if es_bitlocker:
        if not bitlocker_password_cache:
            bitlocker_password_cache = simpledialog.askstring("Contraseña BitLocker",
                                                              f"Ingresá la contraseña para {device}:",
                                                              show='*')
        unlocked = f"/dev/mapper/bitlocker_{loop}_{partnum}"
        cmd = ["dislocker", "-V", device, "-u", bitlocker_password_cache,
               "--", "/mnt/dislocker"]
        os.makedirs("/mnt/dislocker", exist_ok=True)
        subprocess.run(cmd)
        device = "/mnt/dislocker/dislocker-file"

    punto_montaje = f"/mnt/imagen_{loop}_{partnum}"
    os.makedirs(punto_montaje, exist_ok=True)
    resultado = subprocess.run(["mount", device, punto_montaje])
    if resultado.returncode == 0:
        montajes.append(punto_montaje)
        messagebox.showinfo("Montado", f"Montado en: {punto_montaje}")
    else:
        messagebox.showerror("Error", f"No se pudo montar {device}")

def mostrar_particiones(loop):
    output = ejecutar(["fdisk", "-l", f"/dev/{loop}"])
    particiones = re.findall(rf"/dev/{loop}p?(\d+).*", output)
    ventana = tk.Toplevel()
    ventana.title("Elegir partición a montar")

    for part in particiones:
        ruta = f"/dev/{loop}p{part}"
        bitlocker = ejecutar(["blkid", ruta])
        es_bit = "BitLocker" in bitlocker or "FVE" in bitlocker
        etiqueta = f"{ruta} {'(BitLocker)' if es_bit else ''}"
        btn = tk.Button(ventana, text=etiqueta,
                        command=lambda p=part, b=es_bit: [ventana.destroy(), montar_particion(loop, p, b)])
        btn.pack(padx=10, pady=5)

def montar_imagen():
    archivo = filedialog.askopenfilename(filetypes=[("Imágenes de disco", "*.dd *.img *.iso *.raw *.bin"), ("Todos los archivos", "*.*")])
    if not archivo:
        return

    loop = ejecutar(["losetup", "-f", "--show", "-P", archivo])
    if not loop:
        messagebox.showerror("Error", "No se pudo asociar el archivo con loop.")
        return

    loop = os.path.basename(loop)
    mostrar_particiones(loop)

def crear_gui():
    root = tk.Tk()
    root.title("Montador de Imágenes de Disco")
    root.geometry("400x180")

    btn_montar = tk.Button(root, text="Montar imagen", command=montar_imagen, height=2, width=30)
    btn_montar.pack(pady=20)

    btn_desmontar = tk.Button(root, text="Desmontar todo", command=desmontar_todo, height=2, width=30)
    btn_desmontar.pack()

    root.mainloop()

if __name__ == "__main__":
    crear_gui()

