#!/usr/bin/env python3
"""
@file domotic_backend.py
@brief Daemon de Control de Seguridad Domótica, Integración IoT y UART robusto.
"""

# ============================================================================
# [VICENTE GARCIA] Imports del módulo
# ============================================================================
import serial
import time
import threading
import serial.tools.list_ports
import logging
# ============================================================================
# [FRANCISCA] Imports de red para IMAP/SMTP
# ============================================================================
import smtplib
import imaplib
import email
from email.mime.text import MIMEText

BAUD_RATE = 9600
SOF_BYTE = 0xAA

# ============================================================================
# [VICENTE GARCIA] Credenciales de correo (EMAIL_USER, EMAIL_PASS, servidores)
# ============================================================================
EMAIL_USER = "galletas.uv@gmail.com"
EMAIL_PASS = "ljhd eldh rwwb gpjh"
IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ============================================================================
# [VICENTE GARCIA] Configurar logging
# ============================================================================
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s')


class DomoticGateway:

    # ========================================================================
    # [VICENTE GARCIA] __init__: self.ser, self.is_running, self.lock
    # ========================================================================
    def __init__(self):
        self.ser = None
        self.is_running = True
        self.lock = threading.Lock()

    # ========================================================================
    # [VICENTE GARCIA] conectar_serial(): auto-detección de puerto Arduino
    # ========================================================================
    def conectar_serial(self):
        try:
            logging.info("Iniciando escaneo automático de puertos seriales...")
            puertos = serial.tools.list_ports.comports()
            puerto_detectado = None
            
            # Palabras clave para identificar Arduinos genuinos y clones comunes
            palabras_clave = ["arduino", "uno", "ch340", "usb-serial", "ftdi", "vid_2341"]
            
            for p in puertos:
                descripcion = p.description.lower()
                hardware_id = p.hwid.lower()
                
                if any(kw in descripcion or kw in hardware_id for kw in palabras_clave):
                    puerto_detectado = p.device
                    logging.info(f"Dispositivo compatible identificado: {p.description} en {p.device}")
                    break
            
            # Fallback: Si no identifica la palabra clave, usa el primer puerto que encuentre
            if not puerto_detectado and puertos:
                puerto_detectado = puertos[0].device
                logging.warning(f"No se identificó firma explícita de Arduino. Usando puerto por defecto: {puerto_detectado}")
            
            if not puerto_detectado:
                raise serial.SerialException("Falla de hardware: No se detectó ningún dispositivo serial activo en el sistema.")
                
            self.ser = serial.Serial(puerto_detectado, BAUD_RATE, timeout=0.1)
            time.sleep(2)  # Esperar el autoreboot clásico del ATmega328P
            logging.info(f"Conexión UART establecida exitosamente en: {puerto_detectado}")
            
        except Exception as e:
            logging.error(f"Error crítico de configuración serial: {e}")
            raise e

    # ========================================================================
    # [VICENTE GARCIA] enviar_trama(): construir y enviar trama UART con lock
    # ========================================================================
    def enviar_trama(self, msg_id, data=bytes()):
        with self.lock:
            length = len(data)
            checksum = msg_id ^ length
            for b in data:
                checksum ^= b
            
            trama = bytes([SOF_BYTE, msg_id, length]) + data + bytes([checksum])
            self.ser.write(trama)
            logging.info(f"Trama Enviada -> ID: {hex(msg_id)} | Len: {length} | Bytes: {trama.hex().upper()}")

    # ========================================================================
    # [FRANCISCA] enviar_correo_alerta(): enviar alerta SMTP al detectar intruso
    # ========================================================================
    def enviar_correo_alerta(self, distancia):
        # Envía un correo electrónico crítico cuando el Arduino reporta un intruso.
        try:
            msg = MIMEText(f"CRÍTICO: Se ha detectado un intruso a una distancia de {distancia} cm. El sistema ha cerrado los accesos automáticamente.")
            msg['Subject'] = "[ALERTA] Intrusión Detectada en Sistema Domótico"
            msg['From'] = EMAIL_USER
            msg['To'] = EMAIL_USER

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_USER, EMAIL_PASS)
                server.sendmail(EMAIL_USER, [EMAIL_USER], msg.as_string())
            logging.info("Correo electrónico de alerta enviado satisfactoriamente.")
        except Exception as e:
            logging.error(f"Falla al despachar el correo electrónico: {e}")

    # ========================================================================
    # [FRANCISCA] procesar_comando_remoto(): parsear texto y enviar trama UART
    # ========================================================================
    def procesar_comando_remoto(self, comando_texto):
        # Analiza el texto del correo recibido y llama al método enviar_trama
        # para despachar la orden correspondiente al hardware.
        cmd = comando_texto.strip().lower()
        logging.info(f"Procesando comando remoto proveniente de email: '{cmd}'")
        if "abrir puerta" in cmd: self.enviar_trama(0x02)
        elif "cerrar puerta" in cmd: self.enviar_trama(0x03)
        elif "abrir ventana" in cmd: self.enviar_trama(0x04)
        elif "cerrar ventana" in cmd: self.enviar_trama(0x05)
        elif "status" in cmd: self.enviar_trama(0x06)
        else: logging.warning("Comando vía email irreconocible.")

    # ========================================================================
    # [FRANCISCA] hilo_lectura_serial(): FSM receptora en hilo dedicado
    # ========================================================================
    def hilo_lectura_serial(self):
        # Hilo concurrente que escucha pasivamente el puerto COM. 
        # Opera mediante una Máquina de Estados (FSM) validando SOF, ID, LEN y Checksum.
        logging.info("Iniciando Hilo Reactor Serial...")
        state = "WAIT_SOF"
        rx_id = rx_len = t_marca_recibo = 0
        rx_data = bytearray()

        while self.is_running:
            try:
                if self.ser.in_waiting > 0:
                    b = ord(self.ser.read(1))
                    if state == "WAIT_SOF" and b == SOF_BYTE:
                        t_marca_recibo = time.perf_counter_ns()
                        state, rx_data = "WAIT_ID", bytearray()
                    elif state == "WAIT_ID":
                        rx_id, state = b, "WAIT_LEN"
                    elif state == "WAIT_LEN":
                        rx_len = b
                        state = "WAIT_CHK" if rx_len == 0 else "WAIT_DATA"
                    elif state == "WAIT_DATA":
                        rx_data.append(b)
                        if len(rx_data) >= rx_len: state = "WAIT_CHK"
                    elif state == "WAIT_CHK":
                        chk_calc = rx_id ^ rx_len
                        for db in rx_data: chk_calc ^= db
                        if chk_calc == b:
                            self.despachar_trama_valida(rx_id, rx_data, t_marca_recibo)
                        else:
                            logging.error(f"Error de Checksum. Calculado: {hex(chk_calc)}, Recibido: {hex(b)}")
                        state = "WAIT_SOF"
                else:
                    time.sleep(0.001)
            except Exception as e:
                logging.error(f"Error en hilo de lectura serial: {e}")
                break

    # ========================================================================
    # [FRANCISCA] despachar_trama_valida(): procesar tramas según msg_id
    # ========================================================================
    def despachar_trama_valida(self, msg_id, payload, t_recibo):
        # Interpreta la carga útil (payload) de una trama ya validada.
        # Delega el envío de correos a un hilo temporal ("EmailAlertThread") para evitar bloqueos.
        if msg_id == 0x01: 
            threading.Thread(target=self.enviar_correo_alerta, args=(payload[0],), name="EmailAlertThread").start()
        elif msg_id == 0x07: 
            t_mcu_micros = int.from_bytes(payload[1:5], byteorder='little')
            logging.info(f" [ACK Recibido] Comando ID: {hex(payload[0])}. Tiempo interno MCU: {t_mcu_micros} us")
        elif msg_id == 0x06: 
            p, v, a = ("Abierta" if payload[0] == 1 else "Cerrada"), ("Abierta" if payload[1] == 1 else "Cerrada"), ("ACTIVA" if payload[2] == 1 else "Inactiva")
            logging.info(f"=== ESTADO === Puerta: {p} | Ventana: {v} | Alarma: {a}")
        elif msg_id == 0x08: 
            logging.error(f"Microcontrolador reportó error: {hex(payload[0])}")

    # ========================================================================
    # [FRANCISCA] hilo_monitoreo_email(): polling IMAP de comandos remotos
    # ========================================================================
    def hilo_monitoreo_email(self):
        # Hilo que se conecta a Gmail cada 10 segundos buscando comandos en el asunto.
        logging.info("Iniciando Hilo Consultor de Correo IMAP...")
        while self.is_running:
            mail = None
            try:
                mail = imaplib.IMAP4_SSL(IMAP_SERVER)
                mail.login(EMAIL_USER, EMAIL_PASS)
                mail.select("inbox")
                status, search_data = mail.search(None, '(UNSEEN SUBJECT "[DOMOTICA_CMD]")')
                for num in search_data[0].split():
                    status, data = mail.fetch(num, '(RFC822)')
                    email_message = email.message_from_bytes(data[0][1])
                    body = email_message.get_payload(decode=True).decode() if not email_message.is_multipart() else next(part.get_payload(decode=True).decode() for part in email_message.walk() if part.get_content_type() == "text/plain")
                    self.procesar_comando_remoto(body)
                    mail.store(num, '+FLAGS', '\\Seen')
            except Exception as e:
                logging.error(f"Error IMAP: {e}")
            finally:
                if mail:
                    try: mail.logout()
                    except: pass
            time.sleep(10)

    # ========================================================================
    # [VICENTE GARCIA] iniciar(): lanzar hilos y menú CLI interactivo
    # ========================================================================
    def iniciar(self):
        self.conectar_serial()
        # --- [FRANCISCA] INICIO DE HILOS ---
        # Arrancar los procesos paralelos en el fondo para que el menú principal de CLI no se congele.
        t_serial = threading.Thread(target=self.hilo_lectura_serial, name="SerialThread", daemon=True)
        t_email = threading.Thread(target=self.hilo_monitoreo_email, name="EmailThread", daemon=True)
        t_serial.start()
        t_email.start()
        # ---------------------------------------

        try:
            while True:
                print("\n--- Panel de Control de Hardware ---")
                print("1. Consultar Estado")
                print("2. Forzar Apertura de Puerta")
                print("3. Forzar Cierre de Puerta")
                print("4. Forzar Apertura de Ventana")
                print("5. Forzar Cierre de Ventana")
                print("6. Salir")
                opc = input("Seleccione una opción: ")
                
                if opc == '1': 
                    self.enviar_trama(0x06)  # MSG_ESTADO
                elif opc == '2': 
                    self.enviar_trama(0x02)  # MSG_ABRIR_PUERTA
                elif opc == '3': 
                    self.enviar_trama(0x03)  # MSG_CERRAR_PUERTA
                elif opc == '4': 
                    self.enviar_trama(0x04)  # MSG_ABRIR_VENTANA
                elif opc == '5': 
                    self.enviar_trama(0x05)  # MSG_CERRAR_VENTANA
                elif opc == '6': 
                    break
                else:
                    print("Opción no válida. Intente nuevamente.")
        except KeyboardInterrupt:
            pass
        finally:
            self.is_running = False
            if self.ser:
                self.ser.close()
            logging.info("Apagado del sistema limpio completado.")


if __name__ == "__main__":
    gateway = DomoticGateway()
    gateway.iniciar()
