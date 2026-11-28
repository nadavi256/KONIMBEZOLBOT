// Personal coach watch — LILYGO T-Watch S3 / S3 Plus.
//
// The watch is a thin client: it counts steps, records your voice, shows
// screens and plays speech. All the "brain" work (speech-to-text, Claude,
// text-to-speech and rendering Hebrew screens) runs on coach/server.py.
//
// Controls:
//   * Touch and HOLD the screen  -> talk to the coach (release to send)
//   * Tap                        -> next page of the answer / back to home
//   * Side button                -> wake the screen / back to home
//   * The watch vibrates when the coach has something for you
//     (reminders, morning/evening check-ins).
#include <Arduino.h>
#include <LilyGoLib.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <ArduinoJson.h>

#include "config.h"

static const int W = 240, H = 240;
static const uint32_t SAMPLE_RATE = 16000;
static const size_t FRAME_BYTES = W * H * 2;
static const size_t REC_MAX_BYTES = MAX_RECORD_SECONDS * SAMPLE_RATE * 2;

static uint16_t *frame = nullptr;     // 240x240 RGB565 frame buffer (PSRAM)
static uint8_t *recBuf = nullptr;     // voice recording buffer (PSRAM)
static AudioInputIf *mic = nullptr;
static AudioOutputIf *spk = nullptr;
static WiFiMulti wifiMulti;

static volatile uint32_t steps = 0;
static uint32_t lastActivity = 0, lastPoll = 0, lastHomeDraw = 0;
static bool screenOn = true;
static volatile bool buttonClicked = false;

enum Mode { HOME, REPLY };
static Mode mode = HOME;
static String replyId;
static int replyPage = 0, replyPages = 0;

// ---------------------------------------------------------------- helpers
static void buzz(uint8_t effect = 47) {
    instance.setHapticEffects(effect);
    instance.vibrator();
}

static void screenWake() {
    lastActivity = millis();
    if (!screenOn) {
        instance.wakeupDisplay();
        instance.setBrightness(200);
        screenOn = true;
    }
}

static void screenSleep() {
    if (screenOn) {
        instance.setBrightness(0);
        instance.sleepDisplay();
        screenOn = false;
    }
}

static void pushFrame() { instance.pushColors(0, 0, W, H, frame); }

static void fillRect(int x, int y, int w, int h, uint16_t c) {
    for (int j = y; j < y + h && j < H; j++)
        for (int i = x; i < x + w && i < W; i++) frame[j * W + i] = c;
}

// Minimal screen drawn locally when there is no server connection:
// a step progress bar, with a red dot meaning "offline".
static void drawOfflineHome() {
    fillRect(0, 0, W, H, 0x0000);
    float p = min(1.0f, steps / (float)DAILY_STEP_GOAL);
    fillRect(20, 110, 200, 20, 0x2104);
    fillRect(20, 110, (int)(200 * p), 20, 0x07E0);
    fillRect(112, 160, 16, 16, 0xF800);
    pushFrame();
}

// Status/feedback colours while talking (red = recording, blue = thinking).
static void drawStatus(uint16_t color) {
    fillRect(0, 0, W, H, 0x0000);
    for (int y = 0; y < H; y++)
        for (int x = 0; x < W; x++) {
            int dx = x - 120, dy = y - 120;
            if (dx * dx + dy * dy < 60 * 60) frame[y * W + x] = color;
        }
    pushFrame();
}

static int battPercent() { return (int)instance.getBatteryPercent(); }

static String url(const String &path) {
    String sep = path.indexOf('?') >= 0 ? "&" : "?";
    return String(SERVER_URL) + path + sep + "steps=" + steps + "&batt=" + battPercent();
}

static bool httpBegin(HTTPClient &http, NetworkClientSecure &tls, const String &u) {
    bool ok = u.startsWith("https") ? (tls.setInsecure(), http.begin(tls, u)) : http.begin(u);
    if (!ok) return false;
    http.addHeader("X-Device-Key", DEVICE_KEY);
    http.setTimeout(60000);
    return true;
}

static bool online() { return wifiMulti.run(5000) == WL_CONNECTED; }

// GET a full-screen RGB565 image into the frame buffer and show it.
static bool fetchScreen(const String &path) {
    if (!online()) return false;
    HTTPClient http;
    NetworkClientSecure tls;
    if (!httpBegin(http, tls, url(path))) return false;
    bool ok = false;
    if (http.GET() == 200) {
        WiFiClient *s = http.getStreamPtr();
        size_t got = 0;
        uint32_t t0 = millis();
        while (got < FRAME_BYTES && millis() - t0 < 15000) {
            int n = s->read(((uint8_t *)frame) + got, FRAME_BYTES - got);
            if (n > 0) got += n; else delay(2);
        }
        ok = got == FRAME_BYTES;
        if (ok) pushFrame();
    }
    http.end();
    return ok;
}

// GET raw PCM (s16le, 16kHz, mono) and stream it to the speaker.
static void playAudio(const String &id) {
    if (!online()) return;
    HTTPClient http;
    NetworkClientSecure tls;
    if (!httpBegin(http, tls, url("/device/audio/" + id))) return;
    if (http.GET() == 200) {
        spk->open(16, 1, SAMPLE_RATE);
        spk->setVolume(SPEAKER_VOLUME);
        WiFiClient *s = http.getStreamPtr();
        static uint8_t buf[2048];
        uint32_t last = millis();
        while (http.connected() || s->available()) {
            int n = s->read(buf, sizeof(buf) & ~1);
            if (n > 0) { spk->write(buf, n); last = millis(); }
            else if (millis() - last > 5000) break;
            else delay(2);
            instance.loop();
            if (buttonClicked) { buttonClicked = false; break; }  // button = stop talking
        }
        spk->close();
    }
    http.end();
}

static void drawHome() {
    mode = HOME;
    lastHomeDraw = millis();
    if (!fetchScreen("/device/home")) drawOfflineHome();
}

static void showReply(const String &id, int pages) {
    mode = REPLY;
    replyId = id;
    replyPage = 0;
    replyPages = max(1, pages);
    screenWake();
    fetchScreen("/device/screen/" + id + "/0");
    playAudio(id);
    lastActivity = millis();
}

static bool parseReply(const String &body) {
    JsonDocument doc;
    if (deserializeJson(doc, body)) return false;
    if (!doc["id"].is<const char *>()) return false;
    showReply(doc["id"].as<String>(), doc["pages"] | 1);
    return true;
}

// ---------------------------------------------------------------- talk
static void talk() {
    screenWake();
    buzz(1);
    drawStatus(0xF800);  // red = listening

    mic->open(16, 1, SAMPLE_RATE);
    size_t len = 0;
    int16_t x, y;
    // Drop the first ~100ms (PDM mic settling).
    static uint8_t junk[3200];
    mic->read(junk, sizeof(junk));
    while (len < REC_MAX_BYTES) {
        size_t chunk = min((size_t)1024, REC_MAX_BYTES - len);
        int n = mic->read(recBuf + len, chunk);
        if (n > 0) len += n;
        if (instance.getPoint(&x, &y, 1) == 0) break;  // finger lifted
    }
    mic->close();
    buzz(1);

    if (len < SAMPLE_RATE * 2 / 2) {  // shorter than 0.5s: treat as a tap
        drawHome();
        return;
    }
    drawStatus(0x001F);  // blue = thinking

    if (!online()) { drawOfflineHome(); return; }
    HTTPClient http;
    NetworkClientSecure tls;
    if (!httpBegin(http, tls, url("/device/talk"))) { drawHome(); return; }
    http.addHeader("Content-Type", "application/octet-stream");
    int code = http.POST(recBuf, len);
    String body = code == 200 ? http.getString() : "";
    http.end();
    if (!parseReply(body)) drawHome();
}

// ---------------------------------------------------------------- poll
static void poll() {
    lastPoll = millis();
    if (!online()) return;
    HTTPClient http;
    NetworkClientSecure tls;
    if (!httpBegin(http, tls, url("/device/inbox"))) return;
    String body = http.GET() == 200 ? http.getString() : "";
    http.end();
    if (body.length() > 2) {
        buzz(52);
        delay(400);
        buzz(52);
        parseReply(body);
    } else if (screenOn && mode == HOME && millis() - lastHomeDraw > 30000) {
        drawHome();  // refresh clock / steps
    }
}

// ---------------------------------------------------------------- events
static void onDeviceEvent(const DeviceEvent &event, void *) {
    if (event.type == POWER_EVENT && instance.getPMUEventType(event) == PMU_EVENT_KEY_CLICKED) {
        buttonClicked = true;
    }
    if (event.type == SENSOR_EVENT && instance.getSensorEventType(event) == SENSOR_STEPS_UPDATED) {
        steps = instance.getStepCounter();
    }
}

void setup() {
    Serial.begin(115200);
    instance.begin();
    instance.setBrightness(200);
    instance.onEvent(onDeviceEvent);
    mic = instance.getAudioInput();
    spk = instance.getAudioOutput();

    frame = (uint16_t *)ps_malloc(FRAME_BYTES);
    recBuf = (uint8_t *)ps_malloc(REC_MAX_BYTES);

    WiFi.mode(WIFI_STA);
    for (auto &w : WIFI_LIST) wifiMulti.addAP(w[0], w[1]);

    steps = instance.getStepCounter();
    drawHome();
    lastActivity = millis();
}

void loop() {
    instance.loop();

    if (buttonClicked) {
        buttonClicked = false;
        if (!screenOn) { screenWake(); drawHome(); }
        else if (mode == REPLY) drawHome();
        else screenSleep();
    }

    int16_t x, y;
    if (instance.getPoint(&x, &y, 1) > 0) {
        bool wasOff = !screenOn;
        screenWake();
        uint32_t t0 = millis();
        while (instance.getPoint(&x, &y, 1) > 0 && millis() - t0 < 450) delay(10);
        if (instance.getPoint(&x, &y, 1) > 0) {
            talk();                      // held -> talk
        } else if (wasOff) {
            drawHome();                  // tap on a dark screen just wakes it
        } else if (mode == REPLY && replyPage + 1 < replyPages) {
            fetchScreen("/device/screen/" + replyId + "/" + String(++replyPage));
        } else {
            drawHome();
        }
        while (instance.getPoint(&x, &y, 1) > 0) delay(10);
        instance.getPoint(nullptr, nullptr, 0);  // clear touch IRQ
    }

    if (millis() - lastPoll > POLL_INTERVAL_MS) poll();
    if (screenOn && millis() - lastActivity > SCREEN_TIMEOUT_MS) screenSleep();
    delay(20);
}
