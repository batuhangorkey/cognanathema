# Cognanathema

Cloud based face recognition system using Raspberry Pi. I have used Flask as my backend and deepface library for face embeddings.

## Example Keys for signup

- tP8Sjw 
- zvrAgg

## Raspberry Pi

I used official PiCam v2 NoIR camera with picamera2 python library. For thermal camera I used mlx9060 with adafruit libraries.

### Specs
Linux raspberrypi 6.1.0-rpi6-rpi-v8 #1 SMP PREEMPT Debian 1:6.1.58-1+rpt2 (2023-10-27) aarch64 GNU/Linux

## Tips

uuid4() for random uuid

### Flask Database Commands

- flask db init
- flask db migrate -m comment
- flask db upgrade
