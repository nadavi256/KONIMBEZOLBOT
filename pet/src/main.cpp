// Pocket pet + personal coach — M5Stack StickS3.
//
// A little creature ("Pipo") lives on the screen. It grows from your steps
// (egg -> baby -> kid -> teen -> adult), gets sad when you sit too long,
// sleeps at night, and is your personal coach: hold the big button, talk,
// and it answers out loud in Hebrew with a speech bubble.
//
// Buttons:
//   A (front) hold   -> talk to the pet (release to send)
//   A (front) click  -> pet it (hearts!) / next page of a bubble / close it
//   B (side)  click  -> status card (steps, level, XP)
//   Shake it         -> it gets dizzy :)
//   Pick it up       -> screen wakes
//
// The "brain" (speech recognition, Claude, voice, Hebrew text) runs on
// coach/server.py; this firmware draws, counts steps and moves audio.
#include <M5Unified.h>
#include <WiFi.h>
#include <WiFiMulti.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <ArduinoJson.h>
#include <Preferences.h>

#include "config.h"
#include "pet_draw.h"

static const int W = 240, H = 135, GROUND = 116;
static const uint32_t RATE = 16000;
static const size_t SCREEN_BYTES = W * H * 2;
static const size_t REC_SAMPLES = MAX_RECORD_SECONDS * RATE;
static const size_t AUDIO_MAX = 60 * RATE * 2;  // up to 60s of speech
static const size_t REC_CHUNK = 1600;           // 100ms
static const int BRIGHT = 110;

static M5Canvas canvas(&M5.Display);
static uint8_t *bubbleBuf, *statsBuf, *audioBuf;
static int16_t *recBuf;
static WiFiMulti wifiMulti;
static Preferences prefs;

// ------------------------------------------------------------ shared state
enum Mode { M_PET, M_LISTEN, M_THINK, M_SPEAK, M_STATS, M_PARTY };
static Mode mode = M_PET;

struct PetState {
    int stage = 0, xp = 0, nextXp = 30, steps = 0, goal = 8000;
    String mood = "ok";
} pet;

static volatile uint32_t rawSteps = 0;      // local pedometer since boot
static uint32_t rawAtSync = 0;              // rawSteps when server last answered
static bool online = false;

// network job hand-off (main loop <-> net task)
enum Job { J_NONE, J_STATE, J_TALK, J_STATS, J_PAGE };
static volatile Job job = J_NONE;
static volatile bool jobOk = false, jobDone = false;
static size_t recBytes = 0;
static String replyId;
static int replyPages = 1, replyPage = 0, wantPage = 0;
static size_t audioLen = 0;
static volatile bool speakReady = false, incomingMsg = false;
static bool wantStats = false;

// ------------------------------------------------------------ UI state
static uint32_t lastInput = 0, modeSince = 0, lastPoll = 0, speakStart = 0;
static bool screenOn = true;
static Expr flash = EX_NORMAL;         // short-lived expression (love / dizzy)
static uint32_t flashUntil = 0;
static float posX = 120, targetX = 120;
static uint32_t nextWander = 0;

static void setMode(Mode m) { mode = m; modeSince = millis(); }

static void wake() {
    lastInput = millis();
    if (!screenOn) { M5.Display.setBrightness(BRIGHT); screenOn = true; }
}

static void chirp(int n = 1) {
    if (mode == M_LISTEN) return;
    for (int i = 0; i < n; i++) { M5.Speaker.tone(1800 + i * 500, 60); delay(80); }
}

static void melody() {
    const int notes[] = {1046, 1318, 1568, 2093};
    for (int f : notes) { M5.Speaker.tone(f, 110); delay(130); }
}

// ------------------------------------------------------------ pedometer
// Simple peak detector on acceleration magnitude, with a "need a few steps in
// a row" rule so that random hand movements don't count.
static void stepDetector(float ax, float ay, float az) {
    static float lp = 1, base = 1;
    static bool above = false;
    static uint32_t lastPeak = 0;
    static int streak = 0;
    float mag = sqrtf(ax * ax + ay * ay + az * az);
    lp = lp * 0.7f + mag * 0.3f;
    base = base * 0.97f + lp * 0.03f;
    float d = lp - base;
    uint32_t now = millis();
    if (!above && d > 0.11f) {
        above = true;
        uint32_t gap = now - lastPeak;
        if (gap > 260 && gap < 2000) {
            streak++;
            if (streak == 4) rawSteps += 4;     // credit the warm-up steps
            else if (streak > 4) rawSteps++;
        } else if (gap >= 2000) {
            streak = 1;
        }
        if (gap > 260) lastPeak = now;
    } else if (above && d < 0.02f) {
        above = false;
    }
}

static void readMotion() {
    static uint32_t last = 0;
    if (millis() - last < 20) return;   // ~50Hz
    last = millis();
    float ax, ay, az;
    if (!M5.Imu.update()) return;
    M5.Imu.getAccel(&ax, &ay, &az);
    stepDetector(ax, ay, az);
    float mag = sqrtf(ax * ax + ay * ay + az * az);
    if (mag > 2.6f && mode == M_PET) {           // shake!
        flash = EX_DIZZY; flashUntil = millis() + 2500;
        wake();
    } else if (!screenOn && fabsf(mag - 1.0f) > 0.35f) {  // picked up
        wake();
    }
}

// ------------------------------------------------------------ networking (task)
static String url(const String &path) {
    String sep = path.indexOf('?') >= 0 ? "&" : "?";
    return String(SERVER_URL) + path + sep + "steps=" + (uint32_t)rawSteps +
           "&batt=" + M5.Power.getBatteryLevel() + "&w=" + W + "&h=" + H;
}

static bool begin(HTTPClient &http, NetworkClientSecure &tls, const String &path) {
    String u = url(path);
    bool ok = u.startsWith("https") ? (tls.setInsecure(), http.begin(tls, u)) : http.begin(u);
    if (!ok) return false;
    http.addHeader("X-Device-Key", DEVICE_KEY);
    http.setTimeout(60000);
    return true;
}

static size_t readBody(HTTPClient &http, uint8_t *dst, size_t max) {
    WiFiClient *s = http.getStreamPtr();
    int len = http.getSize();  // -1 if unknown
    size_t got = 0;
    uint32_t last = millis();
    while (got < max && (len < 0 || got < (size_t)len)) {
        int n = s->read(dst + got, min((size_t)4096, max - got));
        if (n > 0) { got += n; last = millis(); }
        else if (!http.connected() || millis() - last > 8000) break;
        else delay(2);
    }
    return got;
}

static bool getInto(const String &path, uint8_t *dst, size_t max, size_t *outLen = nullptr) {
    HTTPClient http; NetworkClientSecure tls;
    if (!begin(http, tls, path)) return false;
    bool ok = false;
    if (http.GET() == 200) {
        size_t n = readBody(http, dst, max);
        if (outLen) *outLen = n;
        ok = outLen ? true : n == max;
    }
    http.end();
    return ok;
}

static void applyPet(JsonObjectConst p) {
    if (p.isNull()) return;
    pet.stage = p["stage"] == "egg" ? 0 : p["stage"] == "baby" ? 1 : p["stage"] == "kid" ? 2
              : p["stage"] == "teen" ? 3 : 4;
    pet.xp = p["xp"] | 0;
    pet.nextXp = p["next_xp"] | 0;
    pet.steps = p["steps"] | 0;
    pet.goal = p["goal"] | 8000;
    pet.mood = (const char *)(p["mood"] | "ok");
    rawAtSync = rawSteps;
}

// Fetch first bubble page + the spoken audio of a reply.
static bool loadReply(const String &id, int pages) {
    replyId = id; replyPages = max(1, pages); replyPage = 0;
    if (!getInto("/device/screen/" + id + "/0", bubbleBuf, SCREEN_BYTES)) return false;
    audioLen = 0;
    getInto("/device/audio/" + id, audioBuf, AUDIO_MAX, &audioLen);
    audioLen &= ~1u;
    return true;
}

static bool doState() {
    HTTPClient http; NetworkClientSecure tls;
    if (!begin(http, tls, "/device/state")) return false;
    String body = http.GET() == 200 ? http.getString() : "";
    http.end();
    JsonDocument doc;
    if (body.isEmpty() || deserializeJson(doc, body)) return false;
    applyPet(doc["pet"]);
    if (!doc["msg"].isNull() && loadReply(doc["msg"]["id"].as<String>(), doc["msg"]["pages"] | 1)) {
        incomingMsg = true;
        speakReady = true;
    }
    return true;
}

static bool doTalk() {
    HTTPClient http; NetworkClientSecure tls;
    if (!begin(http, tls, "/device/talk")) return false;
    http.addHeader("Content-Type", "application/octet-stream");
    int code = http.POST((uint8_t *)recBuf, recBytes);
    String body = code == 200 ? http.getString() : "";
    http.end();
    JsonDocument doc;
    if (body.isEmpty() || deserializeJson(doc, body)) return false;
    applyPet(doc["pet"]);
    if (!loadReply(doc["id"].as<String>(), doc["pages"] | 1)) return false;
    speakReady = true;
    return true;
}

static void netTask(void *) {
    for (;;) {
        Job j = job;
        if (j == J_NONE) { vTaskDelay(pdMS_TO_TICKS(20)); continue; }
        online = wifiMulti.run(8000) == WL_CONNECTED;
        bool ok = false;
        if (online) {
            switch (j) {
                case J_STATE: ok = doState(); break;
                case J_TALK:  ok = doTalk(); break;
                case J_STATS: ok = getInto("/device/stats", statsBuf, SCREEN_BYTES); break;
                case J_PAGE:  ok = getInto("/device/screen/" + replyId + "/" + wantPage, bubbleBuf, SCREEN_BYTES); break;
                default: break;
            }
        }
        jobOk = ok;
        jobDone = true;
        job = J_NONE;
    }
}

static bool startJob(Job j) {
    if (job != J_NONE) return false;
    jobDone = false;
    job = j;
    return true;
}

// ------------------------------------------------------------ talking
static size_t recPos = 0;

static void startListening() {
    wake();
    M5.Speaker.end();
    M5.Mic.begin();
    recPos = 0;
    setMode(M_LISTEN);
}

static void keepListening() {
    if (recPos + REC_CHUNK <= REC_SAMPLES && M5.Mic.isRecording() < 2) {
        if (M5.Mic.record(recBuf + recPos, REC_CHUNK, RATE)) recPos += REC_CHUNK;
    }
}

static void stopListening() {
    while (M5.Mic.isRecording()) delay(1);
    M5.Mic.end();
    M5.Speaker.begin();
    M5.Speaker.setVolume(SPEAKER_VOLUME);
    recBytes = recPos * 2;
    if (recPos < RATE / 2 || !startJob(J_TALK)) { setMode(M_PET); return; }  // < 0.5s
    setMode(M_THINK);
}

// Mouth opening from the audio loudness at the current playback position.
static float mouthLevel() {
    if (!M5.Speaker.isPlaying()) return 0;
    size_t pos = (size_t)((millis() - speakStart) * (RATE / 1000)) * 2;
    if (pos + 640 >= audioLen) return 0;
    const int16_t *s = (const int16_t *)(audioBuf + pos);
    long sum = 0;
    for (int i = 0; i < 320; i++) sum += abs(s[i]);
    return min(1.0f, (sum / 320.0f) / 5000.0f);
}

static void startSpeaking() {
    speakReady = false;
    wake();
    if (incomingMsg) { incomingMsg = false; chirp(3); }
    setMode(M_SPEAK);
    if (audioLen > 0) {
        M5.Speaker.playRaw((const int16_t *)audioBuf, audioLen / 2, RATE, false, 1, 0, true);
        speakStart = millis();
    }
}

// ------------------------------------------------------------ rendering
static Expr moodExpr() {
    if (millis() < flashUntil) return flash;
    if (pet.mood == "sleep") return EX_SLEEP;
    if (pet.mood == "happy") return EX_HAPPY;
    if (pet.mood == "sad") return EX_SAD;
    return EX_NORMAL;
}

static void drawHud() {
    canvas.setFont(&fonts::Font0);
    canvas.setTextColor(pal::DIM);
    canvas.setTextDatum(top_left);
    canvas.drawString(String(M5.Power.getBatteryLevel()) + "%", 4, 3);
    canvas.fillCircle(W - 6, 6, 2, online ? pal::BODY : lgfx::color565(220, 60, 60));
    // today's steps
    uint32_t today = pet.steps + (rawSteps - rawAtSync);
    float p = pet.goal ? min(1.0f, today / (float)pet.goal) : 0;
    canvas.fillRoundRect(40, H - 9, W - 80, 5, 2, pal::GROUND);
    if (p > 0) canvas.fillRoundRect(40, H - 9, (int)((W - 80) * p), 5, 2, pal::BODY);
    canvas.setTextDatum(top_right);
    canvas.drawString(String(today), 36, H - 11);
}

static void drawScene(float t) {
    bool night = pet.mood == "sleep";
    canvas.fillScreen(night ? pal::NIGHT : pal::BG);
    if (night) {
        for (int i = 0; i < 14; i++) {
            int x = (i * 73) % W, y = 8 + (i * 37) % 60;
            if (fmodf(t + i * 0.7f, 3.0f) > 0.4f) canvas.drawPixel(x, y, pal::STAR);
        }
    }
    canvas.drawFastHLine(0, GROUND + 2, W, pal::GROUND);

    // wander around when idle and awake
    Expr ex = moodExpr();
    if (mode == M_PET && ex != EX_SLEEP && pet.stage > 0 && millis() > nextWander) {
        targetX = random(70, 171);
        nextWander = millis() + random(3000, 8000);
    }
    if (mode != M_PET || ex == EX_SLEEP) targetX = 120;
    float dx = targetX - posX;
    posX += constrain(dx, -0.8f, 0.8f);
    float look = fabsf(dx) > 1 ? (dx > 0 ? 1 : -1) : 0;

    switch (mode) {
        case M_LISTEN: ex = EX_LISTEN; break;
        case M_THINK:  ex = EX_THINK; break;
        case M_PARTY:  ex = EX_LOVE; break;
        default: break;
    }
    float hatch = pet.stage == 0 && pet.nextXp ? pet.xp / (float)pet.nextXp : 0;
    drawPet(canvas, (int)posX, GROUND, t, pet.stage, ex, look, 0, 0, hatch);

    if (mode == M_LISTEN) {
        canvas.fillCircle(12, 20, 4, (millis() / 400) % 2 ? TFT_RED : pal::BG);
        canvas.setTextColor(pal::TEXT);
        canvas.setFont(&fonts::Font0);
        canvas.setTextDatum(top_left);
        canvas.drawString(String(recPos / RATE) + "s", 20, 17);
    }
    drawHud();
}

static void drawSpeak(float t) {
    canvas.pushImage(0, 0, W, H, (const lgfx::rgb565_t *)bubbleBuf);
    // mini pet in the corner, mouth moving with the voice
    float m = mouthLevel();
    drawPet(canvas, 25, H - 8, t, max(1, pet.stage), m > 0.02f ? EX_TALK : EX_HAPPY, 1, m, 14);
}

static void render() {
    float t = millis() / 1000.0f;
    if (mode == M_SPEAK) drawSpeak(t);
    else if (mode == M_STATS) canvas.pushImage(0, 0, W, H, (const lgfx::rgb565_t *)statsBuf);
    else drawScene(t);
    canvas.pushSprite(0, 0);
}

// ------------------------------------------------------------ setup / loop
void setup() {
    auto cfg = M5.config();
    M5.begin(cfg);
    M5.Display.setRotation(1);
    M5.Display.setBrightness(BRIGHT);
    M5.Speaker.setVolume(SPEAKER_VOLUME);

    canvas.setPsram(true);
    canvas.setColorDepth(16);
    canvas.createSprite(W, H);
    bubbleBuf = (uint8_t *)ps_malloc(SCREEN_BYTES);
    statsBuf = (uint8_t *)ps_malloc(SCREEN_BYTES);
    audioBuf = (uint8_t *)ps_malloc(AUDIO_MAX);
    recBuf = (int16_t *)ps_malloc(REC_SAMPLES * 2);

    prefs.begin("pet", false);
    pet.stage = prefs.getInt("stage", 0);

    WiFi.mode(WIFI_STA);
    for (auto &w : WIFI_LIST) wifiMulti.addAP(w[0], w[1]);
    xTaskCreatePinnedToCore(netTask, "net", 12288, nullptr, 1, nullptr, 0);

    startJob(J_STATE);
    lastPoll = lastInput = millis();
    randomSeed(esp_random());
}

void loop() {
    M5.update();
    readMotion();

    bool anyBtn = M5.BtnA.wasPressed() || M5.BtnB.wasPressed();
    if (anyBtn && !screenOn) { wake(); return; }   // first press only wakes
    if (anyBtn) lastInput = millis();

    // ---- buttons
    if (mode == M_LISTEN) {
        keepListening();
        if (!M5.BtnA.isPressed() || recPos + REC_CHUNK > REC_SAMPLES) stopListening();
    } else if (M5.BtnA.wasHold() && mode != M_THINK) {
        M5.Speaker.stop();
        startListening();
    } else if (M5.BtnA.wasClicked()) {
        if (mode == M_SPEAK) {
            if (replyPage + 1 < replyPages && job == J_NONE) {
                wantPage = replyPage + 1;
                startJob(J_PAGE);
            } else {
                M5.Speaker.stop();
                setMode(M_PET);
            }
        } else if (mode == M_STATS) {
            setMode(M_PET);
        } else if (mode == M_PET) {
            flash = EX_LOVE; flashUntil = millis() + 2500;
            chirp(2);
        }
    }
    if (M5.BtnB.wasClicked() && (mode == M_PET || mode == M_STATS)) {
        if (mode == M_STATS) setMode(M_PET);
        else if (startJob(J_STATS)) wantStats = true;
    }

    // ---- network results
    if (jobDone) {
        jobDone = false;
        if (mode == M_THINK && !speakReady) setMode(M_PET);       // talk failed
        if (wantPage && jobOk) { replyPage = wantPage; wantPage = 0; modeSince = millis(); }
        if (wantStats) { wantStats = false; if (jobOk && mode == M_PET) setMode(M_STATS); }
        int saved = prefs.getInt("stage", 0);
        if (pet.stage > saved) {          // it grew!
            prefs.putInt("stage", pet.stage);
            wake(); setMode(M_PARTY); melody();
        } else if (pet.stage < saved) {
            prefs.putInt("stage", pet.stage);
        }
    }
    if (speakReady && (mode == M_PET || mode == M_THINK || mode == M_STATS)) startSpeaking();

    // ---- timeouts
    uint32_t inMode = millis() - modeSince;
    if (mode == M_PARTY && inMode > 4500) setMode(M_PET);
    if (mode == M_STATS && inMode > 10000) setMode(M_PET);
    if (mode == M_SPEAK && !M5.Speaker.isPlaying() && inMode > 4000 &&
        millis() - lastInput > 15000 && millis() - speakStart > 15000) setMode(M_PET);
    if (mode == M_THINK && inMode > 90000) setMode(M_PET);

    if (millis() - lastPoll > POLL_INTERVAL_MS && mode == M_PET) {
        if (startJob(J_STATE)) lastPoll = millis();
    }

    bool busy = mode != M_PET || M5.Speaker.isPlaying();
    if (screenOn && !busy && millis() - lastInput > SCREEN_TIMEOUT_MS) {
        M5.Display.setBrightness(0);
        screenOn = false;
    }
    if (screenOn) render();
    delay(screenOn ? 15 : 40);
}
