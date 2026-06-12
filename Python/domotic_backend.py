#!/usr/bin/env python3
"""
@file codigo.py
@brief Daemon de Control de Seguridad Domótica, Conexión Serial e Interfaz CLI.
"""

import serial
import time
import threading
import serial.tools.list_ports
import logging

# --- CONFIGURACIONES INTEGRALES ---
BAUD_RATE = 9600
SOF_BYTE = 0xAA

# Configuración estricta de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s')

class DomoticGateway:
    def __init__(self):
        self.ser = None
        self.is_running = True
        self.lock = threading.Lock()
        
    def conectar_serial(self):
        try:
            logging.info("Iniciando escaneo automático de puertos seriales...")
            puertos = serial.tools.list_ports.comports()
            puerto_detectado = None
            
            # Palabras clave para identificar Arduinos genuinos y clones comunes (CH340/Placas Genéricas)
            palabras_clave = ["arduino", "uno", "ch340", "usb-serial", "ftdi", "vid_2341"]
            
            for p in puertos:
                descripcion = p.description.lower()
                hardware_id = p.hwid.lower()
                
                # Evaluar si el puerto coincide con algún criterio conocido
                if any(kw in descripcion or kw in hardware_id for kw in palabras_clave):
                    puerto_detectado = p.device
                    logging.info(f"Dispositivo compatible identificado: {p.description} en {p.device}")
                    break
            
            # Estrategia de respaldo (Fallback): Si no identifica la palabra clave, usa el primer puerto que encuentre
            if not puerto_detectado and puertos:
                puerto_detectado = puertos[0].device
                logging.warning(f"No se identificó firma explícita de Arduino. Usando puerto por defecto: {puerto_detectado}")
            
            # Si la lista está completamente vacía
            if not puerto_detectado:
                raise serial.SerialException("Falla de hardware: No se detectó ningún dispositivo serial activo en el sistema.")
                
            # Establecer la conexión con el puerto dinámico
            self.ser = serial.Serial(puerto_detectado, BAUD_RATE, timeout=0.1)
            time.sleep(2)  # Esperar el autoreboot clásico del ATmega328P
            logging.info(f"Conexión UART establecida exitosamente en: {puerto_detectado}")
            
        except Exception as e:
            logging.error(f"Error crítico de configuración serial: {e}")
            raise e
    
    def enviar_trama(self, msg_id, data=bytes()):
        with self.lock:
            length = len(data)
            checksum = msg_id ^ length
            for b in data:
                checksum ^= b
            
            trama = bytes([SOF_BYTE, msg_id, length]) + data + bytes([checksum])
            self.ser.write(trama)
            logging.info(f"Trama Enviada -> ID: {hex(msg_id)} | Len: {length} | Bytes: {trama.hex().upper()}")

    def hilo_lectura_serial(self):
        logging.info("Iniciando Hilo Reactor Serial...")
        state = "WAIT_SOF"
        rx_id = 0
        rx_len = 0
        rx_data = bytearray()
        
        while self.is_running:
            try:
                if self.ser.in_waiting > 0:
                    b = ord(self.ser.read(1))
                    
                    if state == "WAIT_SOF":
                        if b == SOF_BYTE:
                            t_marca_recibo = time.perf_counter_ns()
                            state = "WAIT_ID"
                            rx_data.clear()
                            
                    elif state == "WAIT_ID":
                        rx_id = b
                        state = "WAIT_LEN"
                        
                    elif state == "WAIT_LEN":
                        rx_len = b
                        if rx_len == 0:
                            state = "WAIT_CHK"
                        else:
                            state = "WAIT_DATA"
                            
                    elif state == "WAIT_DATA":
                        rx_data.append(b)
                        if len(rx_data) >= rx_len:
                            state = "WAIT_CHK"
                            
                    elif state == "WAIT_CHK":
                        # Validar Checksum
                        chk_calc = rx_id ^ rx_len
                        for db in rx_data:
                            chk_calc ^= db
                            
                        if chk_calc == b:
                            # Trama Válida, Despachar lógicamente
                            self.despachar_trama_valida(rx_id, rx_data, t_marca_recibo)
                        else:
                            logging.error(f"Error de Checksum detectado en hardware. Calculado: {hex(chk_calc)}, Recibido: {hex(b)}")
                        state = "WAIT_SOF"
                else:
                    time.sleep(0.001) # Liberar CPU
            except Exception as e:
                logging.error(f"Error en hilo de lectura serial: {e}")
                break

    def despachar_trama_valida(self, msg_id, payload, t_recibo):
        if msg_id == 0x01: # ALERTA_INTRUSO
            distancia = payload[0]
            logging.warning(f"¡INTRUSO DETECTADO! Distancia leída por hardware: {distancia} cm.")
            
        elif msg_id == 0x07: # ACK
            id_confirmado = payload[0]
            t_mcu_micros = int.from_bytes(payload[1:5], byteorder='little')
            logging.info(f" [ACK Recibido] Confirma ejecución de Comando ID: {hex(id_confirmado)}. Tiempo de procesamiento interno MCU: {t_mcu_micros} us")
            
        elif msg_id == 0x06: # ESTADO
            puerta = "Abierta" if payload[0] == 1 else "Cerrada"
            ventana = "Abierta" if payload[1] == 1 else "Cerrada"
            alarma = "ACTIVA" if payload[2] == 1 else "Inactiva"
            logging.info(f"=== REPORTE DE ESTADO DOMÓTICO === Puerta: {puerta} | Ventana: {ventana} | Alarma: {alarma}")
            
        elif msg_id == 0x08: # ERROR
            logging.error(f"El microcontrolador reportó una excepción de enlace de datos. Código de error: {hex(payload[0])}")

    def iniciar(self):
        self.conectar_serial()
        
        t_serial = threading.Thread(target=self.hilo_lectura_serial, name="SerialThread")
        t_serial.start()
        
        try:
            while True:
                # --- MENÚ CLI ---
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
            t_serial.join()
            self.ser.close()
            logging.info("Apagado del sistema limpio completado.")

if __name__ == "__main__":
    gateway = DomoticGateway()
    gateway.iniciar()
