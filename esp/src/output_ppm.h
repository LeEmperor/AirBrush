#pragma once

void ppmInit(int pin = 25);
void ppmSetChannel(int ch, float normalized);  // ch 0-7, value -1..+1
void ppmNeutralAll();
