import tkinter as tk
import math
import socket
import threading
import time
import json

# Configuracion esp32
ESP32_IP = "172.26.109.127"   
ESP32_PORT = 8080

# Comunicaciion tcp
class TCPClient:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.conectado = False
        self.lock = threading.Lock()
        self.conectar()

    def conectar(self):
        while not self.conectado:
            try:
                print("Intentando conectar con ESP32...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.ip, self.port))
                self.sock.settimeout(0.5)
                self.conectado = True
                print(" Conectado al ESP32.")
            except:
                print(" Reintentando conexión en 3s...")
                time.sleep(3)

    def enviar(self, mensaje):
        with self.lock:
            try:
                if self.conectado:
                    self.sock.sendall((mensaje + "\n").encode())
            except:
                print(" Error al enviar, reconectando...")
                self.conectado = False
                self.conectar()

    def recibir(self):
        try:
            if self.conectado:
                data = self.sock.recv(1024).decode().strip()
                return data
        except socket.timeout:
            return ""
        except:
            print(" Conexión perdida, reconectando...")
            self.conectado = False
            self.conectar()
        return ""

# Simulacion de la rueda
class RuedaSimulada:
    def __init__(self, canvas):
        self.canvas = canvas
        self.cabinas = []
        self.angulo = 0
        self.radio = 80
        self.centro = (150, 150)
        self.en_movimiento = False
        self.crear_rueda()

    def crear_rueda(self):
        self.canvas.delete("all")
        self.canvas.create_oval(50, 50, 250, 250, outline="blue", width=3)
        for _ in range(7):
            cabina = self.canvas.create_oval(0, 0, 0, 0, fill="gray")
            self.cabinas.append(cabina)
        self.actualizar()

    def actualizar(self):
        for i, cabina in enumerate(self.cabinas):
            angulo = self.angulo + i * (360 / 7)
            rad = math.radians(angulo)
            x = self.centro[0] + self.radio * math.cos(rad)
            y = self.centro[1] + self.radio * math.sin(rad)
            self.canvas.coords(cabina, x - 10, y - 10, x + 10, y + 10)

    def girar(self, pasos=1, velocidad=2):
        if not self.en_movimiento:
            return
        self.angulo = (self.angulo + 360 / 2048 * pasos) % 360
        self.actualizar()
        self.canvas.after(velocidad, lambda: self.girar(pasos, velocidad))

    def iniciar(self, velocidad):
        if not self.en_movimiento:
            self.en_movimiento = True
            self.girar(1, velocidad)

    def detener(self):
        self.en_movimiento = False

    def activar_cabina(self, index):
        for i, cabina in enumerate(self.cabinas):
            color = "red" if i == index - 1 else "gray"
            self.canvas.itemconfig(cabina, fill=color)

# Interfaz grafica
class GemeloDigital:
    def __init__(self, root, cliente):
        self.root = root
        self.cliente = cliente
        self.velocidad = 2
        self.estado_motor = False

        # Elementos Ui
        self.canvas = tk.Canvas(root, width=300, height=300)
        self.rueda = RuedaSimulada(self.canvas)

        self.conn_lbl = tk.Label(root, text=" Desconectado", fg="red", font=("Arial", 11, "bold"))
        self.estado_lbl = tk.Label(root, text="Estado: ---", font=("Arial", 12))
        self.temp_lbl = tk.Label(root, text="Temperatura: --- °C", font=("Arial", 12))
        self.hum_lbl = tk.Label(root, text="Humedad: --- %", font=("Arial", 12))
        self.vel_lbl = tk.Label(root, text="Velocidad: 2 ms/paso", font=("Arial", 12))

        self.btn_start = tk.Button(root, text="▶ Iniciar", bg="green", fg="white", command=self.iniciar)
        self.btn_stop = tk.Button(root, text="⏸ Detener", bg="red", fg="white", command=self.detener)
        self.btn_mas = tk.Button(root, text="+ Velocidad", command=self.aumentar)
        self.btn_menos = tk.Button(root, text="– Velocidad", command=self.disminuir)

        # Layout
        self.conn_lbl.pack(pady=2)
        self.estado_lbl.pack()
        self.temp_lbl.pack()
        self.hum_lbl.pack()
        self.vel_lbl.pack(pady=3)
        self.btn_start.pack(pady=2)
        self.btn_stop.pack(pady=2)
        self.btn_mas.pack(pady=2)
        self.btn_menos.pack(pady=2)
        self.canvas.pack(pady=10)

        # Hilos
        self.iniciar_hilo_recepcion()
        self.actualizar_estado_conexion()

    # Funciones UI
    def iniciar(self):
        self.estado_motor = True
        self.cliente.enviar("start")
        self.rueda.iniciar(self.velocidad)

    def detener(self):
        self.estado_motor = False
        self.cliente.enviar("stop")
        self.rueda.detener()

    def aumentar(self):
        self.velocidad = max(1, self.velocidad - 1)
        self.cliente.enviar(f"velocidad:{self.velocidad}")
        self.vel_lbl.config(text=f"Velocidad: {self.velocidad} ms/paso")

    def disminuir(self):
        self.velocidad = min(20, self.velocidad + 1)
        self.cliente.enviar(f"velocidad:{self.velocidad}")
        self.vel_lbl.config(text=f"Velocidad: {self.velocidad} ms/paso")

    # Procesar datos
    def procesar(self, linea):
        if not linea:
            return

        if linea.startswith("SENSOR:"):
            try:
                json_str = linea.split("SENSOR:")[1]
                datos = json.loads(json_str)
                temp = datos.get("temperatura", "---")
                hum = datos.get("humedad", "---")
                self.temp_lbl.config(text=f"Temperatura: {temp:.1f} °C")
                self.hum_lbl.config(text=f"Humedad: {hum:.1f} %")
            except Exception as e:
                print("Error parseando SENSOR:", e)

        elif "BLOQUEADO" in linea:
            self.estado_motor = False
            self.rueda.detener()
            self.estado_lbl.config(text="Estado: BLOQUEADO", fg="red")

        elif "OK:STOP" in linea:
            self.estado_motor = False
            self.rueda.detener()
            self.estado_lbl.config(text="Estado: DETENIDO", fg="black")

        elif "OK:START" in linea:
            self.estado_motor = True
            self.rueda.iniciar(self.velocidad)
            self.estado_lbl.config(text="Estado: GIRANDO", fg="green")

        elif "OK:VEL" in linea:
            valor = linea.split(":")[-1]
            self.vel_lbl.config(text=f"Velocidad: {valor} ms/paso")

    # Hilos
    def escuchar(self):
        while True:
            data = self.cliente.recibir()
            if data:
                for linea in data.split("\n"):
                    self.root.after(0, lambda l=linea.strip(): self.procesar(l))

    def iniciar_hilo_recepcion(self):
        hilo = threading.Thread(target=self.escuchar, daemon=True)
        hilo.start()

    def actualizar_estado_conexion(self):
        if self.cliente.conectado:
            self.conn_lbl.config(text=" Conectado", fg="green")
        else:
            self.conn_lbl.config(text=" Desconectado", fg="red")
        self.root.after(1000, self.actualizar_estado_conexion)

# Ejecucion 
if __name__ == "__main__":
    root = tk.Tk()
    root.title(" Gemelo Digital - Rueda de la Fortuna WiFi")

    cliente = TCPClient(ESP32_IP, ESP32_PORT)
    app = GemeloDigital(root, cliente)

    root.mainloop()
