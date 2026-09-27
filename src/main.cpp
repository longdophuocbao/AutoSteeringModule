#include <Arduino.h>
#include <SPI.h>
#include <mcp_can.h>
#include <AudioGeneratorWAV.h>
#include <AudioOutputI2S.h>
#include <AudioFileSourcePROGMEM.h>
#include "audio_data.h"

// -------------------------------------------------------------
// 1. Khai báo chân phần cứng (Hardware Pin Definitions)
// -------------------------------------------------------------
// MCP2515 (SPI)
#define CAN_CS_PIN   D10
#define CAN_INT_PIN  D2
#define CAN_SI_PIN   D11 // SPI MOSI
#define CAN_SO_PIN   D12 // SPI MISO
#define CAN_SCK_PIN  D13 // SPI SCK

// MAX98357A (I2S)
#define I2S_BCLK_PIN D6  // Bit Clock
#define I2S_LRC_PIN  D7  // Left/Right Clock (WS)
#define I2S_DIN_PIN  D8  // Data In

// -------------------------------------------------------------
// 2. Khai báo đối tượng MCP2515 & Audio
// -------------------------------------------------------------
MCP_CAN CAN(CAN_CS_PIN);

AudioGeneratorWAV *wav = nullptr;
AudioFileSourcePROGMEM *file = nullptr;
AudioOutputI2S *out = nullptr;

// -------------------------------------------------------------
// Helper function dừng âm thanh đang phát
// -------------------------------------------------------------
void stopAudio() {
    if (wav) {
        if (wav->isRunning()) {
            wav->stop();
        }
        delete wav;
        wav = nullptr;
    }
    if (file) {
        delete file;
        file = nullptr;
    }
}

// -------------------------------------------------------------
// Helper function phát âm thanh từ PROGMEM
// -------------------------------------------------------------
void playAudio(const uint8_t *data, uint32_t len) {
    stopAudio();
    file = new AudioFileSourcePROGMEM(data, len);
    wav = new AudioGeneratorWAV();
    if (!wav->begin(file, out)) {
        Serial.println("Lỗi: Không thể khởi chạy WAV generator!");
        stopAudio();
    }
}

// -------------------------------------------------------------
// Helper điều khiển đèn LED RGB (Active LOW trên Nano ESP32)
// -------------------------------------------------------------
void setRgbColor(bool red, bool green, bool blue) {
    digitalWrite(LED_RED, red ? LOW : HIGH);
    digitalWrite(LED_GREEN, green ? LOW : HIGH);
    digitalWrite(LED_BLUE, blue ? LOW : HIGH);
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println("\n=== HỆ THỐNG ARDUINO NANO ESP32 BAO GỒM MCP2515 & MAX98357A ===");

    // Khởi tạo các chân LED RGB và tắt hết khi khởi động
    pinMode(LED_RED, OUTPUT);
    pinMode(LED_GREEN, OUTPUT);
    pinMode(LED_BLUE, OUTPUT);
    setRgbColor(false, false, false);

    // Config INT pin cho MCP2515
    pinMode(CAN_INT_PIN, INPUT);

    // Initializing MCP2515 (Thử 8MHz clock trước, nếu không thành công thử 16MHz)
    Serial.print("Đang khởi tạo MCP2515 (500 kbps)... ");
    if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_8MHZ) == CAN_OK) {
        CAN.setMode(MCP_NORMAL);
        Serial.println("Thành công (Clock 8MHz)!");
    } else if (CAN.begin(MCP_ANY, CAN_500KBPS, MCP_16MHZ) == CAN_OK) {
        CAN.setMode(MCP_NORMAL);
        Serial.println("Thành công (Clock 16MHz)!");
    } else {
        Serial.println("Thất bại! Vui lòng kiểm tra kết nối phần cứng MCP2515.");
    }

    // Initializing MAX98357A (ESP8266Audio I2S)
    Serial.println("Đang khởi tạo MAX98357A (I2S)...");
    out = new AudioOutputI2S();
    
    // Ánh xạ chân logic Arduino (D6, D7, D8) sang chân thực tế GPIO của ESP32-S3
    int bclk = digitalPinToGPIONumber(I2S_BCLK_PIN);
    int lrc  = digitalPinToGPIONumber(I2S_LRC_PIN);
    int din  = digitalPinToGPIONumber(I2S_DIN_PIN);
    Serial.printf("I2S Pin Remap: BCLK=GPIO%d, LRC=GPIO%d, DIN=GPIO%d\n", bclk, lrc, din);
    
    out->SetPinout(bclk, lrc, din);
    out->SetGain(0.8); // Âm lượng 80%
    Serial.println("MAX98357A Khởi tạo thành công!");

    Serial.println("\n--- CHẾ ĐỘ TỰ ĐỘNG PHÁT ÂM THANH TUẦN TỰ ---");
    Serial.println("1. MANUAL (LED Xanh dương) -> 2. AUTO (LED Xanh lá) -> 3. CANCEL (LED Đỏ)");
    Serial.println("-----------------------------------------------\n");
}

enum PlayState {
    STATE_PLAY_MANUAL,
    STATE_PLAYING_MANUAL,
    STATE_WAIT_MANUAL,
    STATE_PLAY_AUTO,
    STATE_PLAYING_AUTO,
    STATE_WAIT_AUTO,
    STATE_PLAY_CANCEL,
    STATE_PLAYING_CANCEL,
    STATE_WAIT_CANCEL
};

PlayState currentState = STATE_PLAY_MANUAL;
unsigned long stateTimer = 0;
const unsigned long DELAY_BETWEEN_SOUNDS = 1500; // Nghỉ 1.5 giây giữa các âm thanh

void loop() {
    // 1. Duy trì luồng phát âm thanh nếu đang chạy
    if (wav && wav->isRunning()) {
        if (!wav->loop()) {
            stopAudio();
            setRgbColor(false, false, false); // Tắt đèn khi phát xong
            Serial.println("Đã phát xong âm thanh.");
        }
    }

    // 2. Tự động chuyển đổi và phát lần lượt: MANUAL -> AUTO -> CANCEL
    unsigned long now = millis();

    switch (currentState) {
        case STATE_PLAY_MANUAL:
            Serial.println("\n[1/3] -> Phát âm thanh: MANUAL");
            setRgbColor(false, false, true); // Sáng màu Xanh Dương
            playAudio(sound_manual, sound_manual_len);
            currentState = STATE_PLAYING_MANUAL;
            break;

        case STATE_PLAYING_MANUAL:
            if (!wav || !wav->isRunning()) {
                stateTimer = now;
                setRgbColor(false, false, false);
                currentState = STATE_WAIT_MANUAL;
            }
            break;

        case STATE_WAIT_MANUAL:
            if (now - stateTimer >= DELAY_BETWEEN_SOUNDS) {
                currentState = STATE_PLAY_AUTO;
            }
            break;

        case STATE_PLAY_AUTO:
            Serial.println("\n[2/3] -> Phát âm thanh: AUTO");
            setRgbColor(false, true, false); // Sáng màu Xanh Lá
            playAudio(sound_auto, sound_auto_len);
            currentState = STATE_PLAYING_AUTO;
            break;

        case STATE_PLAYING_AUTO:
            if (!wav || !wav->isRunning()) {
                stateTimer = now;
                setRgbColor(false, false, false);
                currentState = STATE_WAIT_AUTO;
            }
            break;

        case STATE_WAIT_AUTO:
            if (now - stateTimer >= DELAY_BETWEEN_SOUNDS) {
                currentState = STATE_PLAY_CANCEL;
            }
            break;

        case STATE_PLAY_CANCEL:
            Serial.println("\n[3/3] -> Phát âm thanh: CANCEL");
            setRgbColor(true, false, false); // Sáng màu Đỏ
            playAudio(sound_cancel, sound_cancel_len);
            currentState = STATE_PLAYING_CANCEL;
            break;

        case STATE_PLAYING_CANCEL:
            if (!wav || !wav->isRunning()) {
                stateTimer = now;
                setRgbColor(false, false, false);
                currentState = STATE_WAIT_CANCEL;
            }
            break;

        case STATE_WAIT_CANCEL:
            if (now - stateTimer >= 2000) { // Chờ 2 giây trước khi lặp lại chu kỳ mới
                Serial.println("\n=== Hết chu kỳ, lặp lại từ đầu ===");
                currentState = STATE_PLAY_MANUAL;
            }
            break;

        default:
            currentState = STATE_PLAY_MANUAL;
            break;
    }
}
