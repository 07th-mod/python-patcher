// Note: { requestType, requestData } = { requestType : requestType, requestData : requestData }
function makeJSONRequest(requestType, requestData) {
  return JSON.stringify({ requestType, requestData });
}

function decodeJSONResponse(jsonString) {
  const responseObject = JSON.parse(jsonString);
  return [responseObject.responseType, responseObject.responseData];
}

// send any object in JSON format as a POST request to the server.
// the 'url' will be set to 'installer_data'
// the 'params' will be a string = JSON.stringify(object_to_send)
function doPost(requestType, requestData, onSuccessCallback) {
  const http = new XMLHttpRequest();
  const url = 'installer_data'; // in python, is stored in 'self.path' on the handler class

  // in python, is retrieved by calling 'self.rfile.read(content_length)',
  // where content_length is in the header (see python code)
  http.open('POST', url, true);

  // Send the proper header information along with the request
  http.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');

  // Call a function when the state changes.
  http.onreadystatechange = function onReadyStateChange() {
    if (http.readyState === 4 && http.status === 200) {
      const [responseType, responseData] = decodeJSONResponse(http.responseText);
      onSuccessCallback(responseType, responseData);
    }
  };

  http.send(makeJSONRequest(requestType, requestData));
}

function buttonPressed() {
  doPost('getSubModHandles',
    ['shiba', 'inu'],
    (responseType, responseData) => { console.log(responseData); });
}
