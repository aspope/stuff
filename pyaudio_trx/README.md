trx.py
======

A simple tool to send/receive streams of WAVE audio.

Can be used in two modes:
* Sender   (tx): Capture audio from input device and transmit to a receiver.
* Receiver (rx): Listen for a sender and transfer audio to an output device.

The transmission is reasonably low-latency - you can expect 10's to 100's of
milliseconds, depending on your network.

See `--help` for all options and `--list` to list audio devices.

Requires
--------
* pyaudio

Credits
-------
* Inspired by Mark Hills' trx; http://www.pogo.org.uk/~mark/trx/
* Based on code from Quanquan Li's pyaudio voice-chat example; http://sharewebegin.blogspot.com/2013/06/real-time-voice-chat-example-in-python.html
