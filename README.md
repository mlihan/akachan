# BC sample server with NodeJS

This sample is aimed to let developers have a picture about the BC server development.

It is a echo server that shows some functions of [LINE Bussiness Connect](https://developers.line.me/businessconnect/overview)
* Signature Validation
* Receiving Messages
* Sending Messages

## Prerequisite

1. Create the LINE channel on [LINE developers](https://developers.line.me/)
1. Install [nodeJS](https://nodejs.org/), [npm](https://github.com/npm/npm)

## Configuration
* Install the node modules
```
    $ npm install
```

* Rename config/example.config.json as config/config.json, remove all the comments and fill in all necessary information.

## Run
```
    $ node server.js
```

Try to send some message in your account. If you receive 'respond', it means it run sucessfully.


## Dependecies
node_modules
* [body-parser](https://www.npmjs.com/package/body-parser)
* [crypto-js](https://www.npmjs.com/package/crypto-js)
* [express](https://www.npmjs.com/package/express)
* [request](https://www.npmjs.com/package/request)

## Reference
* [The Technical Side of LINE Business Connect](http://developers.linecorp.com/blog/?p=3169)
* [API Reference for LINE Bussiness Connect](https://developers.line.me/businessconnect/api-reference)

### Note
* This sample is built as a simple testbed. Please take care the settings and security staff if you want to use this sample as production enviroment.