// Procedural drawing of "Pipo" — an original little mint blob creature.
// Everything is drawn with shapes, so there are no image files to manage.
//
// Stages:  0 egg  ->  1 baby  ->  2 kid (feet + one sprout)
//          ->  3 teen (arms + two sprouts)  ->  4 adult (bigger + flower)
#pragma once
#include <M5Unified.h>

enum Expr { EX_NORMAL, EX_HAPPY, EX_SAD, EX_SLEEP, EX_LISTEN, EX_THINK, EX_TALK, EX_LOVE, EX_DIZZY, EX_ALERT };

namespace pal {
static const uint16_t BG      = lgfx::color565(14, 16, 28);
static const uint16_t NIGHT   = lgfx::color565(8, 10, 22);
static const uint16_t GROUND  = lgfx::color565(40, 46, 70);
static const uint16_t BODY    = lgfx::color565(94, 224, 176);
static const uint16_t BODY_DK = lgfx::color565(54, 170, 130);
static const uint16_t BELLY   = lgfx::color565(190, 246, 220);
static const uint16_t CHEEK   = lgfx::color565(255, 140, 160);
static const uint16_t EYE     = lgfx::color565(24, 26, 40);
static const uint16_t SHINE   = TFT_WHITE;
static const uint16_t LEAF    = lgfx::color565(120, 200, 80);
static const uint16_t PETAL   = lgfx::color565(255, 200, 70);
static const uint16_t EGG     = lgfx::color565(250, 240, 210);
static const uint16_t HEART   = lgfx::color565(255, 80, 110);
static const uint16_t TEXT    = lgfx::color565(200, 205, 220);
static const uint16_t DIM     = lgfx::color565(110, 116, 140);
static const uint16_t STAR    = lgfx::color565(200, 200, 150);
}

static inline void drawHeart(LGFX_Sprite &c, int x, int y, int s, uint16_t col) {
    c.fillCircle(x - s / 2, y, s / 2 + 1, col);
    c.fillCircle(x + s / 2, y, s / 2 + 1, col);
    c.fillTriangle(x - s - 1, y + 1, x + s + 1, y + 1, x, y + s + 2, col);
}

static inline void drawLeaf(LGFX_Sprite &c, int x, int y, int len, float tilt) {
    int tx = x + (int)(tilt * len), ty = y - len;
    c.drawLine(x, y, tx, ty, pal::BODY_DK);
    c.fillEllipse(tx + (tilt > 0 ? 4 : -4), ty, 6, 3, pal::LEAF);
}

// Draw the pet standing on groundY, centred at cx.
//   t      : time in seconds (drives idle animation)
//   stage  : 0..4
//   ex     : expression
//   look   : -1..1 where the eyes look (left/right)
//   mouth  : 0..1 how open the mouth is (for talking)
//   r0     : 0 = size by stage, otherwise force radius (mini pet)
//   hatch  : 0..1 how close the egg is to hatching (cracks)
static void drawPet(LGFX_Sprite &c, int cx, int groundY, float t, int stage, Expr ex,
                    float look = 0, float mouth = 0, int r0 = 0, float hatch = 0) {
    // ---------------- egg ----------------
    if (stage == 0) {
        int r = r0 ? r0 : 24;
        float wob = (ex == EX_HAPPY || hatch > 0.8f) ? sinf(t * 9) * 3 : sinf(t * 1.5f) * 1;
        int ex_ = cx + (int)wob, ey = groundY - r - 6;
        c.fillEllipse(ex_, groundY - 2, r - 4, 3, pal::GROUND);
        c.fillEllipse(ex_, ey, r - 3, r + 6, pal::EGG);
        c.fillCircle(ex_ - r / 3, ey - r / 3, r / 5, pal::BODY);
        c.fillCircle(ex_ + r / 3, ey + r / 4, r / 6, pal::BODY);
        c.fillCircle(ex_ - r / 6, ey + r / 2, r / 8, pal::BODY);
        if (hatch > 0.5f) {  // cracks appear as it gets close to hatching
            int y = ey - 2;
            c.drawLine(ex_ - r + 6, y, ex_ - r / 2, y - 5, pal::EYE);
            c.drawLine(ex_ - r / 2, y - 5, ex_ - r / 6, y + 2, pal::EYE);
            if (hatch > 0.8f) {
                c.drawLine(ex_ - r / 6, y + 2, ex_ + r / 4, y - 6, pal::EYE);
                c.drawLine(ex_ + r / 4, y - 6, ex_ + r - 6, y, pal::EYE);
            }
        }
        if (ex == EX_SLEEP) {
            c.setTextColor(pal::DIM);
            c.setFont(&fonts::Font2);
            c.drawString("z", ex_ + r, ey - r - 4 - (int)(fmodf(t, 2) * 6));
        }
        return;
    }

    // ---------------- creature ----------------
    static const int RADII[] = {0, 18, 23, 28, 33};
    int r = r0 ? r0 : RADII[stage];
    float bob, squash = 1.0f;
    switch (ex) {
        case EX_HAPPY: case EX_LOVE: case EX_ALERT: {
            float h = fabsf(sinf(t * 6));
            bob = -h * r * 0.6f;
            squash = 1.0f - (1 - h) * 0.12f;
            break;
        }
        case EX_SAD:   bob = sinf(t * 1.2f) * 1 + r * 0.08f; squash = 0.92f; break;
        case EX_SLEEP: bob = 0; squash = 0.9f + sinf(t * 1.3f) * 0.03f; break;
        case EX_DIZZY: bob = sinf(t * 3) * 2; break;
        default:       bob = sinf(t * 2.2f) * 2; break;
    }
    int bw = (int)(r * 1.12f / squash * (squash < 1 ? 1 : 1)), bh = (int)(r * squash);
    int cy = groundY - bh + (int)bob;
    if (ex == EX_SAD) cy = groundY - bh;

    // shadow
    int sh = max(4, r - (int)(-bob) / 2);
    c.fillEllipse(cx, groundY + 1, sh, 3, pal::GROUND);

    // feet
    if (stage >= 2) {
        int fy = groundY - 2;
        int step = (ex == EX_NORMAL) ? (int)(sinf(t * 4) * 1.5f) : 0;
        c.fillEllipse(cx - r / 2, fy + step, r / 4 + 1, r / 7 + 1, pal::BODY_DK);
        c.fillEllipse(cx + r / 2, fy - step, r / 4 + 1, r / 7 + 1, pal::BODY_DK);
    }
    // arms
    if (stage >= 3) {
        float wave = (ex == EX_HAPPY || ex == EX_ALERT) ? sinf(t * 10) * 0.6f : 0.15f;
        int ay = cy + r / 5;
        c.fillEllipse(cx - bw - 1, ay - (int)(wave * r * 0.4f), r / 6 + 1, r / 4, pal::BODY_DK);
        c.fillEllipse(cx + bw + 1, ay - (int)(-wave * r * 0.4f), r / 6 + 1, r / 4, pal::BODY_DK);
    }
    // sprouts / flower on top
    int top = cy - bh;
    float sway = sinf(t * 2.5f) * 0.35f;
    if (stage == 2) drawLeaf(c, cx, top + 2, r / 2 + 2, sway);
    if (stage == 3) { drawLeaf(c, cx - 4, top + 3, r / 2 + 3, -0.6f + sway); drawLeaf(c, cx + 4, top + 3, r / 2 + 3, 0.6f + sway); }
    if (stage == 4) {
        int fx = cx + (int)(sway * 6), fy = top - r / 2;
        c.drawLine(cx, top + 2, fx, fy, pal::BODY_DK);
        for (int i = 0; i < 5; i++) {
            float a = i * 1.2566f + t * 0.5f;
            c.fillCircle(fx + (int)(cosf(a) * 5), fy + (int)(sinf(a) * 5), 4, pal::PETAL);
        }
        c.fillCircle(fx, fy, 3, pal::CHEEK);
    }

    // body
    c.fillEllipse(cx, cy, bw, bh, pal::BODY);
    c.fillEllipse(cx, cy + bh / 3, bw * 2 / 3, bh / 2, pal::BELLY);
    c.fillEllipse(cx - bw / 2, cy - bh / 2, bw / 5, bh / 6, pal::BELLY);  // highlight

    // face
    int lx = (int)(look * r * 0.18f);
    int eyeY = cy - bh / 5, eyeDX = r * 2 / 5, er = max(2, r / 6);
    if (ex == EX_LISTEN || ex == EX_ALERT) er = er * 4 / 3;
    bool blink = fmodf(t, 4.3f) < 0.13f && ex != EX_LISTEN;

    for (int s = -1; s <= 1; s += 2) {
        int ex_ = cx + s * eyeDX + lx;
        switch (ex) {
            case EX_HAPPY:
                c.drawLine(ex_ - er, eyeY + 1, ex_, eyeY - er + 1, pal::EYE);
                c.drawLine(ex_, eyeY - er + 1, ex_ + er, eyeY + 1, pal::EYE);
                c.drawLine(ex_ - er, eyeY + 2, ex_, eyeY - er + 2, pal::EYE);
                c.drawLine(ex_, eyeY - er + 2, ex_ + er, eyeY + 2, pal::EYE);
                break;
            case EX_SLEEP:
                c.drawFastHLine(ex_ - er, eyeY + 1, er * 2, pal::EYE);
                c.drawFastHLine(ex_ - er, eyeY + 2, er * 2, pal::EYE);
                break;
            case EX_DIZZY:
                c.drawLine(ex_ - er, eyeY - er, ex_ + er, eyeY + er, pal::EYE);
                c.drawLine(ex_ - er, eyeY + er, ex_ + er, eyeY - er, pal::EYE);
                break;
            case EX_LOVE:
                drawHeart(c, ex_, eyeY - 1, er, pal::HEART);
                break;
            default:
                if (blink) {
                    c.drawFastHLine(ex_ - er, eyeY, er * 2, pal::EYE);
                } else {
                    c.fillCircle(ex_, eyeY, er, pal::EYE);
                    c.fillCircle(ex_ - er / 3, eyeY - er / 3, max(1, er / 3), pal::SHINE);
                }
                if (ex == EX_SAD)  // worried brows
                    c.drawLine(ex_ - er, eyeY - er - 3 + (s < 0 ? 2 : 0), ex_ + er, eyeY - er - 3 + (s < 0 ? 0 : 2), pal::EYE);
        }
    }
    // cheeks
    if (ex != EX_SAD && ex != EX_SLEEP) {
        c.fillEllipse(cx - eyeDX - er - 1 + lx, eyeY + er + 3, max(2, r / 7), max(1, r / 12), pal::CHEEK);
        c.fillEllipse(cx + eyeDX + er + 1 + lx, eyeY + er + 3, max(2, r / 7), max(1, r / 12), pal::CHEEK);
    }
    // mouth
    int my = eyeY + er + max(4, r / 4), mx = cx + lx;
    switch (ex) {
        case EX_TALK: {
            int h = 1 + (int)(mouth * r * 0.28f);
            c.fillEllipse(mx, my, max(2, r / 6), h, pal::EYE);
            break;
        }
        case EX_HAPPY: case EX_LOVE: case EX_ALERT:
            c.fillArc(mx, my - 1, 0, max(3, r / 5), 0, 180, pal::EYE);
            break;
        case EX_SAD:
            c.drawArc(mx, my + r / 6, max(3, r / 6), max(2, r / 6) - 1, 200, 340, pal::EYE);
            if (fmodf(t, 3) < 2) c.fillCircle(cx + eyeDX + lx + 1, eyeY + er + 3 + (int)(fmodf(t, 3) * 4), 2, lgfx::color565(120, 180, 255));
            break;
        case EX_LISTEN: case EX_THINK:
            c.fillCircle(mx + (ex == EX_THINK ? r / 6 : 0), my, max(2, r / 10), pal::EYE);
            break;
        case EX_SLEEP:
            c.fillCircle(mx, my, 1, pal::EYE);
            break;
        default:
            c.drawArc(mx, my - 2, max(3, r / 6), max(2, r / 6) - 1, 20, 160, pal::EYE);
    }

    // extras around the pet
    c.setFont(&fonts::Font2);
    if (ex == EX_SLEEP) {
        c.setTextColor(pal::DIM);
        for (int i = 0; i < 3; i++) {
            float p = fmodf(t * 0.5f + i * 0.33f, 1.0f);
            c.drawString("z", cx + r + 2 + (int)(p * 10), cy - bh - (int)(p * 22));
        }
    }
    if (ex == EX_THINK) {
        for (int i = 0; i < 3; i++)
            if (fmodf(t * 2, 3) > i) c.fillCircle(cx + r + 6 + i * 7, cy - bh - 4, 2, pal::TEXT);
    }
    if (ex == EX_LOVE) {
        for (int i = 0; i < 3; i++) {
            float p = fmodf(t * 0.8f + i * 0.33f, 1.0f);
            drawHeart(c, cx - r + i * r, cy - bh - 6 - (int)(p * 24), 5, pal::HEART);
        }
    }
    if (ex == EX_ALERT) {
        c.setTextColor(lgfx::color565(255, 210, 80));
        c.setFont(&fonts::Font4);
        c.drawString("!", cx + r + 2, cy - bh - 18);
    }
    if (ex == EX_LISTEN) {
        for (int i = 1; i <= 3; i++) {
            int rr = r + 4 + i * 6 + (int)(fmodf(t * 20, 6));
            c.drawArc(cx, cy, rr, rr - 1, 300, 340, pal::DIM);
            c.drawArc(cx, cy, rr, rr - 1, 200, 240, pal::DIM);
        }
    }
}
