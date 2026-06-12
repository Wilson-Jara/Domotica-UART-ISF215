/**
 * @file DomoticSecurityUART.ino
 * @brief Firmware de Control Domótico - Sistema de Seguridad con UART
 */

#include <Servo.h>

// ============================================================================
// [SARAI] Definir constantes de pines del hardware
// ============================================================================


// ============================================================================
// [WILSON] Enum MensajeID con los IDs del protocolo
// ============================================================================
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


// ============================================================================
// [WILSON] Enum RX_Estado y variables de la FSM receptora UART
// ============================================================================


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

// ============================================================================
// [WILSON] serialEvent(): FSM de recepción byte a byte
// ============================================================================
void serialEvent() {
  // TODO(Wilson)
}

// ============================================================================
// [WILSON] validarYProcesarTrama(): verificar checksum y despachar comandos
// ============================================================================
void validarYProcesarTrama() {
  // TODO(Wilson)
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

// ============================================================================
// [WILSON] enviarTrama(): construir y enviar trama [SOF][ID][LEN][DATA][CHK]
// ============================================================================
void enviarTrama(uint8_t id, uint8_t* data, uint8_t len) {
  // TODO(Wilson)
}

// ============================================================================
// [WILSON] enviarACK(): confirmación con tiempo de procesamiento del MCU
// ============================================================================
void enviarACK(uint8_t idConfirmado) {
  // TODO(Wilson)
}

// ============================================================================
// [WILSON] enviarEstado(): reportar puerta/ventana/alarma al backend
// ============================================================================
void enviarEstado() {
  // TODO(Wilson)
}
