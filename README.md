# Akachan

Akachan is a [LINE BOT API Trial](https://developers.line.me/type-of-accounts/bot-api-trial) account that is linked to a Raspberry Pi, speaker and USB web camera.

The web server is written in Node JS which handles communication between LINE and audio server. It should ideally run on a public IP, Heroku (https://dashboard.heroku.com/), or other cloud services to communicate with LINE securely. Audio server is running on Raspberry Pi and communicates with the web server through web socket. Sound detector uses [Neil Yager](https://github.com/NeilYager/LittleSleeper) application.

## Prerequisite
1. Create the LINE channel on [LINE Bussiness Center](https://business.line.me/)


## Hardware Prerequisite
1. Raspberry Pi
2. Edimax WiFi
3. 8GB or higher SD Card with Raspbian OS
4. Any [supported](http://elinux.org/RPi_USB_Webcams) Web camera
5. Any supported Audio speaker 

## Configuration
* Install [nodeJS](https://nodejs.org/), [npm](https://github.com/npm/npm)
* Install [USB webcam](https://www.raspberrypi.org/documentation/usage/webcams/)
* Install heroku (optional)
* Install the media related applications and node modules
```
    $ sudo apt-get install omxplayer
    $ sudo apt-get install arecord
    $ sudo apt-get install aplay
    $ sudo apt-get install jackd
    $ npm install
```
* Rename config/config_sample.json as config/config.json, input the web address, mid, channel ID and channel secret.
* Please note that you would most likely need to configure a lot more than what's written here. Please check [Raspberry Pi forums](https://www.raspberrypi.org/forums/) for troubleshooting

## Run
### Web Server
```
    $ node server.js
```
### Audio Server
```
    $ python audio_server.py
```

* To check web client open http://<web server>:<web port>



## Dependecies
node_modules
* [body-parser](https://www.npmjs.com/package/body-parser)
* [crypto-js](https://www.npmjs.com/package/crypto-js)
* [express](https://www.npmjs.com/package/express)
* [request](https://www.npmjs.com/package/request)
* [express-ws](https://www.npmjs.com/package/express-ws)
* [socket.io](https://www.npmjs.com/package/socket.io-client)
* [sqlite3](https://www.npmjs.com/package/sqlite3)

## Reference
* [LINE Developers BOT API](https://developers.line.me/bot-api/overview)
* [LINE Developers BOT API Trial](https://developers.line.me/type-of-accounts/bot-api-trial)

### Note
* This sample is built as a simple testbed. Please take care the settings and security staff if you want to use this sample as production enviroment.