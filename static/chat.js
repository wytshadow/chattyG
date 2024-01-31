var projectId = project_id; // Assuming project_id is set in your HTML
var socket = io.connect(window.location.protocol + '//' + document.domain + ':' + location.port);

socket.on('connect', function () {
    console.log('Websocket connected!');
});

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded and parsed');
    var sendButton = document.getElementById('sendButton');
    console.log(sendButton); // Should not be null if the element exists
    var userInput = document.getElementById('user_input');

    sendButton.addEventListener('click', function() {
        sendMessage();
    });

    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
            e.preventDefault(); // Prevent form submission on enter key
        }
    });
});

function sendMessage() {
    console.log('sendMessage called'); // Add this line for debugging
    var user_input = document.getElementById('user_input').value.trim();
    if (user_input) {
        socket.emit('send_message', { message: user_input, project_id: projectId });
        console.log('Message emitted:', user_input);
        appendMessage('You', user_input);
        document.getElementById('user_input').value = ''; // Clear the input after sending
        document.getElementById('loading').style.display = 'block'; // Show loading indicator
    }
}

socket.on('receive_message', function(data) {
    if (data.message) {
        appendMessage('ChatGPT', data.message);
    }
    document.getElementById('loading').style.display = 'none'; // Hide loading indicator
});

function appendMessage(sender, message) {
    var history = document.getElementById('history');
    var messageElement = document.createElement('div');
    messageElement.className = 'message';

    var senderElement = document.createElement('strong');
    senderElement.textContent = sender + ': ';
    var messageText = document.createTextNode(message);
    messageElement.appendChild(senderElement);
    messageElement.appendChild(messageText);

    history.appendChild(messageElement);
    history.scrollTop = history.scrollHeight; // Scroll to the bottom
}
