# Dibujos Mágicos ✨

Una foto de un dibujo de las niñas → un video donde el dibujo **baila, saluda, salta** o **rebota como gelatina**, con fondos de parque, playa, noche, mar o espacio. Después se ven todos en grande en la tele con el **modo función**.

Todo corre en su computadora: las fotos y los videos no salen de la casa.

| Con brazos y piernas | Gelatina (cualquier garabato) |
|---|---|
| ![La niña del vestido bailando en el parque](docs/ejemplo-bailar.gif) | ![Garabato rebotando en el espacio](docs/ejemplo-rebotar.gif) |

---

## Qué necesitan

- Una computadora con **Windows 10 u 11** (de 64 bits). También funciona en Mac o Linux.
- **8 GB de RAM** o más (16 GB es mejor).
- Unos **15 GB libres** en el disco.
- Internet **solo la primera vez**, para descargar todo.
- No hace falta tarjeta de video.

## Instalarlo (una sola vez)

### 1. Instalar Docker Desktop

Docker es el programa que corre las "cajitas" donde vive Dibujos Mágicos, para no tener que instalar nada más a mano.

1. Descárguenlo de <https://www.docker.com/products/docker-desktop/> (el botón "Download for Windows").
2. Ábranlo y acepten las opciones que vienen marcadas. Si pide reiniciar, reinicien.
3. Abran **Docker Desktop**. La primera vez pide aceptar los términos; no hace falta crear cuenta (pueden darle "Skip").
4. Esperen hasta que abajo a la izquierda diga **Engine running** (en verde).

> Si Docker dice que falta **WSL**, abran "Símbolo del sistema" y escriban `wsl --install`, reinicien y vuelvan a abrir Docker Desktop.

### 2. Descargar Dibujos Mágicos

1. En la página del repositorio en GitHub, botón verde **Code → Download ZIP**.
2. Descompriman el ZIP, por ejemplo en `Documentos`.
3. Entren a la carpeta `dibujos-magicos`.

### 3. Arrancarlo

Doble clic en **`Iniciar Dibujos Magicos.bat`**.

- **La primera vez tarda entre 20 y 60 minutos**: descarga la IA de Meta y prepara todo. Pueden dejarlo trabajando. Si Windows pregunta por el firewall, den **Permitir** (en redes privadas) para poder usarlo desde el celular.
- Cuando termina se abre solo el navegador en **http://localhost:8000**.
- Las siguientes veces arranca en segundos. Si no lo detuvieron con el `.bat` de abajo, arranca solo cada vez que abren Docker Desktop.

Para apagarlo: doble clic en **`Detener Dibujos Magicos.bat`**.

En Mac o Linux, en vez del `.bat`, abran la terminal en la carpeta y escriban `./iniciar.sh`.

---

## Usarlo

![El editor de puntos](docs/editor.jpg)

1. **＋ Nuevo dibujo**: tomen la foto (desde el celular es más fácil), pónganle nombre y quién lo dibujó.
2. En unos segundos la IA recorta el dibujo y adivina dónde están la cabeza, los brazos y las piernas.
3. **Revisen los puntos**: si alguno quedó mal, arrástrenlo a su lugar (cabeza, pecho, cadera; y en cada lado hombro → codo → mano y cadera → rodilla → pie). Le den a **Guardar cambios**.
4. Si al recorte le falta un pedazo o le sobra papel, vayan a **2 · Recorte** y usen 🖌️ para agregar o 🧽 para quitar.
5. Elijan un **movimiento** y un **fondo**, y **✨ Crear animación**. Tarda entre 10 segundos y un minuto.
6. Pueden **descargar** el video para mandarlo a la familia.

### Desde el celular

En la página principal aparece un **código QR**. Escanéenlo con la cámara del celular (tiene que estar en el mismo WiFi que la computadora). Así toman la foto del dibujo directo y la suben.

### En la tele: modo función

Botón **▶ Modo función**. Pasa todos los videos uno tras otro, con el nombre del personaje y de la artista antes de cada uno. Para verlo en la tele:

- conecten la computadora a la tele con un cable **HDMI**, o
- abran la dirección que sale en el QR (por ejemplo `http://192.168.1.50:8000/funcion`) en el navegador de la tele, si es Smart TV.

Con las flechas ← → del teclado se cambia de video.

### Dos tipos de movimiento

- **Con brazos y piernas** (bailar, saludar, saltar, brincos tijera, dab): usan movimientos reales de personas, capturados por Meta. Funcionan con dibujos de personas, animales parados, monstruos… cualquier cosa con dos brazos y dos piernas separados del cuerpo.
- **Gelatina** (rebotar, bambolear, flotar, menearse): funcionan con **cualquier dibujo**, incluso los garabatos de la bebé. Cuando la IA ve que un dibujo no tiene brazos ni piernas, deja este modo seleccionado.

### Consejos para fotos que salgan bien

- Papel blanco, foto de frente (desde arriba) y con buena luz, sin sombras fuertes.
- Que el dibujo llene casi toda la foto.
- Los trazos gruesos (crayola, marcador) funcionan mejor que el lápiz.
- Para que pueda bailar: brazos y piernas que no se toquen con el cuerpo.

---

## Dónde quedan los dibujos y videos

En la carpeta **`datos`**, dentro de `dibujos-magicos`. Cada personaje tiene su carpeta con la foto original, el recorte y la carpeta `videos`. Si copian la carpeta `datos` a otra compu, se llevan todo.

## Si algo falla

| Qué pasa | Qué hacer |
|---|---|
| "Docker Desktop no está abierto" | Abran Docker Desktop, esperen "Engine running" y vuelvan a abrir el `.bat`. |
| La primera instalación se cae con "killed" o "out of memory" | Cierren otros programas y vuelvan a intentar. En Docker Desktop → Settings → Resources pueden darle más memoria. |
| La página dice "La magia se está despertando" mucho rato | La IA tarda 1–2 minutos en arrancar. Si pasan más de 5 minutos, apaguen y vuelvan a iniciar. |
| El celular no abre la página | Revisen que esté en el mismo WiFi y que Windows haya permitido a Docker en el firewall (redes privadas). |
| El personaje se mueve raro | Revisen los puntos: los de un lado (naranja) deben ir todos en el mismo brazo y pierna, y los del otro (azul) en los otros. |
| Solo se mueve una parte del dibujo | El recorte quedó en pedazos: únanlos con 🖌️ en "Recorte", o usen un movimiento gelatina. |

Para ver qué está pasando por dentro: en Docker Desktop → Containers → `dibujos-magicos` → ver los registros ("Logs") de `app` o `modelos`.

## Para curiosos: cómo funciona

- **`modelos/`**: los dos modelos de IA de [Animated Drawings de Meta](https://github.com/facebookresearch/AnimatedDrawings) (licencia MIT), servidos con TorchServe. Uno encuentra el dibujo en la foto y el otro adivina los 17 puntos del cuerpo.
- **`app/`**: la página web (Flask) y el motor.
  - `motor/anotar.py`: recorta el dibujo del papel, blanquea el papel y arma el esqueleto. Si la IA no encuentra nada, usa la tinta del papel y un esqueleto de plantilla.
  - `motor/render.py`: crea los videos. Los de brazos y piernas usan Animated Drawings sin pantalla (OSMesa). Los de gelatina son un motor propio con OpenCV. Todo se convierte a MP4 H.264 con ffmpeg.
  - `static/`: las páginas (galería, nuevo dibujo, editor, modo función).
- Los fondos son ilustraciones generadas con IA para este proyecto.

### Ideas para después

- Fiesta: varios personajes bailando juntos en el mismo video.
- Música de fondo en el modo función.
- Grabar movimientos propios (un baile de papá) con una app que convierta video a BVH.
- Que Bubu, el peluche, "vea" los dibujos de las niñas.
