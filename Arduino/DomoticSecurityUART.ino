/**
 * @file DomoticSecurityUART.ino
 * @brief Firmware de Control Domótico - Sistema de Seguridad con UART
 */

#include <Servo.h>

// ============================================================================
// [SARAI] Definir constantes de pines del hardware
// ============================================================================


// Enum con los IDs del protocolo UART.
// Define los codigos de comando, alertas y confirmaciones
// que se intercambian entre el Arduino y el backend Python.
enum MensajeID : uint8_t {
  MSG_ALERTA_INTRUSO = 0x01,
  MSG_ABRIR_PUERTA   = 0x02,
  MSG_CERRAR_PUERTA  = 0x03,
  MSG_ABRIR_VENTANA  = 0x04,
  MSG_CERRAR_VENTANA = 0x05,
  MSG_ESTADO         = 0x06,
  MSG_ACK            = 0x07,
  MSG_ERROR          = 0x08
};

const uint32_t SERIAL_BAUD = 9600;
const uint32_t TIMEOUT_UART_MS = 50;
const uint32_t REFRESH_SENSOR_MS = 250;
const uint8_t DISTANCIA_UMBRAL_CM = 20;
const uint8_t SOF_BYTE = 0xAA;


Servo servoPuerta;
Servo servoVentana;

// ============================================================================
// [SARAI] Variables globales de estado (puerta, ventana, alarma)
// ============================================================================


// FSM de recepcion UART con sus variables de estado.
// Estado actual de la maquina, buffer para armar la trama entrante
// y temporizador para detectar timeout en la recepcion.
enum RX_Estado { WAIT_SOF, WAIT_ID, WAIT_LEN, WAIT_DATA, WAIT_CHK };
RX_Estado estadoActualRX = WAIT_SOF;

uint8_t rxId = 0, rxLen = 0, rxChk = 0, rxIndexData = 0;
uint8_t rxBufferData[64];
uint32_t tUltimoByteRx = 0;
uint32_t tiempoInicioProcesamiento = 0;


// ============================================================================
// [VICENTE SAA] Variable de tiempo para el ping del sensor
// ============================================================================
uint32_t tUltimoPing = 0;

// ============================================================================
// [SARAI] setup(): inicializar Serial, pines y servos
// ============================================================================
void setup() {
  // TODO(Sarai)
}

// ============================================================================
// [VICENTE SAA] loop(): muestreo del sensor, timeout UART y control de alertas
// ============================================================================
void loop() {
  uint32_t tiempoActual = millis();
  
  // 1. Muestreo periódico del sensor
  if (tiempoActual - tUltimoPing >= REFRESH_SENSOR_MS) {
    tUltimoPing = tiempoActual;
    verificarSensorProximidad();
  }
  
  // 2. Control de Seguridad por Timeout UART
  if (estadoActualRX != WAIT_SOF && (tiempoActual - tUltimoByteRx > TIMEOUT_UART_MS)) {
    uint8_t codigoErrorTimeout = 0xE2; 
    enviarTrama(MSG_ERROR, &codigoErrorTimeout, 1); 
    estadoActualRX = WAIT_SOF;
  }
  
  // 3. CONTROL DE ALERTAS VISUALES Y SONORAS 
  if (alarmaActiva) {
    // ESTADO DE EMERGENCIA: Sirena intermitente y LED Rojo parpadeando
    if ((tiempoActual / 150) % 2 == 0) {
      tone(PIN_BUZZER, 3800); 
      digitalWrite(PIN_LED_ALERTA, LOW);  // Enciende LED Rojo (Active-LOW)
    } else {
      noTone(PIN_BUZZER);     
      digitalWrite(PIN_LED_ALERTA, HIGH); // Apaga LED Rojo
    }
    digitalWrite(PIN_LED_OK, HIGH);       // Apaga LED Verde/Amarillo
  } 
  else {
    // ESTADO SEGURO: Sistema en vigilancia, todo en calma
    noTone(PIN_BUZZER);
    digitalWrite(PIN_LED_ALERTA, HIGH);   // Apaga LED Rojo
    digitalWrite(PIN_LED_OK, LOW);        // Enciende LED Verde/Amarillo
  }
}

// Lee byte a byte del puerto serial y arma la trama entrante.
// Avanza por los estados SOF -> ID -> LEN -> DATA -> CHK.
// Al completar la trama llama a validarYProcesarTrama().
void serialEvent() {
  while (Serial.available() > 0) {
    uint8_t byteRecibido = Serial.read();
    tUltimoByteRx = millis();

    switch (estadoActualRX) {
      case WAIT_SOF:
        if (byteRecibido == SOF_BYTE) {
          tiempoInicioProcesamiento = micros();
          estadoActualRX = WAIT_ID;
        }
        break;
      case WAIT_ID:
        rxId = byteRecibido;
        estadoActualRX = WAIT_LEN;
        break;
      case WAIT_LEN:
        rxLen = byteRecibido;
        rxIndexData = 0;
        estadoActualRX = (rxLen == 0) ? WAIT_CHK : WAIT_DATA;
        break;
      case WAIT_DATA:
        rxBufferData[rxIndexData++] = byteRecibido;
        if (rxIndexData >= rxLen) estadoActualRX = WAIT_CHK;
        break;
      case WAIT_CHK:
        rxChk = byteRecibido;
        validarYProcesarTrama();
        break;
    }
  }
}

// Calcula el checksum XOR de la trama y lo compara con el recibido.
// Si es valido, despacha el comando: abre/cierra puerta o ventana,
// o envia el estado actual. Responde con ACK o ERROR segun corresponda.
void validarYProcesarTrama() {
  uint8_t checksumCalculado = rxId ^ rxLen;
  for (uint8_t i = 0; i < rxLen; i++) checksumCalculado ^= rxBufferData[i];

  if (checksumCalculado != rxChk) {
    uint8_t codigoErrorChecksum = 0xE1;
    enviarTrama(MSG_ERROR, &codigoErrorChecksum, 1);
    estadoActualRX = WAIT_SOF;
    return;
  }

  switch (rxId) {
    case MSG_ABRIR_PUERTA:   puertaAbierta = true;   enviarACK(MSG_ABRIR_PUERTA); break;
    case MSG_CERRAR_PUERTA:  puertaAbierta = false;  enviarACK(MSG_CERRAR_PUERTA); break;
    case MSG_ABRIR_VENTANA:  ventanaAbierta = true;  enviarACK(MSG_ABRIR_VENTANA); break;
    case MSG_CERRAR_VENTANA: ventanaAbierta = false; enviarACK(MSG_CERRAR_VENTANA); break;
    case MSG_ESTADO:         enviarEstado(); break;
  }
  actualizarActuadores();
  estadoActualRX = WAIT_SOF;
}

// ============================================================================
// [VICENTE SAA] verificarSensorProximidad(): HC-SR04 con lógica de auto-reset
// ============================================================================
void verificarSensorProximidad() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  
  uint32_t duracion = pulseIn(PIN_ECHO, HIGH, 20000); 
  if(duracion == 0) {
    // Si el sensor no responde o lee vacío, aseguramos que la alarma se apague
    alarmaActiva = false;
    return;
  }
  
  uint8_t distancia = duracion * 0.034 / 2;
  
  // FILTRO: Ignoramos distancias menores a 3 cm porque suelen ser ruidos o errores de inicio
  if (distancia < DISTANCIA_UMBRAL_CM && distancia > 3) {
    if (!alarmaActiva) {
      alarmaActiva = true;
      puertaAbierta = false;  // Cierre automático de seguridad
      ventanaAbierta = false; // Cierre automático de seguridad
      actualizarActuadores();
      enviarTrama(MSG_ALERTA_INTRUSO, &distancia, 1); // Avisa a Python
    }
  } 
  else if (distancia >= DISTANCIA_UMBRAL_CM) {
    // ¡LÓGICA DE AUTO-RESET! Si el intruso se va, la alarma se apaga sola
    alarmaActiva = false;
  }
}

// ============================================================================
// [SARAI] actualizarActuadores(): mover servos según estado
// ============================================================================
void actualizarActuadores() {
  // TODO(Sarai)
}

// Construye una trama binaria con formato [SOF | ID | LEN | DATA | CHK]
// y la envia por el puerto serial. El checksum se calcula con XOR
// entre el ID, la longitud y todos los bytes del payload.
void enviarTrama(uint8_t id, uint8_t* data, uint8_t len) {
  uint8_t chk = id ^ len;
  Serial.write(SOF_BYTE);
  Serial.write(id);
  Serial.write(len);
  for (uint8_t i = 0; i < len; i++) {
    Serial.write(data[i]);
    chk ^= data[i];
  }
  Serial.write(chk);
}

// Envia una trama de confirmacion (ACK) al backend Python.
// Incluye el ID del comando confirmado y el tiempo que tardo
// el microcontrolador en procesarlo, medido en microsegundos.
void enviarACK(uint8_t idConfirmado) {
  uint32_t tiempoEjecucion = micros() - tiempoInicioProcesamiento;
  uint8_t payload[5];
  payload[0] = idConfirmado;
  memcpy(&payload[1], &tiempoEjecucion, 4);
  enviarTrama(MSG_ACK, payload, 5);
}

// Envia al backend el estado actual del sistema en 3 bytes:
// puerta (abierta/cerrada), ventana (abierta/cerrada) y alarma (activa/inactiva).
// Se usa tanto para consultas periodicas como respuesta al comando MSG_ESTADO.
void enviarEstado() {
  uint8_t payload[3];
  payload[0] = puertaAbierta ? 0x01 : 0x00;
  payload[1] = ventanaAbierta ? 0x01 : 0x00;
  payload[2] = alarmaActiva ? 0x01 : 0x00;
  enviarTrama(MSG_ESTADO, payload, 3);
}
