## **Descripción general**

Este programa es una aplicación en Python con interfaz gráfica (Tkinter) que permite **montar y desmontar imágenes de disco** (`.img`, `.dd`, `.iso`, `.raw`, `.bin`), incluso aquellas cifradas con **BitLocker**, en sistemas Linux.
Requiere privilegios de superusuario y está diseñado para ejecutarse con `pkexec` cuando no se invoca como root.

---

## **Flujo principal**

1. **Verifica permisos**: Si no se ejecuta como root (`os.geteuid() != 0`), relanza el script con `pkexec` manteniendo el entorno gráfico.
2. **Carga GUI** con dos botones principales:

   * **Montar imagen**: abre un selector de archivos, asocia la imagen a un dispositivo loop y permite elegir partición.
   * **Desmontar todo**: desmonta todas las particiones montadas y libera los recursos.
3. **Permite montar particiones cifradas con BitLocker** solicitando la contraseña y usando `dislocker`.

---

## **Funciones principales**

### `centrar_ventana(ventana, ancho=400, alto=200)`

Centra la ventana en la pantalla según el ancho y alto indicados.

### `relanzar_con_pkexec()`

Relanza el script usando `pkexec` y manteniendo las variables necesarias (`DISPLAY`, `XAUTHORITY`) para mostrar la interfaz gráfica como root.

### `ejecutar(cmd)`

Ejecuta un comando en la terminal y devuelve la salida como texto. Silencia los errores.

### `desmontar_todo()`

* Desmonta todos los puntos de montaje registrados en `montajes`.
* Si se usó BitLocker, desmonta `/mnt/dislocker` y borra la carpeta.
* Libera los dispositivos loop asociados a imágenes montadas.
* Muestra mensaje de confirmación.

### `montar_particion(loop, partnum, es_bitlocker, bitlocker_password=None, root=None)`

* Determina el dispositivo de la partición (`/dev/loopXpY`).
* Si es BitLocker, usa `dislocker` para desbloquear con la contraseña y monta el volumen resultante.
* Monta la partición en `/mnt/imagen_loop_partición` y la guarda en la lista `montajes`.

### `mostrar_particiones(loop, root)`

* Usa `fdisk` para listar particiones de un dispositivo loop.
* Detecta si alguna está cifrada con BitLocker (`blkid`).
* Muestra botones para montar cada partición, pidiendo la contraseña si corresponde.

### `montar_imagen(root)`

* Permite seleccionar un archivo de imagen de disco.
* Lo asocia a un dispositivo loop con `losetup -P` (detectando particiones).
* Llama a `mostrar_particiones()` para elegir cuál montar.

### `crear_gui()`

* Construye la ventana principal con dos botones:

  * "Montar imagen"
  * "Desmontar todo"
* Inicia el bucle principal de Tkinter.

---

## **Requisitos del sistema**

* Linux con soporte para `losetup`, `mount`, `umount`, `fdisk`, `blkid`, `dislocker`.
* Privilegios de superusuario (`root` o `pkexec`).
* Python 3 con `tkinter` instalado.

---

## **Resumen del funcionamiento**

1. El usuario abre la aplicación → selecciona una imagen de disco.
2. El script crea un dispositivo loop y detecta particiones.
3. El usuario selecciona la partición → si está cifrada, introduce contraseña.
4. El script monta la partición en `/mnt/imagen_loop_part`.
5. Cuando ya no se necesite, se pulsa "Desmontar todo" para liberar recursos.
