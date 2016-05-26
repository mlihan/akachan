import pyaudio
import numpy as np
import time
import multiprocessing as mp
import logging
import ctypes
import json
import socket
import sys
from scipy import ndimage, interpolate
from datetime import datetime
from multiprocessing.connection import Listener

CHUNK_SIZE = 8192
AUDIO_FORMAT = pyaudio.paInt16
SAMPLE_RATE = 16000
BUFFER_HOURS = 1
WEB_SERVER_ADDRESS = ('localhost', 6000)
BROADCAST_INTERVAL = 1000

UPPER_LIMIT = 25000
NOISE_THRESHOLD = 0.25
MIN_QUIET_TIME = 10
MIN_NOISE_TIME = 5


def process_audio(shared_audio, shared_time, shared_pos, lock):
    """
    Endless loop: Grab some audio from the mic and record the maximum

    :param shared_audio:
    :param shared_time:
    :param shared_pos:
    :param lock:
    :return:
    """

    # open default audio input stream
    p = pyaudio.PyAudio()
    stream = p.open(format=AUDIO_FORMAT, channels=1, rate=SAMPLE_RATE, input=True, frames_per_buffer=CHUNK_SIZE)

    while True:
        # grab audio and timestamp
        audio = np.fromstring(stream.read(CHUNK_SIZE), np.int16)
        current_time = time.time()

        # acquire lock
        lock.acquire()

        # record current time
        shared_time[shared_pos.value] = current_time

        # record the maximum volume in this time slice
        shared_audio[shared_pos.value] = np.abs(audio).max()

        # increment counter
        shared_pos.value = (shared_pos.value + 1) % len(shared_time)

        # release lock
        lock.release()
    # I've included the following code for completion, but unless the above
    # loop is modified to include an interrupt it will never be executed
    stream.stop_stream()
    stream.close()
    p.terminate()


def format_time_difference(time1, time2):
    time_diff = datetime.fromtimestamp(time2) - datetime.fromtimestamp(time1)

    return str(time_diff).split('.')[0]


def process_broadcast(shared_audio, shared_time, shared_pos, lock):
    """
    Endless loop: Sends audio data to the web server every interval

    :param shared_audio:
    :param shared_time:
    :param shared_pos:
    :param lock:
    :return:
    """

    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Connect the socket to the port where the server is
    print >>sys.stderr, 'connecting to %s port %s' % WEB_SERVER_ADDRESS
    sock.connect(WEB_SERVER_ADDRESS)
    try: 
        #let it accumulate audio data first
        time.sleep(1)
        while True: 
            time.sleep(1)
            # acquire lock
            lock.acquire()

            # convert to numpy arrays and get a copy of the data
            time_stamps = np.frombuffer(shared_time, np.float64).copy()
            audio_signal = np.frombuffer(shared_audio, np.int16).astype(np.float32)
            current_pos = shared_pos.value

            # release lock
            lock.release()

            # roll the arrays so that the latest readings are at the end
            buffer_len = time_stamps.shape[0]
            time_stamps = np.roll(time_stamps, shift=buffer_len-current_pos)
            audio_signal = np.roll(audio_signal, shift=buffer_len-current_pos)

            # normalise volume level
            audio_signal /= UPPER_LIMIT
            # apply some smoothing
            sigma = 4 * (SAMPLE_RATE / float(CHUNK_SIZE))
            audio_signal = ndimage.gaussian_filter1d(audio_signal, sigma=sigma, mode="reflect")

            # get the last hour of data for the plot and re-sample to 1 value per second
            hour_chunks = int(60 * 60 * (SAMPLE_RATE / float(CHUNK_SIZE)))
            xs = np.arange(hour_chunks)
            f = interpolate.interp1d(xs, audio_signal[-hour_chunks:])
            audio_plot = f(np.linspace(start=0, stop=xs[-1], num=3600))

            # ignore positions with no readings
            mask = time_stamps > 0
            time_stamps = time_stamps[mask]
            audio_signal = audio_signal[mask]

            # partition the audio history into blocks of type:
            #   1. noise, where the volume is greater than noise_threshold
            #   2. silence, where the volume is less than noise_threshold
            noise = audio_signal > NOISE_THRESHOLD 
            silent = audio_signal < NOISE_THRESHOLD
            # join "noise blocks" that are closer together than min_quiet_time
            crying_blocks = []
            if np.any(noise):
                silent_labels, _ = ndimage.label(silent)
                silent_ranges = ndimage.find_objects(silent_labels)
                for silent_block in silent_ranges:
                    start = silent_block[0].start
                    stop = silent_block[0].stop

                    # don't join silence blocks at the beginning or end
                    if start == 0:
                        continue

                    interval_length = time_stamps[stop-1] - time_stamps[start]
                    if interval_length < MIN_QUIET_TIME:
                        noise[start:stop] = True

                # find noise blocks start times and duration
                crying_labels, num_crying_blocks = ndimage.label(noise)
                crying_ranges = ndimage.find_objects(crying_labels)
                for cry in crying_ranges:
                    start = time_stamps[cry[0].start]
                    stop = time_stamps[cry[0].stop-1]
                    duration = stop - start
                    
                    # ignore isolated noises (i.e. with a duration less than min_noise_time)
                    if duration < MIN_NOISE_TIME: 
                        continue

                    # save some info about the noise block
                    crying_blocks.append({'start': start,
                                          'start_str': datetime.fromtimestamp(start).strftime("%I:%M:%S %p").lstrip('0'),
                                          'stop': stop,
                                          'duration': format_time_difference(start, stop)})
            
            # determine how long have we been in the current state
            time_current = time.time()
            time_crying = ""
            time_quiet = ""
            str_crying = "Crying for "
            str_quiet = "Quiet for "

            if len(crying_blocks) == 0:
                time_quiet = str_quiet + format_time_difference(time_stamps[0], time_current)
            else:
                if time_current - crying_blocks[-1]['stop'] < MIN_QUIET_TIME: 
                    time_crying = str_crying + format_time_difference(crying_blocks[-1]['start'], time_current)
                else:
                    time_quiet = str_quiet + format_time_difference(crying_blocks[-1]['stop'], time_current)
            
            # return results to webserver
            results = {"audio_plot": audio_plot,
                       "crying_blocks": crying_blocks,
                       "time_crying": time_crying,
                       "time_quiet": time_quiet}

            # convert to json
            results['audio_plot'] = results['audio_plot'].tolist()
            #print "before json dump: ", results
            jsonString = json.dumps(results)
            #print "sending json dump: ", jsonString
            sock.sendall(jsonString)        
    finally:
        print >>sys.stderr, 'closing socket'
        sock.close()

def init_server():
    # figure out how big the buffer needs to be to contain BUFFER_HOURS of audio
    buffer_len = int(BUFFER_HOURS * 60 * 60 * (SAMPLE_RATE / float(CHUNK_SIZE)))

    # create shared memory
    lock = mp.Lock()
    shared_audio = mp.Array(ctypes.c_short, buffer_len, lock=False)
    shared_time = mp.Array(ctypes.c_double, buffer_len, lock=False)
    shared_pos = mp.Value('i', 0, lock=False)

    # start 2 processes:
    # 1. a process to continuously monitor the audio feed
    # 2. a process to handle requests for the latest audio data
    p1 = mp.Process(target=process_audio, args=(shared_audio, shared_time, shared_pos, lock))
    p2 = mp.Process(target=process_broadcast, args=(shared_audio, shared_time, shared_pos, lock))
    p1.start()
    p2.start()


if __name__ == '__main__':
    init_server()
