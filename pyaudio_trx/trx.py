"""
A simple tool to send/receive streams of WAVE audio.

Can be used in two modes:
  * Sender   (tx): Capture audio from input device and transmit to a receiver.
  * Receiver (rx): Listen for a sender and transfer audio to an output device.

The transmission is reasonably low-latency - you can expect 10's to 100's of
milliseconds, depending on your network.

Requires pyaudio.

Credits:
  * Inspired by Mark Hills' trx; http://www.pogo.org.uk/~mark/trx/
  * Based on code from Quanquan Li's pyaudio voice-chat example;
    http://sharewebegin.blogspot.com/2013/06/real-time-voice-chat-example-in-python.html
"""
import argparse
import errno
import logging
import pyaudio
import signal
import socket
import sys
import time
import wave


class BaseAudio(object):
    audio = None
    sock = None
    stream = None

    def __init__(self, duration=None, channels=1, rate=44100,
                 chunk_size=1024, host='', port=50007, device_index=None,
                 sock_timeout=1.0):
        self.chunk_size = chunk_size
        self.channels = channels
        self.device_index = device_index
        self.duration = duration
        self.rate = rate
        self.host = host
        self.port = port
        self.format = pyaudio.paInt16
        self.audio = pyaudio.PyAudio()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(sock_timeout)
        self.log = logging.getLogger(self.__class__.__name__)

    def list_devices(self):
        devinfos = []
        default_devinfo = self.audio.get_default_output_device_info()
        for i in range(self.audio.get_device_count()):
            devinfos.append(self.audio.get_device_info_by_index(i))
        for i, devinfo in enumerate(devinfos):
            def_string = ""
            if devinfo.get('index') != None and \
                    default_devinfo.get('index') != None and \
                    devinfo['index'] == default_devinfo['index']:
                def_string = " (DEFAULT)"
            print("%d: %s%s" % (i, devinfo.get('name', '?'), def_string))
            print("    Default sample rate: %d" % devinfo.get('defaultSampleRate', 0))
            print("    Max input/output channels: %d/%d" % (
                  devinfo.get('maxInputChannels', 0),
                  devinfo.get('maxOutputChannels', 0)))

    def shutdown(self):
        self.log.info("Shutting down")
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.sock:
            self.sock.close()

    def handle_signal(self, signum, frame=None):
        self.log.warning("Received signal %d" % signum)
        self.shutdown()


class AudioReceiver(BaseAudio):
    width = 2
    wf = None

    def open_audio_stream(self):
        self.stream = self.audio.open(format=self.audio.get_format_from_width(self.width),
                                      channels=self.channels,
                                      rate=self.rate,
                                      output=True,
                                      output_device_index=self.device_index,
                                      frames_per_buffer=self.chunk_size)

    def listen_and_process(self):
        """ Listen for a socket connection and then receive audio. """
        self.sock.bind((self.host, self.port))
        self.sock.listen(1)
        self.log.info("Waiting for new connection...")
        while True:
            try:
                conn, addr = self.sock.accept()
            except socket.timeout:
                continue
            except socket.error as e:
                if e.errno == errno.EINTR:
                    # Interrupted system call - we're probably shutting down.
                    break
            self.log.info("New connection from %s" % str(addr))
            self.receive_audio(conn)

    def receive_audio(self, conn):
        """ Process audio received from a socket connection. """
        self.log.info("Receiving audio...")
        frame_count = 1
        self.open_audio_stream()
        data = conn.recv(1024)
        while data != '':
            self.stream.write(data)
            data = conn.recv(1024)
            self.log.debug("Frame %d" % frame_count)
            frame_count += 1
            if self.wf:
                # If list of frames then write like wf.writeframes(b''.join(frames))
                wf.writeframes(data)
        self.log.info("Data stopped.")
        self.stream.stop_stream()
        self.stream.close()

    def open_wave_file(self, filename=''):
        self.wf = wave.open(filename, 'wb')
        self.wf.setnchannels(self.channels)
        self.wf.setsampwidth(self.audio.get_sample_size(self.format))
        self.wf.setframerate(self.rate)

    def close_wave_file(self):
        if self.wf:
            self.wf.close()


class AudioSender(BaseAudio):
    def socket_connect(self):
        self.sock.connect((self.host, self.port))

    def open_audio_stream(self):
        self.stream = self.audio.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      input_device_index=self.device_index,
                                      frames_per_buffer=self.chunk_size)

    def send_frame(self):
        data = self.stream.read(self.chunk_size)
        self.sock.sendall(data)

    def send_frames_continuously(self):
        while True:
            self.send_frame()

    def send_frames_with_time_limit(self, duration):
        for i in range(0, int(self.rate / self.chunk_size * duration)):
            self.send_frame()

    def start_sending(self):
        self.log.info("Opening socket connection")
        self.socket_connect()
        self.log.info("Opening audio stream")
        self.open_audio_stream()
        self.log.info("Begin audio capture")
        if self.duration:
            self.send_frames_with_time_limit(self.duration)
        else:
            self.send_frames_continuously()
        self.log.info("Finished audio capture")

    def stop_sending(self):
        self.log.info("Stopping")
        self.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Audio sender/receiver utility.")

    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--list", dest="list", action="store_true",
                         help="List available audio devices and quit.")
    actions.add_argument("--tx", dest="tx", action="store_true",
                         help="Transmit audio to a listening receiver.")
    actions.add_argument("--rx", dest="rx", action="store_true",
                         help="Receive audio from a transmitter.")

    audio = parser.add_argument_group("Common audio options")
    audio.add_argument("--rate", dest="rate", action="store",
                       type=int, metavar="HZ", default=44100,
                       help="Sample rate of audio in Hz. Default %(default)s.")
    audio.add_argument("--chunk-size", dest="chunk_size", action="store",
                       type=int, metavar="FRAMES", default=1024,
                       help="Frames per buffer. Default %(default)s.")
    audio.add_argument("--channels", dest="channels", action="store",
                       type=int, metavar="QTY", default=1,
                       help="Number of audio channels. Default %(default)s.")
    audio.add_argument("--dev", dest="device_index", action="store",
                       type=int, metavar="ID", default=None,
                       help="Audio device ID. Use --list to list available devices. If none then assume default ALSA device.")

    sender = parser.add_argument_group("Sender-specific audio options")
    sender.add_argument("--duration", dest="duration", action="store",
                        type=int, metavar="SECS", default=0,
                        help="Max duration of audio to capture and send. Default 0 (unlimited).")

    network = parser.add_argument_group("Network options")
    network.add_argument("--host", dest="host", action="store",
                         type=str, metavar="ADDR", default='',
                         help="Sender: Hostname/IP address of receiver host.\nReceiver: Bind address for listening socket (empty for any).")
    network.add_argument("--port", dest="port", action="store",
                         type=int, metavar="NUM", default=50007,
                         help="TCP port number. Default %(default)s.")
    network.add_argument("--timeout", dest="sock_timeout", action="store",
                         type=float, metavar="SECS", default=1.0,
                         help="TCP socket timeout in secs. Default %(default)s.")

    parser.add_argument("--log", dest="logfile", action="store",
                        type=str, metavar="FILENAME", default="",
                        help="Log messages to file.")
    parser.add_argument("--quiet", dest="quiet_log", action="store_true",
                        help="Do not log to stdout/stderr - just be quiet.")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_true",
                        help="Log debug messages also.")

    args = parser.parse_args()

    # Setup the root logger
    log = logging.getLogger()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    log.setLevel(loglevel)
    # Log to screen under certain conditions
    if not args.quiet_log:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        log.addHandler(stream_handler)
    # Log to file
    if args.logfile:
        sys.stderr.write('Logging to %s' % args.logfile)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=args.logfile, maxBytes=20000000, backupCount=5)
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)

    # Do stuff
    if args.list:
        audio = AudioSender()
        audio.list_devices()
        audio.shutdown()
        sys.exit(0)
    elif args.tx:
        try:
            tx = AudioSender(
                    duration=args.duration,
                    channels=args.channels,
                    rate=args.rate,
                    chunk_size=args.chunk_size,
                    host=args.host,
                    port=args.port,
                    device_index=args.device_index,
                    sock_timeout=args.sock_timeout)
            signal.signal(signal.SIGINT, tx.handle_signal)
            signal.signal(signal.SIGTERM, tx.handle_signal)
            tx.start_sending()
            tx.stop_senddng()
        except KeyboardInterrupt:
            tx.log.warning("Received KeyboardInterrupt")
            tx.stop_sending()
    elif args.rx:
        try:
            rx = AudioReceiver(
                    channels=args.channels,
                    rate=args.rate,
                    chunk_size=args.chunk_size,
                    host=args.host,
                    port=args.port,
                    device_index=args.device_index,
                    sock_timeout=args.sock_timeout)
            signal.signal(signal.SIGINT, rx.handle_signal)
            signal.signal(signal.SIGTERM, rx.handle_signal)
            rx.listen_and_process()
        except KeyboardInterrupt:
            rx.log.warning("Received KeyboardInterrupt")
            rx.shutdown()

