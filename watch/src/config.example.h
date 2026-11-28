// Copy this file to config.h and fill in your details.
#pragma once

// WiFi — your home network or your phone's hotspot (2.4GHz only).
// You can list several; the watch tries them in order.
static const char *WIFI_LIST[][2] = {
    {"HomeWiFi", "password"},
    {"MyPhoneHotspot", "password"},
};

// Address of the coach server (coach/server.py), e.g. "https://my-coach.up.railway.app"
#define SERVER_URL  "http://192.168.1.10:8080"
// Must equal DEVICE_KEY on the server
#define DEVICE_KEY  "change-me-long-random-string"

#define DAILY_STEP_GOAL     8000
#define SCREEN_TIMEOUT_MS   20000   // turn the screen off after this much idle time
#define POLL_INTERVAL_MS    60000   // check for coach messages / sync steps
#define MAX_RECORD_SECONDS  12
#define SPEAKER_VOLUME      90      // 0-100
