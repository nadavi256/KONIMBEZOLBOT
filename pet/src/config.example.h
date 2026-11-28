// Copy this file to config.h and fill in your details.
#pragma once

// WiFi — home network and/or your phone's hotspot (2.4GHz). Tried in order.
static const char *WIFI_LIST[][2] = {
    {"HomeWiFi", "password"},
    {"MyPhoneHotspot", "password"},
};

// Address of the coach server (coach/server.py), e.g. "https://my-coach.up.railway.app"
#define SERVER_URL  "http://192.168.1.10:8080"
// Must equal DEVICE_KEY on the server
#define DEVICE_KEY  "change-me-long-random-string"

#define SCREEN_TIMEOUT_MS   30000   // backlight off after this much idle time
#define POLL_INTERVAL_MS    120000  // check for messages from the pet's brain
#define MAX_RECORD_SECONDS  12
#define SPEAKER_VOLUME      170     // 0-255; M5Stack advises < ~75% on battery
