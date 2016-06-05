'use strict';
var IS_DEBUG = 1;

var express = require('express');
var request = require('request');
var bodyParser = require('body-parser');
var CryptoJS = require("crypto-js");
var config = require('./config/config.json');
var path = require('path');

var app = require('express')();
var http = require('http').Server(app);
var io = require('socket.io')(http);

var audio_app = require('express')();
var audio_http = require('http').Server(audio_app);

var webPort = config.webPort;
var audioPort = config.audioPort;


//database
//var sqlite3 = require('sqlite3').verbose();

app.use(bodyParser.json());
audio_app.use(bodyParser.json());

function verifyRequest(req, res, next) {
	// Refer to https://developers.line.me/businessconnect/development-bot-server#signature_validation
	var channelSignature = req.get('X-LINE-ChannelSignature');
	var sha256 = CryptoJS.HmacSHA256(JSON.stringify(req.body), config.channelSecret);
	var base64encoded = CryptoJS.enc.Base64.stringify(sha256);
	if (base64encoded === channelSignature) {
		next();
	} else {
		res.status(470).end();
	}
}

app.post('/events', verifyRequest, function(req, res) {
	var result = req.body.result;
	if (!result || !result.length || !result[0].content) {
		res.status(470).end();
		return;
	}
	res.status(200).end();

	if (IS_DEBUG)
		console.log(result);
	// One request may have serveral contents in an array.
	var content = result[0].content;
	// mid
	var from = content.from;
	// Content type would be possibly text/image/video/audio/gps/sticker/contact.
	var type = content.type;
	// assume it's text type here.
	var text = content.text;

	// Refer to https://developers.line.me/businessconnect/api-reference#sending_message
	sendMsg(from, {
		contentType: 1,
		toType: 1,
		// you can replace 'respond' with whatever you want
		text: 'your mid is ' + from
	}, function(err) {
		if (err) {
			// sending message failed
			return;
		}
		// message sent
	});
});


function sendMsg(who, content, callback) {
	var data = {
		to: [who],
		toChannel: config.eventToChannelId,
		eventType: config.eventType,
		content: content
	};

	request({
		method: 'POST',
		// https://api.line.me
		url: config.channelUrl,
		headers: {
			'Content-Type': 'application/json',
			'X-LINE-ChannelToken': config.channelToken
		},
		json: data
	}, function(err, res, body) {
		if (err) {
			callback(err);
		} else {
			callback();
		}
	});
}

function sendMsgToKnownUsers(msg) {
        //get mid from config
        sendMsg(config.myMid, {
                contentType: 1, toType: 1, text: msg
                }, function(errMsg) {
                        if (errMsg) {
                                return;
                        }
                });
}

function sendMsgToKnownUsersByDB(msg) {
	//get each mid from DB
	var db = new sqlite3.Database('akachan.db');
	db.serialize(function() {
		db.each("SELECT mid as mid FROM user", function(err, row) { 
			//send message to OA
			sendMsg(row.mid, {
				contentType: 1, toType: 1, text: msg
			}, function(errMsg) { 
				if (errMsg) {
					return;
				}
			});
		});
	});
	db.close();
}

function listenMicData(req, res) {
	var results = new Object();

    //Use tcp socket to communicates with audio_server
	console.log("connected");
	console.log(req)
	results = JSON.parse(data);
	//server.destroy();
	if (results) {
		//send results to clients
		results["date_current"] = new Date().toISOString().slice(0, 10).replace('T', ' ');
    	results["time_current"] = new Date().toISOString().slice(11, 19).replace('T', ' ');

    	//send results to all clients
    	//console.log('time_crying: %s, time_quiet: %s', results["time_crying"], results["time_quiet"]);
		io.emit('results', results);

		if (results.time_crying == "" ) {
				if (IS_DEBUG)
				console.log('baby is quiet');    			
		} else if (results.time_quiet == "" ) {
			if (IS_DEBUG)
				console.log('baby is crying');
		}
		//If cry is detected it will send message to known users
		if (results.time_crying.toString().indexOf("noise for 0:00:06") > -1) {
				if (IS_DEBUG)
				console.log('baby is crying');
			sendMsgToKnownUsers('baby is crying');
		}
	}
	socket.on('error', function (err) {
		console.log(err);
	});
	socket.on('end', function () {
		console.log('audio disconnected');
	});	
}

function broadcastMicData() {
	var parameters = {
		noise_threshold: config.noiseThreshold,
		upper_limit: config.upperLimit, 
		min_noise_time: config.minNoiseTime,
		min_quiet_time: config.minQuietTime
	};
	var jsonString = JSON.stringify(parameters);
	var results = new Object();

	//Use tcp socket to communicates with audio_server
	var net = require('net');
	var audio_conn = net.Socket();
	audio_conn.connect(audioPort, 'localhost', function() {
		audio_conn.write(jsonString);
		//console.log('Sent: %s', jsonString);
	});
	audio_conn.on('data', function (data) {
		//console.log('Received %s', data.toString());
		results = JSON.parse(data);
		audio_conn.destroy();
		if (results) {
			//send results to clients
			results["date_current"] = new Date().toISOString().slice(0, 10).replace('T', ' ');
	    	results["time_current"] = new Date().toISOString().slice(11, 19).replace('T', ' ');

	    	//send results to all clients
	    	console.log('time_crying: %s, time_quiet: %s', results["time_crying"], results["time_quiet"]);
    		io.emit('results', results);

    		if (results.time_crying == "" ) {
 				if (IS_DEBUG)
    				console.log('baby is quiet');    			
    		} else if (results.time_quiet == "" ) {
    			if (IS_DEBUG)
    				console.log('baby is crying');
    		}
    		//If cry is detected it will send message to known users
    		if (results.time_crying.toString().indexOf("noise for 0:00:06") > -1) {
 				if (IS_DEBUG)
    				console.log('baby is crying');
    			sendMsgToKnownUsers('baby is crying');
    		}
		}
	});
	audio_conn.on('error', function (err) {
			console.log(err);
	});
	audio_conn.on('end', function () {
			console.log('audio server disconnected');
	});	
}

// Serve static files
app.use('/static', express.static(path.join(__dirname, 'client/static')));

// Monitor purpose
app.get('/monitor/l7check', function(req,res){
	res.send('ok');
});

// Monitor purpose
audio_app.get('/monitor/l7check', function(req,res){
	res.send('ok');
});

// Serve index files
app.get('/', function(req,res){
	res.sendFile(path.join(__dirname, 'client/index.html'));
});

//websockect browser connection detected
io.on('connection', function (socket) { 
	console.log('web user connected');
	socket.on('disconnect', function() {
		console.log('web user disconnected');
	})
});

// Handle post request from audio client
audio_app.post('/', function(req,res) { 
    //console.log("audio connected");
	// Print out requests 
	//console.log("req.method: " + req.method);
	//console.log("req.params: " + req.params);
	//console.log("req.is json: " + req.is('json'));
	//console.log("req.body: " + req.body);
	
	// Gather results based on audio data then broadcast to web client
	var results = new Object();
	results = req.body;
	// Send a response
	res.send('OK');
	// Analyze request
	if (results) {
		//send results to clients
		results["date_current"] = new Date().toISOString().slice(0, 10).replace('T', ' ');
    	results["time_current"] = new Date().toISOString().slice(11, 19).replace('T', ' ');

    	//send results to all clients
    	//console.log('time_crying: %s, time_quiet: %s', results["time_crying"], results["time_quiet"]);
		io.emit('results', results);

		if (results.time_crying == "" ) {
				if (IS_DEBUG)
				console.log('baby is quiet');    			
		} else if (results.time_quiet == "" ) {
			if (IS_DEBUG)
				console.log('baby is crying');
		}
		//If cry is detected it will send message to known users
		if (results.time_crying.toString().indexOf("noise for 0:00:06") > -1) {
				if (IS_DEBUG)
				console.log('baby is crying');
			sendMsgToKnownUsers('baby is crying');
		}
	}
});


app.listen(webPort);
audio_app.listen(audioPort);


//http.listen(webPort, function(){
//	console.log('web listening on *:' + webPort);
//});

//audio_http.listen(audioPort, function(){
//	console.log('audio listening on *:' + audioPort);
//});

/* express ws
app.ws('/ws', function(ws, req) {
	ws.on('message', function(msg) {
		console.log(msg);
	});
	console.log('socket', req.testing);
});

// express ws example
app.use(function (req, res, next) {
  console.log('middleware');
  req.testing = 'testing';
  return next();
});

app.get('/', function(req, res, next){
  console.log('get route', req.testing);
  res.end();
});
*/

// Route everything else
/* app.get('*', function(req, res){
	res.send('Hello World');
});
*/

//app.listen(webPort);
//console.log('listening to webPort '  + webPort);
