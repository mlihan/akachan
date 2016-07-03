import traceback
import os
import pyaudio
import numpy as np
import time
import multiprocessing as mp
import logging
import ctypes
import json
import requests
import sys
import base64
import subprocess as sp
import signal
from subprocess import call
from base64 import b64encode
from scipy import ndimage, interpolate
from datetime import datetime
from multiprocessing.connection import Listener
from requests.exceptions import ConnectionError

CHUNK_SIZE = 8192
AUDIO_FORMAT = pyaudio.paInt16
SAMPLE_RATE = 16000
BUFFER_HOURS = 1
BROADCAST_INTERVAL = 1
has_imgur = False

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


def process_broadcast(shared_audio, shared_time, shared_pos, config, lock):
    """
    Endless loop: Sends audio data to the web server every interval

    :param shared_audio:
    :param shared_time:
    :param shared_pos:
    :param config:
    :param lock:
    :return:
    """

    # Initialize web server address and port
    web_server = 'http://%s:%s' % (config['serverUrl'], config['audioPort'])
    print >>sys.stderr, 'connecting to %s' % web_server

    # Create TCP socket
    #sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)    
    #sock.connect(web_server)

    try: 
        while True: 
            time.sleep(BROADCAST_INTERVAL)
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
            audio_signal /= config['upperLimit']
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
            noise = audio_signal > config['noiseThreshold'] 
            silent = audio_signal < config['noiseThreshold'] 
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
                    if interval_length < config['minQuietTime']:
                        noise[start:stop] = True

                # find noise blocks start times and duration
                crying_labels, num_crying_blocks = ndimage.label(noise)
                crying_ranges = ndimage.find_objects(crying_labels)
                for cry in crying_ranges:
                    start = time_stamps[cry[0].start]
                    stop = time_stamps[cry[0].stop-1]
                    duration = stop - start
                    
                    # ignore isolated noises (i.e. with a duration less than min_noise_time)
                    if duration < config['minNoiseTime']: 
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
            img_link = ""
            str_crying = "Crying for "
            str_quiet = "Quiet for "
            is_crying = False
            cry_message = "" 
            global has_imgur

            if len(crying_blocks) == 0:
                time_quiet = str_quiet + format_time_difference(time_stamps[0], time_current)
            else:
                if time_current - crying_blocks[-1]['stop'] < config['minQuietTime']: 
                    time_crying = str_crying + format_time_difference(crying_blocks[-1]['start'], time_current)
                    is_crying = True
                else:
                    time_quiet = str_quiet + format_time_difference(crying_blocks[-1]['stop'], time_current)
                    is_crying = False
                    has_imgur = False
            
            # new crying block detected  
            if is_crying and not has_imgur:
                #take a picture and upload to imgur
                photo_path = takePhoto(config['photoDir'], config['photoRes'])
                img_link = uploadImgur(photo_path, config['imgurClientId'])
                print >>sys.stdout, 'imgLink is %s' % img_link
                has_imgur = True

                #play a music
                playMusic(config['musicDir'], config['song'])
                print >>sys.stdout, 'playing %s/%s' % (config['musicDir'], config['song'])

                #cry message
                cry_message = config['babyName'] + ' is crying, I will play a song ' + config['song'] + ' to calm ' + config['babyName'] + '.'
 
            # return results to webserver
            results = {"audio_plot": audio_plot,
                       "crying_blocks": crying_blocks,
                       "time_crying": time_crying,
                       "time_quiet": time_quiet,
                       "img_link": img_link,
                       "cry_message": cry_message}

            # convert to json
            results['audio_plot'] = results['audio_plot'].tolist()
            #print "before json dump: ", results
            jsonString = json.dumps(results)
            #print "sending json dump: ", jsonString

            # send json using requests
            headers = {'content-type': 'application/json'}
            res = requests.post(web_server, data=jsonString, headers=headers)
          
            # read response
            print >>sys.stdout, 'res %s' % res.content
            
    except ConnectionError as e:
        print >>sys.stderr, e
    except Exception, err:
        print >>sys.stderr, 'Unexpected error occurred'
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
    finally:
        del exc_info
        sys.exit()

def takePhoto(photoDir, photoRes):
    photoPath = os.path.join(photoDir, 'pic.jpg')
    call(['fswebcam', '-r', photoRes, '--no-banner', photoPath])
    #sp.Popen(['fswebcam', '-r', photoRes, '--no-banner', photoPath])
    return photoPath

def uploadImgur(photoPath, clientID):
    #encode image as base64
    fh = open(photoPath, 'rb')
    base64img = b64encode(fh.read())
    #send post request to imgur
    res = requests.post('https://api.imgur.com/3/image', 
        data={'image':base64img},
        headers={'Authorization':'Client-ID ' + clientID}
        )
    #parse json response
    json_data = json.loads(res.text)
    return str(json_data[u'data'][u'link'])

def playMusic(musicDir, filename):
    global music_proc
    # stop the current music if it's still playing
    #if music_proc.poll() is None:
        #os.killpg(os.gtpgid(music_proc.pid), signal.SIGTERM)
        #music_proc.kill()
    # play music
    musicPath = os.path.join(musicDir, filename)
    music_proc = sp.Popen(['sudo', 'mplayer', '-ao', 'pulse', musicPath])
    #call(['sudo', 'mplayer', '-ao', 'pulse', musicPath]) 

def init_server():
    # read config file
    with open('../config/config.json', 'r') as f:
        config = json.load(f)
    
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
    p2 = mp.Process(target=process_broadcast, args=(shared_audio, shared_time, shared_pos, config, lock))
    p1.start()
    p2.start()

if __name__ == '__main__':
    init_server()
