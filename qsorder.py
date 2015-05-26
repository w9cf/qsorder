#!/usr/bin/python

##################################################
# qsorder - A contest QSO recorder
# Title: qsorder.py
# Author: k3it
# Generated: Tue, May 26 2015
# Version: 2.8
##################################################

# qsorder is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qsorder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess
import re
import pyaudio
import wave
import time
import sys
# import struct
import threading
# import string
import binascii
import pyhk
import platform
import ctypes

import datetime
import dateutil.parser

from optparse import OptionParser
from collections import deque
from socket import *
# from xml.dom.minidom import parse, parseString
from xml.dom.minidom import parseString



import logging

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
# RATE = 8000
RATE = 11025
BASENAME = "QSO"
LO = 14000
dqlength = 360  # number of chunks to store in the buffer
DELAY = 20.0
MYPORT = 12060
DEBUG_FILE = "qsorder-debug-log.txt"


usage = "usage: %prog [OPTION]..."
parser = OptionParser()
parser.add_option("-D", "--debug", action="store_true", default=False,
                        help="Save debug info[default=%default]")
parser.add_option("-d", "--delay", type="int", default=20,
                        help="Capture x seconds after QSO log entry [default=%default]")
parser.add_option("-i", "--device-index", type="int", default=None,
                        help="Index of the recording input (use -q to list) [default=%default]")
parser.add_option("-k", "--hot-key", type="string", default="O",
                        help="Hotkey for manual recording Ctrl-Alt-<hot_key> [default=%default]")
parser.add_option("-l", "--buffer-length", type="int", default=45,
                        help="Audio buffer length in secs [default=%default]")
# parser.add_option("-m", "--use-month", action="store_true", default=False,
#                         help="Include month and mode in the contest directory [default=%default]")
parser.add_option("-C", "--continuous", action="store_true", default=False,
                        help="Record continuous audio stream in addition to individual QSOs[default=%default]")
parser.add_option("-P", "--port", type="int", default=12060,
                        help="UDP Port [default=%default]")
parser.add_option("-p", "--path", type="string", default=None,
                        help="Base directory for audio files [default=%default]")
parser.add_option("-q", "--query-inputs", action="store_true", default=False,
                        help="Query and print input devices [default=%default]")
parser.add_option("-S", "--so2r", action="store_true", default=False,
                        help="SO2R mode, downmix to mono: Left Ch - Radio1 QSOs, Right Ch - Radio2 QSOs [default=%default]")
parser.add_option("-s", "--station-nr", type="int", default=None,
                        help="Network Station Number [default=%default]")



(options, args) = parser.parse_args()

dqlength = int(options.buffer_length * RATE / CHUNK) + 1
DELAY = options.delay
MYPORT = options.port

if (options.path):
    os.chdir(options.path)

if (len(options.hot_key) == 1):
    HOTKEY = options.hot_key.upper()
else:
    print "Hotkey should be a single character"
    parser.print_help()
    exit(-1)

if (options.debug):
    logging.basicConfig(filename=DEBUG_FILE, level=logging.DEBUG, format='%(asctime)s %(message)s')
    logging.debug('debug log started')
    logging.debug('qsorder options:')
    logging.debug(options)


class wave_file:
        """
        class definition for the WAV file object
        """
        def __init__(self, samp_rate, LO, BASENAME, qso_time, contest_dir, mode):
                # starttime/endtime
                self.create_time = time.time()
                # now=datetime.datetime.utcnow()
                now = qso_time
                # finish=now + datetime.timedelta(seconds=duration)

                self.wavfile = BASENAME + "_"
                self.wavfile += str(now.year)
                self.wavfile += str(now.month).zfill(2)
                self.wavfile += str(now.day).zfill(2)
                self.wavfile += "_"
                self.wavfile += str(now.hour).zfill(2)
                self.wavfile += str(now.minute).zfill(2)
                self.wavfile += str(now.second).zfill(2)
                self.wavfile += "Z_"
                # self.wavfile += str(int(LO/1000))
                self.wavfile += str(LO)
                self.wavfile += "MHz.wav"

                # contest directory
                self.contest_dir = contest_dir
                # if (options.use_month):
                #     self.contest_dir = contest_dir.replace(mode,'')
                #     self.contest_dir += "_" + mode + "_" + now.strftime("%B").upper() + "_" + str(now.year)
                # else:
                self.contest_dir += "_" + str(now.year)



                # fix slash in the file/directory name
                self.wavfile = self.wavfile.replace('/', '-')
                self.contest_dir = self.contest_dir.replace('/', '-')

                self.wavfile = self.contest_dir + "/" + self.wavfile

                # get ready to write wave file
                try:
                    if not os.path.exists(self.contest_dir):
                            os.makedirs(self.contest_dir)
                    self.w = wave.open(self.wavfile, 'wb')
                except:
                    print "unable to open WAV file for writing"
                    sys.exit()
                # 16 bit complex samples
                # self.w.setparams((2, 2, samp_rate, 1, 'NONE', 'not compressed'))
                self.w.setnchannels(CHANNELS)
                self.w.setsampwidth(p.get_sample_size(FORMAT))
                self.w.setframerate(RATE)
                # self.w.close()

        def write(self, data):
                self.w.writeframes(data)

        def close_wave(self, nextfilename=''):
                self.w.close()


def dump_audio(call, contest, mode, freq, qso_time, radio_nr):
    # create the wave file
    BASENAME = call + "_" + contest + "_" + mode
    BASENAME = BASENAME.replace('/', '-')
    w = wave_file(RATE, freq, BASENAME, qso_time, contest, mode)
    __data = (b''.join(frames))
    bytes_written = w.write(__data)
    w.close_wave()

    # try to convert to mp3
    lame_path = os.path.dirname(os.path.realpath(__file__))
    lame_path += "\\lame.exe"

    if (options.so2r and radio_nr == "1"):
        command = [lame_path]
        arguments = ["-h", "-m", "m", "--scale-l", "2", "--scale-r", "0", w.wavfile]
        command.extend(arguments)
    elif (options.so2r and radio_nr == "2"):
        command = [lame_path]
        arguments = ["-h", "-m", "m", "--scale-l", "0", "--scale-r", "2", w.wavfile]
        command.extend(arguments)
    else:
        command = [lame_path]
        arguments = ["-h", w.wavfile]
        command.extend(arguments)


    try:
        if (options.debug):
            logging.debug(command)

        output = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
        gain = re.search('\S*Replay.+', output)
        print "WAV:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), BASENAME[:20] + ".." + str(freq) + "Mhz.mp3", \
            gain.group(0)
        os.remove(w.wavfile)
    except:
        print "could not convert wav to mp3", w.wavfile


def manual_dump():
    print "QSO:", datetime.datetime.utcnow().strftime("%m-%d %H:%M:%S"), "HOTKEY pressed"
    dump_audio("HOTKEY", "AUDIO", "RF", 0, datetime.datetime.utcnow(), 73)


def hotkey():
    # create pyhk class instance
    hot = pyhk.pyhk()

    # add hotkey
    hot.addHotkey(['Ctrl', 'Alt', HOTKEY], manual_dump, isThread=False)
    hot.start()

def get_free_space_mb(folder):
    """ Return folder/drive free space (in bytes)
    """
    if platform.system() == 'Windows':
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(folder), None, None, ctypes.pointer(free_bytes))
        return free_bytes.value/1024/1024
    else:
        st = os.statvfs(folder)
        return st.f_bavail * st.f_frsize/1024/1024


def start_new_lame_stream():

    lame_path = os.path.dirname(os.path.realpath(__file__))
    lame_path += "\\lame.exe"


    # print "CTL: Starting new mp3 file", datetime.datetime.utcnow.strftime("%m-%d %H:%M:%S")
    now = datetime.datetime.utcnow()
    contest_dir = "AUDIO_" + str(now.year)
    if not os.path.exists(contest_dir):
        os.makedirs(contest_dir)

    BASENAME = "CONTEST_AUDIO"
    filename = contest_dir + "/" + BASENAME + "_"
    filename += str(now.year)
    filename += str(now.month).zfill(2)
    filename += str(now.day).zfill(2)
    filename += "_"
    filename += str(now.hour).zfill(2)
    filename += str(now.minute).zfill(2)
    filename += "Z"
    # filename += str(int(LO/1000))
    filename += ".mp3"
    command = [lame_path]
    # arguments = ["-r", "-s", str(RATE), "-v", "--disptime 60", "-h", "--tt", BASENAME, "--ty", str(now.year), "--tg Ham Radio", "-", filename]
    # arguments = ["-r", "-s", str(RATE), "-v", "-h", "--quiet", "--tt", BASENAME, "--ty", str(now.year), "-", filename]
    arguments = ["-r", "-s", str(RATE), "-h", "--flush", "--quiet", "--tt", "Qsorder Contest Recording", "--ty", str(now.year), "--tc", os.path.basename(filename), "-", filename]
    command.extend(arguments)
    try:
        mp3handle = subprocess.Popen(command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    except:
        print "CTL error starting mp3 recording.  Exiting.."
        os._exit(-1)

    print "CTL:", str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + "Z started new .mp3 file: ", filename
    print "CTL: Disk free space:", get_free_space_mb(contest_dir)/1024, "GB"
    if get_free_space_mb(contest_dir) < 100:
        print "CTL: WARNING: Low Disk space"
    return mp3handle,filename



#write continious mp3 stream to disk in a separate worker thread
def writer():
        # start new lame recording
        now = datetime.datetime.utcnow()
        utchr = now.hour
        utcmin = now.minute
        (lame, filename) = start_new_lame_stream()
        while True:
            #open a new file on top of the hour
            now = datetime.datetime.utcnow()
            if utchr != now.hour:
                # sleep some to flush out buffers
                time.sleep(5)
                lame.terminate()
                utchr = now.hour
                (lame, filename) = start_new_lame_stream()
            if (len(replay_frames) > 0):
                data = replay_frames.popleft()
                lame.stdin.write(data)
            else:
               time.sleep(1)
            if (utcmin != now.minute and now.minute % 10 == 0 and now.minute != 0):
                print "CTL:", str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + "Z ...recording:", filename
                contest_dir = "AUDIO_" + str(now.year)
                if get_free_space_mb(contest_dir) < 100:
                    print "CTL: WARNING: Low Disk space"
                utcmin = now.minute



# start hotkey monitoring thread
t = threading.Thread(target=hotkey)
t.start()



print("--------------------------------------")
print "v2.8 QSO Recorder for N1MM, 2015 K3IT\n"
print("--------------------------------------")

p = pyaudio.PyAudio()

if (options.query_inputs):
    max_devs = p.get_device_count()
    print "Detected", max_devs, "devices\n"       ################################
    print "Device index Description"
    print "------------ -----------"
    for i in range(max_devs):
        p = pyaudio.PyAudio()
        devinfo = p.get_device_info_by_index(i)

        if devinfo['maxInputChannels'] > 0:
            try:
                if p.is_format_supported(int(RATE),
                                         input_device=devinfo['index'],
                                         input_channels=devinfo['maxInputChannels'],
                                         input_format=pyaudio.paInt16):
                        print "\t", i, "\t", devinfo['name']
            except ValueError:
                pass
        p.terminate()
    os._exit(0)


if (options.device_index):
    try:
        def_index = p.get_device_info_by_index(options.device_index)
        print "Input Device :", def_index['name']
        DEVINDEX = options.device_index
    except IOError as e:
        print("Invalid Input device: %s" % e[0])
        p.terminate()
        os._exit(-1)

else:
    try:
        def_index = p.get_default_input_device_info()
        print "Input Device :", def_index['index'], def_index['name']
        DEVINDEX = def_index['index']
    except IOError as e:
        print("No Input devices: %s" % e[0])
        p.terminate()
        os._exit(-1)

# queue for chunked recording
frames = deque('', dqlength)

# queue for continous recording
replay_frames = deque('',dqlength)



print "Listening on UDP port", MYPORT


# define callback
def callback(in_data, frame_count, time_info, status):
    frames.append(in_data)
    # add code for continous recording here
    replay_frames.append(in_data)
    return (None, pyaudio.paContinue)


stream = p.open(format=FORMAT,
                channels=CHANNELS,
                input_device_index=DEVINDEX,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                stream_callback=callback)

# start the stream
stream.start_stream()


print "* recording", CHANNELS, "ch,", dqlength * CHUNK / RATE, "secs audio buffer, Delay:", DELAY, "secs"
print "Output directory", os.getcwd() + "\\<contest...>"
print "Hotkey: CTRL+ALT+" + HOTKEY
if (options.station_nr >= 0):
    print "Recording only station", options.station_nr, "QSOs"
if (options.continuous):
    print "Full contest recording enabled."
print("\t--------------------------------\n")


#start continious mp3 writer thread
if (options.continuous):
    mp3 = threading.Thread(target=writer)
    mp3.start()


# listen on UDP port
# Receive UDP packets transmitted by a broadcasting service

s = socket(AF_INET, SOCK_DGRAM)
s.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
try:
        s.bind(('', MYPORT))
except:
        print "Error connecting to the UDP stream."


seen = {}

while stream.is_active():
    try:
        udp_data = s.recv(2048)
        check_sum = binascii.crc32(udp_data)
        dom = parseString(udp_data)

        if (options.debug):
            logging.debug('UDP Packet Received:')
            logging.debug(udp_data)

        # skip packet if duplicate
        if check_sum in seen:
            seen[check_sum] += 1
            if (options.debug):
                logging.debug('DUPE packet skipped')
        else:
            seen[check_sum] = 1
            try:
                now = datetime.datetime.utcnow()

                # read UDP fields
                dom = parseString(udp_data)
                call = dom.getElementsByTagName("call")[0].firstChild.nodeValue
                mycall = dom.getElementsByTagName("mycall")[0].firstChild.nodeValue
                mode = dom.getElementsByTagName("mode")[0].firstChild.nodeValue
                freq = dom.getElementsByTagName("band")[0].firstChild.nodeValue
                contest = dom.getElementsByTagName("contestname")[0].firstChild.nodeValue
                station = dom.getElementsByTagName("NetworkedCompNr")[0].firstChild.nodeValue
                qso_timestamp = dom.getElementsByTagName("timestamp")[0].firstChild.nodeValue
                radio_nr = dom.getElementsByTagName("radionr")[0].firstChild.nodeValue

                # convert qso_timestamp to datetime object
                timestamp = dateutil.parser.parse(qso_timestamp)

                # verify that month matches, if not, give DD-MM-YY format precendense
                if (timestamp.strftime("%m") != now.strftime("%m")):
                    timestamp = dateutil.parser.parse(qso_timestamp, dayfirst=True)

                # skip packet if not matching network station number specified in the command line
                if (options.station_nr >= 0):
                    if (options.station_nr != station):
                        print "QSO:", timestamp.strftime("%m-%d %H:%M:%S"), call, freq, "--- ignoring from stn", station
                        continue

                # skip packet if QSO was more than DELAY seconds ago
                t_delta = (now - timestamp).total_seconds()
                if (t_delta > DELAY):
                        print "---:", timestamp.strftime("%m-%d %H:%M:%S"), call, freq, "--- ignoring ",\
                            t_delta, "sec old QSO"
                        continue

                calls = call + "_de_" + mycall

                # if (mode == "USB" or mode == "LSB"):
                #   mode="SSB"

                # t = threading.Timer( DELAY, dump_audio,[calls,contest,mode,freq,datetime.datetime.utcnow()] )
                t = threading.Timer(DELAY, dump_audio, [calls, contest, mode, freq, timestamp, radio_nr])
                print "QSO:", timestamp.strftime("%m-%d %H:%M:%S"), call, freq
                t.start()
            except:
                if (options.debug):
                    logging.debug('Could not parse previous packet')
                pass  # ignore, probably some other udp packet

    except (KeyboardInterrupt):
        print "73! k3it"
        stream.stop_stream()
        stream.close()
        p.terminate()
        raise


#
stream.close()
p.terminate()
