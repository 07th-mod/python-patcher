'use strict';

const pythonPatcherTimeScriptLoaded = Date.now();

let POSTNotificationErrorCallback = function defaultPOSTNotificationErrorCallback(message) {
  alert(message);
};

function setPOSTNotificationErrorCallback(callback) {
  POSTNotificationErrorCallback = callback;
}

let InstallerErrorCallback = function defaultInstallerErrorCallback(message, detailedExceptionInformation) {
  alert(`${message}\n\n${detailedExceptionInformation}`);
};

function setInstallerErrorCallback(callback) {
  InstallerErrorCallback = callback;
}


// Note: { requestType, requestData } = { requestType : requestType, requestData : requestData }
function makeJSONRequest(requestType, requestData) {
  return JSON.stringify({ requestType, requestData });
}

function decodeJSONResponse(jsonString) {
  const responseObject = JSON.parse(jsonString);
  return [responseObject.responseType, responseObject.responseData];
}

// Send any object in JSON format as a POST request to the server.
//
// Arguments:
//
// - requestType (str): The type of request, as a string, sent to the server.
//    - If incorrect, the server will send a response with type 'error'.
//    - If correct, the server will send a response with the same type as the request
//
// - requestData (object): An object sent to the server with the request.
//
// - onSuccessCallback (function(object)): A fn executed when a response is received
//      from the server. The fn should take the returned object as its only argument
function doPost(requestType, requestData, onSuccessCallback, timeout, onErrorCallback) {
  const http = new XMLHttpRequest();
  const url = 'installer_data'; // in python, is stored in 'self.path' on the handler class

  function errorHandler(msg, reason) {
    const message = `[${requestType}] POST Error - "${msg}" - You must have the install loader window/console open - it is required for the installation.`;
    console.log(message);
    if (reason !== 'abort') {
      POSTNotificationErrorCallback(message);
    }
    if (typeof onErrorCallback !== 'undefined') {
      onErrorCallback(msg, reason);
    }
  }

  // in python, is retrieved by calling 'self.rfile.read(content_length)',
  // where content_length is in the header (see python code)
  http.open('POST', url, true);

  // Send the proper header information along with the request
  http.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');

  http.onload = () => {
    if (http.readyState === 4) {
      if (http.status === 200) {
        const [responseType, responseDataObject] = decodeJSONResponse(http.responseText);
        if (responseType === 'error') {
          console.log(`Error: ${responseDataObject.errorReason}\n\n${responseDataObject.detailedExceptionInformation}`);
          InstallerErrorCallback(responseDataObject.errorReason, responseDataObject.detailedExceptionInformation);
        } else if (responseType === 'unknownRequest' || responseType !== requestType) {
          console.log(`ERROR: sent ${requestType} but got ${responseType}. requestData: ${responseDataObject}`);
        } else {
          onSuccessCallback(responseDataObject);
        }
      } else {
        errorHandler(`Unexpected HTTP Status [${http.status}]`, 'status');
      }
    }
  };

  http.onabort = function () {
    errorHandler('POST Aborted', 'abort');
  };

  http.onerror = function () {
    errorHandler('POST Error', 'error');
  };

  http.ontimeout = function (e) {
    errorHandler(`POST Timeout (${http.timeout / 1000}s)`, 'timeout');
  };

  // Use a timeout of 8 seconds by default.
  // After this errorHandler()/POSTNotificationErrorCallback() will be called
  http.timeout = timeout !== 'undefined' ? timeout : 8000;

  http.send(makeJSONRequest(requestType, requestData));

  return http
}

// TODO: should always navigate to the same install page, as it is shared amongst all games
function setModNameAndNavigate(modName) {
  doPost('setModName', { modName }, (response) => {
    console.log(response);
    if (response.valid) {
      window.location.href = modName.toLowerCase().includes('umineko') ? 'umineko-warning.html' : 'installer.html';
    } else {
      alert(`Error: "${modName}" is not the name of a mod in the JSON config file. Check web console for a list of valid mod names`);
      console.error('Invalid Mod Name! Valid names below:');
      console.error(response.modNames);
    }
  });
}

function getInitStatus(onStatusReceived) {
  // Retrieve the donation status
  doPost('getInitStatus', [], (response) => {
    onStatusReceived(response);
  });
}

// This function can be used to implement a basic terminal. It adds the string
// 'msg' to element 'terminalElement' as a child node, effectively doing a
// 'print()' statement, but appending to a particular html element.

// The total number of elements displayed is limited by the 'maxLines' argument
// Autoscrolling will be enabled if the checkbox
// 'autoscrollCheckboxElement' (must be given as argument) is checked
function addToTerminal(terminalElement, msg, autoscrollCheckboxElement, maxLines) {
  terminalElement.appendChild(document.createTextNode(msg), terminalElement.firstChild);

  // limit max number of lines - remove in blocks of 100 elements to improve performance
  if (terminalElement.childNodes.length > maxLines) {
    for (let i = 0; i < 100 && terminalElement.hasChildNodes(); i += 1) {
      terminalElement.removeChild(terminalElement.firstChild);
    }
  }

  if (autoscrollCheckboxElement.checked) {
    terminalElement.scrollTop = terminalElement.scrollHeight;
  }
}
