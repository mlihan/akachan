var net = require('net');

var HOST = '127.0.0.1';
var PORT = 6000;
var config = require('./../config/config.json');

var client = new net.Socket();

var obj = new Object();

obj.test1 = "123";
obj["test2"] = "asdf";

console.log("first " + obj["test1"] + " " + obj.test2);
obj.test3 = "hello";
console.log(Object.getOwnPropertyNames(obj));
obj.test4 = "hello";

obj.date_current = new Date().toISOString().slice(0, 10).replace('T', ' ');
obj["time_current"] = new Date().toISOString().slice(11, 19).replace('T', ' ');

console.log(obj);
/*
client.connect(PORT, HOST, function() {

    console.log('CONNECTED TO: ' + HOST + ':' + PORT);
    // Write a message to the socket as soon as the client is connected, the server will receive it as message from the client 
    var parameters = {
		noise_threshold: config.noiseThreshold,
		upper_limit: config.upperLimit, 
		min_noise_time: config.minNoiseTime,
		min_quiet_time: config.minQuietTime
	};
	var jsonString = JSON.stringify(parameters);
    client.write(jsonString);

});

// Add a 'data' event handler for the client socket
// data is what the server sent to this socket
client.on('data', function(data) {
    
    console.log('DATA: ' + data);
    // Close the client socket completely
    client.destroy();
    
});

// Add a 'close' event handler for the client socket
client.on('close', function() {
    console.log('Connection closed');
});
*/