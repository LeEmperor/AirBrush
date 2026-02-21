/**
 * PPM output via ESP32 RMT peripheral — generates a standard 8-channel PPM
 * frame on a single GPIO pin.  Useful for trainer port / PPM-in interfaces.
 *
 * PPM timing:
 *   Channel pulse: 1000–2000 µs (center 1500)
 *   Sync pulse: remainder of 22500 µs frame
 *   Polarity: default positive
 */
#include "output_ppm.h"
#include <Arduino.h>
#include <driver/rmt.h>

static const int NUM_CHANNELS = 8;
static const int FRAME_US     = 22500;
static const int PULSE_MIN_US = 1000;
static const int PULSE_MAX_US = 2000;
static const int PULSE_MID_US = 1500;
static const int SEP_US       = 300;  // inter-channel separator

static float channelValues[NUM_CHANNELS];  // -1..+1
static int ppmPin = 25;
static rmt_channel_t rmtChannel = RMT_CHANNEL_0;
static bool ppmReady = false;

static rmt_item32_t ppmItems[NUM_CHANNELS + 1];  // channels + sync

static int normalizedToUs(float v) {
  v = constrain(v, -1.0f, 1.0f);
  return PULSE_MID_US + (int)(v * (float)(PULSE_MAX_US - PULSE_MID_US));
}

static void buildFrame() {
  int totalUs = 0;
  for (int i = 0; i < NUM_CHANNELS; i++) {
    int pw = normalizedToUs(channelValues[i]);
    // High for SEP_US, then low for (pw - SEP_US)
    ppmItems[i].duration0 = SEP_US;
    ppmItems[i].level0    = 1;
    ppmItems[i].duration1 = pw - SEP_US;
    ppmItems[i].level1    = 0;
    totalUs += pw;
  }
  // Sync pulse fills remainder of frame
  int syncUs = FRAME_US - totalUs;
  if (syncUs < SEP_US * 2) syncUs = SEP_US * 2;
  ppmItems[NUM_CHANNELS].duration0 = SEP_US;
  ppmItems[NUM_CHANNELS].level0    = 1;
  ppmItems[NUM_CHANNELS].duration1 = syncUs - SEP_US;
  ppmItems[NUM_CHANNELS].level1    = 0;
}

void ppmInit(int pin) {
  ppmPin = pin;
  for (int i = 0; i < NUM_CHANNELS; i++) channelValues[i] = 0.0f;

  rmt_config_t cfg = RMT_DEFAULT_CONFIG_TX((gpio_num_t)ppmPin, rmtChannel);
  cfg.clk_div = 80;  // 1 µs resolution (80 MHz / 80)
  cfg.tx_config.loop_en = true;
  cfg.tx_config.carrier_en = false;

  rmt_config(&cfg);
  rmt_driver_install(rmtChannel, 0, 0);

  buildFrame();
  rmt_write_items(rmtChannel, ppmItems, NUM_CHANNELS + 1, false);
  ppmReady = true;
}

void ppmSetChannel(int ch, float normalized) {
  if (ch < 0 || ch >= NUM_CHANNELS) return;
  channelValues[ch] = constrain(normalized, -1.0f, 1.0f);

  if (!ppmReady) return;
  rmt_tx_stop(rmtChannel);
  buildFrame();
  rmt_write_items(rmtChannel, ppmItems, NUM_CHANNELS + 1, false);
}

void ppmNeutralAll() {
  for (int i = 0; i < NUM_CHANNELS; i++) channelValues[i] = 0.0f;
  if (!ppmReady) return;
  rmt_tx_stop(rmtChannel);
  buildFrame();
  rmt_write_items(rmtChannel, ppmItems, NUM_CHANNELS + 1, false);
}
