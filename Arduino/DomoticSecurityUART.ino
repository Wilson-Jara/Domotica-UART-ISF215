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
  // TODO(Vicente Saa)
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
  // TODO(Vicente Saa)
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
